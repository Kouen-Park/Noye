"""A second backup must retain both authored versions after a restore conflict."""

from app.config import data_directory
from app.services.folder_backup import reconnect_assets
from app.services.workspace_backup import create_backup, restore_backup
from app.tests.test_folder_foundation import discover, folder


def test_repeated_backup_keeps_current_and_previously_recovered_conflicting_writing(folder):
    db, root, root_id, _, _ = folder
    discover(folder)
    current = root / "documents/report.md"
    current.parent.mkdir()
    current.write_text("Current authored writing")
    workspace = data_directory()
    recovered = workspace / "knowledge" / root_id / "documents/report.md"
    recovered.parent.mkdir(parents=True)
    recovered.write_text("Previously recovered authored writing")
    reconnect_assets(db, root_id, workspace)
    archive = workspace.parent / "repeat-backup.zip"
    create_backup(workspace, workspace / "app.db", archive)
    restored_path = workspace.parent / "repeat-restored"
    restore_backup(archive, restored_path)
    restored_documents = restored_path / "knowledge" / root_id / "documents"
    assert (restored_documents / "report.md").read_text() == "Current authored writing"
    saved_recovered = list((restored_documents / "Recovered backups").rglob("report.md"))
    assert len(saved_recovered) == 1
    assert saved_recovered[0].read_text() == "Previously recovered authored writing"
    assert current.read_text() == "Current authored writing"
    assert recovered.read_text() == "Previously recovered authored writing"
