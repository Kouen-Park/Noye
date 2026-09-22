"""Tests for the files API.

Most tests override the database dependency with a temporary SQLite file,
redirect uploads to a temp directory, and stub the background ingestion, so the
HTTP contract is tested without touching the user's real data or services. The
integration test at the bottom runs the genuine path — real background
ingestion, real Ollama, real Qdrant — and cleans up after itself.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.api import files as files_api
from app.config import get_settings
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.main import app
from app.models.files import FileStatus, FileType


def write_pdf(path: Path, page_texts: list[str]) -> Path:
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 700), text, fontsize=11)
    document.save(path)
    document.close()
    return path


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def db(db_file: Path) -> sqlite3.Connection:
    connection = connect(db_file)
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def scheduled() -> list[str]:
    """File ids handed to the background task."""
    return []


@pytest.fixture
def client(
    db: sqlite3.Connection,
    tmp_path: Path,
    scheduled: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    uploads = tmp_path / "sources"
    uploads.mkdir()
    monkeypatch.setattr(files_api, "sources_dir", lambda: uploads)
    monkeypatch.setattr(files_api, "_ingest_in_background", scheduled.append)
    monkeypatch.setattr(files_api, "delete_file_chunks", lambda file_id, **kwargs: None)

    app.dependency_overrides[files_api.get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def upload(client: TestClient, name: str = "doc.pdf", content: bytes | None = None, tmp_path: Path | None = None):
    if content is None:
        assert tmp_path is not None
        content = write_pdf(tmp_path / f"src-{name}", ["Some page text about graphs."]).read_bytes()
    return client.post("/files", files={"file": (name, content, "application/pdf")})


# --- health ------------------------------------------------------------------


def test_health_still_works(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


# --- upload ------------------------------------------------------------------


def test_upload_returns_201_with_the_file_uploading(client, tmp_path) -> None:
    response = upload(client, tmp_path=tmp_path)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "doc.pdf"
    assert body["file_type"] == FileType.PDF.value
    assert body["status"] == FileStatus.UPLOADING.value
    assert body["size"] > 0
    assert body["error"] is None
    assert body["chunk_count"] == 0


def test_upload_creates_a_row(client, db, tmp_path) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]

    assert file_store.get_file(db, file_id).name == "doc.pdf"


def test_upload_saves_the_original_on_disk(client, db, tmp_path) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]

    stored = Path(file_store.get_file(db, file_id).path)
    assert stored.exists()
    # Prefixed with the id so two uploads of one filename cannot collide.
    assert stored.name.startswith(file_id)
    assert stored.name.endswith("doc.pdf")


def test_upload_schedules_ingestion(client, scheduled, tmp_path) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]

    assert scheduled == [file_id]


def test_response_does_not_leak_the_server_path(client, tmp_path) -> None:
    body = upload(client, tmp_path=tmp_path).json()

    assert "path" not in body


def test_same_filename_twice_does_not_overwrite(client, db, tmp_path) -> None:
    first = upload(client, tmp_path=tmp_path).json()["id"]
    second = upload(client, tmp_path=tmp_path).json()["id"]

    paths = {file_store.get_file(db, first).path, file_store.get_file(db, second).path}
    assert len(paths) == 2
    assert all(Path(p).exists() for p in paths)
    assert len(file_store.list_files(db)) == 2


@pytest.mark.parametrize("name", ["archive.zip", "photo.png", "script.py", "noextension"])
def test_unsupported_type_is_rejected(client, name: str) -> None:
    response = client.post("/files", files={"file": (name, b"some bytes", "application/octet-stream")})

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_unsupported_type_creates_nothing(client, db, tmp_path) -> None:
    client.post("/files", files={"file": ("bad.zip", b"bytes", "application/zip")})

    assert file_store.list_files(db) == []
    assert list((tmp_path / "sources").iterdir()) == []


def test_empty_upload_is_rejected(client, db, tmp_path) -> None:
    response = client.post("/files", files={"file": ("empty.pdf", b"", "application/pdf")})

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
    # No row, and nothing left behind on disk.
    assert file_store.list_files(db) == []
    assert list((tmp_path / "sources").iterdir()) == []


def test_markdown_is_accepted(client) -> None:
    response = client.post("/files", files={"file": ("notes.md", b"# Notes\n", "text/markdown")})

    assert response.status_code == 201
    assert response.json()["file_type"] == FileType.MARKDOWN.value


def test_text_file_is_accepted(client) -> None:
    response = client.post("/files", files={"file": ("log.txt", b"Plain text.\n", "text/plain")})

    assert response.status_code == 201
    assert response.json()["file_type"] == FileType.TEXT.value


# --- list and read -----------------------------------------------------------


def test_list_is_empty_initially(client) -> None:
    assert client.get("/files").json() == []


def test_list_returns_every_file(client, tmp_path) -> None:
    upload(client, "one.pdf", tmp_path=tmp_path)
    upload(client, "two.pdf", tmp_path=tmp_path)

    names = {item["name"] for item in client.get("/files").json()}

    assert names == {"one.pdf", "two.pdf"}


def test_get_one_file(client, tmp_path) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]

    response = client.get(f"/files/{file_id}")

    assert response.status_code == 200
    assert response.json()["id"] == file_id


def test_get_unknown_file_is_404(client) -> None:
    response = client.get("/files/does-not-exist")

    assert response.status_code == 404
    assert "No file with id" in response.json()["detail"]


def test_polling_reflects_pipeline_progress(client, db, tmp_path) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]

    # Stand in for the background task advancing the file.
    file_store.set_status(db, file_id, FileStatus.EMBEDDING)
    assert client.get(f"/files/{file_id}").json()["status"] == "EMBEDDING"

    file_store.set_counts(db, file_id, page_count=3, chunk_count=7)
    file_store.set_status(db, file_id, FileStatus.READY)
    body = client.get(f"/files/{file_id}").json()

    assert body["status"] == "READY"
    assert body["page_count"] == 3
    assert body["chunk_count"] == 7


def test_polling_surfaces_the_failure_reason(client, db, tmp_path) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]
    file_store.set_status(db, file_id, FileStatus.FAILED, error="No extractable text found.")

    body = client.get(f"/files/{file_id}").json()

    assert body["status"] == "FAILED"
    assert body["error"] == "No extractable text found."


# --- delete ------------------------------------------------------------------


def test_delete_removes_row_and_original(client, db, tmp_path) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]
    stored = Path(file_store.get_file(db, file_id).path)

    response = client.delete(f"/files/{file_id}")

    assert response.status_code == 204
    assert not stored.exists()
    with pytest.raises(file_store.FileRecordNotFound):
        file_store.get_file(db, file_id)


def test_delete_removes_the_vectors(client, tmp_path, monkeypatch) -> None:
    removed: list[str] = []
    monkeypatch.setattr(files_api, "delete_file_chunks", lambda file_id, **kw: removed.append(file_id))
    file_id = upload(client, tmp_path=tmp_path).json()["id"]

    client.delete(f"/files/{file_id}")

    assert removed == [file_id]


def test_delete_leaves_other_files_alone(client, db, tmp_path) -> None:
    keep = upload(client, "keep.pdf", tmp_path=tmp_path).json()["id"]
    remove = upload(client, "remove.pdf", tmp_path=tmp_path).json()["id"]
    kept_path = Path(file_store.get_file(db, keep).path)

    client.delete(f"/files/{remove}")

    remaining = [f.id for f in file_store.list_files(db)]
    assert remaining == [keep]
    assert kept_path.exists()


def test_delete_unknown_file_is_404(client) -> None:
    assert client.delete("/files/nope").status_code == 404


def test_delete_keeps_everything_when_vectors_cannot_be_removed(
    client, db, tmp_path, monkeypatch
) -> None:
    from app.services.indexing import IndexingError

    file_id = upload(client, tmp_path=tmp_path).json()["id"]
    stored = Path(file_store.get_file(db, file_id).path)

    def failing(file_id: str, **kwargs):
        raise IndexingError("Qdrant is unreachable")

    monkeypatch.setattr(files_api, "delete_file_chunks", failing)
    response = client.delete(f"/files/{file_id}")

    assert response.status_code == 503
    assert "nothing was deleted" in response.json()["detail"]
    # A half-deleted source whose vectors survive would keep answering questions.
    assert stored.exists()
    assert file_store.get_file(db, file_id).id == file_id


def test_delete_tolerates_an_already_missing_original(client, db, tmp_path) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]
    Path(file_store.get_file(db, file_id).path).unlink()

    assert client.delete(f"/files/{file_id}").status_code == 204


# --- CORS --------------------------------------------------------------------


def test_allowed_origin_gets_cors_headers(client) -> None:
    response = client.get("/files", headers={"Origin": "http://localhost:3000"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_preflight_is_answered_for_the_frontend(client) -> None:
    response = client.options(
        "/files",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]


def test_unknown_origin_gets_no_cors_headers(client) -> None:
    response = client.get("/files", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


# --- integration: the real upload path ---------------------------------------


def service_is_up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=5.0).status_code == 200
    except httpx.RequestError:
        return False


requires_services = pytest.mark.skipif(
    not (
        service_is_up(f"{get_settings().ollama_base_url}/api/version")
        and service_is_up(f"{get_settings().qdrant_url}/")
    ),
    reason="Ollama or Qdrant is not running",
)


@requires_services
def test_real_upload_ingests_and_becomes_ready(tmp_path: Path) -> None:
    """Upload through HTTP and let the real background task process it.

    Uses the real database, sources directory and services — the only way to
    exercise the path a user actually takes — then deletes the file through the
    API so nothing is left behind.
    """
    pdf = write_pdf(
        tmp_path / "api-integration.pdf",
        [
            "Chapter one introduces graphs in general terms.",
            "Dijkstra's algorithm selects the unvisited vertex whose distance "
            "estimate is smallest, drawn from a priority queue.",
        ],
    )

    file_id = None
    with TestClient(app) as client:
        try:
            response = client.post(
                "/files",
                files={"file": ("api-integration.pdf", pdf.read_bytes(), "application/pdf")},
            )
            assert response.status_code == 201
            file_id = response.json()["id"]

            # TestClient runs background tasks before returning, so by now the
            # pipeline has finished.
            body = client.get(f"/files/{file_id}").json()
            assert body["status"] == "READY", body["error"]
            assert body["page_count"] == 2
            assert body["chunk_count"] > 0
        finally:
            if file_id:
                assert client.delete(f"/files/{file_id}").status_code == 204
                assert client.get(f"/files/{file_id}").status_code == 404
