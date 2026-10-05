"""Read-only setup snapshot: no secrets, inference, model pulls or disk writes."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.hardware import HardwareInfo


@pytest.fixture
def probes(monkeypatch, tmp_path):
    settings = Settings(_env_file=None, gemini_api_key="synthetic-secret-never-returned")
    monkeypatch.setattr("app.api.runtime.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.runtime.data_directory", lambda: tmp_path)
    monkeypatch.setattr("app.api.runtime.inspect_hardware", lambda _: HardwareInfo(
        os="Darwin", architecture="arm64", total_memory_bytes=8 * 2**30,
        available_memory_bytes=1 * 2**30,
    ))
    return settings, tmp_path


def transport(monkeypatch, handle):
    original = httpx.AsyncClient
    options = []

    def client(**kwargs):
        options.append(kwargs)
        return original(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr("app.services.runtime_checks.httpx.AsyncClient", client)
    return options


def test_setup_contains_inventory_and_preserves_config_without_mutation(monkeypatch, probes):
    settings, directory = probes
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"name": "qwen3.5:4b", "size": 3_400_000_000},
                {"name": "embeddinggemma:latest", "size": 622_000_000},
            ]})
        return httpx.Response(200)

    options = transport(monkeypatch, handle)
    response = TestClient(app).get("/runtime/setup")
    assert response.status_code == 200
    result = response.json()
    assert result["configured_generation_model"] == "qwen3.5:4b"
    assert result["recommendation"]["generation"]["name"] == "qwen3.5:0.8b"
    assert result["recommendation"]["memory_status"] == "close_apps"
    assert result["services"] == dict.fromkeys([
        "ollama", "qdrant", "generation_model", "embedding_model",
    ], True)
    assert result["installed_models"][0] == {
        "name": "embeddinggemma:latest", "size_bytes": 622_000_000,
    }
    assert result["gemini_configured"] is True
    assert "synthetic-secret" not in response.text
    assert str(directory) not in response.text
    assert list(directory.iterdir()) == []
    assert settings.ollama_model == "qwen3.5:4b"
    assert len(requests) == 2 and all(request.method == "GET" for request in requests)
    assert options == [{"timeout": 1.5, "follow_redirects": False}]


@pytest.mark.parametrize("models", [None, "not a list", [{"name": 123}], [{}], [None],
                                    [{"name": "x"}] * 201])
def test_malformed_inventory_is_unknown_not_installed(monkeypatch, probes, models):
    transport(monkeypatch, lambda _: httpx.Response(200, json={"models": models}))
    result = TestClient(app).get("/runtime/setup").json()
    assert not result["services"]["ollama"]
    assert result["installed_models"] == []


def test_unreachable_services_do_not_block_hardware_guidance(monkeypatch, probes):
    def handle(request):
        raise httpx.ConnectError("unavailable", request=request)

    transport(monkeypatch, handle)
    result = TestClient(app).get("/runtime/setup").json()
    assert not result["services"]["ollama"]
    assert not result["services"]["qdrant"]
    assert result["hardware"]["total_memory_bytes"] == 8 * 2**30


@pytest.mark.parametrize("size", [-1, True, "bad", None])
def test_invalid_model_sizes_remain_unknown(monkeypatch, probes, size):
    transport(monkeypatch, lambda _: httpx.Response(200, json={"models": [
        {"name": "custom:model", "size": size},
    ]}))
    result = TestClient(app).get("/runtime/setup").json()
    assert result["installed_models"] == [{"name": "custom:model", "size_bytes": None}]
