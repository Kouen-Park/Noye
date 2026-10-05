"""Feature-owned additive schema. A registers this with the shared migration runner.

SQLite revisions are authoritative authored data, not a rebuildable index. No
foreign key to files: deleted originals must leave their historical provenance.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki_pages (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('source','concept','project','analysis')),
    identity TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    current_revision TEXT,
    published_hash TEXT,
    publication_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wiki_revisions (
    id TEXT PRIMARY KEY,
    wiki_id TEXT NOT NULL REFERENCES wiki_pages(id),
    parent_id TEXT,
    origin TEXT NOT NULL CHECK(origin IN ('generated','user','proposal')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wiki_revisions_page ON wiki_revisions(wiki_id);
CREATE TABLE IF NOT EXISTS wiki_evidence (
    revision_id TEXT NOT NULL REFERENCES wiki_revisions(id),
    evidence_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version TEXT NOT NULL,
    snapshot TEXT NOT NULL,
    PRIMARY KEY(revision_id,evidence_id)
);
CREATE INDEX IF NOT EXISTS idx_wiki_evidence_source ON wiki_evidence(source_id);
CREATE TABLE IF NOT EXISTS wiki_relations (
    id TEXT PRIMARY KEY,
    origin_id TEXT NOT NULL REFERENCES wiki_pages(id),
    target_id TEXT NOT NULL REFERENCES wiki_pages(id),
    revision_id TEXT NOT NULL REFERENCES wiki_revisions(id),
    kind TEXT NOT NULL,
    reason TEXT NOT NULL,
    origin_evidence_id TEXT NOT NULL,
    target_evidence_id TEXT NOT NULL,
    target_revision TEXT NOT NULL REFERENCES wiki_revisions(id),
    UNIQUE(revision_id,target_id,kind),
    CHECK(origin_id <> target_id)
);
CREATE INDEX IF NOT EXISTS idx_wiki_relations_back ON wiki_relations(target_id);
CREATE TABLE IF NOT EXISTS wiki_index (
    wiki_id TEXT PRIMARY KEY REFERENCES wiki_pages(id),
    revision_id TEXT NOT NULL REFERENCES wiki_revisions(id),
    fingerprint TEXT NOT NULL,
    text TEXT NOT NULL,
    tags TEXT NOT NULL
);
"""


def install(connection):
    # No executescript: preserve the shared migration transaction.
    for statement in SCHEMA.split(";"):
        if statement.strip():
            connection.execute(statement)


def now():
    return datetime.now(UTC).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def page(connection, identifier):
    row = connection.execute("SELECT * FROM wiki_pages WHERE id=?", (identifier,)).fetchone()
    if row is None:
        raise LookupError("This Wiki page does not exist.")
    return dict(row)


def find(connection, identity):
    row = connection.execute("SELECT * FROM wiki_pages WHERE identity=?", (identity,)).fetchone()
    return dict(row) if row else None


def ensure_page(connection, kind, identity, title):
    # Namespace identity is application-defined, never model-selected IDs.
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, f"noye:wiki:v1:{identity}"))
    timestamp = now()
    with connection:
        connection.execute(
            "INSERT OR IGNORE INTO wiki_pages "
            "(id,kind,identity,title,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            (identifier, kind, identity, title, timestamp, timestamp),
        )
    return find(connection, identity)


def revision(connection, identifier):
    row = connection.execute("SELECT * FROM wiki_revisions WHERE id=?", (identifier,)).fetchone()
    if row is None:
        raise LookupError("This Wiki revision does not exist.")
    result = dict(row)
    result["metadata"] = json.loads(result["metadata"])
    result["evidence"] = [json.loads(row[0]) for row in connection.execute(
        "SELECT snapshot FROM wiki_evidence WHERE revision_id=? ORDER BY evidence_id",
        (identifier,),
    )]
    return result


def write_revision(connection, identifier, *, title, content, metadata, evidence,
                   expected, origin="generated", relations=()):
    """Compare-and-publish in one transaction; concurrent/user edits become proposals."""
    revision_id = str(uuid.uuid4())
    timestamp = now()
    connection.execute("BEGIN IMMEDIATE")
    try:
        current = page(connection, identifier)
        prior = (revision(connection, current["current_revision"])
                 if current["current_revision"] else None)
        conflict = current["current_revision"] != expected
        if origin == "user" and conflict:
            raise ValueError("This page changed. Reload before saving your edit.")
        if origin == "generated" and (conflict or (prior and prior["origin"] == "user")):
            origin = "proposal"
        connection.execute(
            "INSERT INTO wiki_revisions VALUES (?,?,?,?,?,?,?,?)",
            (revision_id, identifier, current["current_revision"], origin,
             title, content, encode(metadata), timestamp),
        )
        for item in evidence:
            connection.execute("INSERT INTO wiki_evidence VALUES (?,?,?,?,?)", (
                revision_id, item["id"], item["source"]["source_id"],
                item["source"]["source_version"], encode(item),
            ))
        for relation in relations:
            connection.execute("INSERT INTO wiki_relations VALUES (?,?,?,?,?,?,?,?,?)", (
                str(uuid.uuid4()), identifier, relation["target_id"], revision_id,
                relation["kind"], relation["reason"], relation["origin_evidence_id"],
                relation["target_evidence_id"], relation["target_revision"],
            ))
        if origin != "proposal":
            connection.execute(
                "UPDATE wiki_pages SET title=?,current_revision=?,updated_at=?,"
                "publication_error=NULL "
                "WHERE id=?", (title, revision_id, timestamp, identifier),
            )
            reindex(connection, identifier, revision_id, title, content, metadata)
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return revision(connection, revision_id)


def reindex(connection, identifier, revision_id, title, content, metadata):
    # Independent of source-vector identity, including revision and schema/input format.
    fingerprint = digest(encode({"format": "wiki-lexical-v1", "revision": revision_id,
                                 "content_hash": digest(content)}))
    connection.execute("INSERT OR REPLACE INTO wiki_index VALUES (?,?,?,?,?)", (
        identifier, revision_id, fingerprint, title + "\n" + content,
        encode(metadata.get("tags", [])),
    ))


def list_pages(connection, limit=200):
    return [dict(row) for row in connection.execute(
        "SELECT p.*,r.origin,r.metadata FROM wiki_pages p "
        "LEFT JOIN wiki_revisions r ON r.id=p.current_revision ORDER BY p.updated_at DESC LIMIT ?",
        (limit,),
    )]


def revisions(connection, identifier):
    return [dict(row) for row in connection.execute(
        "SELECT id,parent_id,origin,title,created_at FROM wiki_revisions "
        "WHERE wiki_id=? ORDER BY rowid DESC", (identifier,),
    )]


def relations(connection, identifier):
    # Only published revisions, including backlinks. Proposals cannot change the live graph.
    return [dict(row) for row in connection.execute(
        "SELECT r.*,p.title AS target_title,o.title AS origin_title FROM wiki_relations r "
        "JOIN wiki_pages o ON o.id=r.origin_id JOIN wiki_pages p ON p.id=r.target_id "
        "WHERE r.revision_id=o.current_revision AND (origin_id=? OR target_id=?) LIMIT 60",
        (identifier, identifier),
    )]
