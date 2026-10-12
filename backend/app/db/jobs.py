"""Durable ingestion attempts; history contains identifiers/progress, never text."""

import sqlite3
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime

JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN
        ('queued','running','cancelling','complete','failed','cancelled','interrupted')),
    stage TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    attempt INTEGER NOT NULL,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_active_file ON jobs(file_id)
    WHERE state IN ('queued','running','cancelling');
CREATE INDEX IF NOT EXISTS idx_jobs_file ON jobs(file_id);
"""
OPEN_STATES = ("queued", "running", "cancelling")


def now() -> str:
    return datetime.now(UTC).isoformat()


def latest(connection: sqlite3.Connection, file_id: str) -> dict | None:
    row = connection.execute(
        "SELECT * FROM jobs WHERE file_id=? ORDER BY rowid DESC LIMIT 1", (file_id,)
    ).fetchone()
    return dict(row) if row else None


def queue(connection: sqlite3.Connection, file_id: str, *, transaction=True) -> dict:
    record = connection.execute("SELECT name FROM files WHERE id=?", (file_id,)).fetchone()
    if record is None:
        raise ValueError("The source for this job no longer exists.")
    previous = latest(connection, file_id)
    if previous and previous["state"] in OPEN_STATES:
        raise ValueError("This file already has a queued or running job.")
    identifier, timestamp = str(uuid.uuid4()), now()
    with connection if transaction else nullcontext():
        connection.execute(
            "INSERT INTO jobs (id,file_id,file_name,state,stage,attempt,created_at,updated_at) "
            "VALUES (?,?,?,'queued','queued',?,?,?)",
            (
                identifier,
                file_id,
                record["name"],
                previous["attempt"] + 1 if previous else 1,
                timestamp,
                timestamp,
            ),
        )
    return latest(connection, file_id)


def file_stage(connection, file_id: str, stage: str, error: str | None):
    """Called INSIDE the file's transaction, so file and terminal job commit together."""
    if stage == "READY":
        connection.execute(
            "UPDATE jobs SET state='complete',stage='complete',completed=total,error=NULL,"
            "updated_at=? WHERE file_id=? AND state IN ('queued','running','cancelling')",
            (now(), file_id),
        )
    elif stage == "FAILED":
        connection.execute(
            "UPDATE jobs SET state=CASE WHEN cancel_requested=1 OR ?='Processing was cancelled.' "
            "THEN 'cancelled' ELSE 'failed' END,"
            "stage='failed',error=?,updated_at=? "
            "WHERE file_id=? AND state IN ('queued','running','cancelling')",
            (error, error, now(), file_id),
        )
    elif stage != "UPLOADING":
        connection.execute(
            "UPDATE jobs SET state=CASE WHEN cancel_requested=1 "
            "THEN 'cancelling' ELSE 'running' END,"
            "stage=?,updated_at=? WHERE file_id=? AND state IN ('queued','running','cancelling')",
            (stage.lower(), now(), file_id),
        )


def progress(connection, file_id: str, completed: int, total: int, stage="embedding"):
    with connection:
        connection.execute(
            "UPDATE jobs SET completed=?,total=?,stage=?,updated_at=? "
            "WHERE file_id=? AND state IN ('queued','running','cancelling')",
            (completed, total, stage, now(), file_id),
        )


def request_cancel(connection, file_id: str):
    with connection:
        connection.execute(
            "UPDATE jobs SET cancel_requested=1,state='cancelling',updated_at=? "
            "WHERE file_id=? AND state IN ('queued','running','cancelling')",
            (now(), file_id),
        )


def get(connection, job_id: str) -> dict:
    row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise LookupError("This job no longer exists.")
    return dict(row)


def list_latest(connection, limit=100) -> list[dict]:
    return [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM jobs WHERE rowid IN (SELECT MAX(rowid) FROM jobs GROUP BY file_id) "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
    ]


def recover_interrupted(connection, reason="Processing was interrupted when Noye stopped. Retry."):
    """No network, model call or automatic retry. Old vectors stay excluded until re-ingestion."""
    active = connection.execute(
        "SELECT id,status FROM files WHERE status IN "
        "('UPLOADING','EXTRACTING','CHUNKING','EMBEDDING') OR id IN "
        "(SELECT file_id FROM jobs WHERE state IN ('queued','running','cancelling'))"
    ).fetchall()
    for row in active:
        job = latest(connection, row["id"])
        if job is None or job["state"] not in OPEN_STATES:
            queue(connection, row["id"])
    with connection:
        for row in active:
            connection.execute(
                "UPDATE jobs SET state='interrupted',error=?,updated_at=? "
                "WHERE file_id=? AND state IN ('queued','running','cancelling')",
                (reason, now(), row["id"]),
            )
            connection.execute("DELETE FROM chunks WHERE file_id=?", (row["id"],))
            connection.execute(
                "UPDATE files SET status='FAILED',error=?,chunk_count=0,embedding_model=NULL,"
                "index_fingerprint=NULL,index_metadata=NULL,updated_at=? WHERE id=?",
                (reason, now(), row["id"]),
            )
    return len(active)
