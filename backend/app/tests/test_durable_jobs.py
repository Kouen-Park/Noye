"""Real SQLite/restart boundaries with synthetic originals and local transports."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import httpx
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.api import files as files_api
from app.api.deps import get_db
from app.config import get_settings
from app.db import files, jobs
from app.db.database import connect, init_schema
from app.main import app
from app.models.files import FileStatus, FileType
from app.services import ingestion, model_usage
from app.services.indexing import count_chunks


@pytest.fixture
def workspace(tmp_path):
    path = tmp_path / "app.db"
    db = connect(path)
    init_schema(db)
    original = tmp_path / "original.txt"
    original.write_text(" ".join(f"Sentence {i} has enough original detail." for i in range(800)))
    record = files.create_file(
        db,
        name="original.txt",
        file_type=FileType.TEXT,
        path=str(original),
        size=original.stat().st_size,
    )
    yield path, db, record
    ingestion.release_file(record.id)
    db.close()


@pytest.mark.parametrize("stage", ["queued", "embedding", "indexing"])
def test_restart_retains_attempt_and_progress_and_excludes_partial_files(workspace, stage):
    path, db, record = workspace
    job = jobs.queue(db, record.id)
    jobs.progress(db, record.id, 16, 40, stage)
    files.set_status(db, record.id, FileStatus.EMBEDDING)
    db.close()
    restored = connect(path)
    init_schema(restored)
    assert jobs.recover_interrupted(restored) == 1
    interrupted = jobs.get(restored, job["id"])
    assert interrupted["state"] == "interrupted"
    assert (interrupted["completed"], interrupted["total"]) == (16, 40)
    assert files.get_file(restored, record.id).status is FileStatus.FAILED
    assert files.get_file(restored, record.id).index_fingerprint is None
    assert jobs.recover_interrupted(restored) == 0
    restored.close()


def test_legacy_processing_row_gets_a_recoverable_attempt(workspace):
    _, db, record = workspace
    assert jobs.recover_interrupted(db) == 1
    assert jobs.latest(db, record.id)["attempt"] == 1
    assert jobs.latest(db, record.id)["state"] == "interrupted"


def test_only_one_active_attempt_and_retry_keeps_history(workspace):
    _, db, record = workspace
    first = jobs.queue(db, record.id)
    with pytest.raises(ValueError):
        jobs.queue(db, record.id)
    jobs.recover_interrupted(db)
    second = jobs.queue(db, record.id)
    assert first["id"] != second["id"]
    assert second["attempt"] == 2
    assert jobs.get(db, first["id"])["state"] == "interrupted"
    assert len(jobs.list_latest(db)) == 1


def test_cancel_before_second_embedding_batch_keeps_committed_progress(workspace):
    _, db, record = workspace
    calls = []
    width = get_settings().qdrant_vector_size

    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        assert ingestion.cancel_ingestion(record.id, db)
        return httpx.Response(200, json={"embeddings": [[0.1] * width for _ in body["input"]]})

    with (
        closing(QdrantClient(":memory:")) as qdrant,
        httpx.Client(transport=httpx.MockTransport(handle)) as client,
    ):
        result = ingestion.ingest_file(db, record.id, qdrant_client=qdrant, http_client=client)
        assert result.status is FileStatus.FAILED
        assert count_chunks(file_id=record.id, client=qdrant) == 0
    job = jobs.latest(db, record.id)
    assert len(calls) == 1
    assert job["state"] == "cancelled"
    assert job["completed"] == 16 < job["total"]
    assert files.list_chunks(db, record.id) == []


def test_repeated_retry_replaces_vectors_without_duplicates(workspace):
    _, db, record = workspace
    width = get_settings().qdrant_vector_size

    def handle(request):
        inputs = json.loads(request.content)["input"]
        return httpx.Response(200, json={"embeddings": [[0.1] * width for _ in inputs]})

    with (
        closing(QdrantClient(":memory:")) as qdrant,
        httpx.Client(transport=httpx.MockTransport(handle)) as client,
    ):
        for attempt in range(1, 4):
            result = ingestion.ingest_file(db, record.id, qdrant_client=qdrant, http_client=client)
            assert result.status is FileStatus.READY
            assert count_chunks(file_id=record.id, client=qdrant) == result.chunk_count
            job = jobs.latest(db, record.id)
            assert job["attempt"] == attempt
            assert job["state"] == "complete"
            assert job["completed"] == job["total"] == result.chunk_count


def test_queued_job_can_cancel_without_entering_busy_pipeline(workspace, monkeypatch):
    _, db, record = workspace
    ingestion.reserve_ingestion(record.id)
    jobs.queue(db, record.id)
    ingestion.cancel_ingestion(record.id, db)
    ingestion._pipeline_slot.acquire()
    monkeypatch.setattr(ingestion, "delete_file_chunks", lambda *a, **kw: None)
    try:
        result = ingestion.ingest_file(db, record.id, reserved=True)
        assert result.error == "Processing was cancelled."
        assert jobs.latest(db, record.id)["state"] == "cancelled"
    finally:
        ingestion._pipeline_slot.release()


def test_job_api_retry_is_explicit_and_old_attempt_is_rejected(workspace, monkeypatch):
    _, db, record = workspace
    jobs.recover_interrupted(db)
    job = jobs.latest(db, record.id)
    scheduled = []
    monkeypatch.setattr(files_api, "_ingest_in_background", scheduled.append)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        assert client.get("/jobs").json()[0]["state"] == "interrupted"
        assert not scheduled
        retry = client.post("/jobs/" + job["id"] + "/resume")
        assert retry.status_code == 202
        assert retry.json()["attempt"] == 2
        assert scheduled == [record.id]
        assert client.post("/jobs/" + job["id"] + "/resume").status_code == 409
        cancelled = client.post("/jobs/" + retry.json()["id"] + "/cancel")
        assert cancelled.status_code == 202
        assert cancelled.json()["cancel_requested"] == 1
        assert client.post("/jobs/missing/resume").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_inference_gate_serializes_different_models_and_releases_errors():
    entered = threading.Event()
    release = threading.Event()
    second = threading.Event()

    def first():
        with model_usage.inference("first"):
            entered.set()
            release.wait(2)

    def next_model():
        with model_usage.inference("second"):
            second.set()

    with ThreadPoolExecutor(2) as pool:
        pending = pool.submit(first)
        assert entered.wait(1)
        other = pool.submit(next_model)
        assert not second.wait(0.05)
        release.set()
        pending.result(timeout=2)
        other.result(timeout=2)
    assert second.is_set()
    with pytest.raises(ValueError), model_usage.inference("second"):
        raise ValueError()
    assert not model_usage.active


def test_inference_wait_is_bounded_and_does_not_leak_usage(monkeypatch):
    monkeypatch.setattr(model_usage, "WAIT_SECONDS", 0.01)
    model_usage.slots.acquire()
    try:
        with pytest.raises(model_usage.ModelBusyError), model_usage.inference("waiting"):
            pass
        assert not model_usage.active
    finally:
        model_usage.slots.release()
