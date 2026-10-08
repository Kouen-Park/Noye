import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.wiki import router
from app.db import jobs as ingestion_jobs
from app.db import wiki as store
from app.models.wiki import WikiScope
from app.services import knowledge_jobs
from app.services.wiki import jobs, pipeline, relations, service
from app.services.wiki.local import WikiError
from app.tests.test_folder_foundation import discover, folder, ingest
from app.tests.test_wiki_integration import generate, model, workspace


@pytest.fixture
def client(workspace):
    db, *_ = workspace
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client


def install_model(monkeypatch):
    request = pipeline.structured
    monkeypatch.setattr(
        pipeline,
        "structured",
        lambda *args, **kwargs: request(*args, **{**kwargs, "client": model()}),
    )
    monkeypatch.setattr(
        relations,
        "structured",
        lambda *args, **kwargs: request(*args, **{**kwargs, "client": model()}),
    )


def test_real_job_failure_is_separate_from_indexing_and_restart_retry(
    workspace, client, monkeypatch
):
    db, *_ = workspace
    record = discover(workspace)
    jobs.register()
    worker = knowledge_jobs.KnowledgeWorker()
    response = client.post("/wiki/generate", json={"source_id": record.id})
    assert response.status_code == 202
    job = response.json()
    knowledge_jobs.recover_interrupted(db)
    interrupted = knowledge_jobs.get(db, job["id"])
    assert interrupted["state"] == "interrupted"
    assert interrupted["events"][-1]["state"] == "interrupted"
    retry = knowledge_jobs.resume(db, job["id"])

    def fail(*args, **kwargs):
        raise WikiError("Local model invalid JSON")

    monkeypatch.setattr(pipeline, "structured", fail)
    worker.run_one(db, retry["id"])
    assert knowledge_jobs.get(db, retry["id"])["state"] == "failed"
    assert ingestion_jobs.latest(db, record.id)["state"] == "complete"
    assert db.execute("SELECT status FROM files WHERE id=?", (record.id,)).fetchone()[0] == "READY"
    # A new explicit attempt retains scope and version manifest, never broadens on restart.
    monkeypatch.undo()
    install_model(monkeypatch)
    completed = knowledge_jobs.resume(db, retry["id"])
    assert completed["manifest"] == job["manifest"] and completed["scope"] == job["scope"]
    worker.run_one(db, completed["id"])
    output = knowledge_jobs.get(db, completed["id"])
    assert output["state"] == "complete" and output["artifact_id"]
    assert client.get("/wiki/" + output["artifact_id"]).json()["revision"]["origin"] == "generated"


def test_cancellation_and_deduplication(workspace, client):
    db, *_ = workspace
    record = discover(workspace)
    job = client.post("/wiki/generate", json={"source_id": record.id}).json()
    assert client.post("/wiki/generate", json={"source_id": record.id}).status_code == 409
    cancelled = knowledge_jobs.cancel(db, job["id"])
    assert cancelled["state"] == "cancelled"
    assert cancelled["events"][-1]["state"] == "cancelled"
    knowledge_jobs.KnowledgeWorker().run_one(db, job["id"])
    assert knowledge_jobs.get(db, job["id"])["artifact_id"] is None


def test_api_edit_conflict_revision_history_and_empty_scope(workspace, client):
    db, *_ = workspace
    record = discover(workspace)
    result = generate(db, record.id)
    identifier = result["wiki_id"]
    response = client.patch(
        "/wiki/" + identifier,
        json={
            "expected_revision": result["revision_id"],
            "title": "Edited",
            "content": "Authored Markdown",
        },
    )
    assert response.status_code == 200
    assert response.json()["revision"]["origin"] == "user"
    assert (
        client.patch(
            "/wiki/" + identifier,
            json={
                "expected_revision": result["revision_id"],
                "title": "Stale",
                "content": "Do not overwrite",
            },
        ).status_code
        == 409
    )
    assert client.post("/wiki/list", json={"mode": "empty"}).json() == []
    assert client.get(f"/wiki/{identifier}/revisions/{result['revision_id']}").json()["content"]
    assert client.get("/wiki/unknown").status_code == 404


def test_real_pdf_page_locations(workspace):
    import pymupdf

    db, root, _, scan, _ = workspace
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), "Reservoir introduction.")
        pdf.new_page().insert_text((72, 72), "Reservoir capacity: 37 litres except on Sundays.")
        pdf.save(root / "reservoir.pdf")
    scan()
    (identifier,) = scan()
    ingest(db, identifier)
    result = generate(db, identifier)
    revision = store.revision(db, result["revision_id"])
    assert {p["page_number"] for p in revision["evidence"]} == {1, 2}
    assert "page 2" in revision["content"] and "page 99" not in revision["content"]


def test_topic_failure_keeps_committed_source_artifact(workspace, monkeypatch):
    db, *_ = workspace
    record = discover(workspace)
    jobs.register()
    install_model(monkeypatch)

    def fail(*args, **kwargs):
        raise WikiError("Topic projection failed after source revision committed")

    monkeypatch.setattr(service, "refresh_topics", fail)
    job = jobs.enqueue(db, record.id, WikiScope())
    worker = knowledge_jobs.KnowledgeWorker()
    worker.run_one(db, job["id"])
    failed = knowledge_jobs.get(db, job["id"])
    assert failed["state"] == "failed" and failed["artifact_id"]
    page = store.page(db, failed["artifact_id"])
    assert store.revision(db, page["current_revision"])["metadata"]["source"]["source_id"] == (
        record.id
    )
