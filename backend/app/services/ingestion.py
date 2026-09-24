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
* **One pipeline per file.** A second run on a file already being ingested is
  refused outright rather than interleaved, because both would write the same
  chunk rows and the same Qdrant point ids.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import replace

import httpx
from qdrant_client import QdrantClient

from app.config import get_settings
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.logging_config import get_logger, timed
from app.models.files import Chunk as ChunkRow
from app.models.files import File, FileStatus
from app.services.chunking import chunk_pages
from app.services.embeddings import embed_chunks
from app.services.extraction import ExtractedPage, extract_file
from app.services.indexing import delete_file_chunks, index_chunks, point_id

#: Identifiers, counts and timings only. A chunk's text never goes in here — see
#: app/logging_config.py for why that is a rule rather than a preference.
logger = get_logger("ingestion")


def ingest_in_background(file_id: str) -> None:
    """Run ingestion on its own connection, for a FastAPI background task.

    Lives here rather than in the files router because two routers now queue it —
    upload and re-ingest in `/files`, and the whole-library rebuild in `/index` — and
    it is about running the pipeline, not about shaping a request.

    The request's connection is closed as soon as the response is sent, and this runs
    on a different thread, so it must not borrow it.

    The reservation is released on every path. A file left reserved is a file nothing
    can ever ingest again, which is worse than a failed ingestion because it has no
    visible cause.
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


def _first_sentence(reason: str) -> str:
    """The cause, without the advice that follows it.

    Ingestion reasons are written for the user, so they carry remediation —
    "Could not reach Ollama at http://localhost:11434. Check that it is running
    (brew services start ollama)." A log wants the first half; the second is
    instructions to a person and it pushes the identifiers off the line.
    """
    head, separator, _ = reason.partition(". ")
    return head + "." if separator else reason


class IngestionError(Exception):
    """A file could not be ingested.

    The message is user-facing: it is stored on the file row and shown in the
    library, so it says what went wrong in terms the user can act on.
    """


class AlreadyIngesting(RuntimeError):
    """This file is being ingested right now, so a second run was refused.

    Raised rather than ignored: two pipelines on one file would interleave their
    writes to the same chunk rows and the same Qdrant point ids, and the loser
    would leave a half-replaced index behind. A caller that hits this has a bug
    or a user double-clicked, and either way the right answer is to say no.
    """


# Which files are being ingested in this process, right now.
#
# This is the only reliable answer to "is this file busy?". A row's status
# cannot answer it: a file left in EMBEDDING by a server that restarted
# mid-ingestion looks busy forever, and a large file embedding for minutes
# without a status write looks idle to any timeout-based guess. Membership here
# is the truth, which also means an orphaned row is correctly re-ingestable.
#
# Per-process, which matches how Noye runs: one local uvicorn, one user. A
# multi-process deployment would need this in SQLite instead.
_in_flight: dict[str, threading.Event | None] = {}
_in_flight_lock = threading.Lock()


def is_ingesting(file_id: str) -> bool:
    """Whether this file is being ingested right now."""
    with _in_flight_lock:
        return file_id in _in_flight


def _claim(file_id: str, cancellation: threading.Event | None = None) -> None:
    with _in_flight_lock:
        if file_id in _in_flight:
            raise AlreadyIngesting(f"File {file_id} is already being ingested")
        _in_flight[file_id] = cancellation


def reserve_ingestion(file_id: str) -> None:
    """Reserve a file before its background task is scheduled."""
    _claim(file_id, threading.Event())


def reserve_delete(file_id: str) -> None:
    """Keep ingestion and a second delete out until deletion finishes."""
    _claim(file_id)


def cancel_ingestion(file_id: str) -> bool:
    """Ask a queued or running pipeline to stop at its next safe checkpoint."""
    with _in_flight_lock:
        cancellation = _in_flight.get(file_id)
        if cancellation is None:
            return False
        cancellation.set()
        return True


def release_file(file_id: str) -> None:
    with _in_flight_lock:
        _in_flight.pop(file_id, None)


def _release(file_id: str, cancellation: threading.Event) -> None:
    with _in_flight_lock:
        if _in_flight.get(file_id) is cancellation:
            _in_flight.pop(file_id, None)


def _check_cancel(cancellation: threading.Event) -> None:
    if cancellation.is_set():
        raise IngestionError("Processing was cancelled.")


def cancel_orphaned_file(connection: sqlite3.Connection, file_id: str) -> File:
    """Settle a processing row left behind when the server stopped mid-run.

    The caller must first reserve this file, so no new ingestion can begin
    during cleanup.
    """
    record = file_store.get_file(connection, file_id)
    return _fail(connection, record, "Processing was interrupted.", qdrant_client=None)


def ingest_file(
    connection: sqlite3.Connection,
    file_id: str,
    *,
    qdrant_client: QdrantClient | None = None,
    http_client: httpx.Client | None = None,
    reserved: bool = False,
) -> File:
    """Process an uploaded file into searchable, citable chunks.

    Expects the file row to exist and its ``path`` to point at a saved file.
    Advances the row's status as it goes and returns the final record — READY on
    success, FAILED with a reason on any failure.

    Does not raise for ingestion failures: the failure is the outcome, recorded
    on the file so the library can display it. Only a missing file row or an
    already-running ingestion raises, since both mean the caller is wrong.

    Raises:
        FileRecordNotFound: no file row with ``file_id``.
        AlreadyIngesting: this file is being ingested already.
    """
    record = file_store.get_file(connection, file_id)

    if reserved:
        with _in_flight_lock:
            cancellation = _in_flight.get(file_id)
        if cancellation is None:
            raise AlreadyIngesting(f"File {file_id} has no ingestion reservation")
    else:
        cancellation = threading.Event()
        _claim(file_id, cancellation)
    try:
        try:
            logger.info(
                "Ingestion started file=%s type=%s size=%d",
                record.id,
                record.file_type.value,
                record.size,
            )
            _check_cancel(cancellation)
            pages = _extract(connection, record)
            _check_cancel(cancellation)
            chunks = _chunk(connection, record, pages)
            _check_cancel(cancellation)
            _embed_and_index(
                connection, record, chunks, qdrant_client=qdrant_client, http_client=http_client,
                cancellation=cancellation,
            )
            _check_cancel(cancellation)
        except IngestionError as exc:
            # The full reason is the user's and reaches the UI through the file
            # row. The log keeps only its first sentence: the rest is advice
            # written for a person ("Check that it is running (brew services
            # start ollama)"), which a log line does not need and which pushes
            # the fields that matter off the end of the terminal.
            #
            # Not dropped entirely, even though the stage line above usually
            # carries the same cause: a failure raised outside a timed stage —
            # a file with no extractable text — has no other line at all.
            logger.warning(
                "Ingestion failed file=%s reason=%s", record.id, _first_sentence(str(exc))
            )
            return _fail(connection, record, str(exc), qdrant_client=qdrant_client)
        except Exception as exc:
            # An unexpected error must still leave the file in a terminal state
            # with a reason; a row stuck in EMBEDDING forever is worse than an
            # ugly message, and the original type is preserved in the text.
            #
            # This is the one place a traceback is worth keeping: the message on
            # the row names the exception type but throws away where it came
            # from, and an unexpected error is exactly the case where that
            # matters.
            logger.exception("Unexpected ingestion error file=%s", record.id)
            return _fail(
                connection,
                record,
                f"Unexpected {type(exc).__name__} during ingestion: {exc}",
                qdrant_client=qdrant_client,
            )

        # Commit READY while holding the same lock used by cancellation. A
        # successful cancel request must never race past the final checkpoint.
        with _in_flight_lock:
            cancelled = cancellation.is_set()
            if not cancelled:
                result = file_store.set_status(connection, file_id, FileStatus.READY)
                _in_flight.pop(file_id, None)
                # pages is omitted for a format that has none. Logging
                # "pages=None" for every Markdown file reads as a page count that
                # could not be determined, which is a different and alarming
                # thing from a format where the number is meaningless.
                if record.file_type.has_pages:
                    logger.info(
                        "Ingestion complete file=%s pages=%s chunks=%s",
                        file_id,
                        result.page_count,
                        result.chunk_count,
                    )
                else:
                    logger.info(
                        "Ingestion complete file=%s chunks=%s",
                        file_id,
                        result.chunk_count,
                    )
                return result
        logger.info("Ingestion cancelled file=%s", file_id)
        return _fail(connection, record, "Processing was cancelled.", qdrant_client=qdrant_client)
    finally:
        _release(file_id, cancellation)


def _extract(connection: sqlite3.Connection, record: File) -> list[ExtractedPage]:
    file_store.set_status(connection, record.id, FileStatus.EXTRACTING)

    try:
        with timed(logger, "Extracted", file=record.id):
            pages = extract_file(record.path, record.file_type)
    except Exception as exc:
        raise IngestionError(str(exc)) from exc

    # Only meaningful for page-aware formats; Markdown and text come back as a
    # single placeholder page, and reporting "1 page" for them would be noise.
    if record.file_type.has_pages:
        file_store.set_counts(connection, record.id, page_count=len(pages))
    return pages


def _chunk(
    connection: sqlite3.Connection, record: File, pages: list[ExtractedPage]
) -> list:
    file_store.set_status(connection, record.id, FileStatus.CHUNKING)

    chunks = chunk_pages(pages, file_id=record.id)

    if not record.file_type.has_pages:
        # Drop the placeholder page number here, before anything downstream sees
        # it. Citations are built from the Qdrant payload, so clearing it only in
        # the database rows would still leak "page 1" into every citation for a
        # Markdown or text file.
        chunks = [replace(chunk, page_number=None) for chunk in chunks]

    if not chunks:
        # Nothing to search. For a PDF this almost always means a scan with no
        # text layer; for a text file it means the file held only whitespace.
        # Marking either READY would leave a document that looks indexed and
        # never matches anything, so it fails with an explanation instead. OCR
        # is out of MVP scope.
        if record.file_type.has_pages:
            raise IngestionError(
                "No extractable text found. If this is a scanned document, it "
                "needs OCR, which Noye does not do yet."
            )
        raise IngestionError("The file contains no text to index.")

    file_store.set_counts(connection, record.id, chunk_count=len(chunks))
    return chunks


def _embed_and_index(
    connection: sqlite3.Connection,
    record: File,
    chunks: list,
    *,
    qdrant_client: QdrantClient | None,
    http_client: httpx.Client | None,
    cancellation: threading.Event,
) -> None:
    file_store.set_status(connection, record.id, FileStatus.EMBEDDING)

    try:
        with timed(
            logger,
            "Embedded",
            file=record.id,
            chunks=len(chunks),
            model=get_settings().ollama_embedding_model,
        ):
            vectors = embed_chunks(chunks, client=http_client)
    except Exception as exc:
        raise IngestionError(str(exc)) from exc

    # Clear the previous run before writing: chunk rows are replaced wholesale,
    # but vectors are keyed by chunk index, so a shorter second run would
    # otherwise leave the tail of the first run searchable.
    try:
        _check_cancel(cancellation)
        with timed(logger, "Indexed", file=record.id, points=len(chunks)):
            delete_file_chunks(record.id, client=qdrant_client)
            _check_cancel(cancellation)
            index_chunks(chunks, vectors, client=qdrant_client)
        _check_cancel(cancellation)
    except Exception as exc:
        raise IngestionError(str(exc)) from exc

    # After the write, not before. This column is read to decide whether a file's
    # vectors are from the current embedding space, so it must never name a model
    # for vectors that were not actually stored.
    file_store.set_embedding_model(
        connection, record.id, get_settings().ollama_embedding_model
    )

    rows = [
        ChunkRow(
            id=f"{record.id}:{chunk.chunk_index}",
            file_id=record.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_number=chunk.page_number,
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
    except Exception as exc:  # noqa: BLE001
        # Cleanup is best-effort: reporting the original failure matters more
        # than a secondary error from an already-unreachable Qdrant.
        #
        # Swallowing it silently, though, hid the case that actually matters —
        # the file is marked FAILED while its vectors survive in the index, so
        # search keeps returning passages from a document the library shows as
        # broken. Nothing in the UI can show that, which is precisely why it
        # belongs in a log.
        logger.warning(
            "Vector cleanup failed after ingestion failure, index may hold stale "
            "points file=%s error=%s: %s",
            record.id,
            type(exc).__name__,
            exc,
        )

    file_store.replace_chunks(connection, record.id, [])
    # The chunk rows are gone, so the count must go with them. Leaving it behind
    # made a file that chunked and then failed at embedding advertise passages it
    # no longer had — the library showed "24 passages" beside "Could not read".
    # page_count is left alone: the pages really were read, and that stays true.
    file_store.set_counts(connection, record.id, chunk_count=0)
    # The vectors are gone, so the model that made them must go with them. Leaving
    # it would have a FAILED file claiming an embedding space it no longer occupies,
    # which is exactly the confusion the column exists to prevent.
    file_store.set_embedding_model(connection, record.id, None)
    return file_store.set_status(connection, record.id, FileStatus.FAILED, error=reason)
