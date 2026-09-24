"""Whether the index still describes the library.

Read-only, and separate from `/files` because it answers a question about the
*relationship* between the files and the index rather than about any one file.

The expensive check is opt-in via `?deep=true`. It costs one Qdrant round trip per
file, which is fine for something a person asked for and not fine on a page that
polls.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import get_db
from app.config import get_settings
from app.db import files as file_store
from app.logging_config import get_logger
from app.models.files import FileStatus
from app.services.indexing import IndexingError
from app.services.ingestion import ingest_in_background
from app.services.integrity import FileIntegrity, Problem, check_library
from app.services.rebuild import plan_rebuild

router = APIRouter(prefix="/index", tags=["index"])

logger = get_logger("api.index")


class FileProblems(BaseModel):
    """One file's standing."""

    file_id: str
    file_name: str
    problems: list[Problem]
    #: Whether this file may currently answer a question.
    searchable: bool
    #: Populated only by a deep check. None means the count could not be read —
    #: Qdrant unreachable — which is deliberately not the same as zero.
    indexed_points: int | None = None
    expected_points: int | None = None

    @classmethod
    def of(cls, report: FileIntegrity) -> FileProblems:
        return cls(
            file_id=report.file_id,
            file_name=report.file_name,
            problems=list(report.problems),
            searchable=report.is_searchable,
            indexed_points=report.indexed_points,
            expected_points=report.expected_points,
        )


class IndexStatus(BaseModel):
    """The library's standing as a whole."""

    #: The embedding model a file's vectors must come from to be searched.
    embedding_model: str
    #: Files that have finished indexing, whatever their integrity.
    ready_files: int
    #: Of those, how many may currently answer a question.
    searchable_files: int
    #: Whether the deep Qdrant comparison ran.
    deep: bool
    #: Only files with something wrong. A sound library reports an empty list rather
    #: than every file with an empty problem list, which would make the response
    #: grow with the library and say nothing.
    problems: list[FileProblems]


@router.get("/status", response_model=IndexStatus)
def index_status(
    deep: bool = Query(
        False,
        description=(
            "Also compare stored chunk counts against Qdrant. One round trip per "
            "file, so off by default."
        ),
    ),
    db: sqlite3.Connection = Depends(get_db),
) -> IndexStatus:
    """Report whether the index still matches the files it was built from.

    Three problems are reported separately because each needs a different remedy:
    a changed source needs that one file re-ingested, a changed embedding model needs
    re-indexing and meanwhile removes the file from search, and a short point count
    usually means the collection or its volume was dropped.
    """
    records = file_store.list_files(db)
    reports = check_library(db, check_points=deep)

    ready_ids = {
        record.id for record in records if record.status is FileStatus.READY
    }
    searchable = sum(
        1
        for report in reports
        if report.file_id in ready_ids and report.is_searchable
    )

    return IndexStatus(
        embedding_model=get_settings().ollama_embedding_model,
        ready_files=len(ready_ids),
        searchable_files=searchable,
        deep=deep,
        problems=[FileProblems.of(report) for report in reports if not report.is_sound],
    )


class SkippedFile(BaseModel):
    """A file the rebuild did not queue."""

    file_id: str
    file_name: str
    reason: str


class RebuildStarted(BaseModel):
    """What the rebuild is doing. Returned before the work finishes."""

    #: How many files were queued for re-ingestion.
    queued: int
    #: Files not queued, each with a reason.
    skipped: list[SkippedFile]
    #: Whether the collection had to be dropped. True only when its vector width
    #: disagreed with the configuration, which makes existing points unusable.
    collection_recreated: bool
    #: The model the new vectors will come from.
    embedding_model: str


@router.post(
    "/rebuild", response_model=RebuildStarted, status_code=status.HTTP_202_ACCEPTED
)
def rebuild_index(
    background: BackgroundTasks,
    db: sqlite3.Connection = Depends(get_db),
) -> RebuildStarted:
    """Re-index every file from the originals on disk.

    Returns 202 immediately: re-embedding a real library is minutes to hours of local
    inference. Each file moves through the ordinary pipeline stages, so `GET /files`
    shows the progress and nothing new has to be polled.

    The collection is **not** dropped unless its vector width disagrees with the
    configuration. Dropping first would mean a rebuild that fails part-way leaves no
    index at all, where before there was a stale one that still answered — and a
    stale answer beats no answer. Per-file re-ingestion replaces each file's vectors
    as it goes, so the index is never wholly absent.

    A file whose original is missing is skipped rather than failed: its existing
    vectors are still the best record of a document the user no longer has.
    """
    try:
        plan = plan_rebuild(db)
    except IndexingError as exc:
        logger.warning("Rebuild could not start error=%s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not reach the index to rebuild it: {exc}",
        ) from exc

    for file_id in plan.file_ids:
        file_store.reset_counts(db, file_id)
        file_store.set_status(db, file_id, FileStatus.UPLOADING)
        background.add_task(ingest_in_background, file_id)

    return RebuildStarted(
        queued=plan.queued,
        skipped=[
            SkippedFile(file_id=item.file_id, file_name=item.file_name, reason=item.reason)
            for item in plan.skipped
        ],
        collection_recreated=plan.collection_recreated,
        embedding_model=plan.embedding_model,
    )
