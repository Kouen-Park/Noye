"""The ingestion pipeline.

One function drives a saved file through every stage of the knowledge engine:

    EXTRACTING -> CHUNKING -> EMBEDDING -> READY

The status is written to SQLite as each stage begins, which is what lets the
library show real progress instead of a fabricated percentage. Two properties
matter more than the happy path:

* **A failure never leaves a partial index.** If embedding dies halfway, the
  vectors already stored are deleted before the file is marked FAILED —
  otherwise a file the user sees as failed would still answer questions, using
  half its content.
* **Re-ingesting is safe.** The file's vectors and chunk rows are cleared
  before new ones are written, so a retried upload cannot leave stale chunks
  from a previous run behind.
"""

from __future__ import annotations

import sqlite3

import httpx
from qdrant_client import QdrantClient

from app.db import files as file_store
from app.models.files import Chunk as ChunkRow
from app.models.files import File, FileStatus, FileType
from app.services.chunking import chunk_pages
from app.services.embeddings import embed_chunks
from app.services.extraction import ExtractedPage, extract_pdf
from app.services.indexing import delete_file_chunks, index_chunks, point_id


class IngestionError(Exception):
    """A file could not be ingested.

    The message is user-facing: it is stored on the file row and shown in the
    library, so it says what went wrong in terms the user can act on.
    """


def ingest_file(
    connection: sqlite3.Connection,
    file_id: str,
    *,
    qdrant_client: QdrantClient | None = None,
    http_client: httpx.Client | None = None,
) -> File:
    """Process an uploaded file into searchable, citable chunks.

    Expects the file row to exist and its ``path`` to point at a saved file.
    Advances the row's status as it goes and returns the final record — READY on
    success, FAILED with a reason on any failure.

    Does not raise for ingestion failures: the failure is the outcome, recorded
    on the file so the library can display it. Only a missing file row raises,
    since that means the caller passed a bad id.

    Raises:
        FileRecordNotFound: no file row with ``file_id``.
    """
    record = file_store.get_file(connection, file_id)

    try:
        pages = _extract(connection, record)
        chunks = _chunk(connection, record, pages)
        _embed_and_index(
            connection, record, chunks, qdrant_client=qdrant_client, http_client=http_client
        )
    except IngestionError as exc:
        return _fail(connection, record, str(exc), qdrant_client=qdrant_client)
    except Exception as exc:  # noqa: BLE001 - last resort, see below
        # An unexpected error must still leave the file in a terminal state with
        # a reason; a row stuck in EMBEDDING forever is worse than an ugly
        # message, and the original type is preserved in the text.
        return _fail(
            connection,
            record,
            f"Unexpected {type(exc).__name__} during ingestion: {exc}",
            qdrant_client=qdrant_client,
        )

    return file_store.set_status(connection, file_id, FileStatus.READY)


def _extract(connection: sqlite3.Connection, record: File) -> list[ExtractedPage]:
    file_store.set_status(connection, record.id, FileStatus.EXTRACTING)

    if record.file_type is not FileType.PDF:
        raise IngestionError(
            f"{record.file_type.value.upper()} files are not supported yet. "
            "Only PDF files can be processed at the moment."
        )

    try:
        pages = extract_pdf(record.path)
    except Exception as exc:
        raise IngestionError(str(exc)) from exc

    file_store.set_counts(connection, record.id, page_count=len(pages))
    return pages


def _chunk(
    connection: sqlite3.Connection, record: File, pages: list[ExtractedPage]
) -> list:
    file_store.set_status(connection, record.id, FileStatus.CHUNKING)

    chunks = chunk_pages(pages, file_id=record.id)

    if not chunks:
        # Every page was empty. For a PDF this almost always means a scan with
        # no text layer: extraction succeeded, but there is nothing to search.
        # Marking it READY would leave a document that looks indexed and never
        # matches anything, so it fails with an explanation instead. OCR is out
        # of MVP scope.
        raise IngestionError(
            "No extractable text found. If this is a scanned document, it needs "
            "OCR, which Noye does not do yet."
        )

    file_store.set_counts(connection, record.id, chunk_count=len(chunks))
    return chunks


def _embed_and_index(
    connection: sqlite3.Connection,
    record: File,
    chunks: list,
    *,
    qdrant_client: QdrantClient | None,
    http_client: httpx.Client | None,
) -> None:
    file_store.set_status(connection, record.id, FileStatus.EMBEDDING)

    try:
        vectors = embed_chunks(chunks, client=http_client)
    except Exception as exc:
        raise IngestionError(str(exc)) from exc

    # Clear the previous run before writing: chunk rows are replaced wholesale,
    # but vectors are keyed by chunk index, so a shorter second run would
    # otherwise leave the tail of the first run searchable.
    try:
        delete_file_chunks(record.id, client=qdrant_client)
        index_chunks(chunks, vectors, client=qdrant_client)
    except Exception as exc:
        raise IngestionError(str(exc)) from exc

    rows = [
        ChunkRow(
            id=f"{record.id}:{chunk.chunk_index}",
            file_id=record.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_number=chunk.page_number if record.file_type.has_pages else None,
            vector_id=point_id(record.id, chunk.chunk_index),
        )
        for chunk in chunks
    ]
    file_store.replace_chunks(connection, record.id, rows)


def _fail(
    connection: sqlite3.Connection,
    record: File,
    reason: str,
    *,
    qdrant_client: QdrantClient | None,
) -> File:
    """Mark the file FAILED and remove anything it managed to index."""
    try:
        delete_file_chunks(record.id, client=qdrant_client)
    except Exception:  # noqa: BLE001
        # Cleanup is best-effort: reporting the original failure matters more
        # than a secondary error from an already-unreachable Qdrant.
        pass

    file_store.replace_chunks(connection, record.id, [])
    return file_store.set_status(connection, record.id, FileStatus.FAILED, error=reason)
