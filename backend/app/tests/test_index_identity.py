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


@pytest.mark.parametrize("name", ["embeddinggemma", "embeddinggemma:latest"])
def test_resolves_installed_digest_for_default_tag(name):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json={"models": [{"name": name, "digest": "a" * 64}]}
    ))) as client:
        assert resolve_model_digest(client=client) == "a" * 64


@pytest.mark.parametrize("body", [None, {}, {"models": {}}, {"models": [None]},
    {"models": [{"name": "embeddinggemma:latest"}]},
    {"models": [{"name": "embeddinggemma", "digest": ""}]}])
def test_invalid_identity_is_not_guessed(body):
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=body)
    )) as client, pytest.raises(EmbeddingError):
        resolve_model_digest(client=client)


def test_missing_model_is_distinguished_from_unreachable_service():
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"models": []})
    )) as client, pytest.raises(EmbeddingError, match="not installed"):
        resolve_model_digest(client=client)


def test_transport_errors_do_not_expose_response_bodies():
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(500, text="private server detail")
    )) as client, pytest.raises(EmbeddingError) as error:
        resolve_model_digest(client=client)
    assert "private server detail" not in str(error.value)


def test_same_tag_with_different_digest_changes_fingerprint():
    assert build_identity("a" * 64).fingerprint != build_identity("b" * 64).fingerprint


@pytest.mark.parametrize("field,value", [("chunk_size", 1200), ("chunk_overlap", 100),
    ("qdrant_vector_size", 1024), ("ollama_embedding_model", "another-model")])
def test_processing_settings_change_fingerprint(monkeypatch, field, value):
    before = build_identity("a" * 64)
    monkeypatch.setattr(get_settings(), field, value)
    assert build_identity("a" * 64).fingerprint != before.fingerprint


@pytest.mark.parametrize("module,field", [(index_identity, "CHUNKER_VERSION"),
    (index_identity, "EXTRACTOR_VERSION")])
def test_algorithm_versions_change_fingerprint(monkeypatch, module, field):
    before = build_identity("a" * 64)
    monkeypatch.setattr(module, field, "v2")
    assert build_identity("a" * 64).fingerprint != before.fingerprint


def test_embedding_format_is_versioned(monkeypatch):
    from app.services import embeddings
    before = build_identity("a" * 64)
    monkeypatch.setattr(embeddings, "INPUT_FORMAT_VERSION", "task-prefix-v2")
    assert build_identity("a" * 64).fingerprint != before.fingerprint


def test_generation_model_does_not_invalidate_index(monkeypatch):
    before = build_identity("a" * 64)
    monkeypatch.setattr(get_settings(), "ollama_model", "another-generation-model")
    assert build_identity("a" * 64) == before


def test_invalid_chunk_window_is_rejected():
    with pytest.raises(ValueError, match="CHUNK_OVERLAP"):
        Settings(_env_file=None, chunk_size=100, chunk_overlap=100)


