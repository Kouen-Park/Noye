"""File APIs: upload, list, status, retry, cancel, delete.

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
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import get_db
from app.config import sources_dir
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.models.files import File, FileStatus, FileType
from app.services.indexing import IndexingError, delete_file_chunks
from app.services.ingestion import (
    AlreadyIngesting, cancel_ingestion, cancel_orphaned_file, ingest_file, release_file,
    reserve_delete, reserve_ingestion,
)

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
    try:
        connection = connect()
    except Exception:
        release_file(file_id)
        raise
    try:
        try:
            init_schema(connection)
        except Exception:
            release_file(file_id)
            raise
        ingest_file(connection, file_id, reserved=True)
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

    reserve_ingestion(file_id)
    try:
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
    except BaseException:
        release_file(file_id)
        target.unlink(missing_ok=True)
        raise


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


@router.post("/{file_id}/reingest", response_model=FileOut, status_code=status.HTTP_202_ACCEPTED)
def reingest_file(
    file_id: str,
    background: BackgroundTasks,
    db: sqlite3.Connection = Depends(get_db),
) -> FileOut:
    """Run an already-uploaded file through the pipeline again.

    This is the answer to a FAILED file, which was otherwise a dead end: the only
    move was to delete it and upload the same bytes a second time. A scanned PDF
    is still a scanned PDF, but an encoding problem, an unreachable Ollama, or a
    Qdrant that was down are all fixable without the original file leaving the
    machine.

    Allowed on a READY file too — re-indexing after a chunking or embedding
    change is the same operation.

    Returns 202 with the file back in ``UPLOADING``; poll ``GET /files/{id}`` as
    with an upload.
    """
    try:
        reserve_ingestion(file_id)
    except AlreadyIngesting as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This file is already being processed. Wait for it to finish.",
        ) from exc

    try:
        try:
            record = file_store.get_file(db, file_id)
        except file_store.FileRecordNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not Path(record.path).exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The original file is missing from disk. Upload it again to retry.",
            )
        file_store.reset_counts(db, file_id)
        record = file_store.set_status(db, file_id, FileStatus.UPLOADING)
        background.add_task(_ingest_in_background, file_id)
        return FileOut.of(record)
    except BaseException:
        release_file(file_id)
        raise


@router.post("/{file_id}/cancel", response_model=FileOut, status_code=status.HTTP_202_ACCEPTED)
def cancel_file(file_id: str, db: sqlite3.Connection = Depends(get_db)) -> FileOut:
    """Request cancellation; poll the file until it reaches FAILED."""
    try:
        record = file_store.get_file(db, file_id)
    except file_store.FileRecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if cancel_ingestion(file_id):
        return FileOut.of(record)
    try:
        reserve_ingestion(file_id)
    except AlreadyIngesting as exc:
        raise HTTPException(status_code=409, detail="This file is busy.") from exc
    try:
        try:
            record = file_store.get_file(db, file_id)
        except file_store.FileRecordNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not record.status.is_processing:
            raise HTTPException(status_code=409, detail="This file is not being processed.")
        return FileOut.of(cancel_orphaned_file(db, file_id))
    finally:
        release_file(file_id)


#: How each format is served back to the browser.
#:
#: PDFs keep their own type so the browser's viewer renders them and a
#: `#page=N` fragment lands on the cited page. Markdown and text are served as
#: plain text rather than `text/markdown`, because browsers download the latter
#: instead of displaying it — and a source you cannot look at is not a source
#: reference.
SOURCE_MEDIA_TYPES: dict[FileType, str] = {
    FileType.PDF: "application/pdf",
    FileType.MARKDOWN: "text/plain; charset=utf-8",
    FileType.TEXT: "text/plain; charset=utf-8",
}


@router.get("/{file_id}/source")
def read_source(file_id: str, db: sqlite3.Connection = Depends(get_db)) -> FileResponse:
    """Serve a file's saved original, for opening a search hit at its source.

    The path comes from the database row, never from the request: the only thing
    a caller supplies is an id. That is what keeps this route from becoming a way
    to read arbitrary files off the machine, and it is re-checked below in case a
    row ever holds a path outside the sources directory.

    Served inline so a PDF opens in the browser's viewer, where the client can
    append `#page=N` from a citation. Markdown and text open as text; neither has
    pages, and this route does not invent one.
    """
    try:
        record = file_store.get_file(db, file_id)
    except file_store.FileRecordNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    path = Path(record.path)

    # Defence in depth. The row is written by this application, so a path outside
    # the sources directory means the database was edited or corrupted — and
    # serving whatever it points at would turn an id into a file-read primitive.
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(sources_dir().resolve())
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The original file is no longer on disk.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This file's stored location is not somewhere Noye serves from.",
        ) from exc

    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The original file is no longer on disk.",
        )

    return FileResponse(
        resolved,
        media_type=SOURCE_MEDIA_TYPES[record.file_type],
        # The display name, not the `{id}__{name}` used on disk.
        filename=record.name,
        content_disposition_type="inline",
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: str, db: sqlite3.Connection = Depends(get_db)) -> None:
    """Delete a source completely: vectors, original file, and metadata.

    Vectors go first. If that fails the request fails too, leaving the file
    intact — a half-deleted source whose vectors survive would keep answering
    questions about a document the user believes is gone, which is worse than a
    failed delete they can retry.
    """
    try:
        reserve_delete(file_id)
    except AlreadyIngesting as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This file is being processed. Cancel it and wait for processing to stop before removing it.",
        ) from exc
    try:
        try:
            record = file_store.get_file(db, file_id)
        except file_store.FileRecordNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if record.status.is_processing:
            raise HTTPException(
                status_code=409,
                detail="This file is still processing. Stop it before removing it.",
            )
        try:
            delete_file_chunks(record.id)
        except IndexingError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Could not remove this file's vectors, so nothing was deleted: {exc}",
            ) from exc
        Path(record.path).unlink(missing_ok=True)
        file_store.delete_file(db, record.id)
    finally:
        release_file(file_id)
