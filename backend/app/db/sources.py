"""Additive folder metadata; external originals are never owned by file deletion."""

SOURCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_roots (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK(kind IN ('managed','connected')),
    device INTEGER NOT NULL, inode INTEGER NOT NULL,
    connected INTEGER NOT NULL DEFAULT 1, processing INTEGER NOT NULL DEFAULT 1,
    organization_prefix TEXT, availability TEXT NOT NULL DEFAULT 'available',
    error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    file_id TEXT PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    root_id TEXT NOT NULL REFERENCES source_roots(id), relative_path TEXT NOT NULL,
    device INTEGER NOT NULL, inode INTEGER NOT NULL, size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL, version TEXT NOT NULL, availability TEXT NOT NULL,
    manual_category TEXT, error TEXT, UNIQUE(root_id, relative_path)
);
CREATE TABLE IF NOT EXISTS source_versions (
    file_id TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    version TEXT NOT NULL, snapshot_path TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(file_id, version)
);
CREATE TABLE IF NOT EXISTS source_passages (
    file_id TEXT NOT NULL, version TEXT NOT NULL, chunk_index INTEGER NOT NULL,
    page_number INTEGER, content TEXT NOT NULL,
    PRIMARY KEY(file_id, version, chunk_index),
    FOREIGN KEY(file_id,version) REFERENCES source_versions(file_id,version)
);
CREATE TABLE IF NOT EXISTS source_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
    source_id TEXT, root_id TEXT, relative_path TEXT, version TEXT,
    error TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS filing_journal (
    id TEXT PRIMARY KEY, source_id TEXT NOT NULL, root_id TEXT NOT NULL,
    old_path TEXT NOT NULL, new_path TEXT NOT NULL, version TEXT NOT NULL,
    device INTEGER NOT NULL, inode INTEGER NOT NULL, manual INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_jobs (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, subject_id TEXT NOT NULL,
    dedupe_key TEXT NOT NULL, payload_json TEXT NOT NULL, scope_json TEXT NOT NULL,
    manifest_json TEXT NOT NULL, state TEXT NOT NULL, stage TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
    attempt INTEGER NOT NULL DEFAULT 1, cancel_requested INTEGER NOT NULL DEFAULT 0,
    artifact_id TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_jobs_active ON knowledge_jobs(dedupe_key)
    WHERE state IN ('queued','running','cancelling');
"""

FOLDER_ISSUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS folder_issues (
    root_id TEXT NOT NULL REFERENCES source_roots(id),
    kind TEXT NOT NULL CHECK(kind IN ('intake','recovery')),
    relative_path TEXT NOT NULL, message TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY(root_id,kind,relative_path)
);
"""


def issues(connection, root_id, kind):
    return [
        dict(row)
        for row in connection.execute(
            "SELECT relative_path,message FROM folder_issues WHERE root_id=? AND kind=? "
            "ORDER BY relative_path",
            (root_id, kind),
        )
    ]


def record_issue(connection, root_id, kind, relative_path, message):
    from app.db.jobs import now

    with connection:
        connection.execute(
            "INSERT INTO folder_issues VALUES (?,?,?,?,?) "
            "ON CONFLICT(root_id,kind,relative_path) DO UPDATE SET "
            "message=excluded.message,updated_at=excluded.updated_at",
            (root_id, kind, relative_path, message, now()),
        )


def clear_issue(connection, root_id, kind, relative_path=None):
    with connection:
        connection.execute(
            "DELETE FROM folder_issues WHERE root_id=? AND kind=? "
            "AND (? IS NULL OR relative_path=?)",
            (root_id, kind, relative_path, relative_path),
        )
