"""Mock-only official API contracts: never use a real key or bill a provider."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import app
from app.services import generation
from app.services.documents import SYSTEM_PROMPT as DOCUMENT_SYSTEM
from app.services.documents import draft_document


@pytest.fixture(params=["openai", "anthropic"])
def cloud(request, monkeypatch):
    provider = request.param
    settings = Settings(_env_file=None, **{f"{provider}_api_key": "synthetic-secret"})
    monkeypatch.setattr(generation, "get_settings", lambda: settings)
    return provider, settings


def answer(provider, text="answer"):
    if provider == "openai":
        return {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                }
            ],
        }
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}


def test_official_request_and_response_contract(cloud):
    provider, settings = cloud
    seen = []

    def handle(request):
        seen.append(request)
        payload = json.loads(request.content)
        assert payload["model"] == getattr(settings, f"{provider}_model")
        if provider == "openai":
            assert str(request.url) == "https://api.openai.com/v1/responses"
            assert payload["store"] is False
            assert payload["input"] == "question"
            assert payload["instructions"] == generation.SYSTEM_PROMPT
            assert request.headers["Authorization"] == "Bearer synthetic-secret"
        else:
            assert str(request.url) == "https://api.anthropic.com/v1/messages"
            assert payload["messages"] == [{"role": "user", "content": "question"}]
            assert payload["system"] == generation.SYSTEM_PROMPT
            assert request.headers["x-api-key"] == "synthetic-secret"
            assert request.headers["anthropic-version"] == "2023-06-01"
        return httpx.Response(200, json=answer(provider, "  answer  "))

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert generation.generate("question", provider=provider, client=client) == "answer"
    assert len(seen) == 1


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_errors_never_leak_provider_body_or_retry(cloud, status):
    provider, _ = cloud
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(
            status,
            json={"error": "synthetic-secret private question"},
            headers={"location": "https://evil.example"},
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(generation.GenerationError) as error:
            generation.generate("question", provider=provider, client=client)
    assert "synthetic-secret" not in str(error.value)
    assert "private question" not in str(error.value)
    assert len(seen) == 1


@pytest.mark.parametrize("body", [{}, [], {"content": "invalid"}, {"status": "incomplete"}])
def test_malformed_or_incomplete_answers_rejected(cloud, body):
    provider, _ = cloud
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))) as c:
        with pytest.raises(generation.GenerationError, match="complete usable"):
            generation.generate("q", provider=provider, client=c)


def test_missing_key_makes_no_request(cloud):
    provider, settings = cloud
    setattr(settings, f"{provider}_api_key", SecretStr(""))
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: pytest.fail("unexpected API call"))
    ) as c:
        with pytest.raises(generation.GenerationError, match="API key"):
            generation.generate("q", provider=provider, client=c)


def test_document_generation_reuses_adapter(cloud):
    provider, _ = cloud

    def handle(request):
        payload = json.loads(request.content)
        assert payload.get("instructions", payload.get("system")) == DOCUMENT_SYSTEM
        return httpx.Response(200, json=answer(provider, "# Document"))

    with httpx.Client(transport=httpx.MockTransport(handle)) as c:
        assert draft_document("notes", "saved answer", provider=provider, client=c) == "# Document"


def test_provider_list_exposes_only_availability(monkeypatch):
    settings = Settings(
        _env_file=None, openai_api_key="synthetic-openai", anthropic_api_key="synthetic-claude"
    )
    monkeypatch.setattr("app.api.ai.get_settings", lambda: settings)
    response = TestClient(app).get("/ai/providers")
    assert {p["id"] for p in response.json()} == {"ollama", "gemini", "openai", "anthropic"}
    assert "synthetic-" not in response.text
