"""SQLite connection and schema.

Uses the standard library's ``sqlite3`` directly. The schema is five columns
wide and one relationship deep, so an ORM would add a dependency and a layer
without removing any work.

SQLite holds application metadata only. The files under ``data/sources/`` are
the source of truth and the Qdrant index is derived, so this database can be
deleted and rebuilt from the sources without losing a user's documents.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import PROJECT_ROOT, get_settings
from app.db.migrations import apply_migrations

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    file_type    TEXT NOT NULL,
    path         TEXT NOT NULL,
    size         INTEGER NOT NULL,
    status       TEXT NOT NULL,
    error        TEXT,
    page_count   INTEGER,
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    -- sha256 of the file's bytes. How a duplicate is identified, and how a source
    -- edited on disk after indexing is noticed. NULL for files indexed before
    -- Noye recorded it; see migrations._step_1_file_provenance.
    content_hash TEXT,
    -- The embedding model whose vectors are in the index for this file. Search
    -- must never mix two embedding spaces in one ranking. NULL means unknown,
    -- not mismatched.
    embedding_model TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id           TEXT PRIMARY KEY,
    file_id      TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    page_number  INTEGER,
    vector_id    TEXT NOT NULL,
    UNIQUE (file_id, chunk_index)
);

-- Deleting a source must be able to find its chunks cheaply; this is the only
-- access pattern chunks are queried by.
CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);

-- The library lists newest first.
CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at DESC);

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id               TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT NOT NULL,
    content          TEXT NOT NULL,
    -- Set when answering failed, so the user's question stays in the
    -- conversation with the reason attached instead of the turn being lost.
    error            TEXT,
    created_at       TEXT NOT NULL
);

-- Citations are STORED rather than recomputed at display time. Re-running
-- retrieval to re-render an old answer would show sources that were never the
-- ones behind it, because the index changes as files are added, re-ingested and
-- removed. `file_name` is copied in so a past answer keeps naming what it was
-- based on even after that file is deleted; `file_id` is kept as well so the
-- source can still be opened while it does exist.
CREATE TABLE IF NOT EXISTS message_citations (
    id           TEXT PRIMARY KEY,
    message_id   TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    file_id      TEXT NOT NULL,
    file_name    TEXT NOT NULL,
    page_number  INTEGER,
    -- The retrieved chunk indexes behind this citation, comma-separated, so the
    -- exact passages stay inspectable. A join table for a handful of integers
    -- that are only ever read together would cost more than it explains.
    chunk_indexes TEXT NOT NULL,
    best_score   REAL NOT NULL,
    UNIQUE (message_id, position)
);

-- A conversation is always read as a whole, in order.
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

-- Citations are always read for a message, in display order.
CREATE INDEX IF NOT EXISTS idx_citations_message
    ON message_citations(message_id, position);

-- The conversation list is by most recent activity.
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
    ON conversations(updated_at DESC);

CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    -- Markdown, as the user last left it. AI-generated text must always remain
    -- editable, so this column is the document — not a cache of something that
    -- could be regenerated.
    content     TEXT NOT NULL,
    -- Where it came from, when it came from somewhere. Deliberately WITHOUT a
    -- foreign key: deleting a conversation must not delete the documents made
    -- from it. The document is the user's work; the conversation was scaffolding.
    source_conversation_id  TEXT,
    source_message_id       TEXT,
    -- The instruction that produced the first draft, kept so a person can see
    -- what they asked for months later.
    source_instruction      TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Citations are copied onto the document for the same reason as on a message:
-- the index changes as files are added, re-ingested and removed, so re-deriving
-- them later would attribute the document to sources that were never behind it.
CREATE TABLE IF NOT EXISTS document_citations (
    id            TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    file_id       TEXT NOT NULL,
    file_name     TEXT NOT NULL,
    page_number   INTEGER,
    chunk_indexes TEXT NOT NULL,
    best_score    REAL NOT NULL,
    UNIQUE (document_id, position)
);

-- Citations are always read for a document, in display order.
CREATE INDEX IF NOT EXISTS idx_document_citations_document
    ON document_citations(document_id, position);

-- The document list is by most recently edited.
CREATE INDEX IF NOT EXISTS idx_documents_updated_at
    ON documents(updated_at DESC);
"""


def database_path() -> Path:
    """Resolve the configured SQLite path to an absolute path.

    ``DATABASE_URL`` is a URL for forward compatibility, but only SQLite is
    supported; a relative path in it is taken relative to the project root so
    the database lands in the same place regardless of the working directory.
    """
    url = get_settings().database_url
    prefix = "sqlite:///"
    raw = url[len(prefix) :] if url.startswith(prefix) else url
    path = Path(raw)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection with the settings Noye relies on.

    * ``foreign_keys`` is off by default in SQLite, so deleting a file would
      silently orphan its chunk rows without this.
    * ``WAL`` lets the background ingestion task write while a request reads
      the file list, which is the whole point of processing in the background.
    * ``row_factory`` gives dict-like rows so the mapping code reads by name.
    """
    target = Path(path) if path is not None else database_path()
    if str(target) != ":memory:":
        target.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(target, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if str(target) != ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")
    return connection


def init_schema(connection: sqlite3.Connection) -> None:
    """Create the tables and indexes, then bring the schema up to date.

    Safe to re-run: every statement in ``SCHEMA`` is ``IF NOT EXISTS`` and every
    migration step checks the live schema before changing it.

    The order is not interchangeable. ``SCHEMA`` creates tables; migrations alter
    them. A migration that ran first would find no table to alter — which it
    raises on rather than skipping, because skipping would leave a column quietly
    missing.

    ``SCHEMA`` describes the current shape, including columns that migrations add,
    so a fresh database gets them from the ``CREATE TABLE`` and the migrations then
    find their work already done. An existing database gets them from the
    migration. Both end in the same place.
    """
    with connection:
        connection.executescript(SCHEMA)
    apply_migrations(connection)


@contextmanager
def session(path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection with the schema applied, and close it afterwards."""
    connection = connect(path)
    try:
        init_schema(connection)
        yield connection
    finally:
        connection.close()
