"""Additive query snapshots and durable stage history; authored evidence survives rebuild."""

import json

SCHEMA = """
CREATE TABLE IF NOT EXISTS message_knowledge (
    message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    snapshot_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_job_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES knowledge_jobs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL, state TEXT NOT NULL, completed INTEGER NOT NULL,
    total INTEGER NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_events_job ON knowledge_job_events(job_id,sequence);
"""


def install(connection):
    for statement in SCHEMA.split(";"):
        if statement.strip():
            connection.execute(statement)


def save(connection, message_id, snapshot):
    with connection:
        connection.execute(
            "INSERT INTO message_knowledge VALUES (?,?)",
            (message_id, json.dumps(snapshot, ensure_ascii=False)),
        )


def read(connection, message_id):
    row = connection.execute(
        "SELECT snapshot_json FROM message_knowledge WHERE message_id=?", (message_id,)
    ).fetchone()
    if not row:
        return None
    result = json.loads(row[0])
    for page in result.get("wiki_pages", []):
        current = connection.execute(
            "SELECT current_revision FROM wiki_pages WHERE id=?", (page["wiki_id"],)
        ).fetchone()
        page["revision_status"] = (
            "missing"
            if current is None
            else "unchanged"
            if current[0] == page["revision_id"]
            else "superseded"
        )
    return result
