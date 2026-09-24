"""Persistence for files and chunks.

Thin functions over SQL rather than a repository class: each one is a single
statement plus row mapping, and the plan's code-design rules ask for that
directly instead of a layer that forwards to it.

Every function takes the connection explicitly, so a request handler, the
background ingestion task, and a test can each pass their own and nothing
depends on a module-level global.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from app.models.files import Chunk, File, FileStatus, FileType


class FileRecordNotFound(LookupError):
    """No file row with the requested id exists.

    Deliberately not named ``FileNotFoundError``: that name is a builtin for a
    missing file on disk, and ingestion handles both kinds of absence. Shadowing
    it would make ``except FileNotFoundError`` silently catch the wrong one.
    """


def new_file_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _to_file(row: sqlite3.Row) -> File:
    return File(
        id=row["id"],
        name=row["name"],
        file_type=FileType(row["file_type"]),
        path=row["path"],
        size=row["size"],
        status=FileStatus(row["status"]),
        error=row["error"],
        page_count=row["page_count"],
        chunk_count=row["chunk_count"],
        content_hash=row["content_hash"],
        embedding_model=row["embedding_model"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _to_chunk(row: sqlite3.Row) -> Chunk:
    return Chunk(
        id=row["id"],
        file_id=row["file_id"],
        chunk_index=row["chunk_index"],
        content=row["content"],
        page_number=row["page_number"],
        vector_id=row["vector_id"],
    )


# --- files -------------------------------------------------------------------


def find_by_content_hash(
    connection: sqlite3.Connection, content_hash: str
) -> File | None:
    """The oldest file with these exact bytes, or None.

    Oldest rather than newest: if several copies somehow exist, the one the user
    has had longest is the one they will recognise, and it is the one whose
    conversations and documents cite it.

    A ``content_hash`` of None is never matched — the caller must not pass one.
    NULL means "indexed before Noye recorded this", so treating two unknowns as
    equal would call every pre-Phase-6 file a duplicate of every other.

    Returns:
        The existing file, or None when these bytes are new.
    """
    if not content_hash:
        raise ValueError("Cannot look a file up by an empty content hash")

    row = connection.execute(
        """
        SELECT * FROM files
        WHERE content_hash = ?
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (content_hash,),
    ).fetchone()
    return _to_file(row) if row else None


def create_file(
    connection: sqlite3.Connection,
    *,
    name: str,
    file_type: FileType,
    path: str,
    size: int,
    file_id: str | None = None,
    content_hash: str | None = None,
) -> File:
    """Insert a file in ``UPLOADING`` state and return it.

    ``content_hash`` is optional so a caller that has not computed one — a
    test, or a future importer — is not forced to invent a value. Upload always
    passes it, since it has the bytes in hand.
    """
    record = File(
        id=file_id or new_file_id(),
        name=name,
        file_type=file_type,
        path=path,
        size=size,
        content_hash=content_hash,
    )
    with connection:
        connection.execute(
            """
            INSERT INTO files (id, name, file_type, path, size, status, error,
                               page_count, chunk_count, content_hash,
                               embedding_model, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, 0, ?, NULL, ?, ?)
            """,
            (
                record.id,
                record.name,
                record.file_type.value,
                record.path,
                record.size,
                record.status.value,
                record.content_hash,
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
    return record


def get_file(connection: sqlite3.Connection, file_id: str) -> File:
    """Return one file.

    Raises:
        FileRecordNotFound: no such id.
    """
    row = connection.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if row is None:
        raise FileRecordNotFound(f"No file with id {file_id}")
    return _to_file(row)


def list_files(connection: sqlite3.Connection) -> list[File]:
    """Return every file, newest first — the order the library displays."""
    rows = connection.execute("SELECT * FROM files ORDER BY created_at DESC, id").fetchall()
    return [_to_file(row) for row in rows]


def file_names(connection: sqlite3.Connection) -> dict[str, str]:
    """Map file id to display name, for citation rendering."""
    rows = connection.execute("SELECT id, name FROM files").fetchall()
    return {row["id"]: row["name"] for row in rows}


def set_status(
    connection: sqlite3.Connection,
    file_id: str,
    status: FileStatus,
    *,
    error: str | None = None,
) -> File:
    """Move a file to a new processing state.

    ``error`` is cleared on any status other than ``FAILED``, so a file that
    fails, is retried, and succeeds does not keep showing a stale reason.

    Raises:
        ValueError: ``FAILED`` was given without an error message — a failure
            the UI cannot explain is worse than no failure state at all.
        FileRecordNotFound: no such id.
    """
    if status is FileStatus.FAILED and not error:
        raise ValueError("A FAILED status requires an error message")

    stored_error = error if status is FileStatus.FAILED else None
    with connection:
        cursor = connection.execute(
            "UPDATE files SET status = ?, error = ?, updated_at = ? WHERE id = ?",
            (status.value, stored_error, _now_iso(), file_id),
        )
    if cursor.rowcount == 0:
        raise FileRecordNotFound(f"No file with id {file_id}")
    return get_file(connection, file_id)


def set_embedding_model(
    connection: sqlite3.Connection, file_id: str, model: str | None
) -> File:
    """Record which embedding model produced this file's vectors.

    Its own function rather than a parameter on ``set_counts``, because it is
    written at a different moment and means something different: the counts are for
    display, and this is what search correctness depends on. A cosine score between
    two embedding spaces is meaningless, so a ranking that mixes them is confidently
    wrong — which is worse than empty, because the wrongness is invisible.

    ``None`` clears it, which is what a failed or cleared index needs: claiming a
    model for vectors that are not there would be the same lie in reverse.

    Raises:
        FileRecordNotFound: no such id.
    """
    with connection:
        cursor = connection.execute(
            "UPDATE files SET embedding_model = ?, updated_at = ? WHERE id = ?",
            (model, _now_iso(), file_id),
        )
    if cursor.rowcount == 0:
        raise FileRecordNotFound(f"No file with id {file_id}")
    return get_file(connection, file_id)


def set_counts(
    connection: sqlite3.Connection,
    file_id: str,
    *,
    page_count: int | None = None,
    chunk_count: int | None = None,
) -> File:
    """Record extraction and chunking results for display.

    Raises:
        FileRecordNotFound: no such id.
    """
    assignments, values = [], []
    if page_count is not None:
        assignments.append("page_count = ?")
        values.append(page_count)
    if chunk_count is not None:
        assignments.append("chunk_count = ?")
        values.append(chunk_count)

    if assignments:
        assignments.append("updated_at = ?")
        values.extend([_now_iso(), file_id])
        with connection:
            cursor = connection.execute(
                f"UPDATE files SET {', '.join(assignments)} WHERE id = ?", values
            )
        if cursor.rowcount == 0:
            raise FileRecordNotFound(f"No file with id {file_id}")

    return get_file(connection, file_id)


def reset_counts(connection: sqlite3.Connection, file_id: str) -> File:
    """Forget a file's page and chunk counts.

    Needed because :func:`set_counts` treats ``None`` as "leave alone", so it
    cannot clear a value. Re-ingesting uses this: if the second run dies during
    extraction, the counts from the first run would otherwise still be on
    display, describing an index that no longer exists.

    Raises:
        FileRecordNotFound: no such id.
    """
    with connection:
        cursor = connection.execute(
            "UPDATE files SET page_count = NULL, chunk_count = 0, updated_at = ? WHERE id = ?",
            (_now_iso(), file_id),
        )
    if cursor.rowcount == 0:
        raise FileRecordNotFound(f"No file with id {file_id}")
    return get_file(connection, file_id)


def delete_file(connection: sqlite3.Connection, file_id: str) -> None:
    """Delete a file row and, by cascade, its chunk rows.

    Deleting the original from disk and the vectors from Qdrant is the caller's
    job; this function owns only the metadata.

    Raises:
        FileRecordNotFound: no such id.
    """
    with connection:
        cursor = connection.execute("DELETE FROM files WHERE id = ?", (file_id,))
    if cursor.rowcount == 0:
        raise FileRecordNotFound(f"No file with id {file_id}")


# --- chunks ------------------------------------------------------------------


def replace_chunks(
    connection: sqlite3.Connection, file_id: str, chunks: Sequence[Chunk]
) -> int:
    """Store a file's chunks, replacing any it already had.

    Replacing rather than appending makes re-ingestion idempotent, matching the
    deterministic Qdrant point ids: running a file through the pipeline twice
    leaves one set of rows, not two.

    Returns the number of chunks stored.
    """
    with connection:
        connection.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
        connection.executemany(
            """
            INSERT INTO chunks (id, file_id, chunk_index, content, page_number, vector_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (c.id, c.file_id, c.chunk_index, c.content, c.page_number, c.vector_id)
                for c in chunks
            ],
        )
    return len(chunks)


def list_chunks(connection: sqlite3.Connection, file_id: str) -> list[Chunk]:
    """Return a file's chunks in reading order."""
    rows = connection.execute(
        "SELECT * FROM chunks WHERE file_id = ? ORDER BY chunk_index", (file_id,)
    ).fetchall()
    return [_to_chunk(row) for row in rows]


def count_chunks(connection: sqlite3.Connection, file_id: str | None = None) -> int:
    """Count stored chunk rows, for one file or for all of them."""
    if file_id is None:
        row = connection.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()
    else:
        row = connection.execute(
            "SELECT COUNT(*) AS n FROM chunks WHERE file_id = ?", (file_id,)
        ).fetchone()
    return row["n"]
