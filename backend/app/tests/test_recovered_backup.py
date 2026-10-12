"""A second backup must retain both authored versions after a restore conflict."""

from pathlib import Path

import pytest

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


@pytest.mark.parametrize("operation", ["copy", "retain"])
def test_backup_rejects_authored_staging_failures_and_preserves_both_originals(
    folder, monkeypatch, operation
):
    db, root, root_id, _, _ = folder
    record = discover(folder)
    report = root / "documents" / "report.md"
    report.parent.mkdir()
    report.write_bytes(b"Complete current authored writing must survive in full.")
    workspace = data_directory()
    previous = workspace / "knowledge" / root_id / "documents" / "report.md"
    previous.parent.mkdir(parents=True)
    previous.write_bytes(b"Previously recovered authored writing must also survive.")
    archive = workspace.parent / "failed-backup.zip"
    real_write, real_rename = Path.write_bytes, Path.rename

    def short_write(path, data):
        if path.name == "report.md" and path != report:
            real_write(path, data[:8])
            raise OSError("Synthetic short staging write.")
        return real_write(path, data)

    def failed_retention(path, target):
        if path.name == "report.md" and path != report:
            raise OSError("Synthetic failed staging retention move.")
        return real_rename(path, target)

    with monkeypatch.context() as patch:
        if operation == "copy":
            patch.setattr(Path, "write_bytes", short_write)
        else:
            patch.setattr(Path, "rename", failed_retention)
        with pytest.raises(ValueError, match="could not be copied"):
            create_backup(workspace, workspace / "app.db", archive)
    assert not archive.exists()
    assert report.read_bytes() == b"Complete current authored writing must survive in full."
    assert previous.read_bytes() == b"Previously recovered authored writing must also survive."
    assert Path(record.path).read_bytes() == (root / "note.txt").read_bytes()
    assert not db.execute("SELECT 1 FROM folder_issues").fetchone()

    create_backup(workspace, workspace / "app.db", archive)
    restored = workspace.parent / "after-retrying-backup"
    restore_backup(archive, restored)
    copied = restored / "knowledge" / root_id / "documents"
    assert (copied / "report.md").read_bytes() == report.read_bytes()
    retained = list((copied / "Recovered backups").rglob("report.md"))
    assert len(retained) == 1 and retained[0].read_bytes() == previous.read_bytes()
