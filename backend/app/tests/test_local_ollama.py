"""Original-evidence paths reject remote aliases before sending any prompt."""

import json

import httpx
import pytest

from app.config import Settings
from app.models.wiki import SectionSummary
from app.services import generation
from app.services.wiki.local import WikiError, structured


@pytest.mark.parametrize(
    "descriptor",
    [
        {"remote_host": "https://ollama.com", "remote_model": "cloud"},
        {"model_info": {"general.architecture": "qwen"}, "remote_host": "https://ollama.com"},
        {"model_info": {}},
        [],
    ],
)
@pytest.mark.parametrize("route", ["wiki", "question"])
def test_remote_alias_never_receives_originals(descriptor, route, monkeypatch):
    calls = []

    def reply(request):
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json=descriptor)

    settings = Settings(_env_file=None)
    monkeypatch.setattr(generation, "get_settings", lambda: settings)
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        with pytest.raises((WikiError, generation.GenerationError), match="local model"):
            if route == "wiki":
                structured("Private source 37", SectionSummary, settings=settings, client=client)
            else:
                generation.generate("Private source 37", client=client, local_only=True)
    assert calls == [("/api/show", {"model": settings.ollama_model})]


def test_proven_local_question_preflight_precedes_originals(monkeypatch):
    calls = []

    def reply(request):
        payload = json.loads(request.content)
        calls.append((request.url.path, payload))
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"general.architecture": "qwen"}})
        return httpx.Response(200, json={"done": True, "response": "37 litres."})

    monkeypatch.setattr(generation, "get_settings", lambda: Settings(_env_file=None))
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        assert (
            generation.generate("Private source 37", client=client, local_only=True) == "37 litres."
        )
    assert [path for path, _ in calls] == ["/api/show", "/api/generate"]
    assert "Private source 37" not in str(calls[0])
