"""Tests for rebuilding the index from the originals on disk.

The assertion that carries the branch is that the collection is **not** dropped in the
ordinary case. Dropping first is the obvious implementation, returns the same 202, and
is only distinguishable by checking that `recreate_collection` was never called — so a
test that reads the response cannot tell the safe version from the dangerous one.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import index as index_api
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.main import app
from app.models.files import FileStatus, FileType
from app.services import ingestion, rebuild
from app.services.indexing import IndexingError

CONFIGURED_DIM = 768


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    connection = connect(tmp_path / "t.db")
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def queued() -> list[str]:
    """File ids handed to the background task."""
    return []


@pytest.fixture
def recreated() -> list[int]:
    """Records every call to recreate_collection, so 'never' is assertable."""
    return []


@pytest.fixture
def client(
    db: sqlite3.Connection,
    queued: list[str],
    recreated: list[int],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setattr(index_api, "ingest_in_background", queued.append)
    monkeypatch.setattr(rebuild, "recreate_collection", lambda *a, **kw: recreated.append(1))
    # Matching width by default: the ordinary case, where nothing must be dropped.
    monkeypatch.setattr(rebuild, "collection_vector_size", lambda *a, **kw: CONFIGURED_DIM)

    app.dependency_overrides[index_api.get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    for file_id in queued:
        ingestion.release_file(file_id)
    app.dependency_overrides.clear()


def add_file(
    db: sqlite3.Connection,
    tmp_path: Path,
    *,
    name: str,
    on_disk: bool = True,
    status: FileStatus = FileStatus.READY,
    chunks: int = 4,
) -> file_store.File:
    source = tmp_path / name
    if on_disk:
        source.write_text(f"# {name}\n\nText.\n", encoding="utf-8")
    record = file_store.create_file(
        db,
        name=name,
        file_type=FileType.MARKDOWN,
        path=str(source),
        size=32,
        content_hash="a" * 64,
    )
    file_store.set_counts(db, record.id, chunk_count=chunks)
    file_store.set_embedding_model(db, record.id, "embeddinggemma")
    return file_store.set_status(
        db, record.id, status, error="x" if status is FileStatus.FAILED else None
    )


class TestTheOrdinaryRebuild:
    def test_does_not_drop_the_collection(self, client, db, tmp_path, recreated):
        """The decision the module exists to make.

        Dropping first returns the same 202 and leaves the user with no index at all
        if re-embedding then fails part-way — where before they had a stale index that
        still answered. A stale answer beats no answer.
        """
        add_file(db, tmp_path, name="a.md")

        response = client.post("/index/rebuild")

        assert response.status_code == 202
        assert recreated == []
        assert response.json()["collection_recreated"] is False

    def test_queues_every_file_with_a_source(self, client, db, tmp_path, queued):
        add_file(db, tmp_path, name="a.md")
        add_file(db, tmp_path, name="b.md")

        body = client.post("/index/rebuild").json()

        assert body["queued"] == 2
        assert len(queued) == 2

    def test_resets_each_file_to_the_start_of_the_pipeline(self, client, db, tmp_path):
        record = add_file(db, tmp_path, name="a.md", chunks=9)

        client.post("/index/rebuild")

        refreshed = file_store.get_file(db, record.id)
        assert refreshed.status is FileStatus.UPLOADING
        assert refreshed.chunk_count == 0

    def test_reports_the_model_the_new_vectors_will_come_from(self, client, db, tmp_path):
        add_file(db, tmp_path, name="a.md")

        assert client.post("/index/rebuild").json()["embedding_model"] == "embeddinggemma"

    def test_rebuilds_a_failed_file_too(self, client, db, tmp_path, queued):
        """A FAILED file is exactly what a rebuild is for.

        Its source is still there, and whatever broke — Ollama down, Qdrant down —
        may well be fixed now.
        """
        record = add_file(db, tmp_path, name="broken.md", status=FileStatus.FAILED)

        client.post("/index/rebuild")

        assert queued == [record.id]

    def test_an_empty_library_queues_nothing(self, client):
        body = client.post("/index/rebuild").json()

        assert body["queued"] == 0
        assert body["skipped"] == []


class TestSkipping:
    def test_skips_a_file_whose_original_is_gone(self, client, db, tmp_path, queued):
        """Its existing vectors are still the best record of a document the user
        no longer has on disk, so this is a skip rather than a failure."""
        record = add_file(db, tmp_path, name="lost.md", on_disk=False)

        body = client.post("/index/rebuild").json()

        assert queued == []
        assert body["queued"] == 0
        assert body["skipped"] == [
            {
                "file_id": record.id,
                "file_name": "lost.md",
                "reason": "The original file is missing from disk.",
            }
        ]

    def test_skips_a_file_already_being_processed(self, client, db, tmp_path, queued):
        record = add_file(db, tmp_path, name="busy.md")
        ingestion.reserve_ingestion(record.id)
        try:
            body = client.post("/index/rebuild").json()
        finally:
            ingestion.release_file(record.id)

        assert queued == []
        assert body["skipped"][0]["reason"] == "Already being processed."

    def test_skipping_one_does_not_stop_the_others(self, client, db, tmp_path, queued):
        add_file(db, tmp_path, name="lost.md", on_disk=False)
        good = add_file(db, tmp_path, name="fine.md")

        body = client.post("/index/rebuild").json()

        assert queued == [good.id]
        assert body["queued"] == 1
        assert len(body["skipped"]) == 1


class TestADimensionChange:
    def test_recreates_the_collection_when_the_width_disagrees(
        self, client, db, tmp_path, recreated, monkeypatch
    ):
        """The one case where there is nothing to preserve.

        A collection created for 768-wide vectors cannot accept 1024-wide ones, so the
        old points are unusable by definition.
        """
        monkeypatch.setattr(rebuild, "collection_vector_size", lambda *a, **kw: 1024)
        add_file(db, tmp_path, name="a.md")

        body = client.post("/index/rebuild").json()

        assert recreated == [1]
        assert body["collection_recreated"] is True
        assert body["queued"] == 1

    def test_does_not_recreate_a_collection_that_does_not_exist_yet(
        self, client, db, tmp_path, recreated, monkeypatch
    ):
        """Nothing to recreate before the first ingestion; ingestion creates it."""
        monkeypatch.setattr(rebuild, "collection_vector_size", lambda *a, **kw: None)
        add_file(db, tmp_path, name="a.md")

        body = client.post("/index/rebuild").json()

        assert recreated == []
        assert body["collection_recreated"] is False


class TestAnUnreachableIndex:
    def test_reports_503_rather_than_starting(self, client, db, tmp_path, monkeypatch, queued):
        """Queueing work that cannot possibly succeed would set every file back to
        UPLOADING and then fail each one, which is worse than refusing."""

        def unreachable(*args, **kwargs):
            raise IndexingError("connection refused")

        monkeypatch.setattr(rebuild, "collection_vector_size", unreachable)
        record = add_file(db, tmp_path, name="a.md")

        response = client.post("/index/rebuild")

        assert response.status_code == 503
        assert "Could not reach the index" in response.json()["detail"]
        assert queued == []
        # And the file is untouched, not left mid-reset.
        assert file_store.get_file(db, record.id).status is FileStatus.READY


class TestNeedsRecreation:
    def test_true_only_for_a_real_disagreement(self, monkeypatch):
        monkeypatch.setattr(rebuild, "collection_vector_size", lambda *a, **kw: 1024)
        assert rebuild.needs_recreation() is True

        monkeypatch.setattr(
            rebuild, "collection_vector_size", lambda *a, **kw: CONFIGURED_DIM
        )
        assert rebuild.needs_recreation() is False

    def test_false_when_there_is_no_collection(self, monkeypatch):
        monkeypatch.setattr(rebuild, "collection_vector_size", lambda *a, **kw: None)
        assert rebuild.needs_recreation() is False
