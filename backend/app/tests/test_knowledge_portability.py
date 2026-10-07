"""Actual integrated authored data and job state through backup/new-destination restore."""

from contextlib import closing

import pytest

from app.config import data_directory
from app.db import documents
from app.db import source_documents as document_store
from app.db.database import connect, init_schema
from app.services import knowledge_jobs
from app.services.workspace_backup import create_backup, restore_backup
from app.tests.test_folder_foundation import discover, folder
from app.tests.test_source_documents import enqueue, run, workspace


def test_document_edits_versions_and_stage_history_survive_new_workspace_restore(workspace):
    db, root, root_id, *_ = workspace
    original = discover(workspace, "Course/one.md", "Reservoir stores 37 litres except on Sundays.")
    before = (root / "Course/one.md").read_bytes()
    job = enqueue(db)
    artifact = run(db, job)
    documents.update_document(db, artifact, content="# 사용자 편집\nKeep exactly 37 and my notes.")
    expected = document_store.current(db, artifact)
    assert expected["metadata"]["selected_manifest"][0]["version"] == original.content_hash
    archive = data_directory().parent / "integrated.zip"
    manifest = create_backup(data_directory(), data_directory() / "app.db", archive)
    assert manifest["external_originals"].startswith("not included")
    target = data_directory().parent / "restored-integration"
    report = restore_backup(archive, target)
    assert report["external_roots"] == [
        {"id": root_id, "name": root.name, "availability": "disconnected"}
    ]
    with closing(connect(target / "app.db")) as restored:
        init_schema(restored)
        head = document_store.current(restored, artifact)
        assert head == expected
        assert len(document_store.revisions(restored, artifact)) == 2
        assert knowledge_jobs.get(restored, job["id"])["state"] == "interrupted"
        assert (
            knowledge_jobs.get(restored, job["id"])["events"]
            == knowledge_jobs.get(db, job["id"])["events"]
        )
        assert (
            restored.execute(
                "SELECT connected FROM source_roots WHERE id=?", (root_id,)
            ).fetchone()[0]
            == 0
        )
    assert (root / "Course/one.md").read_bytes() == before
    with pytest.raises(ValueError, match="already exists"):
        restore_backup(archive, target)


def test_backup_rejects_replaced_owned_trigger_and_arbitrary_views(workspace):
    db, *_ = workspace
    discover(workspace)
    with db:
        db.execute("DROP TRIGGER preserve_source_document_edits")
        db.execute(
            "CREATE TRIGGER preserve_source_document_edits AFTER UPDATE ON documents "
            "BEGIN DELETE FROM documents; END"
        )
    with pytest.raises(ValueError, match="custom triggers"):
        create_backup(
            data_directory(), data_directory() / "app.db", data_directory().parent / "bad.zip"
        )
    assert not (data_directory().parent / "bad.zip").exists()
