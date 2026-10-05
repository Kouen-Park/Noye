"""Synthetic originals through real registry/scanner/ingestion/evidence/filing."""

import json
from contextlib import closing
from pathlib import Path

import httpx
import pytest
from qdrant_client import QdrantClient

from app.config import get_settings
from app.db import files, jobs
from app.db.database import connect, init_schema
from app.models.files import FileStatus
from app.services import ingestion
from app.services.folder_scanner import FolderScanner
from app.services.folders import SourceError, read_original, register_root, root_record, update_root
from app.services.source_catalog import EvidenceReader, SourceCatalog


@pytest.fixture
def folder(tmp_path, monkeypatch):
    app_data = tmp_path / "app"
    monkeypatch.setenv("NOYE_DATA_DIR", str(app_data))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{app_data / 'app.db'}")
    get_settings.cache_clear()
    original = tmp_path / "knowledge"
    original.mkdir()
    db = connect()
    init_schema(db)
    root_id = register_root(db, original, "connected")
    moment = [0.0]
    scanner = FolderScanner(clock=lambda: moment[0])

    def scan():
        result = scanner.scan_root(db, root_id)
        moment[0] += 3
        return result

    yield db, original, root_id, scan, scanner
    for row in db.execute("SELECT id FROM files"):
        ingestion.release_file(row["id"])
    db.close()
    get_settings.cache_clear()


def ingest(db, file_id):
    def response(request):
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={"embeddings": [[0.1] * get_settings().qdrant_vector_size for _ in body["input"]]},
        )

    with (
        closing(QdrantClient(":memory:")) as qdrant,
        httpx.Client(transport=httpx.MockTransport(response)) as client,
    ):
        result = ingestion.ingest_file(
            db,
            file_id,
            qdrant_client=qdrant,
            http_client=client,
            reserved=ingestion.is_ingesting(file_id),
        )
    assert result.status is FileStatus.READY
    return result


def discover(
    folder, relative="note.txt", content="Original fact: the limit is 37, except on Sundays."
):
    db, root, root_id, scan, _ = folder
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    assert scan() == []
    (file_id,) = scan()
    return ingest(db, file_id)


def test_stable_intake_real_ingestion_and_b_evidence(folder):
    db, root, root_id, scan, _ = folder
    record = discover(folder)
    catalog = SourceCatalog(db)
    (descriptor,) = catalog.list_sources()
    assert descriptor["source_id"] == record.id
    assert descriptor["root_id"] == root_id
    assert "path" not in descriptor
    assert scan() == []
    evidence = EvidenceReader(db).read(record.id, descriptor["version"], {"mode": "all"})
    assert evidence[0]["page_number"] is None
    assert "37" in evidence[0]["content"]
    assert Path(record.path).read_bytes() == (root / "note.txt").read_bytes()
    assert jobs.latest(db, record.id)["state"] == "complete"
    assert len(catalog.changes()) >= 2


def test_unstable_writes_do_not_queue_partial_or_duplicate_work(folder):
    db, root, _, scan, _ = folder
    path = root / "note.txt"
    for text in ("first", "second", "third"):
        path.write_text(text)
        assert scan() == []
    (file_id,) = scan()
    assert scan() == []
    assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    assert Path(files.get_file(db, file_id).path).read_text() == "third"


def test_edit_preserves_id_and_historical_extraction(folder):
    db, root, _, scan, _ = folder
    first = discover(folder)
    old = SourceCatalog(db).freeze()
    (root / "note.txt").write_text("Changed number: 92.")
    assert scan() == []
    (file_id,) = scan()
    assert file_id == first.id
    second = ingest(db, file_id)
    assert first.content_hash != second.content_hash
    reader = EvidenceReader(db)
    with pytest.raises(SourceError, match="changed"):
        reader.read(file_id, first.content_hash, {"mode": "all"}, old)
    historical = reader.read(file_id, first.content_hash, {"mode": "all"}, old, historical=True)
    assert "37" in historical[0]["content"] and historical[0]["historical"]
    assert Path(first.path).read_bytes() != Path(second.path).read_bytes()
    assert db.execute("SELECT COUNT(*) FROM source_versions").fetchone()[0] == 2


def test_rename_uses_identity_copy_does_not_and_no_reembedding(folder):
    db, root, _, scan, _ = folder
    first = discover(folder)
    (root / "note.txt").rename(root / "renamed.txt")
    scan()
    assert scan() == []
    source = SourceCatalog(db).get(first.id)
    assert source["relative_path"] == "renamed.txt"
    assert jobs.latest(db, first.id)["attempt"] == 1
    (root / "copy.txt").write_bytes((root / "renamed.txt").read_bytes())
    scan()
    (copied,) = scan()
    assert copied != first.id


def test_unavailable_root_never_declares_sources_missing_and_reconnects(folder):
    db, root, root_id, scan, _ = folder
    first = discover(folder)
    moved = root.with_name("temporarily-unmounted")
    root.rename(moved)
    for _ in range(4):
        scan()
    assert root_record(db, root_id)["availability"] == "unavailable"
    assert SourceCatalog(db).get(first.id)["availability"] == "unavailable"
    assert not any(row["kind"] == "missing" for row in SourceCatalog(db).changes())
    moved.rename(root)
    assert scan() == []
    assert SourceCatalog(db).get(first.id)["availability"] == "available"


def test_missing_disconnect_pause_and_restart_catchup(folder):
    db, root, root_id, scan, _ = folder
    first = discover(folder)
    update_root(db, root_id, processing=False)
    (root / "second.txt").write_text("A source created while paused.")
    scan()
    assert scan() == []
    update_root(db, root_id, processing=True)
    (file_id,) = scan()
    ingest(db, file_id)
    (root / "note.txt").unlink()
    scan()
    scan()
    assert SourceCatalog(db).get(first.id)["availability"] == "missing"
    update_root(db, root_id, disconnect=True)
    assert (root / "second.txt").exists() and SourceCatalog(db).list_sources() == []
    register_root(db, root, "connected", reconnect_id=root_id)
    (root / "closed.txt").write_text("Created while the app was closed.")
    startup = FolderScanner(clock=lambda: 0)
    assert startup.scan_root(db, root_id) == []
    startup.clock = lambda: 3
    (new,) = startup.scan_root(db, root_id)
    assert new not in {first.id, file_id}


@pytest.mark.parametrize(
    "relative",
    [
        "../secret.txt",
        "/tmp/secret.txt",
        "a/../secret.txt",
        "a//b.txt",
        "link/secret.txt",
        "file-link.txt",
    ],
)
def test_path_traversal_and_links_cannot_read_originals(folder, relative):
    db, root, root_id, _, _ = folder
    secret = root.parent / "secret.txt"
    secret.write_text("outside")
    (root / "link").symlink_to(root.parent, target_is_directory=True)
    (root / "file-link.txt").symlink_to(secret)
    with pytest.raises(SourceError):
        read_original(root_record(db, root_id), relative)


def test_excludes_generated_temporary_and_app_data(folder):
    db, root, _, scan, _ = folder
    for name in (
        "wiki/sources/generated.md",
        "documents/report.txt",
        ".hidden.txt",
        "~draft.txt",
        "app-data/copied.txt",
        "logs/debug.txt",
        "qdrant/state.txt",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("must not ingest")
    scan()
    assert scan() == []
    assert SourceCatalog(db).list_sources() == []


def test_all_empty_chosen_and_frozen_inventory_cannot_expand(folder):
    db, root, _, scan, _ = folder
    first = discover(folder)
    catalog = SourceCatalog(db)
    frozen = catalog.freeze({"mode": "all"})
    (root / "later.txt").write_text("Later discovery cannot enlarge a running job.")
    scan()
    (second,) = scan()
    ingest(db, second)
    assert catalog.list_sources({"mode": "empty"}) == []
    assert len(catalog.list_sources({"mode": "chosen", "source_ids": [first.id]})) == 1
    with pytest.raises(SourceError):
        catalog.assert_allowed(second, {"mode": "all"}, frozen)
    with pytest.raises(SourceError):
        catalog.assert_allowed(first.id, {"mode": "empty"})


