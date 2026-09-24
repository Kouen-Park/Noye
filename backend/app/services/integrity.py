"""Whether the index still describes the files it was built from.

A library that has been used for a while can drift from its index in three ways, and
they are kept apart here because **each needs a different remedy**. Collapsing them
into one "stale" flag would tell the user something is wrong without telling them
what to do, which is the failure mode this module exists to avoid.

    SOURCE_CHANGED   the file on disk is not the file that was indexed
                     -> re-ingest that one file
    MODEL_CHANGED    the vectors are from a superseded embedding model
                     -> re-ingest, and until then do not search it
    POINTS_MISSING   Qdrant holds fewer points than SQLite records chunks
                     -> re-ingest; usually a dropped collection or deleted volume

Why the second one is a correctness problem, not tidiness
---------------------------------------------------------
A cosine score between vectors from two different embedding models is meaningless.
It is not *wrong by a little* — the two spaces have no relationship, so the number
is noise that sorts. Search would rank confidently and incorrectly, and the user has
no way to see it, because a plausible-looking passage list is exactly what a working
search produces.

That is worse than returning nothing. Nothing is visible. So a file whose vectors
came from a superseded model **leaves the searchable set** until it is re-indexed —
the same treatment a file mid-ingestion already gets, for the same reason.

Cost, and why the checks are not all run together
-------------------------------------------------
The first two are free: a stored hash against a file's bytes, and a stored model name
against the configuration. The third needs a round trip to Qdrant per file, so it is
not something to do on the search path. `searchable_file_ids` therefore uses only the
cheap check that bears on correctness, and the expensive one belongs to the status
endpoint a person asks for deliberately.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from qdrant_client import QdrantClient

from app.config import get_settings
from app.db import files as file_store
from app.logging_config import get_logger
from app.models.files import File, FileStatus
from app.services.indexing import IndexingError, count_chunks

logger = get_logger("integrity")

#: Read in blocks rather than whole: a source can be as large as the upload limit,
#: and hashing one is not a reason to hold 100 MB in memory.
_HASH_CHUNK = 1024 * 1024


class Problem(str, Enum):
    """What is wrong with one file's index entry.

    ``str`` mixin so the value serializes directly, matching ``FileStatus``.
    """

    MISSING_SOURCE = "MISSING_SOURCE"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    MODEL_CHANGED = "MODEL_CHANGED"
    POINTS_MISSING = "POINTS_MISSING"

    @property
    def blocks_search(self) -> bool:
        """Whether this problem makes the file unsafe to search.

        Only a model change does. A changed source or a partly missing index makes
        results *incomplete* or *out of date*, which is disappointing; mixing
        embedding spaces makes them *wrong while looking right*, which is not
        recoverable by the user noticing.
        """
        return self is Problem.MODEL_CHANGED


@dataclass(frozen=True)
class FileIntegrity:
    """One file's standing, with what to do about it."""

    file_id: str
    file_name: str
    problems: tuple[Problem, ...]
    #: Present only when the expensive check ran.
    indexed_points: int | None = None
    expected_points: int | None = None

    @property
    def is_sound(self) -> bool:
        return not self.problems

    @property
    def is_searchable(self) -> bool:
        return not any(problem.blocks_search for problem in self.problems)


def hash_file(path: str | Path) -> str | None:
    """sha256 of a file's bytes, or None when it cannot be read.

    None rather than an exception: a missing source is a finding this module
    reports, not an error that should stop it checking the rest of the library.
    """
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            while chunk := handle.read(_HASH_CHUNK):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def check_file(
    record: File,
    *,
    expected_model: str | None = None,
    qdrant_client: QdrantClient | None = None,
    check_points: bool = False,
) -> FileIntegrity:
    """Assess one file. Only READY files have an index entry to be wrong about.

    ``expected_model`` defaults to the configured embedding model. It is a parameter
    so a caller checking a whole library resolves the setting once rather than per
    file.

    ``check_points`` opts into the Qdrant round trip.
    """
    model = expected_model or get_settings().ollama_embedding_model
    problems: list[Problem] = []
    indexed = expected = None

    if record.status is not FileStatus.READY:
        # A file mid-ingestion or FAILED has no index entry that is supposed to be
        # right, so reporting it as damaged would be noise.
        return FileIntegrity(record.id, record.name, ())

    actual_hash = hash_file(record.path)
    if actual_hash is None:
        problems.append(Problem.MISSING_SOURCE)
    elif record.content_hash is not None and actual_hash != record.content_hash:
        # Only when a hash was recorded. None means "indexed before Noye recorded
        # this", and reading unknown as changed would report every pre-#27 file as
        # damaged on upgrade alone.
        problems.append(Problem.SOURCE_CHANGED)

    if record.embedding_model is not None and record.embedding_model != model:
        # Again only when known. An unrecorded model is not evidence of a mismatch.
        problems.append(Problem.MODEL_CHANGED)

    if check_points:
        expected = record.chunk_count
        try:
            indexed = count_chunks(record.id, client=qdrant_client)
        except IndexingError as exc:
            # An unreachable Qdrant is NOT "points missing". Conflating them would
            # report every file in the library as damaged whenever the container is
            # simply not running, which is both alarming and the wrong instruction —
            # the fix is starting Qdrant, not re-indexing anything. Left as None,
            # which the response renders as "could not check".
            logger.info(
                "Point count unavailable file=%s error=%s", record.id, type(exc).__name__
            )
            indexed = None
        if indexed is not None and indexed < expected:
            problems.append(Problem.POINTS_MISSING)

    return FileIntegrity(
        record.id,
        record.name,
        tuple(problems),
        indexed_points=indexed,
        expected_points=expected,
    )


def check_library(
    connection: sqlite3.Connection,
    *,
    qdrant_client: QdrantClient | None = None,
    check_points: bool = False,
) -> list[FileIntegrity]:
    """Assess every file. The configuration is read once, not per file."""
    model = get_settings().ollama_embedding_model
    return [
        check_file(
            record,
            expected_model=model,
            qdrant_client=qdrant_client,
            check_points=check_points,
        )
        for record in file_store.list_files(connection)
    ]


def searchable_file_ids(connection: sqlite3.Connection) -> dict[str, str]:
    """The files a query may be answered from, as id -> display name.

    Replaces the plain READY filter that search and chat used. READY is still
    necessary — a file mid-ingestion has some passages indexed and not others — but
    it is no longer sufficient, because a READY file can hold vectors from an
    embedding space the current model knows nothing about.

    Uses only the cheap checks. The Qdrant count is a round trip per file and has no
    business on the search path; a partly missing index gives incomplete results,
    which is a different and lesser harm than a meaningless ranking.
    """
    model = get_settings().ollama_embedding_model
    searchable: dict[str, str] = {}
    excluded: list[str] = []

    for record in file_store.list_files(connection):
        if record.status is not FileStatus.READY:
            continue
        if record.embedding_model is not None and record.embedding_model != model:
            excluded.append(record.id)
            continue
        searchable[record.id] = record.name

    if excluded:
        logger.warning(
            "Excluded %d file(s) from search: vectors are from a superseded "
            "embedding model, current=%s files=%s",
            len(excluded),
            model,
            ",".join(excluded),
        )

    return searchable
