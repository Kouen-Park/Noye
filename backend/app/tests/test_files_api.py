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
from app.services import ingestion


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
def uploads(tmp_path: Path) -> Path:
    """Where uploads land during a test, in place of the real sources dir."""
    directory = tmp_path / "sources"
    directory.mkdir()
    return directory


@pytest.fixture
def client(
    db: sqlite3.Connection,
    uploads: Path,
    scheduled: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setattr(files_api, "sources_dir", lambda: uploads)
    monkeypatch.setattr(files_api, "_ingest_in_background", scheduled.append)
    monkeypatch.setattr(files_api, "delete_file_chunks", lambda file_id, **kwargs: None)

    app.dependency_overrides[files_api.get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    for file_id in scheduled:
        ingestion.release_file(file_id)
    app.dependency_overrides.clear()


def finish_scheduled(db: sqlite3.Connection, file_id: str) -> None:
    """The test's background stub records the task without running it."""
    ingestion.release_file(file_id)
    file_store.set_status(db, file_id, FileStatus.READY)


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
    finish_scheduled(db, file_id)
    stored = Path(file_store.get_file(db, file_id).path)

    response = client.delete(f"/files/{file_id}")

    assert response.status_code == 204
    assert not stored.exists()
    with pytest.raises(file_store.FileRecordNotFound):
        file_store.get_file(db, file_id)


def test_delete_removes_the_vectors(client, db, tmp_path, monkeypatch) -> None:
    removed: list[str] = []
    monkeypatch.setattr(files_api, "delete_file_chunks", lambda file_id, **kw: removed.append(file_id))
    file_id = upload(client, tmp_path=tmp_path).json()["id"]
    finish_scheduled(db, file_id)

    client.delete(f"/files/{file_id}")

    assert removed == [file_id]


def test_delete_leaves_other_files_alone(client, db, tmp_path) -> None:
    keep = upload(client, "keep.pdf", tmp_path=tmp_path).json()["id"]
    remove = upload(client, "remove.pdf", tmp_path=tmp_path).json()["id"]
    finish_scheduled(db, remove)
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
    finish_scheduled(db, file_id)
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
    finish_scheduled(db, file_id)
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


# --- re-ingesting ------------------------------------------------------------


def make_stored_file(
    db: sqlite3.Connection,
    uploads: Path,
    *,
    status: FileStatus = FileStatus.FAILED,
    error: str | None = "No extractable text found.",
    name: str = "doc.pdf",
) -> str:
    """A file row whose original really is on disk, in the given state."""
    file_id = file_store.new_file_id()
    path = uploads / f"{file_id}__{name}"
    write_pdf(path, ["Dijkstra picks the smallest distance estimate."])
    file_store.create_file(
        db,
        name=name,
        file_type=FileType.PDF,
        path=str(path),
        size=path.stat().st_size,
        file_id=file_id,
    )
    file_store.set_status(db, file_id, status, error=error)
    return file_id


def test_reingest_accepts_a_failed_file(client, db, uploads, scheduled) -> None:
    file_id = make_stored_file(db, uploads)

    response = client.post(f"/files/{file_id}/reingest")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "UPLOADING"
    assert body["error"] is None
    assert scheduled == [file_id]


def test_reingest_clears_the_previous_runs_counts(client, db, uploads) -> None:
    file_id = make_stored_file(db, uploads)
    file_store.set_counts(db, file_id, page_count=9, chunk_count=30)

    body = client.post(f"/files/{file_id}/reingest").json()

    assert body["page_count"] is None
    assert body["chunk_count"] == 0


def test_reingest_is_allowed_on_a_ready_file(client, db, uploads, scheduled) -> None:
    """Re-indexing after a chunking change is the same operation."""
    file_id = make_stored_file(db, uploads, status=FileStatus.READY, error=None)

    response = client.post(f"/files/{file_id}/reingest")

    assert response.status_code == 202
    assert scheduled == [file_id]


def test_reingest_of_an_unknown_file_is_404(client) -> None:
    response = client.post("/files/does-not-exist/reingest")
    assert response.status_code == 404


def test_reingest_is_refused_while_the_file_is_being_processed(
    client, db, uploads, scheduled, monkeypatch
) -> None:
    file_id = make_stored_file(db, uploads)
    ingestion.reserve_ingestion(file_id)

    response = client.post(f"/files/{file_id}/reingest")

    assert response.status_code == 409
    assert "already being processed" in response.json()["detail"]
    assert scheduled == []
    ingestion.release_file(file_id)


def test_reingest_is_refused_when_the_original_is_gone(
    client, db, uploads, scheduled
) -> None:
    """Everything else is derived from the original, so without it there is
    nothing to re-read."""
    file_id = make_stored_file(db, uploads)
    Path(file_store.get_file(db, file_id).path).unlink()

    response = client.post(f"/files/{file_id}/reingest")

    assert response.status_code == 409
    assert "missing from disk" in response.json()["detail"]
    assert scheduled == []


def test_reingest_leaves_a_refused_file_untouched(client, db, uploads) -> None:
    file_id = make_stored_file(db, uploads)
    file_store.set_counts(db, file_id, page_count=4, chunk_count=11)
    Path(file_store.get_file(db, file_id).path).unlink()

    client.post(f"/files/{file_id}/reingest")

    record = file_store.get_file(db, file_id)
    assert record.status is FileStatus.FAILED
    assert record.chunk_count == 11
    assert record.page_count == 4


def test_reingest_appears_in_the_openapi_schema(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/files/{file_id}/reingest" in paths
    assert "post" in paths["/files/{file_id}/reingest"]


def test_delete_refuses_a_queued_ingestion(client, db, tmp_path) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]
    original = Path(file_store.get_file(db, file_id).path)

    response = client.delete(f"/files/{file_id}")

    assert response.status_code == 409
    assert original.exists()
    assert file_store.get_file(db, file_id).id == file_id


def test_cancel_stops_a_queued_ingestion_and_allows_retry(
    client, db, tmp_path, monkeypatch
) -> None:
    file_id = upload(client, tmp_path=tmp_path).json()["id"]
    monkeypatch.setattr(ingestion, "delete_file_chunks", lambda *args, **kwargs: None)

    response = client.post(f"/files/{file_id}/cancel")
    assert response.status_code == 202
    assert client.delete(f"/files/{file_id}").status_code == 409

    stopped = ingestion.ingest_file(db, file_id, reserved=True)
    assert stopped.status is FileStatus.FAILED
    assert stopped.error == "Processing was cancelled."
    assert ingestion.is_ingesting(file_id) is False
    assert client.post(f"/files/{file_id}/reingest").status_code == 202


def test_cancel_idle_file_is_conflict(client, db, uploads) -> None:
    file_id = make_stored_file(db, uploads)
    assert client.post(f"/files/{file_id}/cancel").status_code == 409


def test_orphaned_processing_row_can_be_stopped_then_deleted(client, db, uploads, monkeypatch) -> None:
    file_id = make_stored_file(db, uploads, status=FileStatus.EMBEDDING, error=None)
    monkeypatch.setattr(ingestion, "delete_file_chunks", lambda *args, **kwargs: None)
    assert client.delete(f"/files/{file_id}").status_code == 409
    response = client.post(f"/files/{file_id}/cancel")
    assert response.status_code == 202
    assert response.json()["status"] == "FAILED"
    assert response.json()["error"] == "Processing was interrupted."
    assert client.delete(f"/files/{file_id}").status_code == 204


def test_second_reingest_is_refused_before_background_start(client, db, uploads) -> None:
    file_id = make_stored_file(db, uploads)
    assert client.post(f"/files/{file_id}/reingest").status_code == 202
    assert client.post(f"/files/{file_id}/reingest").status_code == 409


# --- serving the original source --------------------------------------------


def store_source(
    db: sqlite3.Connection,
    uploads: Path,
    *,
    name: str,
    file_type: FileType,
    body: bytes,
) -> str:
    """A file row whose original really is on disk, in the uploads directory."""
    file_id = file_store.new_file_id()
    path = uploads / f"{file_id}__{name}"
    path.write_bytes(body)
    file_store.create_file(
        db,
        name=name,
        file_type=file_type,
        path=str(path),
        size=path.stat().st_size,
        file_id=file_id,
    )
    return file_id


def test_source_serves_a_pdf_for_the_browser_viewer(client, db, uploads, tmp_path) -> None:
    """Inline with the PDF type, so `#page=N` from a citation lands correctly."""
    pdf = write_pdf(tmp_path / "src.pdf", ["Page one about graphs."])
    file_id = store_source(
        db, uploads, name="lecture.pdf", file_type=FileType.PDF, body=pdf.read_bytes()
    )

    response = client.get(f"/files/{file_id}/source")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_source_names_the_file_as_the_user_knows_it(client, db, uploads, tmp_path) -> None:
    """Not the `{id}__{name}` form used on disk."""
    pdf = write_pdf(tmp_path / "src.pdf", ["Text."])
    file_id = store_source(
        db, uploads, name="lecture.pdf", file_type=FileType.PDF, body=pdf.read_bytes()
    )

    disposition = client.get(f"/files/{file_id}/source").headers["content-disposition"]

    assert "lecture.pdf" in disposition
    assert file_id not in disposition


def test_source_serves_markdown_as_readable_text(client, db, uploads) -> None:
    """text/markdown downloads in browsers instead of displaying."""
    file_id = store_source(
        db,
        uploads,
        name="notes.md",
        file_type=FileType.MARKDOWN,
        body=b"# Shortest paths\n\nDijkstra uses a priority queue.\n",
    )

    response = client.get(f"/files/{file_id}/source")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert "priority queue" in response.text


def test_source_serves_plain_text(client, db, uploads) -> None:
    file_id = store_source(
        db, uploads, name="log.txt", file_type=FileType.TEXT, body=b"Meeting notes.\n"
    )

    response = client.get(f"/files/{file_id}/source")

    assert response.status_code == 200
    assert response.text == "Meeting notes.\n"


def test_source_preserves_non_ascii_content(client, db, uploads) -> None:
    file_id = store_source(
        db,
        uploads,
        name="한글.md",
        file_type=FileType.MARKDOWN,
        body="# 최단 경로\n\n우선순위 큐를 사용한다.\n".encode(),
    )

    response = client.get(f"/files/{file_id}/source")

    assert response.status_code == 200
    assert "우선순위 큐" in response.text


def test_source_of_an_unknown_file_is_404(client) -> None:
    assert client.get("/files/not-a-real-id/source").status_code == 404


def test_source_is_404_when_the_original_is_gone(client, db, uploads) -> None:
    file_id = store_source(
        db, uploads, name="notes.md", file_type=FileType.MARKDOWN, body=b"text"
    )
    Path(file_store.get_file(db, file_id).path).unlink()

    response = client.get(f"/files/{file_id}/source")

    assert response.status_code == 404
    assert "no longer on disk" in response.json()["detail"]


def test_source_refuses_a_row_pointing_outside_the_sources_directory(
    client, db, uploads, tmp_path
) -> None:
    """The row is written by this app, so a path outside means a tampered or
    corrupted database — and serving it would turn an id into a file read."""
    outside = tmp_path / "secret.txt"
    outside.write_text("not for serving", encoding="utf-8")
    file_id = file_store.new_file_id()
    file_store.create_file(
        db,
        name="secret.txt",
        file_type=FileType.TEXT,
        path=str(outside),
        size=outside.stat().st_size,
        file_id=file_id,
    )

    response = client.get(f"/files/{file_id}/source")

    assert response.status_code == 404
    assert "not somewhere Noye serves from" in response.json()["detail"]
    assert "not for serving" not in response.text


def test_source_refuses_a_traversal_path_in_the_row(client, db, uploads) -> None:
    """A row whose path escapes the sources directory with `..` resolves outside
    it, and is refused on that basis rather than on the spelling."""
    file_id = file_store.new_file_id()
    file_store.create_file(
        db,
        name="escape.txt",
        file_type=FileType.TEXT,
        path=str(uploads / ".." / ".." / "etc" / "hosts"),
        size=1,
        file_id=file_id,
    )

    assert client.get(f"/files/{file_id}/source").status_code == 404


def test_source_takes_no_path_from_the_request(client, db, uploads) -> None:
    """The only input is an id; a path-shaped id is just an unknown id."""
    for probe in ["../../../etc/hosts", "..%2F..%2Fetc%2Fhosts", "%2Fetc%2Fhosts"]:
        assert client.get(f"/files/{probe}/source").status_code in (404, 422)


def test_source_appears_in_the_openapi_schema(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/files/{file_id}/source" in paths
    assert "get" in paths["/files/{file_id}/source"]
