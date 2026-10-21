"""Original-evidence paths reject remote aliases before sending any prompt."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.models.wiki import SectionSummary
from app.services import embeddings, generation, index_identity
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


class LocalReply(BaseModel):
    answer: str


@pytest.fixture
def poisoned_proxy(monkeypatch):
    received, options = [], {"redirect": False}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def do_DELETE(self):
            self.respond()

        def respond(self):
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length)) if length else None
            received.append((self.server.server_port, self.path, payload))
            if (
                options["redirect"]
                and self.server is direct
                and not self.path.endswith("/api/show")
            ):
                self.send_response(307)
                self.send_header("Location", f"http://127.0.0.1:{proxy.server_port}{self.path}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path.endswith("/api/show"):
                data = {"model_info": {"general.architecture": "mock-local"}}
            elif self.path.endswith("/api/embed"):
                data = {"embeddings": [[1.0, 0.0]]}
            elif self.path.endswith("/api/tags"):
                data = {"models": [{"name": "mock-local-embed:latest", "digest": "direct-digest"}]}
            elif self.path.endswith("/api/chat"):
                data = {"done": True, "message": {"content": json.dumps({"answer": "37 litres."})}}
            else:
                data = {"done": True, "response": json.dumps({"answer": "37 litres."})}
            encoded = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args):
            pass

    with (
        ThreadingHTTPServer(("127.0.0.1", 0), Handler) as direct,
        ThreadingHTTPServer(("127.0.0.1", 0), Handler) as proxy,
    ):
        threads = [
            Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
            for server in (direct, proxy)
        ]
        for thread in threads:
            thread.start()
        try:
            for name in (
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "http_proxy",
                "https_proxy",
                "all_proxy",
            ):
                monkeypatch.setenv(name, f"http://127.0.0.1:{proxy.server_port}")
            monkeypatch.setenv("NO_PROXY", "")
            monkeypatch.setenv("no_proxy", "")
            yield f"http://127.0.0.1:{direct.server_port}", direct.server_port, received, options
        finally:
            direct.shutdown()
            proxy.shutdown()
            for thread in threads:
                thread.join(timeout=1)


@pytest.mark.parametrize("route", ["wiki", "question", "embedding", "index_identity"])
@pytest.mark.parametrize("redirect", [False, True])
def test_owned_original_clients_bypass_proxy_and_reject_redirects(
    poisoned_proxy, monkeypatch, route, redirect
):
    url, port, received, options = poisoned_proxy
    options["redirect"] = redirect
    settings = Settings(
        _env_file=None,
        ollama_base_url=url,
        ollama_model="mock-local",
        ollama_embedding_model="mock-local-embed",
        qdrant_vector_size=2,
    )
    for module in (generation, embeddings, index_identity):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    original = "Synthetic private evidence 37"

    def invoke():
        if route == "wiki":
            return structured(original, LocalReply, settings=settings).answer
        if route == "question":
            return json.loads(generation.generate(original, local_only=True))["answer"]
        if route == "embedding":
            return embeddings.embed_text(original)
        return index_identity.resolve_model_digest()

    if redirect:
        with pytest.raises((WikiError, generation.GenerationError, embeddings.EmbeddingError)):
            invoke()
    else:
        assert (
            invoke()
            == {
                "wiki": "37 litres.",
                "question": "37 litres.",
                "embedding": [1.0, 0.0],
                "index_identity": "direct-digest",
            }[route]
        )
    assert all(target_port == port for target_port, _, _ in received)
    assert [path for _, path, _ in received] == {
        "wiki": ["/api/show", "/api/generate"],
        "question": ["/api/show", "/api/generate"],
        "embedding": ["/api/embed"],
        "index_identity": ["/api/tags"],
    }[route]
    if route != "index_identity":
        payload = received[-1][2]
        assert original in str(payload)
    if route in {"wiki", "question"}:
        assert original not in str(received[0][2])


@pytest.mark.parametrize("route", ["wiki", "source_document"])
@pytest.mark.parametrize("thinking", [False, True])
def test_structured_endpoint_honors_thinking_and_only_validates_final_content(route, thinking):
    from app.services.source_documents import local as documents
    from app.services.wiki import local as wiki

    calls = []
    configured = Settings(_env_file=None, ollama_thinking=thinking)

    def reply(request):
        body = json.loads(request.content)
        calls.append((request.url.path, body))
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"general.architecture": "qwen"}})
        data = {"done": True, "done_reason": "stop", "response": '{"answer":"wrong field"}'}
        if thinking:
            data["message"] = {
                "thinking": '{"answer":"reasoning is not an answer"}',
                "content": '{"answer":"final 37 litres"}',
            }
        else:
            data["response"] = '{"answer":"final 37 litres"}'
        return httpx.Response(200, json=data)

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        if route == "wiki":
            actual = wiki.structured(
                "Original 37 litres", LocalReply, settings=configured, client=client
            )
        else:
            actual = documents.structured(
                {"task": "test", "original": "Original 37 litres"},
                LocalReply,
                settings=configured,
                client=client,
            )
    assert actual.answer == "final 37 litres"
    assert [p for p, _ in calls] == ["/api/show", "/api/chat" if thinking else "/api/generate"]
    assert calls[0][1] == {"model": configured.ollama_model}
    body = calls[1][1]
    assert body["think"] is thinking and body["stream"] is False
    assert body["format"] == LocalReply.model_json_schema()
    if thinking:
        assert [m["role"] for m in body["messages"]] == ["system", "user"]
        assert "Original 37 litres" in body["messages"][1]["content"]
        assert "prompt" not in body and "system" not in body
    else:
        assert "Original 37 litres" in body["prompt"] and "messages" not in body


@pytest.mark.parametrize("route", ["wiki", "source_document"])
@pytest.mark.parametrize(
    "message",
    [
        {"thinking": '{"answer":"37"}'},
        {"thinking": '{"answer":"37"}', "content": ""},
        {"content": "not valid JSON"},
    ],
)
def test_structured_reasoning_or_missing_final_json_never_becomes_output(route, message):
    from app.services.source_documents import local as documents
    from app.services.wiki import local as wiki

    calls = []

    def reply(request):
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json=(
                {"model_info": {"general.architecture": "qwen"}}
                if request.url.path == "/api/show"
                else {"done": True, "message": message}
            ),
        )

    settings = Settings(_env_file=None, ollama_thinking=True)
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        with pytest.raises((wiki.WikiError, documents.DocumentError), match=r"[Ii]nvalid"):
            if route == "wiki":
                wiki.structured("Original", LocalReply, settings=settings, client=client)
            else:
                documents.structured({"task": "test"}, LocalReply, settings=settings, client=client)
    assert calls == ["/api/show", "/api/chat"]


@pytest.mark.parametrize("route", ["wiki", "source_document"])
@pytest.mark.parametrize("redirect", [False, True])
def test_owned_thinking_clients_keep_originals_off_proxies_and_redirects(
    poisoned_proxy, route, redirect
):
    from app.services.source_documents import local as documents
    from app.services.wiki import local as wiki

    url, port, received, options = poisoned_proxy
    options["redirect"] = redirect
    settings = Settings(
        _env_file=None, ollama_base_url=url, ollama_model="mock-local", ollama_thinking=True
    )

    def invoke():
        if route == "wiki":
            return wiki.structured("Synthetic original 37", LocalReply, settings=settings).answer
        return documents.structured(
            {"task": "test", "original": "Synthetic original 37"}, LocalReply, settings=settings
        ).answer

    if redirect:
        with pytest.raises((wiki.WikiError, documents.DocumentError)):
            invoke()
    else:
        assert invoke() == "37 litres."
    assert [(target_port, path) for target_port, path, _ in received] == [
        (port, "/api/show"),
        (port, "/api/chat"),
    ]
