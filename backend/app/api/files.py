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

import hashlib
import sqlite3
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import get_db
from app.config import get_settings, sources_dir
from app.db import files as file_store
from app.logging_config import get_logger
from app.models.files import File, FileStatus, FileType
from app.services.indexing import IndexingError, delete_file_chunks
from app.services.ingestion import (
    AlreadyIngesting,
    cancel_ingestion,
    cancel_orphaned_file,
    ingest_in_background,
    release_file,
    reserve_delete,
    reserve_ingestion,
)

router = APIRouter(prefix="/files", tags=["files"])

logger = get_logger("api.files")

#: How much is read per iteration while saving an upload. Large enough that a
#: 100 MB file is a few hundred reads rather than tens of thousands, small enough
#: that the limit check happens long before a runaway upload matters.
_COPY_CHUNK = 1024 * 1024

#: PDF's magic bytes. A PDF that does not start with these is not a PDF, whatever
#: its name says.
_PDF_MAGIC = b"%PDF-"


class UploadTooLarge(Exception):
    """The upload passed the configured limit and was abandoned part-written."""

    def __init__(self, limit_bytes: int) -> None:
        self.limit_bytes = limit_bytes
        super().__init__(f"Upload exceeds the {limit_bytes} byte limit")


def _starts_with(path: Path, prefix: bytes) -> bool:
    """Whether a file's first bytes are ``prefix``.

    Read from the saved file rather than kept from the copy: the first chunk is
    already gone by then, and a few bytes off a file just written is a page cache
    hit, not disk I/O.
    """
    try:
        with path.open("rb") as handle:
            return handle.read(len(prefix)) == prefix
    except OSError:
        # If it cannot be read back, let extraction produce the error — it says
        # more about why than a guess here could.
        return True


def _save_upload(source, target: Path, *, limit_bytes: int) -> tuple[int, str]:
    """Stream an upload to ``target``, returning its size and sha256.

    Two things happen in this one pass, both deliberately:

    **The limit is enforced while writing, not after.** Checking
    ``target.stat().st_size`` once the copy finished — which is what this replaced
    — means a 4 GB file is already on the disk by the time it is rejected. On a
    machine whose whole point is holding the user's own documents, filling the disk
    to then say "too large" is the failure the limit exists to prevent. So the copy
    stops at the first chunk that crosses the limit and the partial file is removed.

    **The hash is computed from the bytes already in hand.** Re-reading a 100 MB PDF
    to hash it afterwards would double the I/O for a value this pass could produce
    for free. The hash is what identifies a duplicate and what detects a source
    edited on disk after indexing — see the ``content_hash`` column.

    Raises:
        UploadTooLarge: the limit was crossed; nothing is left on disk.
        OSError: the write failed.
    """
    digest = hashlib.sha256()
    size = 0

    try:
        with target.open("wb") as destination:
            while chunk := source.read(_COPY_CHUNK):
                size += len(chunk)
                if size > limit_bytes:
                    raise UploadTooLarge(limit_bytes)
                digest.update(chunk)
                destination.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise

    return size, digest.hexdigest()


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
    def of(cls, record: File) -> FileOut:
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
    """Queue ingestion. The work lives in the service; this is the seam.

    Kept as a module-level name rather than calling the service directly, because the
    tests replace it here to observe what a request scheduled without running a real
    pipeline. Calling through this attribute is what makes that interception work.
    """
    ingest_in_background(file_id)


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
    settings = get_settings()
    limit_bytes = settings.max_upload_mb * 1024 * 1024

    try:
        size, content_hash = _save_upload(file.file, target, limit_bytes=limit_bytes)
    except UploadTooLarge:
        logger.info(
            "Upload refused, over limit name=%s limit_mb=%d",
            Path(file.filename).name,
            settings.max_upload_mb,
        )
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"That file is larger than the {settings.max_upload_mb} MB limit. "
                "Split it, or raise MAX_UPLOAD_MB if you meant to index something "
                "this big."
            ),
        ) from None
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save the upload: {exc}",
        ) from exc

    if size == 0:
        # Nothing to extract, and an empty row would sit in the library as a
        # file that can never become READY.
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty"
        )

    # A renamed file is the commonest corrupt upload there is, and the cheapest to
    # catch: extraction already fails on it with a clear reason, but only after the
    # file is stored and a row exists, leaving the user a FAILED entry to clean up.
    # Refusing it here makes it an error they can act on instead.
    #
    # Only PDF is checked. Markdown and text have no magic bytes — anything that
    # decodes as UTF-8 is legitimately text — and extraction already rejects what
    # does not decode, with a message that says how to fix it.
    if file_type is FileType.PDF and not _starts_with(target, _PDF_MAGIC):
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{Path(file.filename).name} is named as a PDF but its contents are "
                "not one. If it was renamed, give it back its real extension."
            ),
        )

    # A duplicate is the same BYTES, not the same name. The same name in two
    # folders is legitimately two files, and a renamed copy is still the one the
    # user already has — which is why this compares the hash computed above.
    #
    # Refused rather than accepted-and-linked. Pointing two rows at one blob would
    # save disk but make deletion ambiguous: removing one file would have to know
    # the other still needs the bytes. And the user's real question is "do I
    # already have this?", whose useful answer is a name they recognise.
    #
    # A pre-Phase-6 file has content_hash NULL and so is never matched. That is
    # unavoidable — its bytes were never hashed — and the failure is the safe
    # direction: a missed duplicate, not a wrongly refused upload.
    existing = file_store.find_by_content_hash(db, content_hash)
    if existing is not None:
        target.unlink(missing_ok=True)
        logger.info(
            "Upload refused, duplicate of file=%s", existing.id
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You already have this file, as \u201c{existing.name}\u201d. "
                "Delete that one first if you want to replace it, or re-index it "
                "from the library if it needs another attempt."
            ),
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
            content_hash=content_hash,
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
            detail=(
                "This file is being processed. Cancel it and wait for "
                "processing to stop before removing it."
            ),
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
