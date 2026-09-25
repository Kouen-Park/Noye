"""Tests for the index status endpoint."""

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
from app.services import integrity
from app.services.indexing import IndexingError
from app.services.integrity import hash_file

CURRENT_MODEL = "embeddinggemma"
OLD_MODEL = "nomic-embed-text"


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    connection = connect(tmp_path / "t.db")
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def client(db: sqlite3.Connection) -> TestClient:
    app.dependency_overrides[index_api.get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_ready(
    db: sqlite3.Connection,
    tmp_path: Path,
    *,
    name: str,
    model: str | None = CURRENT_MODEL,
    chunks: int = 3,
) -> file_store.File:
    source = tmp_path / name
    source.write_text(f"# {name}\n\nIndexed text.\n", encoding="utf-8")
    record = file_store.create_file(
        db,
        name=name,
        file_type=FileType.MARKDOWN,
        path=str(source),
        size=source.stat().st_size,
        content_hash=hash_file(source),
    )
    file_store.set_counts(db, record.id, chunk_count=chunks)
    if model is not None:
        file_store.set_embedding_model(db, record.id, model)
    return file_store.set_status(db, record.id, FileStatus.READY)


class TestStatus:
    def test_an_empty_library_is_sound(self, client):
        body = client.get("/index/status").json()

        assert body["ready_files"] == 0
        assert body["searchable_files"] == 0
        assert body["problems"] == []
        assert body["deep"] is False
        assert body["point_check_complete"] is False

    def test_a_sound_library_lists_no_problems(self, client, db, tmp_path):
        """Only problems are listed.

        Returning every file with an empty problem list would make the response grow
        with the library while saying nothing.
        """
        add_ready(db, tmp_path, name="a.md")
        add_ready(db, tmp_path, name="b.md")

        body = client.get("/index/status").json()

        assert body["ready_files"] == 2
        assert body["searchable_files"] == 2
        assert body["problems"] == []

    def test_names_the_model_a_file_must_match(self, client):
        """So a person can see what their files are being compared against."""
        assert client.get("/index/status").json()["embedding_model"] == CURRENT_MODEL

    def test_reports_a_model_mismatch_and_drops_it_from_searchable(
        self, client, db, tmp_path
    ):
        add_ready(db, tmp_path, name="good.md", model=CURRENT_MODEL)
        stale = add_ready(db, tmp_path, name="stale.md", model=OLD_MODEL)

        body = client.get("/index/status").json()

        assert body["ready_files"] == 2
        assert body["searchable_files"] == 1
        assert len(body["problems"]) == 1
        problem = body["problems"][0]
        assert problem["file_id"] == stale.id
        assert problem["file_name"] == "stale.md"
        assert problem["problems"] == ["MODEL_CHANGED"]
        assert problem["searchable"] is False

    def test_reports_a_changed_source_but_keeps_it_searchable(
        self, client, db, tmp_path
    ):
        record = add_ready(db, tmp_path, name="edited.md")
        (tmp_path / "edited.md").write_text("# Changed on disk\n", encoding="utf-8")

        body = client.get("/index/status").json()

        assert body["searchable_files"] == 1
        problem = body["problems"][0]
        assert problem["problems"] == ["SOURCE_CHANGED"]
        assert problem["searchable"] is True
        assert problem["file_id"] == record.id

    def test_reports_both_problems_on_one_file(self, client, db, tmp_path):
        """They are independent, so a file can have both and needs both fixed."""
        add_ready(db, tmp_path, name="bad.md", model=OLD_MODEL)
        (tmp_path / "bad.md").write_text("# Changed too\n", encoding="utf-8")

        problems = client.get("/index/status").json()["problems"][0]["problems"]

        assert set(problems) == {"SOURCE_CHANGED", "MODEL_CHANGED"}


class TestDeepCheck:
    def test_is_off_by_default(self, client, db, tmp_path, monkeypatch):
        called = []
        monkeypatch.setattr(
            integrity, "count_chunks", lambda *a, **kw: called.append(1) or 0
        )
        add_ready(db, tmp_path, name="a.md")

        body = client.get("/index/status").json()

        assert called == []
        assert body["problems"] == []
        assert body["problems"] == []

    def test_reports_a_short_point_count(self, client, db, tmp_path, monkeypatch):
        monkeypatch.setattr(integrity, "count_chunks", lambda *a, **kw: 1)
        add_ready(db, tmp_path, name="a.md", chunks=5)

        body = client.get("/index/status", params={"deep": "true"}).json()

        assert body["deep"] is True
        assert body["point_check_complete"] is True
        problem = body["problems"][0]
        assert problem["problems"] == ["POINTS_MISSING"]
        assert problem["indexed_points"] == 1
        assert problem["expected_points"] == 5

    def test_an_unreachable_index_reports_no_problem(
        self, client, db, tmp_path, monkeypatch
    ):
        """Qdrant being off is not a damaged library.

        This is the most likely real-world case, and sending the user to re-index
        would be the wrong instruction as well as an alarming one.
        """

        def unreachable(*args, **kwargs):
            raise IndexingError("connection refused")

        monkeypatch.setattr(integrity, "count_chunks", unreachable)
        add_ready(db, tmp_path, name="a.md", chunks=5)

        body = client.get("/index/status", params={"deep": "true"}).json()

        assert body["problems"] == []
        assert body["searchable_files"] == 1
        assert body["point_check_complete"] is False

    def test_a_point_count_above_the_chunk_count_is_not_a_problem(
        self, client, db, tmp_path, monkeypatch
    ):
        """Extra points are not a missing index.

        They would mean leftovers from an earlier run, which re-ingestion clears
        anyway, and calling it POINTS_MISSING would be plainly wrong.
        """
        monkeypatch.setattr(integrity, "count_chunks", lambda *a, **kw: 9)
        add_ready(db, tmp_path, name="a.md", chunks=5)

        body = client.get("/index/status", params={"deep": "true"}).json()

        assert body["problems"] == []
        assert body["point_check_complete"] is True
