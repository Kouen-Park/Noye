"""Real SQLite/WAL snapshots preserve writing and never overwrite a workspace."""

import stat
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.api import models, workspace
from app.config import Settings
from app.db import conversations as conversations_db
from app.db import documents as documents_db
from app.db import files as files_db
from app.db.database import connect, init_schema
from app.db.migrations import LATEST_VERSION
from app.main import app
from app.models.conversations import Role
from app.models.files import FileType
from app.services import ingestion, workspace_backup
from app.services.evidence import capture_citations
from app.services.retrieval import SearchResult
from app.services.workspace_access import WorkspaceBusy, request_access, snapshot_access
from app.services.workspace_backup import create_backup, restore_backup


@pytest.fixture
def saved_workspace(tmp_path):
    root = tmp_path / "active"
    (root / "sources").mkdir(parents=True)
    (root / "documents").mkdir()
    original = root / "sources" / "source.md"
    original.write_text("한국어 원문 742 units")
    db = connect(root / "app.db")
    init_schema(db)
    record = files_db.create_file(
        db, name="source.md", file_type=FileType.MARKDOWN,
        path=str(original), size=original.stat().st_size,
    )
    citations = capture_citations([SearchResult(
        file_id=record.id, content="saved old excerpt", chunk_index=0,
        page_number=None, score=0.9,
    )], {record.id: record.name})
    conversation = conversations_db.create_conversation(db, first_question="Original question")
    message = conversations_db.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="saved answer", citations=citations,
    )
    document = documents_db.create_document(db, content="first draft", citations=citations)
    db.execute("PRAGMA wal_autocheckpoint = 0")
    documents_db.update_document(db, document.id, content="# User edited writing\n한국어")
    (root / "documents" / "export.md").write_text("a separate export")
    for secret in (".env", "preferences.json", "logs/private.log", "models/weights",
                   "qdrant/storage/vector"):
        path = root / secret
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("excluded synthetic secret")
    yield root, db, record, message, document
    db.close()


def archive_for(saved_workspace, tmp_path):
    root, _, *_ = saved_workspace
    archive = tmp_path / "backup.zip"
    with snapshot_access():
        create_backup(root, root / "app.db", archive)
    return archive


def test_round_trip_preserves_wal_writing_and_independent_evidence(saved_workspace, tmp_path):
    root, original_db, record, message, document = saved_workspace
    assert (root / "app.db-wal").is_file()
    archive = archive_for(saved_workspace, tmp_path)
    with zipfile.ZipFile(archive) as packed:
        assert set(packed.namelist()) == {
            "manifest.json", "app.db", "sources/source.md", "documents/export.md",
        }
    destination = tmp_path / "restored"
    report = restore_backup(archive, destination)
    assert report["rebuild_required"] and report["missing_sources"] == []
    with connect(destination / "app.db") as db:
        assert conversations_db.get_message(db, message.id).content == "saved answer"
        saved = documents_db.get_document(db, document.id)
        assert saved.content == "# User edited writing\n한국어"
        assert saved.citations == document.citations
        restored = files_db.get_file(db, record.id)
        assert restored.path == str(destination / "sources" / "source.md")
        assert restored.status.value == "FAILED" and restored.index_fingerprint is None
    assert (destination / "sources" / "source.md").read_bytes() == (
        root / "sources" / "source.md"
    ).read_bytes()
    assert documents_db.get_document(original_db, document.id).content.startswith("# User")
    assert files_db.get_file(original_db, record.id).path == record.path


@pytest.mark.parametrize("empty", [False, True])
def test_existing_destination_is_never_overwritten(saved_workspace, tmp_path, empty):
    archive = archive_for(saved_workspace, tmp_path)
    destination = tmp_path / "existing"
    destination.mkdir()
    if not empty:
        (destination / "keep.txt").write_text("keep me")
    with pytest.raises(ValueError, match="already exists"):
        restore_backup(archive, destination)
    assert sorted(path.name for path in destination.iterdir()) == ([] if empty else ["keep.txt"])


@pytest.mark.parametrize("bad_name", ["../escaped", "/absolute", "sources/../../escaped", ".env"])
def test_archive_cannot_escape_or_import_secrets(tmp_path, bad_name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as packed:
        packed.writestr(bad_name, "untrusted")
    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="invalid workspace path"):
        restore_backup(archive, destination)
    assert not destination.exists()
    assert not (tmp_path / "escaped").exists()


def test_checksums_and_manifest_completeness_are_required(saved_workspace, tmp_path):
    archive = archive_for(saved_workspace, tmp_path)
    with zipfile.ZipFile(archive) as packed:
        entries = {name: packed.read(name) for name in packed.namelist()}
    entries["sources/source.md"] = b"tampered"
    bad = tmp_path / "tampered.zip"
    with zipfile.ZipFile(bad, "w") as packed:
        for name, body in entries.items():
            packed.writestr(name, body)
    with pytest.raises(ValueError, match=r"size|checksum"):
        restore_backup(bad, tmp_path / "bad")
    entries.pop("sources/source.md")
    with zipfile.ZipFile(bad, "w") as packed:
        for name, body in entries.items():
            packed.writestr(name, body)
    with pytest.raises(ValueError, match="manifest"):
        restore_backup(bad, tmp_path / "partial")
    assert not (tmp_path / "partial").exists()


def test_symbolic_links_are_not_backed_up_or_restored(saved_workspace, tmp_path):
    root, *_ = saved_workspace
    (root / "sources" / "link").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="links"):
        create_backup(root, root / "app.db", tmp_path / "backup.zip")
    archive = tmp_path / "symlink.zip"
    entry = zipfile.ZipInfo("sources/link")
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as packed:
        packed.writestr(entry, "../../outside")
    with pytest.raises(ValueError, match="unsupported"):
        restore_backup(archive, tmp_path / "restored")


def test_missing_original_is_reported_without_losing_writing(saved_workspace, tmp_path):
    root, _, record, _, document = saved_workspace
    (root / "sources" / "source.md").unlink()
    archive = archive_for(saved_workspace, tmp_path)
    destination = tmp_path / "restored"
    assert restore_backup(archive, destination)["missing_sources"] == [record.id]
    with connect(destination / "app.db") as db:
        assert "missing" in files_db.get_file(db, record.id).error
        assert documents_db.get_document(db, document.id).content.startswith("# User")


def test_legacy_snapshot_migrates_without_fabricated_excerpts(saved_workspace, tmp_path):
    _, db, _, message, _ = saved_workspace
    db.execute("ALTER TABLE message_citations DROP COLUMN evidence_json")
    db.execute("ALTER TABLE document_citations DROP COLUMN evidence_json")
    db.execute("PRAGMA user_version=2")
    db.commit()
    archive = archive_for(saved_workspace, tmp_path)
    destination = tmp_path / "restored"
    restore_backup(archive, destination)
    with connect(destination / "app.db") as restored:
        assert restored.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
        assert conversations_db.get_message(restored, message.id).citations[0].evidence is None


def test_newer_schema_is_rejected_without_creating_an_archive(saved_workspace, tmp_path):
    root, db, *_ = saved_workspace
    db.execute(f"PRAGMA user_version={LATEST_VERSION + 1}")
    db.commit()
    with pytest.raises(ValueError, match="newer"):
        create_backup(root, root / "app.db", tmp_path / "backup.zip")
    assert not (tmp_path / "backup.zip").exists()


def test_backup_detects_external_source_edits(saved_workspace, tmp_path, monkeypatch):
    root, *_ = saved_workspace
    real_copy = workspace_backup.shutil.copyfile

    def changed(source, target):
        result = real_copy(source, target)
        source.write_text("changed during copy")
        return result

    monkeypatch.setattr(workspace_backup.shutil, "copyfile", changed)
    with pytest.raises(ValueError, match="changed"):
        create_backup(root, root / "app.db", tmp_path / "backup.zip")


def test_snapshot_blocks_requests_and_processing_and_releases_after_failure():
    with request_access(), pytest.raises(WorkspaceBusy):
        with snapshot_access():
            pytest.fail("active request")
    ingestion.reserve_ingestion("synthetic-busy")
    try:
        with pytest.raises(ingestion.MaintenanceBusy):
            with snapshot_access():
                pytest.fail("active ingestion")
    finally:
        ingestion.release_file("synthetic-busy")
    with snapshot_access():
        with pytest.raises(WorkspaceBusy):
            with request_access():
                pytest.fail("write during snapshot")
        with pytest.raises(ingestion.MaintenanceBusy):
            ingestion.reserve_ingestion("new")
    with request_access():
        pass


def test_desktop_api_download_restore_and_capability(saved_workspace, monkeypatch):
    root, *_ = saved_workspace
    settings = Settings(_env_file=None, noye_data_dir=root)
    monkeypatch.setattr(models, "get_settings", lambda: settings)
    monkeypatch.setattr(workspace, "data_directory", lambda: root)
    monkeypatch.setattr(workspace, "database_path", lambda: root / "app.db")
    monkeypatch.setenv("NOYE_CONTROL_TOKEN", "synthetic-control")
    client = TestClient(app)
    assert client.post("/workspace/backup").status_code == 403
    headers = {"X-Noye-Control": "synthetic-control"}
    backup = client.post("/workspace/backup", headers=headers)
    assert backup.status_code == 200 and backup.content.startswith(b"PK")
    restored = client.post("/workspace/restore", headers=headers,
                           files={"file": ("backup.zip", backup.content)})
    assert restored.status_code == 201 and restored.json()["rebuild_required"]
    assert restored.json()["destination"].startswith(str(root.parent / "noye-restored-"))
