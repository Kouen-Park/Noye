"""Real identity parsing, upgrade safety, and incompatible-space exclusion."""

import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.api.deps import get_db
from app.config import Settings, get_settings
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.db.migrations import apply_migrations
from app.main import app
from app.models.files import FileStatus, FileType
from app.services import index_identity, ingestion, integrity, retrieval
from app.services.chunking import Chunk
from app.services.embeddings import EmbeddingError
from app.services.index_identity import build_identity, resolve_model_digest
from app.services.indexing import count_chunks, index_chunks


def test_query_never_ranks_unknown_or_different_fingerprints(monkeypatch):
    client = QdrantClient(":memory:")
    vector = [1.0] + [0.0] * (get_settings().qdrant_vector_size - 1)
    identity = build_identity("a" * 64)
    try:
        for file_id, fingerprint in [("compatible", identity.fingerprint),
            ("different", build_identity("b" * 64).fingerprint), ("legacy", None)]:
            index_chunks([Chunk(file_id, 1, 0, file_id)], [vector], client=client,
                         index_fingerprint=fingerprint)
        monkeypatch.setattr(retrieval, "embed_text", lambda query: vector)
        assert [r.file_id for r in retrieval.search("question", client=client)] == ["compatible"]
        assert retrieval.search("question", client=client, file_ids=["different"]) == []
        assert retrieval.search("question", client=client, file_ids=[]) == []
    finally:
        client.close()


def test_changed_query_model_is_refused_before_ranking(monkeypatch):
    identities = iter([build_identity("a" * 64), build_identity("b" * 64)])
    monkeypatch.setattr(index_identity, "current_index_identity", lambda **kw: next(identities))
    monkeypatch.setattr(retrieval, "embed_text", lambda query: [1.0] * 768)
    client = QdrantClient(":memory:")
    try:
        with pytest.raises(EmbeddingError, match="changed during the query"):
            retrieval.search("question", client=client)
    finally:
        client.close()


@pytest.fixture
def db(tmp_path):
    connection = connect(tmp_path / "identity.db")
    init_schema(connection)
    yield connection
    connection.close()


def ready(db, tmp_path, identity):
    source = tmp_path / "source.txt"
    source.write_text("Synthetic source text.")
    record = file_store.create_file(db, name="source.txt", file_type=FileType.TEXT,
                                   path=str(source), size=source.stat().st_size)
    if identity:
        file_store.set_index_identity(db, record.id, identity.fingerprint, identity.metadata_json)
    return file_store.set_status(db, record.id, FileStatus.READY)


def test_legacy_identity_requires_explicit_rebuild(db, tmp_path):
    record = ready(db, tmp_path, None)
    report = integrity.check_file(record)
    assert report.problems == (integrity.Problem.INDEX_UNKNOWN,)
    assert not report.is_searchable
    assert integrity.searchable_file_ids(db) == {}


def test_changed_identity_and_unavailable_model_are_separate(db, tmp_path, monkeypatch):
    record = ready(db, tmp_path, build_identity("b" * 64))
    assert integrity.check_file(record).problems == (integrity.Problem.INDEX_CHANGED,)
    def unavailable(**kwargs):
        raise EmbeddingError("Ollama unavailable")
    monkeypatch.setattr(index_identity, "current_index_identity", unavailable)
    assert integrity.check_file(record).problems == (integrity.Problem.IDENTITY_UNAVAILABLE,)


def test_identity_unavailability_is_visible_in_search_and_saved_chat(db, tmp_path, monkeypatch):
    ready(db, tmp_path, build_identity("a" * 64))
    def unavailable(**kwargs):
        raise EmbeddingError("Ollama unavailable")
    monkeypatch.setattr(index_identity, "current_index_identity", unavailable)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            assert client.get("/search", params={"q": "question"}).status_code == 503
            body = client.post("/chat", json={"question": "question"}).json()
            assert body["answer"]["error"] == "Ollama unavailable"
            status = client.get("/index/status").json()
            assert status["problems"][0]["problems"] == ["IDENTITY_UNAVAILABLE"]
            assert status["rebuild_required"] is False
    finally:
        app.dependency_overrides.clear()


def test_missing_model_refuses_rebuild_before_reset(db, monkeypatch):
    from app.services import rebuild
    resets = []
    def unavailable(**kwargs):
        raise EmbeddingError("Embedding model is not installed")
    monkeypatch.setattr(index_identity, "current_index_identity", unavailable)
    monkeypatch.setattr(rebuild, "recreate_collection", lambda **kw: resets.append(1))
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            assert client.post("/index/rebuild").status_code == 503
        assert resets == []
    finally:
        app.dependency_overrides.clear()


def test_chat_explains_that_a_legacy_index_needs_attention(db, tmp_path):
    ready(db, tmp_path, None)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            body = client.post("/chat", json={"question": "question"}).json()
            assert "No compatible index" in body["answer"]["content"]
            assert body["searched_files"] == 0
            status = client.get("/index/status").json()
            assert status["rebuild_required"] is True
    finally:
        app.dependency_overrides.clear()


def test_upgrade_keeps_user_writing_and_marks_old_identity_unknown():
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE files (id TEXT PRIMARY KEY, content_hash TEXT, embedding_model TEXT);
        CREATE TABLE conversations (id TEXT PRIMARY KEY, title TEXT);
        CREATE TABLE messages (id TEXT PRIMARY KEY, content TEXT);
        CREATE TABLE documents (id TEXT PRIMARY KEY, content_markdown TEXT);
        INSERT INTO files VALUES ('source', 'original-sha', 'embeddinggemma');
        INSERT INTO conversations VALUES ('chat', 'Saved conversation');
        INSERT INTO messages VALUES ('message', 'Saved question and answer');
        INSERT INTO documents VALUES ('document', 'User-edited writing');
        PRAGMA user_version = 1;
    """)
    apply_migrations(db)
    row = db.execute("SELECT index_fingerprint, index_metadata FROM files").fetchone()
    assert row == (None, None)
    assert db.execute("SELECT content_hash FROM files").fetchone()[0] == "original-sha"
    writing = db.execute("SELECT content_markdown FROM documents").fetchone()[0]
    assert writing == "User-edited writing"
    assert db.execute("SELECT content FROM messages").fetchone()[0] == "Saved question and answer"
    assert db.execute("SELECT title FROM conversations").fetchone()[0] == "Saved conversation"
    assert apply_migrations(db) == 0
    db.close()


def test_model_replacement_during_ingestion_cleans_partial_identity(db, tmp_path, monkeypatch):
    record = ready(db, tmp_path, None)
    identities = iter([build_identity("a" * 64), build_identity("b" * 64)])
    monkeypatch.setattr(index_identity, "current_index_identity", lambda **kw: next(identities))
    monkeypatch.setattr(ingestion, "embed_chunks", lambda chunks, **kw: [[1.0] * 768] * len(chunks))
    client = QdrantClient(":memory:")
    try:
        result = ingestion.ingest_file(db, record.id, qdrant_client=client)
        assert result.status is FileStatus.FAILED
        assert "changed during processing" in result.error
        assert result.index_fingerprint is None
        assert count_chunks(client=client) == 0
    finally:
        client.close()


def test_settings_change_during_chunking_cannot_label_chunks_with_a_new_version(
    db, tmp_path, monkeypatch
):
    record = ready(db, tmp_path, None)
    original = ingestion._chunk
    def change_settings(*args):
        chunks = original(*args)
        monkeypatch.setattr(get_settings(), "chunk_size", 1200)
        return chunks
    monkeypatch.setattr(ingestion, "_chunk", change_settings)
    client = QdrantClient(":memory:")
    try:
        result = ingestion.ingest_file(db, record.id, qdrant_client=client)
        assert result.status is FileStatus.FAILED
        assert result.index_fingerprint is None
        assert count_chunks(client=client) == 0
    finally:
        client.close()
