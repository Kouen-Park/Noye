"""Persistence for conversations, messages and stored citations.

Thin functions over SQL, like :mod:`app.db.files`, and every function takes the
connection explicitly so a request handler and a test can each pass their own.

The one structural note: citations are written with the message that produced
them and read back verbatim. They are never recomputed from the live index,
because the index changes as files are added, re-ingested and removed — an old
answer re-rendered from today's index would show sources that were never the ones
behind it.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from app.models.conversations import (
    Conversation,
    Message,
    MessageCitation,
    Role,
    derive_title,
)


class ConversationNotFound(LookupError):
    """No conversation row with the requested id exists."""


class MessageNotFound(LookupError):
    """No message row with the requested id exists."""


def new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_conversation(row: sqlite3.Row) -> Conversation:
    return Conversation(
        id=row["id"],
        title=row["title"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _to_message(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=Role(row["role"]),
        content=row["content"],
        error=row["error"],
        created_at=datetime.fromisoformat(row["created_at"]),
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


# --- conversations -----------------------------------------------------------


def create_conversation(
    connection: sqlite3.Connection,
    *,
    title: str | None = None,
    first_question: str | None = None,
    conversation_id: str | None = None,
) -> Conversation:
    """Start a conversation.

    The title comes from ``title`` if given, otherwise from ``first_question``.
    Naming a conversation before having it is a question the user cannot answer,
    so the first question is the default.
    """
    resolved = title or derive_title(first_question or "")
    record = Conversation(id=conversation_id or new_id(), title=resolved)
    with connection:
        connection.execute(
            """
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                record.id,
                record.title,
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
    return record


def get_conversation(connection: sqlite3.Connection, conversation_id: str) -> Conversation:
    """Return one conversation, without its messages.

    Raises:
        ConversationNotFound: no such id.
    """
    row = connection.execute(
        "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    if row is None:
        raise ConversationNotFound(f"No conversation with id {conversation_id}")
    return _to_conversation(row)


def read_conversation(connection: sqlite3.Connection, conversation_id: str) -> Conversation:
    """Return one conversation with its messages and their citations.

    Raises:
        ConversationNotFound: no such id.
    """
    conversation = get_conversation(connection, conversation_id)
    conversation.messages = list_messages(connection, conversation_id)
    return conversation


def list_conversations(connection: sqlite3.Connection) -> list[Conversation]:
    """Return every conversation, most recently active first.

    By ``updated_at`` rather than ``created_at``: the sidebar should surface what
    the user was last talking about, not what they started longest ago.
    """
    rows = connection.execute(
        "SELECT * FROM conversations ORDER BY updated_at DESC, id"
    ).fetchall()
    return [_to_conversation(row) for row in rows]


def rename_conversation(
    connection: sqlite3.Connection, conversation_id: str, title: str
) -> Conversation:
    """Set a conversation's title.

    Raises:
        ValueError: the title is blank.
        ConversationNotFound: no such id.
    """
    cleaned = " ".join(title.split())
    if not cleaned:
        raise ValueError("A conversation title cannot be empty")

    with connection:
        cursor = connection.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (cleaned, _now_iso(), conversation_id),
        )
    if cursor.rowcount == 0:
        raise ConversationNotFound(f"No conversation with id {conversation_id}")
    return get_conversation(connection, conversation_id)


def touch_conversation(connection: sqlite3.Connection, conversation_id: str) -> None:
    """Mark a conversation as recently active."""
    with connection:
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (_now_iso(), conversation_id),
        )


def delete_conversation(connection: sqlite3.Connection, conversation_id: str) -> None:
    """Delete a conversation and, by cascade, its messages and their citations.

    Raises:
        ConversationNotFound: no such id.
    """
    with connection:
        cursor = connection.execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )
    if cursor.rowcount == 0:
        raise ConversationNotFound(f"No conversation with id {conversation_id}")


# --- messages ----------------------------------------------------------------


def add_message(
    connection: sqlite3.Connection,
    conversation_id: str,
    *,
    role: Role,
    content: str,
    error: str | None = None,
    citations: Sequence[MessageCitation] = (),
    message_id: str | None = None,
) -> Message:
    """Append a message, with its citations, and mark the conversation active.

    Citations are stored as given. They belong to this answer at this moment and
    are never derived again later.

    Raises:
        ConversationNotFound: no such conversation.
    """
    # Checked explicitly so the caller gets a domain error rather than a foreign
    # key failure from SQLite.
    get_conversation(connection, conversation_id)

    record = Message(
        id=message_id or new_id(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        error=error,
        citations=list(citations),
    )

    with connection:
        connection.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.conversation_id,
                record.role.value,
                record.content,
                record.error,
                record.created_at.isoformat(),
            ),
        )
        connection.executemany(
            """
            INSERT INTO message_citations
                (id, message_id, position, file_id, file_name, page_number,
                 chunk_indexes, best_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    new_id(),
                    record.id,
                    position,
                    citation.file_id,
                    citation.file_name,
                    citation.page_number,
                    ",".join(str(index) for index in citation.chunk_indexes),
                    citation.best_score,
                )
                for position, citation in enumerate(record.citations)
            ],
        )

    touch_conversation(connection, conversation_id)
    return record


def list_messages(connection: sqlite3.Connection, conversation_id: str) -> list[Message]:
    """Return a conversation's messages in order, each with its citations."""
    rows = connection.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at, id",
        (conversation_id,),
    ).fetchall()
    messages = [_to_message(row) for row in rows]
    if not messages:
        return []

    # One query for every citation in the conversation rather than one per
    # message: a conversation is always read whole, and this is the read path the
    # chat page uses on every load.
    placeholders = ",".join("?" for _ in messages)
    citation_rows = connection.execute(
        f"""
        SELECT * FROM message_citations
        WHERE message_id IN ({placeholders})
        ORDER BY message_id, position
        """,
        [message.id for message in messages],
    ).fetchall()

    by_message: dict[str, list[MessageCitation]] = {}
    for row in citation_rows:
        by_message.setdefault(row["message_id"], []).append(_to_citation(row))

    for message in messages:
        message.citations = by_message.get(message.id, [])
    return messages


def get_message(connection: sqlite3.Connection, message_id: str) -> Message:
    """Return one message with its citations.

    Raises:
        MessageNotFound: no such id.
    """
    row = connection.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        raise MessageNotFound(f"No message with id {message_id}")
    message = _to_message(row)
    citation_rows = connection.execute(
        "SELECT * FROM message_citations WHERE message_id = ? ORDER BY position",
        (message_id,),
    ).fetchall()
    message.citations = [_to_citation(row) for row in citation_rows]
    return message


def count_messages(connection: sqlite3.Connection, conversation_id: str | None = None) -> int:
    """Count messages, in one conversation or in all of them."""
    if conversation_id is None:
        row = connection.execute("SELECT COUNT(*) AS n FROM messages").fetchone()
    else:
        row = connection.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
    return row["n"]
