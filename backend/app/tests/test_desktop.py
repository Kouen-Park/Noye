"""Desktop lifecycle tests use temporary data and never start AI services."""

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import (
    PROJECT_ROOT,
    Settings,
    data_directory,
    documents_dir,
    get_settings,
    sources_dir,
)
from app.db.database import database_path
from app.logging_config import log_directory
from app.main import app


@pytest.fixture
def desktop_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("NOYE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_all_data_uses_desktop_root(desktop_settings):
    assert data_directory() == desktop_settings
    assert database_path() == desktop_settings / "app.db"
    assert sources_dir() == desktop_settings / "sources"
    assert documents_dir() == desktop_settings / "documents"
    assert log_directory() == desktop_settings / "logs"
    assert get_settings().qdrant_collection == "noye_desktop"


def test_startup_initializes_database_before_ready(desktop_settings):
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/files").json() == []
        assert (desktop_settings / "app.db").exists()


def test_explicit_existing_storage_can_be_reused(monkeypatch, tmp_path):
    existing = tmp_path / "existing.db"
    monkeypatch.setenv("NOYE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{existing}")
    get_settings.cache_clear()
    try:
        assert database_path() == existing
    finally:
        get_settings.cache_clear()


def test_web_data_default_is_unchanged(monkeypatch):
    settings = Settings(_env_file=None)
    settings.noye_data_dir = None
    settings.database_url = "sqlite:///./data/app.db"
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.db.database.get_settings", lambda: settings)
    assert data_directory() == PROJECT_ROOT / "data"
    assert database_path() == PROJECT_ROOT / "data/app.db"


@pytest.mark.parametrize("shutdown", ["line", "eof"])
def test_managed_backend_starts_and_stops_without_services(tmp_path, shutdown):
    env = {**os.environ, "LOG_TO_FILE": "false", "FRONTEND_ORIGINS": "tauri://localhost"}
    root = tmp_path / "workspace"
    executable = os.environ.get("NOYE_TEST_SIDECAR")
    command = [executable] if executable else [
        sys.executable, str(PROJECT_ROOT / "backend/desktop.py"),
    ]
    with subprocess.Popen(
        [*command, "--data-dir", str(root)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env,
    ) as child:
        try:
            lines = queue.Queue()
            threading.Thread(target=lambda: lines.put(child.stdout.readline()), daemon=True).start()
            line = lines.get(timeout=20)
            assert line, child.stderr.read()
            ready = json.loads(line)
            assert ready["event"] == "ready"
            assert ready["url"].startswith("http://127.0.0.1:")
            with httpx.Client(base_url=ready["url"], timeout=3) as client:
                assert client.get("/health").json() == {"status": "ok"}
                assert client.get("/files").json() == []
                setup = client.get("/runtime/setup")
                assert setup.status_code == 200
                assert "catalog_checked_on" in setup.json()["recommendation"]
                response = client.options("/files", headers={
                    "Origin": "tauri://localhost", "Access-Control-Request-Method": "GET",
                })
                assert response.headers["access-control-allow-origin"] == "tauri://localhost"
            assert (root / "app.db").is_file()
            if shutdown == "line":
                child.stdin.write("shutdown\n")
                child.stdin.flush()
            else:
                child.stdin.close()
            assert child.wait(timeout=10) == 0
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


@pytest.mark.parametrize("unavailable", [False, True])
def test_service_checks_are_read_only_and_bounded(monkeypatch, unavailable):
    settings = Settings(_env_file=None)
    monkeypatch.setattr("app.api.runtime.get_settings", lambda: settings)
    requests = []

    def handle(request):
        requests.append(request)
        if unavailable:
            raise httpx.ConnectError("unavailable", request=request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"name": "qwen3.5:4b"}, {"name": "embeddinggemma:latest"},
            ]})
        return httpx.Response(200, text="healthz check passed")

    original = httpx.AsyncClient
    monkeypatch.setattr("app.services.runtime_checks.httpx.AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(handle), **kwargs,
    ))
    response = TestClient(app).get("/runtime/services")
    assert response.json() == dict.fromkeys([
        "ollama", "qdrant", "generation_model", "embedding_model",
    ], not unavailable)
    assert len(requests) == 2
    assert all(request.method == "GET" for request in requests)


def test_model_tags_do_not_confuse_latest_with_a_different_size():
    from app.services.runtime_checks import model_installed

    assert model_installed("embeddinggemma", {"embeddinggemma:latest"})
    assert not model_installed("qwen3.5:4b", {"qwen3.5:9b"})


def test_desktop_does_not_read_repository_secrets(desktop_settings):
    (desktop_settings / ".env").write_text("OLLAMA_MODEL=desktop-test-model\n")
    get_settings.cache_clear()
    assert get_settings().ollama_model == "desktop-test-model"
    assert get_settings().noye_data_dir == desktop_settings
