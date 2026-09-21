"""Tests for embeddings.

Unit tests drive the service through ``httpx.MockTransport``, so they never
touch the network and can assert exactly what Noye sends to Ollama. The
integration tests at the bottom talk to a real Ollama and skip when one is not
running.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import get_settings
from app.services.chunking import Chunk
from app.services.embeddings import (
    EmbeddingError,
    embed_chunks,
    embed_text,
    embed_texts,
)

VECTOR_SIZE = get_settings().qdrant_vector_size


def vector(fill: float = 0.1, size: int = VECTOR_SIZE) -> list[float]:
    return [fill] * size


def mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def responder(*, embeddings=None, status=200, body=None):
    """Build a handler returning a canned Ollama response, recording requests."""
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        if body is not None:
            return httpx.Response(status, text=body)
        payload = {"model": "test-model", "embeddings": embeddings or []}
        return httpx.Response(status, json=payload)

    handler.seen = seen  # type: ignore[attr-defined]
    return handler


def test_embed_text_returns_one_vector() -> None:
    handler = responder(embeddings=[vector()])

    with mock_client(handler) as client:
        result = embed_text("Dijkstra's algorithm", client=client)

    assert result == vector()


def test_embed_text_sends_the_configured_model_and_input() -> None:
    handler = responder(embeddings=[vector()])

    with mock_client(handler) as client:
        embed_text("some text", client=client)

    sent = handler.seen[0]
    assert sent["model"] == get_settings().ollama_embedding_model
    assert sent["input"] == ["some text"]


def test_embed_texts_preserves_input_order() -> None:
    handler = responder(embeddings=[vector(0.1), vector(0.2), vector(0.3)])

    with mock_client(handler) as client:
        result = embed_texts(["a", "b", "c"], client=client)

    assert result == [vector(0.1), vector(0.2), vector(0.3)]


def test_embed_texts_batches_requests() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content)["input"]
        calls.append(len(inputs))
        return httpx.Response(200, json={"embeddings": [vector()] * len(inputs)})

    with mock_client(handler) as client:
        result = embed_texts([f"text {index}" for index in range(5)], batch_size=2, client=client)

    assert calls == [2, 2, 1]
    assert len(result) == 5


def test_embed_texts_with_no_input_makes_no_request() -> None:
    handler = responder(embeddings=[])

    with mock_client(handler) as client:
        assert embed_texts([], client=client) == []

    assert handler.seen == []


def test_embed_chunks_returns_a_vector_per_chunk() -> None:
    chunks = [
        Chunk(file_id="f1", page_number=1, chunk_index=0, content="first"),
        Chunk(file_id="f1", page_number=2, chunk_index=1, content="second"),
    ]
    handler = responder(embeddings=[vector(0.1), vector(0.2)])

    with mock_client(handler) as client:
        result = embed_chunks(chunks, client=client)

    assert len(result) == len(chunks)
    assert handler.seen[0]["input"] == ["first", "second"]


def test_empty_text_is_rejected_before_any_request() -> None:
    handler = responder(embeddings=[vector()])

    with mock_client(handler) as client:
        with pytest.raises(ValueError, match="Cannot embed empty text"):
            embed_text("   ", client=client)

    assert handler.seen == []


def test_empty_text_in_a_batch_is_reported_with_its_position() -> None:
    handler = responder(embeddings=[vector()])

    with mock_client(handler) as client:
        with pytest.raises(ValueError, match="index 1"):
            embed_texts(["fine", ""], client=client)


@pytest.mark.parametrize("batch_size", [0, -3])
def test_non_positive_batch_size_is_rejected(batch_size: int) -> None:
    handler = responder(embeddings=[vector()])

    with mock_client(handler) as client:
        with pytest.raises(ValueError, match="batch_size must be positive"):
            embed_texts(["text"], batch_size=batch_size, client=client)


def test_unreachable_ollama_raises_embedding_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with mock_client(handler) as client:
        with pytest.raises(EmbeddingError, match="Could not reach Ollama"):
            embed_text("text", client=client)


def test_missing_model_raises_with_the_pull_command() -> None:
    handler = responder(status=404, body="model not found")

    with mock_client(handler) as client:
        with pytest.raises(EmbeddingError, match="ollama pull"):
            embed_text("text", client=client)


def test_server_error_raises_embedding_error() -> None:
    handler = responder(status=500, body="internal error")

    with mock_client(handler) as client:
        with pytest.raises(EmbeddingError, match="HTTP 500"):
            embed_text("text", client=client)


def test_non_json_response_raises_embedding_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json at all")

    with mock_client(handler) as client:
        with pytest.raises(EmbeddingError, match="non-JSON"):
            embed_text("text", client=client)


def test_response_without_embeddings_raises_embedding_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "test-model"})

    with mock_client(handler) as client:
        with pytest.raises(EmbeddingError, match="no embeddings"):
            embed_text("text", client=client)


def test_mismatched_embedding_count_raises_embedding_error() -> None:
    handler = responder(embeddings=[vector()])

    with mock_client(handler) as client:
        with pytest.raises(EmbeddingError, match="1 embeddings for 2 inputs"):
            embed_texts(["a", "b"], client=client)


def test_wrong_dimension_raises_with_remediation() -> None:
    handler = responder(embeddings=[vector(size=384)])

    with mock_client(handler) as client:
        with pytest.raises(EmbeddingError, match="QDRANT_VECTOR_SIZE"):
            embed_text("text", client=client)


# --- Integration: requires a running Ollama with the configured model ---------


def ollama_is_available() -> bool:
    settings = get_settings()
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/version", timeout=2.0)
    except httpx.RequestError:
        return False
    return response.status_code == 200


requires_ollama = pytest.mark.skipif(
    not ollama_is_available(), reason="Ollama is not running"
)


@requires_ollama
def test_real_ollama_returns_the_configured_dimension() -> None:
    result = embed_text("Dijkstra's algorithm assumes non-negative edge weights.")

    assert len(result) == get_settings().qdrant_vector_size
    assert any(value != 0.0 for value in result)


@requires_ollama
def test_real_ollama_embeds_korean_text() -> None:
    result = embed_text("다익스트라 알고리즘은 음수 가중치를 허용하지 않는다.")

    assert len(result) == get_settings().qdrant_vector_size


@requires_ollama
def test_related_texts_are_closer_than_unrelated_ones() -> None:
    """The property search depends on: similar meaning, similar vector."""
    graphs, graphs_again, cooking = embed_texts(
        [
            "Dijkstra's algorithm finds shortest paths in a graph.",
            "Shortest path search over weighted graph edges.",
            "Preheat the oven and butter a cake tin.",
        ]
    )

    def similarity(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        norm = (sum(a * a for a in left) ** 0.5) * (sum(b * b for b in right) ** 0.5)
        return dot / norm

    assert similarity(graphs, graphs_again) > similarity(graphs, cooking)


@requires_ollama
def test_real_ollama_matches_korean_question_to_korean_passage() -> None:
    """Cross-language retrieval is the reason embeddinggemma was chosen."""
    question, korean_answer, unrelated = embed_texts(
        [
            "다익스트라는 다음 정점을 어떻게 고르는가?",
            "다익스트라 알고리즘은 거리 추정값이 가장 작은 정점을 우선순위 큐에서 선택한다.",
            "오븐을 예열하고 케이크 틀에 버터를 바른다.",
        ]
    )

    def similarity(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        norm = (sum(a * a for a in left) ** 0.5) * (sum(b * b for b in right) ** 0.5)
        return dot / norm

    assert similarity(question, korean_answer) > similarity(question, unrelated)
