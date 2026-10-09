"""Visible folder failures and Library actions preserve originals and saved evidence."""

from app.api import folders as folder_api
from app.config import data_directory, get_settings
from app.db.database import connect, init_schema
from app.db.migrations import apply_migrations
from app.db.sources import issues, record_issue
from app.services.folder_backup import reconnect_assets
from app.services.folders import root_record
from app.services.workspace_backup import create_backup, restore_backup
from app.tests.test_folder_foundation import discover, folder, ingest


def test_oversized_discovery_is_durable_visible_and_recovers_after_reduction(folder):
    db, root, root_id, scan, _ = folder
    path = root / "large.txt"
    with path.open("wb") as output:
        output.truncate(get_settings().max_upload_mb * 1024 * 1024 + 1)
    assert scan() == [] and scan() == []
    assert db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
    assert len(issues(db, root_id, "intake")) == 1
    # A fresh watcher and database connection must retain the reason before scanning again.
    reopened = connect(data_directory() / "app.db")
    try:
        tree = folder_api.tree(root_id, reopened)
        entry = next(e for e in tree["entries"] if e["relative_path"] == "large.txt")
        assert entry["source"] is None
        assert "100 MB" in entry["intake_error"] and "Finder" in entry["intake_error"]
    finally:
        reopened.close()
    path.write_text("Reduced original; searchable now.")
    assert scan() == []
    (identifier,) = scan()
    assert ingest(db, identifier).status.value == "READY"
    assert issues(db, root_id, "intake") == []
    assert path.read_text() == "Reduced original; searchable now."


def test_removed_failed_intake_clears_only_its_notice(folder):
    db, root, root_id, scan, _ = folder
    path = root / "large.pdf"
    with path.open("wb") as output:
        output.truncate(get_settings().max_upload_mb * 1024 * 1024 + 1)
    scan()
    scan()
    record_issue(db, root_id, "recovery", "documents/saved.md", "Retained recovered writing")
    path.unlink()
    scan()
    assert not issues(db, root_id, "intake")
    assert issues(db, root_id, "recovery")


def test_recovery_conflict_survives_scans_until_acknowledged_without_deleting_bytes(folder):
    db, root, root_id, scan, _ = folder
    current = root / "documents/report.md"
    current.parent.mkdir()
    current.write_text("Current authored writing")
    recovered = data_directory() / "knowledge" / root_id / "documents/report.md"
    recovered.parent.mkdir(parents=True)
    recovered.write_text("Recovered authored writing")
    reconnect_assets(db, root_id, data_directory())
    expected = issues(db, root_id, "recovery")
    assert expected[0]["relative_path"] == "documents/report.md"
    scan()
    scan()
    assert root_record(db, root_id)["error"] is None
    assert folder_api.tree(root_id, db)["root"]["recovery_conflicts"] == expected
    folder_api.control(root_id, folder_api.RootPatch(acknowledge_recovery_conflicts=True), db)
    assert not issues(db, root_id, "recovery")
    assert current.read_text() == "Current authored writing"
    assert recovered.read_text() == "Recovered authored writing"


def test_recovery_conflict_clears_when_reconnected_files_match(folder):
    db, root, root_id, _, _ = folder
    current = root / "wiki/saved.md"
    current.parent.mkdir()
    current.write_text("Current")
    recovered = data_directory() / "knowledge" / root_id / "wiki/saved.md"
    recovered.parent.mkdir(parents=True)
    recovered.write_text("Recovered")
    reconnect_assets(db, root_id, data_directory())
    assert issues(db, root_id, "recovery")
    current.write_bytes(recovered.read_bytes())
    reconnect_assets(db, root_id, data_directory())
    assert not issues(db, root_id, "recovery")


def test_notices_survive_backup_restore_with_original_evidence(folder):
    db, _, root_id, _, _ = folder
    record = discover(folder)
    record_issue(db, root_id, "intake", "large.txt", "Reduce to 100 MB in Finder")
    record_issue(db, root_id, "recovery", "documents/report.md", "Both authored versions retained")
    workspace = data_directory()
    archive = workspace.parent / "notices.zip"
    create_backup(workspace, workspace / "app.db", archive)
    restored_path = workspace.parent / "restored-notices"
    restore_backup(archive, restored_path)
    restored = connect(restored_path / "app.db")
    try:
        assert issues(restored, root_id, "intake") == issues(db, root_id, "intake")
        assert issues(restored, root_id, "recovery") == issues(db, root_id, "recovery")
        assert (
            restored.execute(
                "SELECT COUNT(*) FROM source_versions WHERE file_id=?", (record.id,)
            ).fetchone()[0]
            == 1
        )
        assert restored.execute("PRAGMA foreign_key_check").fetchone() is None
    finally:
        restored.close()


def test_version_nine_migration_preserves_existing_recovery_warning(folder):
    db, _, root_id, _, _ = folder
    warning = "1 recovered Wiki/output conflicts retained in the restored workspace."
    db.execute("DROP TABLE folder_issues")
    db.execute("PRAGMA user_version=9")
    db.execute("UPDATE source_roots SET error=? WHERE id=?", (warning, root_id))
    db.commit()
    assert apply_migrations(db) == 1
    assert issues(db, root_id, "recovery") == [{"relative_path": "", "message": warning}]
    init_schema(db)
    assert issues(db, root_id, "recovery") == [{"relative_path": "", "message": warning}]
