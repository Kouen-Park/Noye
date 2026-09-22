"""File APIs: upload, list, status, delete.

Upload returns as soon as the file is on disk and its row exists; ingestion runs
in a background task and the client polls `GET /files/{id}` for the status. A
synchronous upload would hold the request open for minutes on a large PDF, and
the staged progress the library shows only means anything if the stages are
observable while they happen.

Routes stay thin: they validate input, call a service, and map a failure to a
status code. The work lives in `app.services.ingestion`.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import sources_dir
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.models.files import File, FileStatus, FileType
from app.services.indexing import IndexingError, delete_file_chunks
from app.services.ingestion import ingest_file

router = APIRouter(prefix="/files", tags=["files"])


class FileOut(BaseModel):
    """A file as the API reports it.

    Named `FileOut` rather than `FileResponse` to avoid colliding with
    FastAPI's own response class of that name.
    """

    id: str
    name: str
    file_type: FileType
    size: int
    status: FileStatus
    error: str | None
    page_count: int | None
    chunk_count: int
    created_at: str
    updated_at: str

    @classmethod
    def of(cls, record: File) -> "FileOut":
        return cls(
            id=record.id,
            name=record.name,
            file_type=record.file_type,
            size=record.size,
            status=record.status,
            error=record.error,
            page_count=record.page_count,
            chunk_count=record.chunk_count,
            created_at=record.created_at.isoformat(),
            updated_at=record.updated_at.isoformat(),
        )

    # `path` is deliberately absent: the client has no use for a server
    # filesystem path, and exposing one invites it to be treated as a URL.


def get_db() -> Iterator[sqlite3.Connection]:
    """Per-request database connection."""
    connection = connect()
    try:
        init_schema(connection)
        yield connection
    finally:
        connection.close()


def stored_path(file_id: str, name: str) -> Path:
    """Where an upload is saved.

    The id prefix keeps two uploads of the same filename from overwriting each
    other, while `File.name` preserves the original for display. Duplicate
    detection proper is Phase 6; silently destroying the first upload is not an
    acceptable stand-in for it.
    """
    return sources_dir() / f"{file_id}__{Path(name).name}"


def _ingest_in_background(file_id: str) -> None:
    """Run ingestion on its own connection.

    The request's connection is closed as soon as the response is sent, and this
    runs on a different thread, so it must not borrow it.
    """
    connection = connect()
    try:
        init_schema(connection)
        ingest_file(connection, file_id)
    finally:
        connection.close()


@router.post("", response_model=FileOut, status_code=status.HTTP_201_CREATED)
def upload_file(
    background: BackgroundTasks,
    file: UploadFile,
    db: sqlite3.Connection = Depends(get_db),
) -> FileOut:
    """Accept a file, store it, and start ingesting it.

    Returns immediately with the file in `UPLOADING`. Poll `GET /files/{id}` to
    watch it move through the pipeline.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A filename is required"
        )

    try:
        file_type = FileType.from_filename(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    file_id = file_store.new_file_id()
    target = stored_path(file_id, file.filename)

    try:
        with target.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save the upload: {exc}",
        ) from exc

    size = target.stat().st_size
    if size == 0:
        # Nothing to extract, and an empty row would sit in the library as a
        # file that can never become READY.
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty"
        )

    record = file_store.create_file(
        db,
        name=Path(file.filename).name,
        file_type=file_type,
        path=str(target),
        size=size,
        file_id=file_id,
    )

    background.add_task(_ingest_in_background, record.id)
    return FileOut.of(record)


@router.get("", response_model=list[FileOut])
def list_files(db: sqlite3.Connection = Depends(get_db)) -> list[FileOut]:
    """List every file, newest first."""
    return [FileOut.of(record) for record in file_store.list_files(db)]


@router.get("/{file_id}", response_model=FileOut)
def get_file(file_id: str, db: sqlite3.Connection = Depends(get_db)) -> FileOut:
    """Read one file's current state. This is the polling endpoint."""
    try:
        return FileOut.of(file_store.get_file(db, file_id))
    except file_store.FileRecordNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: str, db: sqlite3.Connection = Depends(get_db)) -> None:
    """Delete a source completely: vectors, original file, and metadata.

    Vectors go first. If that fails the request fails too, leaving the file
    intact — a half-deleted source whose vectors survive would keep answering
    questions about a document the user believes is gone, which is worse than a
    failed delete they can retry.
    """
    try:
        record = file_store.get_file(db, file_id)
    except file_store.FileRecordNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        delete_file_chunks(record.id)
    except IndexingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not remove this file's vectors, so nothing was deleted: {exc}",
        ) from exc

    Path(record.path).unlink(missing_ok=True)
    file_store.delete_file(db, record.id)
