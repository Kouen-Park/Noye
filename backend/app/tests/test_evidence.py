"""Evidence must outlive changes to the live source, index and conversation."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.api import chat, documents, files
from app.db import conversations as conversations_db
from app.db import documents as documents_db
from app.db import files as files_db
from app.db.database import connect, init_schema
from app.main import app
from app.models.conversations import MessageCitation, Role
from app.models.files import FileStatus, FileType
from app.services import index_identity, ingestion
from app.services.chunking import Chunk
from app.services.evidence import capture_citations
from app.services.generation import Answer
from app.services.indexing import index_chunks
from app.services.retrieval import SearchResult, _to_result


def hit(file_id="f1", **kwargs):
    return SearchResult(
        content="  Lumen shipped 742 units; failure rate was 0.8%.\n한국어 사례.  ",
        file_id=file_id, page_number=None, chunk_index=2, score=0.9,
        source_hash="a" * 64, index_fingerprint="b" * 64,
        index_metadata='{"input_format":"raw-v1"}', **kwargs,
    )


def test_snapshot_retains_exact_text_ranking_and_point_identity():
    excerpts = [hit("f2"), hit("f1")]
    citations = capture_citations(excerpts, {"f1": "One.md", "f2": "Two.md"})
    assert [c.file_name for c in citations] == ["One.md", "Two.md"]
    snapshot = citations[1].evidence
    assert snapshot.excerpts[0].content == excerpts[0].content
    assert snapshot.excerpts[0].retrieval_rank == 1
    assert snapshot.excerpts[0].source_hash == "a" * 64
    assert snapshot.excerpts[0].index_metadata == excerpts[0].index_metadata


def test_evidence_survives_reindex_delete_reload_and_user_edits(tmp_path):
    path = tmp_path / "workspace.db"
    db = connect(path)
    init_schema(db)
    original = tmp_path / "One.md"
    original.write_text("original", encoding="utf-8")
    record = files_db.create_file(
        db, name="One.md", file_type=FileType.MARKDOWN, path=str(original), size=8
    )
    citations = capture_citations([hit(record.id)], {record.id: record.name})
    conversation = conversations_db.create_conversation(db, first_question="Units?")
    message = conversations_db.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="A short answer", citations=citations
    )
    doc = documents_db.create_document(
        db, content="# First draft", citations=message.citations, source_message_id=message.id
    )
    original.write_text("replaced source", encoding="utf-8")
    files_db.set_content_hash(db, record.id, "c" * 64)
    files_db.set_index_identity(db, record.id, "d" * 64, "replacement")
    files_db.delete_file(db, record.id)
    original.unlink()
    assert conversations_db.get_message(db, message.id).citations == citations
    conversations_db.delete_conversation(db, conversation.id)
    documents_db.update_document(db, doc.id, content="# My edited text")
    db.close()
    with connect(path) as reloaded:
        saved = documents_db.get_document(reloaded, doc.id)
        assert saved.citations == citations
        assert saved.content == "# My edited text"


def test_additive_upgrade_preserves_legacy_citations_without_invented_excerpts(tmp_path):
    db = connect(tmp_path / "legacy.db")
    init_schema(db)
    citation = MessageCitation("f1", "legacy.pdf", 3, (2,), 0.7)
    conversation = conversations_db.create_conversation(db)
    message = conversations_db.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="old", citations=[citation]
    )
    doc = documents_db.create_document(db, content="user's writing", citations=[citation])
    db.execute("ALTER TABLE message_citations DROP COLUMN evidence_json")
    db.execute("ALTER TABLE document_citations DROP COLUMN evidence_json")
    db.execute("PRAGMA user_version = 2")
    db.commit()
    init_schema(db)
    init_schema(db)
    assert conversations_db.get_message(db, message.id).citations == [citation]
    assert documents_db.get_document(db, doc.id).citations[0].evidence is None
    assert documents_db.get_document(db, doc.id).content == "user's writing"
    db.close()


def test_qdrant_results_carry_the_revision_that_was_actually_indexed():
    client = QdrantClient(":memory:")
    chunk = Chunk(file_id="f1", page_number=None, chunk_index=2, content="742 units")
    identity = index_identity.current_index_identity()
    index_chunks(
        [chunk], [[1.0] + [0.0] * 767], client=client, source_hash="a" * 64,
        index_fingerprint=identity.fingerprint, index_metadata=identity.metadata_json,
    )
    point = client.query_points(
        "noye", query=[1.0] + [0.0] * 767, with_payload=True
    ).points[0]
    result = _to_result(point)
    assert result.source_hash == "a" * 64
    assert result.index_fingerprint == identity.fingerprint
    assert result.index_metadata == identity.metadata_json
    client.close()


def test_source_status_detects_edits_missing_files_and_unsafe_paths(tmp_path, monkeypatch):
    db = connect(tmp_path / "status.db")
    init_schema(db)
    monkeypatch.setattr(files, "sources_dir", lambda: tmp_path)
    original = tmp_path / "source.md"
    original.write_text("first")
    record = files_db.create_file(
        db, name="source.md", file_type=FileType.MARKDOWN, path=str(original), size=5
    )
    app.dependency_overrides[files.get_db] = lambda: db
    try:
        with TestClient(app) as client:
            url = f"/files/{record.id}/source-status"
            first = client.get(url).json()
            assert first == {
                "status": "available", "current_hash": hashlib.sha256(b"first").hexdigest()
            }
            original.write_text("second")
            assert client.get(url).json()["current_hash"] != first["current_hash"]
            original.unlink()
            assert client.get(url).json()["status"] == "missing"
            db.execute("UPDATE files SET path = ? WHERE id = ?", ("/etc/hosts", record.id))
            db.commit()
            assert client.get(url).json()["status"] == "unavailable"
            assert client.get("/files/deleted/source-status").json()["status"] == "missing"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_ingestion_stamps_the_extracted_source_version_on_real_points(tmp_path, monkeypatch):
    db = connect(tmp_path / "ingested.db")
    init_schema(db)
    original = tmp_path / "source.md"
    original.write_text("Lumen shipped 742 units. 한국어 원문.", encoding="utf-8")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    record = files_db.create_file(
        db, name="source.md", file_type=FileType.MARKDOWN,
        path=str(original), size=original.stat().st_size,
    )
    monkeypatch.setattr(ingestion, "embed_chunks", lambda chunks, **kwargs: [
        [1.0] + [0.0] * 767 for chunk in chunks
    ])
    client = QdrantClient(":memory:")
    processed = ingestion.ingest_file(db, record.id, qdrant_client=client)
    assert processed.status is FileStatus.READY
    points, _ = client.scroll("noye", with_payload=True)
    assert points[0].payload["source_hash"] == digest
    assert points[0].payload["index_metadata"] == processed.index_metadata
    assert points[0].payload["content"] == original.read_text(encoding="utf-8")
    client.close()
    db.close()


def test_chat_captures_returned_context_and_documents_copy_it(tmp_path, monkeypatch):
    db = connect(tmp_path / "flow.db")
    init_schema(db)
    record = files_db.create_file(
        db, name="One.md", file_type=FileType.MARKDOWN, path=str(tmp_path / "one"), size=8
    )
    files_db.set_status(db, record.id, FileStatus.READY)
    identity = index_identity.current_index_identity()
    files_db.set_index_identity(db, record.id, identity.fingerprint, identity.metadata_json)
    monkeypatch.setattr(chat, "answer_question", lambda *args, **kwargs: Answer(
        text="A brief answer.", sources=[hit(record.id)]
    ))
    monkeypatch.setattr(documents, "draft_document", lambda *args, **kwargs: "# Draft")
    app.dependency_overrides[chat.get_db] = lambda: db
    try:
        with TestClient(app) as client:
            answer = client.post("/chat", json={"question": "Units?"}).json()["answer"]
            evidence = answer["citations"][0]["evidence"]
            assert evidence["excerpts"][0]["content"] == hit().content
            created = client.post("/documents/generate", json={
                "message_id": answer["id"], "instruction": "notes"
            }).json()
            assert created["citations"][0]["evidence"] == evidence
            loaded = client.get(f'/documents/{created["id"]}').json()
            assert loaded["citations"][0]["evidence"] == evidence
            assert "source_hash" in json.dumps(loaded)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_changed_source_during_extraction_is_refused(tmp_path, monkeypatch):
    db = connect(tmp_path / "changed.db")
    init_schema(db)
    original = tmp_path / "source.txt"
    original.write_text("first")
    record = files_db.create_file(
        db, name="source.txt", file_type=FileType.TEXT, path=str(original), size=5
    )
    extract = ingestion.extract_file

    def changing(path, file_type):
        pages = extract(path, file_type)
        original.write_text("changed during extraction")
        return pages

    monkeypatch.setattr(ingestion, "extract_file", changing)
    with pytest.raises(ingestion.IngestionError, match="changed during extraction"):
        ingestion._extract(db, record)
    assert files_db.get_file(db, record.id).content_hash is None
    db.close()
