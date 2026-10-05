"""Portable authored assets, private authorization and current original APIs."""

import json
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.config import data_directory
from app.db.database import connect
from app.main import app
from app.services.folder_backup import reconnect_assets
from app.services.folders import register_root, root_record, update_root
from app.services.source_catalog import EvidenceReader, SourceCatalog
from app.services.workspace_backup import create_backup, restore_backup
from app.tests.test_folder_foundation import discover, folder, ingest


def test_backup_retains_bytes_versions_authored_wiki_jobs_and_requires_reconnection(folder):
    _, root, root_id, _, _ = folder
    first = discover(folder)
    (root / "wiki/sources").mkdir(parents=True)
    authored = root / "wiki/sources/authored.md"
    authored.write_text("# User edit\n한국어 37; keep this exact text.")
    (root / "documents").mkdir()
    (root / "documents/report.md").write_text("A portable authored report.")
    workspace = data_directory()
    (workspace / "wiki/analyses").mkdir(parents=True)
    (workspace / "wiki/analyses/cross-root.md").write_text("Authored cross-root analysis 한국어")
    archive = workspace.parent / "backup.zip"
    manifest = create_backup(workspace, workspace / "app.db", archive)
    assert manifest["external_originals"].startswith("not included")
    assert manifest["missing_knowledge_roots"] == []
    new = workspace.parent / "restore"
    report = restore_backup(archive, new)
    assert report["rebuild_required"]
    restored = connect(new / "app.db")
    try:
        assert (
            new / "wiki/analyses/cross-root.md"
        ).read_text() == "Authored cross-root analysis 한국어"
        assert not root_record(restored, root_id)["connected"]
        assert SourceCatalog(restored).list_sources() == []
        snapshot = restored.execute("SELECT snapshot_path FROM source_versions").fetchone()[0]
        assert Path(snapshot).read_bytes() == (root / "note.txt").read_bytes()
        saved_asset = new / "knowledge" / root_id / "wiki/sources/authored.md"
        assert saved_asset.read_bytes() == authored.read_bytes()
        new_root = root.parent / "reconnected"
        new_root.mkdir()
        register_root(restored, new_root, "connected", reconnect_id=root_id)
        reconnect_assets(restored, root_id, new)
        assert (new_root / "wiki/sources/authored.md").read_bytes() == authored.read_bytes()
        (new_root / "wiki/sources/authored.md").write_text("newer local edit")
        reconnect_assets(restored, root_id, new)
        assert (new_root / "wiki/sources/authored.md").read_text() == "newer local edit"
        assert saved_asset.exists() and root_record(restored, root_id)["error"]
        historical = EvidenceReader(restored).read(
            first.id,
            first.content_hash,
            {"mode": "chosen", "source_ids": [first.id]},
            historical=True,
        )
        assert "37" in historical[0]["content"]
    finally:
        restored.close()


def test_unavailable_wiki_roots_are_explicit_in_backup(folder):
    _, root, root_id, _, _ = folder
    discover(folder)
    root.rename(root.with_name("unmounted"))
    workspace = data_directory()
    manifest = create_backup(workspace, workspace / "app.db", workspace.parent / "backup.zip")
    assert manifest["missing_knowledge_roots"] == [root_id]
    assert manifest["missing_sources"] == []  # internal snapshots are still present


def test_native_root_boundaries_and_folder_api_never_authorize_paths(folder, monkeypatch):
    db, root, root_id, _, _ = folder
    monkeypatch.setenv("NOYE_CONTROL_TOKEN", "synthetic-control")
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        assert client.get("/folders").status_code == 403
        headers = {"X-Noye-Control": "synthetic-control"}
        result = client.get("/folders", headers=headers).json()
        assert "path" not in result[0] and result[0]["id"] == root_id
        assert client.post("/folders", headers=headers, json={"path": str(root)}).status_code == 405
        nested = root / "nested"
        nested.mkdir()
        with pytest.raises(ValueError):
            register_root(db, nested, "connected")
        with pytest.raises(ValueError):
            register_root(db, data_directory(), "managed")
    finally:
        app.dependency_overrides.clear()


def test_current_source_open_status_disconnect_and_delete_are_distinct(folder):
    db, root, root_id, _, _ = folder
    record = discover(folder)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        response = client.get(f"/files/{record.id}/source")
        assert response.status_code == 200
        assert response.content == (root / "note.txt").read_bytes()
        (root / "note.txt").write_text("Changed live original without a scan yet.")
        current = client.get(f"/files/{record.id}/source-status").json()
        assert current["current_hash"] != record.content_hash
        assert client.post(f"/files/{record.id}/reingest").status_code == 409
        assert client.delete(f"/files/{record.id}").status_code == 409
        update_root(db, root_id, disconnect=True)
        assert client.get(f"/files/{record.id}/source").status_code == 404
        assert client.get(f"/files/{record.id}/source-status").json()["status"] == "unavailable"
        assert (root / "note.txt").exists() and Path(record.path).exists()
    finally:
        app.dependency_overrides.clear()


def test_real_pdf_extraction_keeps_actual_pages_and_page_free_text(folder):
    db, root, _, scan, _ = folder
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), "First page overview.")
        pdf.new_page().insert_text((72, 72), "Exact limit 37 appears on physical page two.")
        pdf.save(root / "fact.pdf")
    scan()
    (identifier,) = scan()
    record = ingest(db, identifier)
    passages = EvidenceReader(db).read(identifier, record.content_hash, {"mode": "all"})
    assert [passage["page_number"] for passage in passages] == [1, 2]
    assert "37" in passages[1]["content"]


def test_failed_reconnection_write_retains_recovery_bytes_and_never_publishes_partial(
    folder, monkeypatch
):
    db, root, root_id, _, _ = folder
    workspace = data_directory()
    recovered = workspace / "knowledge" / root_id / "wiki/sources/test.md"
    recovered.parent.mkdir(parents=True)
    recovered.write_bytes(b"Recovered complete authored bytes")
    monkeypatch.setattr(
        "app.services.filing.rename_exclusive",
        lambda *args: (_ for _ in ()).throw(OSError("power loss")),
    )
    with pytest.raises(OSError):
        reconnect_assets(db, root_id, workspace)
    assert recovered.read_bytes() == b"Recovered complete authored bytes"
    assert not (root / "wiki/sources/test.md").exists()
    assert not list((root / "wiki/sources").glob(".noye-reconnect-*"))
