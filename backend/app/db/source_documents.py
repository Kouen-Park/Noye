"""Authored revisions and restartable requests, backed up with the whole SQLite DB.

No source/conversation foreign keys: historical evidence outlives their deletion.
The edit trigger also protects edits made through the existing document API.
"""

import json
import uuid

from app.db.wiki import now

STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS source_document_requests (
        id TEXT PRIMARY KEY, request_json TEXT NOT NULL, manifest_json TEXT NOT NULL,
        plan_json TEXT, report_json TEXT NOT NULL DEFAULT '{}',
        cache_json TEXT NOT NULL DEFAULT '{}',
        artifact_id TEXT, clarification TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS source_document_revisions (
        id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        parent_id TEXT, origin TEXT NOT NULL CHECK(origin IN ('generated','user')),
        title TEXT NOT NULL, content TEXT NOT NULL, metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS source_document_heads (
        document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
        revision_id TEXT NOT NULL REFERENCES source_document_revisions(id)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_source_document_revisions
        ON source_document_revisions(document_id,created_at)""",
    """CREATE TRIGGER IF NOT EXISTS preserve_source_document_edits
        AFTER UPDATE OF title,content ON documents
        WHEN (OLD.content <> NEW.content OR OLD.title <> NEW.title)
        AND EXISTS(SELECT 1 FROM source_document_heads WHERE document_id=NEW.id)
        BEGIN
          INSERT INTO source_document_revisions
            (id,document_id,parent_id,origin,title,content,metadata_json,created_at)
          SELECT lower(hex(randomblob(16))),NEW.id,r.id,'user',NEW.title,NEW.content,
            r.metadata_json,NEW.updated_at FROM source_document_revisions r
            JOIN source_document_heads h ON h.revision_id=r.id WHERE h.document_id=NEW.id;
          UPDATE source_document_heads SET revision_id=(
            SELECT id FROM source_document_revisions WHERE document_id=NEW.id
            ORDER BY rowid DESC LIMIT 1) WHERE document_id=NEW.id;
        END""",
]


APPROVED_TRIGGERS = {"preserve_source_document_edits": STATEMENTS[-1]}


def install(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def request(connection, identifier):
    row = connection.execute(
        "SELECT * FROM source_document_requests WHERE id=?", (identifier,)
    ).fetchone()
    if row is None:
        raise LookupError("This document request does not exist.")
    value = dict(row)
    for field in ("request", "manifest", "plan", "report", "cache"):
        raw = value.pop(field + "_json")
        value[field] = json.loads(raw) if raw is not None else None
    return value


def save_request(connection, identifier, **fields):
    allowed = {"plan", "report", "cache", "artifact_id", "clarification"}
    if not fields or not fields.keys() <= allowed:
        raise ValueError("Invalid document checkpoint fields.")
    assignments, values = [], []
    for field, value in fields.items():
        column = field + "_json" if field in {"plan", "report", "cache"} else field
        assignments.append(column + "=?")
        values.append(encode(value) if column.endswith("_json") else value)
    with connection:
        connection.execute(
            "UPDATE source_document_requests SET "
            + ",".join(assignments)
            + ",updated_at=? WHERE id=?",
            (*values, now(), identifier),
        )


def current(connection, document_id):
    row = connection.execute(
        "SELECT r.* FROM source_document_revisions r JOIN "
        "source_document_heads h ON h.revision_id=r.id "
        "WHERE h.document_id=?",
        (document_id,),
    ).fetchone()
    return decode(row) if row else None


def decode(row):
    value = dict(row)
    value["metadata"] = json.loads(value.pop("metadata_json"))
    return value


def revision(connection, document_id, revision_id):
    row = connection.execute(
        "SELECT * FROM source_document_revisions WHERE document_id=? AND id=?",
        (document_id, revision_id),
    ).fetchone()
    if row is None:
        raise LookupError("This document revision does not exist.")
    return decode(row)


def revisions(connection, document_id):
    return [
        dict(row)
        for row in connection.execute(
            "SELECT id,origin,title,created_at FROM source_document_revisions "
            "WHERE document_id=? ORDER BY rowid DESC",
            (document_id,),
        )
    ]


def edit(connection, document_id, expected, title, content):
    connection.execute("BEGIN IMMEDIATE")
    try:
        head = current(connection, document_id)
        if head is None:
            raise LookupError("This source-driven document does not exist.")
        if head["id"] != expected:
            raise ValueError("The document changed. Your draft was kept; reload before saving.")
        if not title.strip():
            raise ValueError("Give the document a title.")
        connection.execute(
            "UPDATE documents SET title=?,content=?,updated_at=? WHERE id=?",
            (title.strip(), content, now(), document_id),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return current(connection, document_id)


def publish(connection, request_id, title, content, metadata, citations):
    """One transaction, one artifact per request, never regenerate existing user work."""
    from app.db.documents import _write_citations

    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, f"noye:source-document:{request_id}"))
    revision_id, timestamp = str(uuid.uuid4()), now()
    connection.execute("BEGIN IMMEDIATE")
    try:
        req = request(connection, request_id)
        if req["artifact_id"]:
            connection.rollback()
            return req["artifact_id"]
        connection.execute(
            "INSERT INTO documents(id,title,content,source_conversation_id,source_instruction,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (
                identifier,
                title,
                content,
                req["request"]["conversation_id"],
                req["request"]["instruction"],
                timestamp,
                timestamp,
            ),
        )
        _write_citations(connection, identifier, citations)
        connection.execute(
            "INSERT INTO source_document_revisions VALUES(?,?,NULL,'generated',?,?,?,?)",
            (revision_id, identifier, title, content, encode(metadata), timestamp),
        )
        connection.execute(
            "INSERT INTO source_document_heads VALUES(?,?)", (identifier, revision_id)
        )
        connection.execute(
            "UPDATE source_document_requests SET artifact_id=?,updated_at=? WHERE id=?",
            (identifier, timestamp, request_id),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return identifier
