"""Whether the index still describes the library.

Read-only, and separate from `/files` because it answers a question about the
*relationship* between the files and the index rather than about any one file.

The expensive check is opt-in via `?deep=true`. It costs one Qdrant round trip per
file, which is fine for something a person asked for and not fine on a page that
polls.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_db
from app.config import get_settings
from app.db import files as file_store
from app.models.files import FileStatus
from app.services.integrity import FileIntegrity, Problem, check_library

router = APIRouter(prefix="/index", tags=["index"])


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
