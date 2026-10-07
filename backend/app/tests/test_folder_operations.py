"""Original byte safety, recovery journal and generic durable jobs."""

import pytest

from app.db import jobs
from app.services import filing, knowledge_jobs
from app.services.folders import SourceError, update_root
from app.services.source_catalog import SourceCatalog
from app.tests.test_folder_foundation import discover, folder


def test_filing_optin_collision_manual_lock_bytes_and_identity(folder):
    db, root, root_id, scan, _ = folder
    first = discover(folder, "sources/inbox/note.txt")
    with pytest.raises(SourceError):
        filing.file_source(db, first.id, "sources/topic/note.txt", first.content_hash)
    update_root(db, root_id, set_organization=True, organization_prefix="sources")
    original_bytes = (root / "sources/inbox/note.txt").read_bytes()
    journal = filing.file_source(
        db, first.id, "sources/topic/note.txt", first.content_hash, manual=True
    )
    assert journal["state"] == "complete"
    assert (root / "sources/topic/note.txt").read_bytes() == original_bytes
    assert SourceCatalog(db).get(first.id)["manual_category"] == "sources/topic"
    assert scan() == [] and scan() == []
    assert jobs.latest(db, first.id)["attempt"] == 1
    with pytest.raises(SourceError, match="manually fixed"):
        filing.file_source(db, first.id, "sources/other/note.txt", first.content_hash)
    (root / "sources/topic/collision.txt").write_text("KEEP")
    with pytest.raises(SourceError):
        filing.file_source(
            db, first.id, "sources/topic/collision.txt", first.content_hash, manual=True
        )
    assert (root / "sources/topic/collision.txt").read_text() == "KEEP"
    assert (root / "sources/topic/note.txt").read_bytes() == original_bytes
    assert db.execute(
        "SELECT state FROM filing_journal WHERE new_path='sources/topic/collision.txt'"
    ).fetchone()[0] == "failed"
    retry = filing.file_source(
        db, first.id, "sources/topic/another-name.txt", first.content_hash, manual=True
    )
    assert retry["state"] == "complete"
    assert (root / "sources/topic/another-name.txt").read_bytes() == original_bytes
    assert (root / "sources/topic/collision.txt").read_text() == "KEEP"
    assert SourceCatalog(db).get(first.id)["relative_path"] == "sources/topic/another-name.txt"
    assert jobs.latest(db, first.id)["attempt"] == 1


def test_filing_recovers_crash_after_move_before_registry_update(folder, monkeypatch):
    db, root, root_id, _, _ = folder
    first = discover(folder, "sources/inbox/note.txt")
    update_root(db, root_id, set_organization=True, organization_prefix="sources")
    finish = filing._finish

    def crash(*args):
        raise RuntimeError("synthetic power loss")

    monkeypatch.setattr(filing, "_finish", crash)
    with pytest.raises(RuntimeError):
        filing.file_source(db, first.id, "sources/topic/note.txt", first.content_hash)
    assert (root / "sources/topic/note.txt").exists()
    assert SourceCatalog(db).get(first.id)["relative_path"] == "sources/inbox/note.txt"
    monkeypatch.setattr(filing, "_finish", finish)
    filing.recover_filing(db)
    assert SourceCatalog(db).get(first.id)["relative_path"] == "sources/topic/note.txt"
    assert db.execute("SELECT state FROM filing_journal").fetchone()[0] == "complete"


def test_knowledge_jobs_execute_progress_cancel_restart_and_retry(folder):
    db, _, _, _, _ = folder
    first = discover(folder)
    job = knowledge_jobs.enqueue(
        db, kind="test-wiki", subject_id=first.id, payload={"safe": True}, scope={"mode": "all"}
    )
    with pytest.raises(ValueError):
        knowledge_jobs.enqueue(
            db, kind="test-wiki", subject_id=first.id, payload={}, scope={"mode": "all"}
        )
    knowledge_jobs.recover_interrupted(db)
    assert knowledge_jobs.get(db, job["id"])["state"] == "interrupted"
    retry = knowledge_jobs.resume(db, job["id"])
    assert retry["attempt"] == 2 and retry["manifest"] == job["manifest"]

    def handler(context, payload):
        assert payload["safe"]
        context.checkpoint("drafting", 1, 2)
        return "artifact-123"

    knowledge_jobs.register("test-wiki", handler)
    worker = knowledge_jobs.KnowledgeWorker()
    worker.run_one(db, retry["id"])
    assert knowledge_jobs.get(db, retry["id"])["artifact_id"] == "artifact-123"
    other = knowledge_jobs.enqueue(
        db, kind="test-wiki", subject_id="other", payload={}, scope={"mode": "empty"}
    )
    knowledge_jobs.cancel(db, other["id"])
    worker.run_one(db, other["id"])
    assert knowledge_jobs.get(db, other["id"])["state"] == "cancelled"


def test_late_cancellation_retains_saved_artifact_without_claiming_complete(folder, monkeypatch):
    db, _, _, _, _ = folder
    job = knowledge_jobs.enqueue(
        db, kind="late-cancel", subject_id="artifact", payload={}, scope={"mode": "empty"}
    )
    knowledge_jobs.register("late-cancel", lambda context, payload: "saved-artifact")
    checkpoint = knowledge_jobs.WorkContext.checkpoint

    def cancel_after_last_check(context, stage, *args):
        checkpoint(context, stage, *args)
        if stage == "saving":
            knowledge_jobs.cancel(db, job["id"])

    monkeypatch.setattr(knowledge_jobs.WorkContext, "checkpoint", cancel_after_last_check)
    knowledge_jobs.KnowledgeWorker().run_one(db, job["id"])
    result = knowledge_jobs.get(db, job["id"])
    assert result["state"] == "cancelled" and result["artifact_id"] == "saved-artifact"


def test_local_job_never_calls_handler_when_ollama_is_remote(folder, monkeypatch):
    from app.config import Settings

    db, _, _, _, _ = folder
    settings = Settings(_env_file=None, ollama_base_url="https://cloud.example.invalid")
    monkeypatch.setattr(knowledge_jobs, "get_settings", lambda: settings)
    called = []
    knowledge_jobs.register("local-only", lambda context, payload: called.append(True))
    job = knowledge_jobs.enqueue(
        db, kind="local-only", subject_id="local", payload={}, scope={"mode": "empty"}
    )
    knowledge_jobs.KnowledgeWorker().run_one(db, job["id"])
    assert not called
    assert "no cloud fallback" in knowledge_jobs.get(db, job["id"])["error"]
