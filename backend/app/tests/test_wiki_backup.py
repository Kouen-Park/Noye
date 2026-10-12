"""Actual Wiki schema/content through A's portable backup and native reconnection contract."""

from contextlib import closing

from app.config import data_directory
from app.db import wiki as store
from app.db.database import connect
from app.models.wiki import EditWiki, SaveAnalysis, WikiScope
from app.services.folder_backup import reconnect_assets
from app.services.folders import register_root, root_record
from app.services.wiki import jobs, publication, service
from app.services.workspace_backup import create_backup, restore_backup
from app.tests.test_folder_foundation import discover, folder, ingest
from app.tests.test_wiki_integration import generate, workspace


def test_wiki_backup_preserves_authored_revisions_proposals_evidence_and_links(workspace):
    db, root, root_id, scan, _ = workspace
    first = discover(workspace, "one.md", "HELIOS capacity is 37 litres.")
    second = discover(workspace, "two.txt", "HELIOS manual valve; Sunday capacity is 29 litres.")
    a, b = generate(db, first.id), generate(db, second.id)
    service.edit(
        db,
        a["wiki_id"],
        EditWiki(
            expected_revision=a["revision_id"], title="Authored 한국어", content="Keep my 37."
        ),
    )
    (root / "one.md").write_text("HELIOS capacity changed to 92 litres.")
    scan()
    (identifier,) = scan()
    ingest(db, identifier)
    proposal = generate(db, identifier)
    assert store.revision(db, proposal["revision_id"])["origin"] == "proposal"
    analysis = service.save_analysis(
        db,
        SaveAnalysis(
            title="Reusable analysis",
            content="My interpretation; verify originals.",
            wiki_ids=[b["wiki_id"]],
        ),
    )
    queued = jobs.enqueue(db, second.id, WikiScope())
    expected = {
        table: [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
        for table in (
            "wiki_pages",
            "wiki_revisions",
            "wiki_evidence",
            "wiki_relations",
            "wiki_index",
        )
    }
    app_data = data_directory()
    archive, restored_root = app_data.parent / "wiki.zip", app_data.parent / "restored"
    manifest = create_backup(app_data, app_data / "app.db", archive)
    assert not manifest["missing_knowledge_roots"]
    restore_backup(archive, restored_root)
    with closing(connect(restored_root / "app.db")) as restored:
        for table, rows in expected.items():
            assert [
                tuple(row) for row in restored.execute(f"SELECT * FROM {table} ORDER BY rowid")
            ] == rows
        assert not root_record(restored, root_id)["connected"]
        assert (
            restored.execute(
                "SELECT state FROM knowledge_jobs WHERE id=?", (queued["id"],)
            ).fetchone()[0]
            == "interrupted"
        )
        for wiki_id in (a["wiki_id"], b["wiki_id"], analysis):
            saved = publication.disk_path(db, wiki_id)
            portable = restored_root / "knowledge" / root_id / saved.relative_to(root)
            assert portable.read_bytes() == saved.read_bytes()
        reconnected = root.parent / "reconnected"
        reconnected.mkdir()
        register_root(restored, reconnected, "connected", reconnect_id=root_id)
        reconnect_assets(restored, root_id, restored_root)
        target = reconnected / "wiki/sources" / f"{a['wiki_id']}.md"
        assert target.read_text() == "Keep my 37."
        target.write_text("Newer local edit; retain it.")
        reconnect_assets(restored, root_id, restored_root)
        assert target.read_text() == "Newer local edit; retain it."
        assert store.revision(restored, proposal["revision_id"])["origin"] == "proposal"
