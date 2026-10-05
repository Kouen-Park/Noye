"""All model operations mocked; never download/delete user's Ollama models."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import apply_desktop_configuration, get_settings
from app.main import app
from app.services import model_manager as module
from app.services.model_manager import ModelManager


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv("NOYE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NOYE_CONTROL_TOKEN", "synthetic-capability")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_desktop_snapshot_does_not_mutate_running_requests(configured):
    old = get_settings()
    apply_desktop_configuration({"openai_api_key": "synthetic-secret", "ollama_model": "new"})
    assert not old.openai_api_key.get_secret_value()
    assert get_settings().openai_api_key.get_secret_value() == "synthetic-secret"
    assert old.ollama_model != get_settings().ollama_model
    with pytest.raises(ValueError):
        apply_desktop_configuration({"qdrant_url": "https://evil.example"})


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/models/job", None),
        ("POST", "/models/cancel", None),
        (
            "POST",
            "/models/pull",
            {"model": "qwen3.5:0.8b", "storage_path": "/tmp", "confirmed_storage": True},
        ),
        ("DELETE", "/models", {"model": "unused:latest"}),
    ],
)
def test_model_routes_require_desktop_capability(configured, method, path, body):
    client = TestClient(app)
    assert client.request(method, path, json=body).status_code == 403
    assert (
        client.request(method, path, json=body, headers={"X-Noye-Control": "wrong"}).status_code
        == 403
    )


def test_download_requires_actual_volume_confirmation(configured):
    response = TestClient(app).post(
        "/models/pull",
        headers={"X-Noye-Control": "synthetic-capability"},
        json={"model": "qwen3.5:0.8b", "storage_path": str(configured), "confirmed_storage": False},
    )
    assert response.status_code == 400


def install_transport(monkeypatch, handle):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handle), **kw),
    )


def test_pull_progress_completion_and_no_auto_selection(monkeypatch, configured):
    seen = []

    def handle(request):
        seen.append(request)
        if request.url.path == "/api/pull":
            return httpx.Response(200, text='{"total":100,"completed":50}\n{"status":"success"}\n')
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:0.8b"}]})
        return httpx.Response(200)

    install_transport(monkeypatch, handle)

    async def run():
        manager = ModelManager()
        await manager.pull("qwen3.5:0.8b", str(configured))
        await manager.task
        assert manager.job["state"] == "complete"
        assert manager.job["completed"] == 50

    asyncio.run(run())
    assert get_settings().ollama_model != "qwen3.5:0.8b"
    assert sum(r.method == "POST" for r in seen) == 1


@pytest.mark.parametrize("body", ['{"error":"private data"}\n', "{}\n", "[]\n", "bad\n"])
def test_failed_pull_is_sanitized_and_retryable(monkeypatch, configured, body):
    install_transport(monkeypatch, lambda r: httpx.Response(200, text=body))

    async def run():
        manager = ModelManager()
        for _ in range(2):
            await manager.pull("qwen3.5:0.8b", str(configured))
            await manager.task
            assert manager.job["state"] == "failed"
            assert "private data" not in manager.job["error"]

    asyncio.run(run())


def test_low_disk_or_unknown_model_makes_no_network_call(monkeypatch, configured):
    monkeypatch.setattr(module.shutil, "disk_usage", lambda path: SimpleNamespace(free=1))

    async def run():
        manager = ModelManager()
        for model in ["qwen3.5:0.8b", "unknown"]:
            with pytest.raises(HTTPException):
                await manager.pull(model, str(configured))
        assert manager.task is None

    asyncio.run(run())


def test_cancellation_and_concurrent_operation_guard(monkeypatch, configured):
    async def handle(request):
        await asyncio.sleep(60)
        return httpx.Response(200)

    install_transport(monkeypatch, handle)

    async def run():
        manager = ModelManager()
        await manager.pull("qwen3.5:0.8b", str(configured))
        await asyncio.sleep(0)
        with pytest.raises(HTTPException) as error:
            await manager.pull("qwen3.5:2b", str(configured))
        assert error.value.status_code == 409
        await manager.cancel()
        assert manager.job["state"] == "cancelled"

    asyncio.run(run())


def test_selected_models_cannot_be_deleted(configured):
    async def run():
        manager = ModelManager()
        for model in [get_settings().ollama_model, "embeddinggemma:latest"]:
            with pytest.raises(HTTPException) as error:
                await manager.delete(model)
            assert error.value.status_code == 409

    asyncio.run(run())


def test_delete_exact_installed_model_only(monkeypatch, configured):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"models": [{"name": "unused:latest"}]})

    install_transport(monkeypatch, handle)

    async def run():
        manager = ModelManager()
        await manager.delete("unused:latest")
        with pytest.raises(HTTPException) as error:
            await manager.delete("not-installed")
        assert error.value.status_code == 404

    asyncio.run(run())
    writes = [r for r in seen if r.method == "DELETE"]
    assert len(writes) == 1
    assert writes[0].content == b'{"model":"unused:latest"}'


def test_active_inference_cannot_be_deleted(configured):
    from app.services.model_usage import inference

    async def run():
        with inference("previous-model"):
            with pytest.raises(HTTPException) as error:
                await ModelManager().delete("previous-model:latest")
            assert error.value.status_code == 409

    asyncio.run(run())


def test_configuration_cannot_select_a_model_during_deletion(configured):
    from app.services.model_usage import ModelBusyError, deletion, inference

    with deletion("unused"):
        with pytest.raises(ValueError):
            apply_desktop_configuration({"ollama_model": "unused:latest"})
        with pytest.raises(ModelBusyError):
            with inference("unused"):
                pytest.fail("model is reserved for deletion")


def test_cancel_before_task_starts_is_terminal(configured):
    async def run():
        manager = ModelManager()
        await manager.pull("qwen3.5:0.8b", str(configured))
        await manager.cancel()
        assert manager.job["state"] == "cancelled"

    asyncio.run(run())


def test_model_management_refuses_remote_server(monkeypatch, configured):
    settings = get_settings().model_copy(update={"ollama_base_url": "https://example.com"})
    monkeypatch.setattr(module, "get_settings", lambda: settings)

    async def run():
        with pytest.raises(HTTPException) as error:
            await ModelManager().pull("qwen3.5:0.8b", str(configured))
        assert error.value.status_code == 400

    asyncio.run(run())
