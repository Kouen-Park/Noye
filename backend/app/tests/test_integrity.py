"""Tests for whether the index still describes the files it was built from.

Two things carry most of the weight.

First, **an unreachable Qdrant must not look like a damaged library.** That is the
error this module is most likely to make in real use — the container is not running
far more often than the collection is actually dropped — and reporting every file as
missing points would send the user to re-index a library that is perfectly fine.

Second, **an unknown value is not a mismatch.** A file indexed before Noye recorded a
hash or a model has NULL in both columns. Reading NULL as "changed" would report a
whole pre-existing library as broken on upgrade alone.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import files as file_store
from app.db.database import connect, init_schema
from app.models.files import FileStatus, FileType
from app.services import integrity
from app.services.indexing import IndexingError
from app.services.integrity import (
    Problem,
    check_file,
    check_library,
    hash_file,
    searchable_file_ids,
)

CURRENT_MODEL = "embeddinggemma"
OLD_MODEL = "nomic-embed-text"


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    connection = connect(tmp_path / "t.db")
    init_schema(connection)
    yield connection
    connection.close()


def make_ready(
    db: sqlite3.Connection,
    tmp_path: Path,
    *,
    name: str = "notes.md",
    body: str = "# Notes\n\nSome indexed text.\n",
    record_hash: bool = True,
    model: str | None = CURRENT_MODEL,
    chunks: int = 3,
) -> tuple[file_store.File, Path]:
    """A READY file whose source exists on disk, as ingestion would leave it."""
    source = tmp_path / name
    source.write_text(body, encoding="utf-8")
    record = file_store.create_file(
        db,
        name=name,
        file_type=FileType.MARKDOWN,
        path=str(source),
        size=source.stat().st_size,
        content_hash=hash_file(source) if record_hash else None,
    )
    file_store.set_counts(db, record.id, chunk_count=chunks)
    if model is not None:
        file_store.set_embedding_model(db, record.id, model)
    return file_store.set_status(db, record.id, FileStatus.READY), source


class TestASoundFile:
    def test_reports_no_problems(self, db, tmp_path):
        record, _ = make_ready(db, tmp_path)

        report = check_file(record, expected_model=CURRENT_MODEL)

        assert report.problems == ()
        assert report.is_sound
        assert report.is_searchable


class TestSourceChanged:
    def test_detects_an_edited_source(self, db, tmp_path):
        record, source = make_ready(db, tmp_path)
        source.write_text("# Notes\n\nSomething quite different.\n", encoding="utf-8")

        report = check_file(record, expected_model=CURRENT_MODEL)

        assert Problem.SOURCE_CHANGED in report.problems

    def test_an_edited_source_is_still_searchable(self, db, tmp_path):
        """Out of date is a lesser harm than wrong.

        Results from the previous version are disappointing; they are not
        meaningless, which is what a mixed embedding space produces.
        """
        record, source = make_ready(db, tmp_path)
        source.write_text("# Notes\n\nDifferent.\n", encoding="utf-8")

        assert check_file(record, expected_model=CURRENT_MODEL).is_searchable

    def test_detects_a_missing_source(self, db, tmp_path):
        record, source = make_ready(db, tmp_path)
        source.unlink()

        report = check_file(record, expected_model=CURRENT_MODEL)

        assert Problem.MISSING_SOURCE in report.problems
        # And not also SOURCE_CHANGED: there is no content to have changed, and
        # reporting both would imply two separate things to fix.
        assert Problem.SOURCE_CHANGED not in report.problems

    def test_an_unrecorded_hash_is_not_a_change(self, db, tmp_path):
        """NULL means "indexed before Noye recorded this", not "edited"."""
        record, source = make_ready(db, tmp_path, record_hash=False)
        source.write_text("# Notes\n\nEdited since.\n", encoding="utf-8")

        report = check_file(record, expected_model=CURRENT_MODEL)

        assert Problem.SOURCE_CHANGED not in report.problems


class TestModelChanged:
    def test_detects_a_superseded_model(self, db, tmp_path):
        record, _ = make_ready(db, tmp_path, model=OLD_MODEL)

        report = check_file(record, expected_model=CURRENT_MODEL)

        assert Problem.MODEL_CHANGED in report.problems

    def test_a_superseded_model_makes_the_file_unsearchable(self, db, tmp_path):
        """The correctness rule, and the only problem that blocks search.

        A cosine score between two embedding spaces is noise that sorts. Search
        would rank confidently and wrongly, and a plausible passage list is exactly
        what a working search looks like — so the user cannot see the error.
        """
        record, _ = make_ready(db, tmp_path, model=OLD_MODEL)

        assert not check_file(record, expected_model=CURRENT_MODEL).is_searchable

    def test_an_unrecorded_model_is_not_a_mismatch(self, db, tmp_path):
        record, _ = make_ready(db, tmp_path, model=None)

        report = check_file(record, expected_model=CURRENT_MODEL)

        assert Problem.MODEL_CHANGED not in report.problems
        assert report.is_searchable


class TestPointsMissing:
    def test_detects_fewer_points_than_chunks(self, db, tmp_path, monkeypatch):
        record, _ = make_ready(db, tmp_path, chunks=10)
        monkeypatch.setattr(integrity, "count_chunks", lambda *a, **kw: 4)

        report = check_file(record, expected_model=CURRENT_MODEL, check_points=True)

        assert Problem.POINTS_MISSING in report.problems
        assert report.indexed_points == 4
        assert report.expected_points == 10

    def test_an_unreachable_index_is_not_reported_as_damage(
        self, db, tmp_path, monkeypatch
    ):
        """The mistake this module is most likely to make in real use.

        Qdrant not running is far more common than a dropped collection, and the fix
        is starting it — not re-indexing a library that is perfectly fine.
        """

        def unreachable(*args, **kwargs):
            raise IndexingError("Could not count vectors in Qdrant: connection refused")

        record, _ = make_ready(db, tmp_path, chunks=10)
        monkeypatch.setattr(integrity, "count_chunks", unreachable)

        report = check_file(record, expected_model=CURRENT_MODEL, check_points=True)

        assert Problem.POINTS_MISSING not in report.problems
        assert report.is_sound
        # None, not zero: "could not check" and "nothing is indexed" are different
        # answers and only one of them means re-index.
        assert report.indexed_points is None

    def test_the_check_is_skipped_unless_asked_for(self, db, tmp_path, monkeypatch):
        """One Qdrant round trip per file has no business on a polling path."""
        called = []
        monkeypatch.setattr(
            integrity, "count_chunks", lambda *a, **kw: called.append(1) or 0
        )
        record, _ = make_ready(db, tmp_path)

        check_file(record, expected_model=CURRENT_MODEL)

        assert called == []


class TestUnfinishedFiles:
    @pytest.mark.parametrize(
        "state", [FileStatus.UPLOADING, FileStatus.EMBEDDING, FileStatus.FAILED]
    )
    def test_a_file_that_is_not_ready_is_not_assessed(self, db, tmp_path, state):
        """It has no index entry that is supposed to be right.

        Reporting one as damaged would be noise, and a FAILED file already says why
        it failed.
        """
        record, source = make_ready(db, tmp_path)
        source.unlink()  # would be MISSING_SOURCE if it were assessed
        record = file_store.set_status(
            db, record.id, state, error="x" if state is FileStatus.FAILED else None
        )

        assert check_file(record, expected_model=CURRENT_MODEL).is_sound


class TestAnUnreachableQdrant:
    """The catch must cover a connection refusal, not only a bad response.

    qdrant-client raises ResponseHandlingException when the server cannot be
    reached. It is a sibling of UnexpectedResponse under ApiException and is NOT an
    OSError, so catching the narrower pair let a refusal escape uncaught — which
    surfaced as a 500 from /search with Qdrant simply not running, where the answer
    is a 503 saying so.

    These call through the real functions with a client whose transport refuses, so
    they break if the catch is ever narrowed back.
    """

    def test_count_chunks_raises_indexing_error(self, monkeypatch):
        from qdrant_client.http.exceptions import ResponseHandlingException

        from app.services import indexing

        class Refusing:
            def collection_exists(self, *args, **kwargs):
                raise ResponseHandlingException(OSError("[Errno 61] Connection refused"))

        monkeypatch.setattr(indexing, "get_client", Refusing)

        with pytest.raises(IndexingError, match="Could not count vectors"):
            indexing.count_chunks("some-file")

    def test_the_refusal_is_an_api_exception_but_not_an_os_error(self):
        """Documents why the tuple had to change, so nobody 'simplifies' it back."""
        from qdrant_client.http.exceptions import (
            ApiException,
            ResponseHandlingException,
            UnexpectedResponse,
        )

        refusal = ResponseHandlingException(OSError("[Errno 61] Connection refused"))

        assert isinstance(refusal, ApiException)
        assert not isinstance(refusal, OSError)
        assert not isinstance(refusal, UnexpectedResponse)
        assert issubclass(UnexpectedResponse, ApiException)


class TestSearchableFileIds:
    def test_includes_a_sound_ready_file(self, db, tmp_path):
        record, _ = make_ready(db, tmp_path)

        assert searchable_file_ids(db) == {record.id: record.name}

    def test_excludes_a_model_mismatch(self, db, tmp_path):
        """Relies on the configured default being CURRENT_MODEL.

        No monkeypatch: get_settings is lru_cached, so setting the environment
        variable here would do nothing and only imply control this test does not
        have. The default in config.py is `embeddinggemma`, which is what
        CURRENT_MODEL is — asserted below so this breaks loudly if that changes
        rather than passing for the wrong reason.
        """
        from app.config import get_settings

        assert get_settings().ollama_embedding_model == CURRENT_MODEL

        make_ready(db, tmp_path, name="old.md", model=OLD_MODEL)
        good, _ = make_ready(db, tmp_path, name="new.md", model=CURRENT_MODEL)

        assert list(searchable_file_ids(db)) == [good.id]

    def test_keeps_a_file_whose_source_changed(self, db, tmp_path):
        """Only a model change blocks search; the hash check is not run here.

        Hashing every source on every query would put file I/O on the search path
        for a problem that makes results out of date rather than wrong.
        """
        record, source = make_ready(db, tmp_path)
        source.write_text("# Changed\n", encoding="utf-8")

        assert record.id in searchable_file_ids(db)

    def test_excludes_a_file_that_is_not_ready(self, db, tmp_path):
        record, _ = make_ready(db, tmp_path)
        file_store.set_status(db, record.id, FileStatus.EMBEDDING)

        assert searchable_file_ids(db) == {}


class TestCheckLibrary:
    def test_reports_every_file(self, db, tmp_path):
        make_ready(db, tmp_path, name="a.md")
        make_ready(db, tmp_path, name="b.md", model=OLD_MODEL)

        reports = check_library(db)

        assert len(reports) == 2
        assert sum(1 for report in reports if report.is_sound) == 1


class TestHashFile:
    def test_matches_a_single_pass_digest(self, tmp_path):
        import hashlib

        payload = bytes(range(256)) * 8000  # larger than one read
        source = tmp_path / "big.bin"
        source.write_bytes(payload)

        assert hash_file(source) == hashlib.sha256(payload).hexdigest()

    def test_returns_none_for_a_file_that_is_not_there(self, tmp_path):
        """A finding to report, not an error that stops the rest of the library."""
        assert hash_file(tmp_path / "absent.md") is None
