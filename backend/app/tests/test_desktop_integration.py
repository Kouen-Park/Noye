"""Desktop readiness and configured generation budgets, without private data."""

import json
import uuid

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings, _base_settings, get_settings
from app.services.generation import GenerationError, generate
from app.services.runtime_checks import ServicesOut, readiness


def test_readiness_separates_services_models_and_saved_cloud_configuration():
    settings = Settings(_env_file=None, openai_api_key=SecretStr("synthetic-key"))
    offline = ServicesOut(ollama=False, qdrant=False, generation_model=False, embedding_model=False)
    report = readiness(settings, offline)
    assert not report["indexing_available"]
    assert not report["local_generation_available"]
    assert report["cloud_configuration"] == {"openai": True, "anthropic": False, "gemini": False}
    assert not report["cloud_access_verified"]
    assert "synthetic-key" not in json.dumps(report)
    installed = offline.model_copy(update={"ollama": True, "embedding_model": True})
    assert not readiness(settings, installed)["indexing_available"]
    assert not readiness(settings, installed)["local_generation_available"]
    recovered = installed.model_copy(update={"qdrant": True, "generation_model": True})
    assert readiness(settings, recovered)["indexing_available"]
    assert readiness(settings, recovered)["local_generation_available"]


def test_generation_options_are_bounded(monkeypatch):
    settings = Settings(
        _env_file=None, generation_context_tokens=4096, generation_output_tokens=512
    )
    monkeypatch.setattr("app.services.generation.get_settings", lambda: settings)
    captured = []

    def handle(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200, json={"response": "Saved answer.", "done": True, "done_reason": "stop"}
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert generate("synthetic instruction", client=client) == "Saved answer."
    assert captured[0]["options"] == {"num_ctx": 4096, "num_predict": 512}


@pytest.mark.parametrize("text", ["x" * 4000, "한" * 1400])
def test_oversized_local_input_never_reaches_ollama(monkeypatch, text):
    settings = Settings(
        _env_file=None, generation_context_tokens=4096, generation_output_tokens=512
    )
    monkeypatch.setattr("app.services.generation.get_settings", lambda: settings)

    def refuse(request):
        pytest.fail("An oversized prompt reached a model.")

    with httpx.Client(transport=httpx.MockTransport(refuse)) as client:
        with pytest.raises(GenerationError, match="input budget"):
            generate(text, client=client)


@pytest.mark.parametrize("metadata", [{"done": False}, {"done_reason": "length"}])
def test_incomplete_output_is_rejected_instead_of_saved(metadata):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"response": "Incomplete text", **metadata})
        )
    ) as client:
        with pytest.raises(GenerationError, match="output limit"):
            generate("short request", client=client)


def test_output_must_fit_within_context():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, generation_context_tokens=2048, generation_output_tokens=2048)


def test_each_restored_workspace_uses_a_different_collection(tmp_path, monkeypatch):
    collections = []
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
    try:
        for name in ("one", "two"):
            root = tmp_path / name
            root.mkdir()
            marker = {"format": "noye-restored-workspace", "version": 1, "id": str(uuid.uuid4())}
            (root / "noye-workspace.json").write_text(json.dumps(marker))
            monkeypatch.setenv("NOYE_DATA_DIR", str(root))
            get_settings.cache_clear()
            collections.append(_base_settings().qdrant_collection)
        assert collections[0] != collections[1]
        assert all(name.startswith("noye_desktop_") for name in collections)
        root = tmp_path / "legacy"
        root.mkdir()
        monkeypatch.setenv("NOYE_DATA_DIR", str(root))
        get_settings.cache_clear()
        assert _base_settings().qdrant_collection == "noye_desktop"
    finally:
        get_settings.cache_clear()


def test_invalid_restored_identity_cannot_silently_share_the_original_index(tmp_path, monkeypatch):
    (tmp_path / "noye-workspace.json").write_text('{"format":"invalid","version":1}')
    monkeypatch.setenv("NOYE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="identity"):
            _base_settings()
    finally:
        get_settings.cache_clear()
