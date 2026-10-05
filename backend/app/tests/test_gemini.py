"""Provider routing, cloud failure handling, and credential boundaries."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.api import ai, chat, documents
from app.config import Settings
from app.db import conversations as conversation_store
from app.db.database import connect, init_schema
from app.main import app
from app.models.conversations import Role
from app.services import generation
from app.services.documents import SYSTEM_PROMPT as DOCUMENT_SYSTEM
from app.services.documents import draft_document
from app.services.generation import Answer, GenerationError, answer_question, generate
from app.services.retrieval import SearchResult

KEY = "private-key-test-sentinel"
CONTENT = "private-document-test-sentinel"


@pytest.fixture
def settings(monkeypatch):
    configured = Settings(_env_file=None, gemini_api_key=SecretStr(KEY))
    monkeypatch.setattr(generation, "get_settings", lambda: configured)
    monkeypatch.setattr(ai, "get_settings", lambda: configured)
    return configured


def response_body(parts=None, finish="STOP"):
    return {"candidates": [{
        "finishReason": finish,
        "content": {"parts": parts if parts is not None else [{"text": " Answer "}]},
    }]}


def test_gemini_uses_header_key_and_separates_system_prompt(settings):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=response_body())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert generate(CONTENT, provider="gemini", client=client) == "Answer"
    request = seen[0]
    assert request.url.host == "generativelanguage.googleapis.com"
    assert request.url.path.endswith(f"/{settings.gemini_model}:generateContent")
    assert KEY not in str(request.url)
    assert request.headers["x-goog-api-key"] == KEY
    body = json.loads(request.content)
    assert body["contents"][0]["parts"][0]["text"] == CONTENT
    assert body["systemInstruction"]["parts"][0]["text"] == generation.SYSTEM_PROMPT
    assert KEY not in str(body)


def test_default_is_local_even_with_gemini_key(settings):
    def handler(request):
        assert request.url.host == "localhost"
        assert "x-goog-api-key" not in request.headers
        return httpx.Response(200, json={"response": "Local answer"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert generate("prompt", client=client) == "Local answer"


def test_missing_key_does_not_send_any_request(settings):
    settings.gemini_api_key = SecretStr(" ")

    def handler(request):
        pytest.fail("No request should be sent without a key")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GenerationError, match="GEMINI_API_KEY"):
            generate(CONTENT, provider="gemini", client=client)


@pytest.mark.parametrize("status,match", [
    (401, "API key"), (403, "permissions"), (404, "GEMINI_MODEL"),
    (429, "quota"), (500, "HTTP 500"),
])
def test_error_bodies_never_escape_and_no_fallback_or_retry(settings, status, match):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(status, text=f"{KEY} {CONTENT}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GenerationError, match=match) as error:
            generate(CONTENT, provider="gemini", client=client)
    assert len(seen) == 1
    assert KEY not in str(error.value)
    assert CONTENT not in str(error.value)


def test_connection_errors_do_not_expose_exception_details(settings):
    def handler(request):
        raise httpx.ConnectError(f"{KEY} {CONTENT}", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GenerationError, match="internet") as error:
            generate(CONTENT, provider="gemini", client=client)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__
    assert KEY not in str(error.value)


@pytest.mark.parametrize("body", [
    [], None, {}, {"candidates": []}, {"candidates": None},
    response_body(finish="SAFETY"), response_body(finish="MAX_TOKENS"),
    response_body(parts=[{"text": "thinking", "thought": True}]),
    response_body(parts=[{"text": " "}]), response_body(parts=[None]),
])
def test_unusable_or_incomplete_responses_are_not_saved(settings, body):
    def handler(request):
        # Use serialized text so JSON null remains null instead of an empty body.
        return httpx.Response(200, text=json.dumps(body))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GenerationError):
            generate("prompt", provider="gemini", client=client)


def test_thoughts_are_excluded_and_answer_parts_are_joined(settings):
    def handler(request):
        return httpx.Response(200, json=response_body(parts=[
            {"text": "secret reasoning", "thought": True},
            {"text": "First "}, {"text": "second"},
        ]))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert generate("prompt", provider="gemini", client=client) == "First second"


def test_rag_keeps_retrieved_provenance_with_cloud_generation(settings, monkeypatch):
    passage = SearchResult(
        content=CONTENT, file_id="f1", page_number=2, chunk_index=0, score=0.9,
    )
    monkeypatch.setattr(generation, "search", lambda *args, **kwargs: [passage])

    def handler(request):
        assert CONTENT in json.loads(request.content)["contents"][0]["parts"][0]["text"]
        return httpx.Response(200, json=response_body())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        answer = answer_question("question", provider="gemini", client=client)
    assert answer.sources == [passage]
    assert answer.text == "Answer"


def test_empty_retrieval_never_calls_cloud(settings, monkeypatch):
    monkeypatch.setattr(generation, "search", lambda *args, **kwargs: [])
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("cloud"))) as c:
        answer = answer_question("question", provider="gemini", client=c)
    assert not answer.sources
    assert answer.text == generation.NO_CONTEXT_ANSWER


def test_document_generation_routes_to_gemini_with_document_prompt(settings):
    def handler(request):
        body = json.loads(request.content)
        assert body["systemInstruction"]["parts"][0]["text"] == DOCUMENT_SYSTEM
        assert CONTENT in body["contents"][0]["parts"][0]["text"]
        return httpx.Response(200, json=response_body(parts=[{"text": "# Notes"}]))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert draft_document("notes", CONTENT, provider="gemini", client=client) == "# Notes"


def test_provider_endpoint_never_returns_key(settings):
    with TestClient(app) as client:
        result = client.get("/ai/providers")
    assert result.status_code == 200
    assert KEY not in result.text
    assert result.json()[1]["configured"] is True
    assert KEY not in repr(settings)


def test_provider_endpoint_reports_missing_key(settings):
    settings.gemini_api_key = SecretStr("")
    with TestClient(app) as client:
        assert client.get("/ai/providers").json()[1]["configured"] is False


def test_unknown_provider_is_rejected_before_work():
    with TestClient(app) as client:
        assert client.post("/chat", json={"question": "q", "provider": "other"}).status_code == 422
        assert client.post("/documents/generate", json={
            "message_id": "m1", "instruction": "notes", "provider": "other",
        }).status_code == 422


def test_model_cannot_change_request_path():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gemini_model="../../other?key=anything")


def test_api_routes_forward_explicit_provider_and_preserve_failures(tmp_path, monkeypatch):
    db = connect(tmp_path / "providers.db")
    init_schema(db)
    app.dependency_overrides[chat.get_db] = lambda: db
    monkeypatch.setattr(chat, "_ready_file_names", lambda db: {"f1": "notes.md"})
    called = []

    def answer(question, **kwargs):
        called.append(kwargs["provider"])
        if kwargs["provider"] == "gemini":
            raise GenerationError("Gemini's quota was reached")
        return Answer(text="Local answer", sources=[])

    def draft(instruction, answer, citations, **kwargs):
        called.append(kwargs["provider"])
        return "# Cloud notes"

    monkeypatch.setattr(chat, "answer_question", answer)
    monkeypatch.setattr(documents, "draft_document", draft)
    try:
        with TestClient(app) as client:
            local = client.post("/chat", json={"question": "local?"}).json()
            cloud = client.post("/chat", json={
                "question": "cloud?", "provider": "gemini",
            }).json()
            assert cloud["question"]["content"] == "cloud?"
            assert "quota" in cloud["answer"]["error"]
            stored = conversation_store.read_conversation(db, cloud["conversation_id"])
            assert stored.messages[0].role == Role.USER
            assert stored.messages[1].failed
            result = client.post("/documents/generate", json={
                "message_id": local["answer"]["id"], "instruction": "notes",
                "provider": "gemini",
            })
            assert result.status_code == 201
            assert result.json()["content"] == "# Cloud notes"
        assert called == ["ollama", "gemini", "gemini"]
    finally:
        app.dependency_overrides.clear()
        db.close()
