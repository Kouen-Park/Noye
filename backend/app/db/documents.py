"""Persistence for documents and their citations.

Thin functions over SQL, like the other stores, with the connection passed in.

Two things this layer refuses to do, both deliberate:

* It never regenerates content. :func:`update_document` writes what it is given,
  so an edit is the document from then on.
* It never joins provenance. ``source_conversation_id`` is returned as stored even
  when that conversation is gone, because a document that outlived its
  conversation is the normal case rather than an error.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from app.models.conversations import MessageCitation
from app.models.documents import Document, derive_title


class DocumentNotFound(LookupError):
    """No document row with the requested id exists."""


def new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_document(row: sqlite3.Row) -> Document:
    return Document(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        source_conversation_id=row["source_conversation_id"],
        source_message_id=row["source_message_id"],
        source_instruction=row["source_instruction"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _to_citation(row: sqlite3.Row) -> MessageCitation:
    raw = row["chunk_indexes"]
    return MessageCitation(
        file_id=row["file_id"],
        file_name=row["file_name"],
        page_number=row["page_number"],
        chunk_indexes=tuple(int(part) for part in raw.split(",") if part != ""),
        best_score=row["best_score"],
    )


def _write_citations(
    connection: sqlite3.Connection,
    document_id: str,
    citations: Sequence[MessageCitation],
) -> None:
    """Replace a document's citations. Called inside the caller's transaction."""
    connection.execute("DELETE FROM document_citations WHERE document_id = ?", (document_id,))
    connection.executemany(
        """
        INSERT INTO document_citations
            (id, document_id, position, file_id, file_name, page_number,
             chunk_indexes, best_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                new_id(),
                document_id,
                position,
                citation.file_id,
                citation.file_name,
                citation.page_number,
                ",".join(str(index) for index in citation.chunk_indexes),
                citation.best_score,
            )
            for position, citation in enumerate(citations)
        ],
    )


def create_document(
    connection: sqlite3.Connection,
    *,
    content: str,
    title: str | None = None,
    instruction: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    citations: Sequence[MessageCitation] = (),
    document_id: str | None = None,
) -> Document:
    """Store a document.

    The title comes from ``title`` if given, otherwise from ``instruction`` — what
    the person asked for makes a better name than asking them to invent one before
    they have read the draft.
    """
    record = Document(
        id=document_id or new_id(),
        title=title or derive_title(instruction or ""),
        content=content,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
        source_instruction=instruction,
        citations=list(citations),
    )

    with connection:
        connection.execute(
            """
            INSERT INTO documents
                (id, title, content, source_conversation_id, source_message_id,
                 source_instruction, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.title,
                record.content,
                record.source_conversation_id,
                record.source_message_id,
                record.source_instruction,
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
        _write_citations(connection, record.id, record.citations)

    return record


def get_document(connection: sqlite3.Connection, document_id: str) -> Document:
    """Return one document with its citations.

    Raises:
        DocumentNotFound: no such id.
    """
    row = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise DocumentNotFound(f"No document with id {document_id}")
    document = _to_document(row)
    citation_rows = connection.execute(
        "SELECT * FROM document_citations WHERE document_id = ? ORDER BY position",
        (document_id,),
    ).fetchall()
    document.citations = [_to_citation(row) for row in citation_rows]
    return document


def list_documents(connection: sqlite3.Connection) -> list[Document]:
    """Return every document, most recently edited first, without citations.

    The list shows titles and dates; fetching every document's citations to render
    a list that does not display them would be work for nothing.
    """
    rows = connection.execute(
        "SELECT * FROM documents ORDER BY updated_at DESC, id"
    ).fetchall()
    return [_to_document(row) for row in rows]


def update_document(
    connection: sqlite3.Connection,
    document_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
) -> Document:
    """Change a document's title, its content, or both.

    ``None`` means leave alone, so saving an edit does not require resending the
    title. An empty string is a real value: a user may clear a document's body.

    Raises:
        ValueError: a title was given and is blank.
        DocumentNotFound: no such id.
    """
    assignments: list[str] = []
    values: list[object] = []

    if title is not None:
        cleaned = " ".join(title.split())
        if not cleaned:
            raise ValueError("A document title cannot be empty")
        assignments.append("title = ?")
        values.append(cleaned)

    if content is not None:
        assignments.append("content = ?")
        values.append(content)

    if not assignments:
        return get_document(connection, document_id)

    assignments.append("updated_at = ?")
    values.extend([_now_iso(), document_id])

    with connection:
        cursor = connection.execute(
            f"UPDATE documents SET {', '.join(assignments)} WHERE id = ?", values
        )
    if cursor.rowcount == 0:
        raise DocumentNotFound(f"No document with id {document_id}")
    return get_document(connection, document_id)


def delete_document(connection: sqlite3.Connection, document_id: str) -> None:
    """Delete a document and, by cascade, its citations.

    Raises:
        DocumentNotFound: no such id.
    """
    with connection:
        cursor = connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    if cursor.rowcount == 0:
        raise DocumentNotFound(f"No document with id {document_id}")


def count_documents(connection: sqlite3.Connection) -> int:
    return connection.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
