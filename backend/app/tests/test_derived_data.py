"""Derived cleanup cannot lose originals, stable IDs, evidence, or authored Wiki revisions."""

import pytest

from app.db import wiki as store
from app.models.wiki import EditWiki
from app.services import derived_data, ingestion
from app.services.folders import SourceError, update_root
from app.services.source_catalog import SourceCatalog
from app.services.wiki import service
from app.tests.test_folder_foundation import discover, folder
from app.tests.test_wiki_integration import generate, workspace


def test_paused_derived_removal_preserves_bytes_identity_versions_and_user_edits(
    workspace, monkeypatch
):
    db, root, root_id, *_ = workspace
    record = discover(workspace)
    page = generate(db, record.id)
    service.edit(
        db,
        page["wiki_id"],
        EditWiki(
            expected_revision=page["revision_id"],
            title="Authored",
            content="User edit preserved exactly.",
        ),
    )
    before = (root / "note.txt").read_bytes()
    calls = []
    monkeypatch.setattr(
        derived_data, "delete_file_chunks", lambda identifier: calls.append(identifier)
    )
    with pytest.raises(SourceError, match="Pause"):
        derived_data.remove_source_index(db, record.id)
    assert not calls
    update_root(db, root_id, processing=False)
    with ingestion.read_access([record.id]):
        with pytest.raises(ingestion.AlreadyIngesting):
            derived_data.remove_source_index(db, record.id)
    assert not calls
    result = derived_data.remove_source_index(db, record.id)
    assert result["original_preserved"] and result["history_preserved"]
    assert calls == [record.id] and (root / "note.txt").read_bytes() == before
    assert SourceCatalog(db).get(record.id)["version"] == record.content_hash
    assert db.execute("SELECT COUNT(*) FROM source_versions").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM source_passages").fetchone()[0] > 0
    assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    revision = store.revision(db, store.page(db, page["wiki_id"])["current_revision"])
    assert revision["origin"] == "user" and revision["content"] == "User edit preserved exactly."


def test_index_failure_leaves_registry_and_authored_data_unchanged(workspace, monkeypatch):
    from app.services.indexing import IndexingError

    db, root, root_id, *_ = workspace
    record = discover(workspace)
    update_root(db, root_id, processing=False)

    def unavailable(*args):
        raise IndexingError("Derived index is unreachable")

    monkeypatch.setattr(derived_data, "delete_file_chunks", unavailable)
    with pytest.raises(IndexingError):
        derived_data.remove_source_index(db, record.id)
    assert db.execute("SELECT status FROM files").fetchone()[0] == "READY"
    assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] > 0
    assert not ingestion.is_ingesting(record.id)
    assert (root / "note.txt").exists()


def test_rebuild_respects_disconnected_and_paused_folder_controls(workspace):
    from contextlib import closing

    from qdrant_client import QdrantClient

    from app.services.rebuild import plan_rebuild

    db, _, root_id, *_ = workspace
    record = discover(workspace)
    update_root(db, root_id, processing=False)
    with closing(QdrantClient(":memory:")) as client:
        try:
            plan = plan_rebuild(db, client=client)
            assert plan.file_ids == ()
            assert any(
                item.file_id == record.id and "disabled" in item.reason for item in plan.skipped
            )
        finally:
            ingestion.end_rebuild()
