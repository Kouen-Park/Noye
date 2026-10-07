"""Real ingestion/Wiki/filing wrapper: opt-in, collision, retries and edited pages."""

from app.db import jobs as ingestion_jobs
from app.db import wiki as store
from app.models.wiki import EditWiki, WikiScope
from app.services import knowledge_jobs, knowledge_maintenance
from app.services.folders import update_root
from app.services.source_catalog import SourceCatalog
from app.services.wiki import jobs, service
from app.tests.test_folder_foundation import discover, folder
from app.tests.test_wiki_integration import model, workspace


def run(db, record, monkeypatch):
    original = service.generate_source
    monkeypatch.setattr(
        jobs.service,
        "generate_source",
        lambda *args, **kwargs: original(*args, **kwargs, client=model()),
    )
    knowledge_maintenance.register()
    queued = jobs.enqueue(db, record.id, WikiScope())
    knowledge_jobs.KnowledgeWorker().run_one(db, queued["id"])
    return knowledge_jobs.get(db, queued["id"])


def test_ingestion_summary_authorized_filing_topics_and_no_embedding_loop(workspace, monkeypatch):
    db, root, root_id, scan, _ = workspace
    record = discover(workspace, "sources/inbox/note.txt")
    original = (root / "sources/inbox/note.txt").read_bytes()
    update_root(db, root_id, set_organization=True, organization_prefix="sources")
    job = run(db, record, monkeypatch)
    assert job["state"] == "complete"
    assert (root / "sources/Learning/note.txt").read_bytes() == original
    assert SourceCatalog(db).get(record.id)["relative_path"] == "sources/Learning/note.txt"
    assert ingestion_jobs.latest(db, record.id)["attempt"] == 1
    scan()
    assert scan() == []
    outcomes = {item["stage"]: item for item in job["events"]}
    assert outcomes["filing"]["state"] == "complete"
    assert outcomes["relations_topics"]["state"] == "complete"
    assert store.page(db, job["artifact_id"])["current_revision"]


def test_disabled_filing_is_visible_skip_and_preserves_existing_layout(workspace, monkeypatch):
    db, root, *_ = workspace
    record = discover(workspace)
    job = run(db, record, monkeypatch)
    assert job["state"] == "complete" and (root / "note.txt").exists()
    filing = [event for event in job["events"] if event["stage"] == "filing"][-1]
    assert filing["state"] == "skipped" and "disabled" in filing["detail"]["reason"]


def test_collision_fails_only_filing_retains_wiki_and_retry_reuses_revision(workspace, monkeypatch):
    db, root, root_id, *_ = workspace
    record = discover(workspace, "sources/inbox/note.txt")
    original_bytes = (root / "sources/inbox/note.txt").read_bytes()
    update_root(db, root_id, set_organization=True, organization_prefix="sources")
    collision = root / "sources/Learning/note.txt"
    collision.parent.mkdir(parents=True)
    collision.write_text("KEEP EXISTING BYTES")
    job = run(db, record, monkeypatch)
    assert job["state"] == "failed" and job["stage"] == "filing" and job["artifact_id"]
    assert job["events"][-1]["state"] == "failed"
    assert collision.read_text() == "KEEP EXISTING BYTES"
    assert (root / "sources/inbox/note.txt").exists()
    revisions = store.revisions(db, job["artifact_id"])
    collision.rename(collision.with_name("collision-kept.txt"))
    retry = knowledge_jobs.resume(db, job["id"])
    knowledge_jobs.KnowledgeWorker().run_one(db, retry["id"])
    assert knowledge_jobs.get(db, retry["id"])["state"] == "complete"
    assert store.revisions(db, job["artifact_id"]) == revisions
    assert collision.read_bytes() == original_bytes
    assert (root / "sources/Learning/collision-kept.txt").read_text() == "KEEP EXISTING BYTES"


def test_manually_fixed_category_and_wiki_user_revision_survive_refresh(workspace, monkeypatch):
    db, _root, root_id, *_ = workspace
    record = discover(workspace, "sources/inbox/note.txt")
    update_root(db, root_id, set_organization=True, organization_prefix="sources")
    job = run(db, record, monkeypatch)
    page = store.page(db, job["artifact_id"])
    service.edit(
        db,
        page["id"],
        EditWiki(
            expected_revision=page["current_revision"],
            title="Edited",
            content="User interpretation stays.",
        ),
    )
    with db:
        db.execute("UPDATE sources SET manual_category=? WHERE file_id=?", ("Pinned", record.id))
    # Restore actual model service before creating another wrapper in run().
    monkeypatch.undo()
    second = run(db, record, monkeypatch)
    assert second["state"] == "complete"
    assert SourceCatalog(db).get(record.id)["relative_path"] == "sources/Learning/note.txt"
    current = store.revision(db, store.page(db, page["id"])["current_revision"])
    assert current["origin"] == "user" and current["content"] == "User interpretation stays."
    assert any(r["origin"] == "proposal" for r in store.revisions(db, page["id"]))
