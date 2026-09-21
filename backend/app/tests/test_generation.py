"""Tests for grounded generation.

Unit tests use ``httpx.MockTransport`` and a stubbed search, so prompt
construction and error handling are asserted without a model. The integration
tests run the real model and check the behavior that matters for a knowledge
tool: the answer comes from the excerpts, and the model declines when they do
not contain it.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import get_settings
from app.services import generation
from app.services.chunking import Chunk
from app.services.generation import (
    NO_CONTEXT_ANSWER,
    SYSTEM_PROMPT,
    Answer,
    GenerationError,
    answer_question,
    build_prompt,
    generate,
)
from app.services.indexing import delete_file_chunks, index_chunks
from app.services.retrieval import SearchResult


def result(page: int, content: str, score: float = 0.9) -> SearchResult:
    return SearchResult(
        content=content,
        file_id="file-1",
        page_number=page,
        chunk_index=page,
        score=score,
    )


def mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def responder(text: str = "An answer.", *, status: int = 200, body: str | None = None):
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        if body is not None:
            return httpx.Response(status, text=body)
        return httpx.Response(status, json={"response": text})

    handler.seen = seen  # type: ignore[attr-defined]
    return handler


@pytest.fixture
def stub_search(monkeypatch: pytest.MonkeyPatch):
    def set_results(results: list[SearchResult]) -> list[dict]:
        calls: list[dict] = []

        def fake_search(query, *, limit=None, file_ids=None, min_score=None, client=None):
            calls.append(
                {"query": query, "limit": limit, "file_ids": file_ids, "min_score": min_score}
            )
            return results

        monkeypatch.setattr(generation, "search", fake_search)
        return calls

    return set_results


def test_prompt_contains_every_excerpt_and_its_page() -> None:
    prompt = build_prompt(
        "How does Dijkstra choose?",
        [result(34, "Smallest distance estimate."), result(41, "Negative weights break it.")],
    )

    assert "Excerpt 1 — page 34" in prompt
    assert "Excerpt 2 — page 41" in prompt
    assert "Smallest distance estimate." in prompt
    assert "Negative weights break it." in prompt
    assert "How does Dijkstra choose?" in prompt


def test_prompt_numbers_excerpts_from_one() -> None:
    prompt = build_prompt("q", [result(5, "a"), result(6, "b"), result(7, "c")])

    assert "Excerpt 1" in prompt and "Excerpt 3" in prompt
    assert "Excerpt 0" not in prompt


def test_system_prompt_forbids_inventing_sources() -> None:
    # The whole citation design depends on the model not writing its own.
    assert "Do not write a citation list" in SYSTEM_PROMPT
    assert "only the numbered excerpts" in SYSTEM_PROMPT


def test_generate_returns_the_model_text() -> None:
    handler = responder("  Dijkstra picks the smallest estimate.  ")

    with mock_client(handler) as client:
        assert generate("prompt", client=client) == "Dijkstra picks the smallest estimate."


def test_generate_sends_the_configured_model_and_system_prompt() -> None:
    handler = responder()

    with mock_client(handler) as client:
        generate("a prompt", client=client)

    sent = handler.seen[0]
    assert sent["model"] == get_settings().ollama_model
    assert sent["system"] == SYSTEM_PROMPT
    assert sent["prompt"] == "a prompt"
    assert sent["stream"] is False


def test_generate_disables_thinking_by_default() -> None:
    handler = responder()

    with mock_client(handler) as client:
        generate("a prompt", client=client)

    # With thinking on, a one-sentence answer measured ~30x slower locally.
    assert handler.seen[0]["think"] is False


def test_empty_prompt_is_rejected() -> None:
    handler = responder()

    with mock_client(handler) as client:
        with pytest.raises(ValueError, match="empty prompt"):
            generate("   ", client=client)

    assert handler.seen == []


def test_unreachable_ollama_raises_generation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with mock_client(handler) as client:
        with pytest.raises(GenerationError, match="Could not reach Ollama"):
            generate("prompt", client=client)


def test_missing_model_raises_with_the_pull_command() -> None:
    handler = responder(status=404, body="not found")

    with mock_client(handler) as client:
        with pytest.raises(GenerationError, match="ollama pull"):
            generate("prompt", client=client)


def test_server_error_raises_generation_error() -> None:
    handler = responder(status=500, body="boom")

    with mock_client(handler) as client:
        with pytest.raises(GenerationError, match="HTTP 500"):
            generate("prompt", client=client)


def test_non_json_response_raises_generation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    with mock_client(handler) as client:
        with pytest.raises(GenerationError, match="non-JSON"):
            generate("prompt", client=client)


def test_blank_answer_raises_generation_error() -> None:
    handler = responder("   ")

    with mock_client(handler) as client:
        with pytest.raises(GenerationError, match="no answer text"):
            generate("prompt", client=client)


def test_answer_question_attaches_the_retrieved_sources(stub_search) -> None:
    sources = [result(34, "Smallest distance estimate.")]
    stub_search(sources)
    handler = responder("Dijkstra picks the smallest estimate.")

    with mock_client(handler) as client:
        answer = answer_question("How does Dijkstra choose?", client=client)

    assert isinstance(answer, Answer)
    assert answer.text == "Dijkstra picks the smallest estimate."
    assert answer.sources == sources
    assert answer.is_grounded


def test_answer_question_passes_search_options_through(stub_search) -> None:
    calls = stub_search([result(1, "text")])
    handler = responder()

    with mock_client(handler) as client:
        answer_question("q", limit=3, file_ids=["a"], min_score=0.4, client=client)

    assert calls[0] == {"query": "q", "limit": 3, "file_ids": ["a"], "min_score": 0.4}


def test_no_results_means_no_model_call(stub_search) -> None:
    stub_search([])
    handler = responder("should never be used")

    with mock_client(handler) as client:
        answer = answer_question("something unindexed", client=client)

    assert answer.text == NO_CONTEXT_ANSWER
    assert answer.sources == []
    assert not answer.is_grounded
    # Asking a model to answer with no context is how ungrounded answers happen.
    assert handler.seen == []


def test_empty_question_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty question"):
        answer_question("  ")


# --- Integration: requires Ollama and Qdrant ---------------------------------


def service_is_up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2.0).status_code == 200
    except httpx.RequestError:
        return False


requires_services = pytest.mark.skipif(
    not (
        service_is_up(f"{get_settings().ollama_base_url}/api/version")
        and service_is_up(f"{get_settings().qdrant_url}/")
    ),
    reason="Ollama or Qdrant is not running",
)

INTEGRATION_FILE = "integration-rag-file"


@pytest.fixture
def indexed_corpus():
    from qdrant_client import QdrantClient

    from app.services.embeddings import embed_chunks

    real = QdrantClient(url=get_settings().qdrant_url)
    chunks = [
        Chunk(
            file_id=INTEGRATION_FILE,
            page_number=34,
            chunk_index=0,
            content=(
                "Dijkstra's algorithm repeatedly selects the unvisited vertex with "
                "the smallest distance estimate, taken from a priority queue."
            ),
        ),
        Chunk(
            file_id=INTEGRATION_FILE,
            page_number=41,
            chunk_index=1,
            content=(
                "Negative edge weights break Dijkstra's correctness guarantee, so "
                "Bellman-Ford is used when edges may be negative."
            ),
        ),
    ]
    index_chunks(chunks, embed_chunks(chunks), client=real)
    yield real
    delete_file_chunks(INTEGRATION_FILE, client=real)
    real.close()


@requires_services
def test_real_answer_uses_the_retrieved_passage(indexed_corpus) -> None:
    answer = answer_question(
        "How does Dijkstra pick the next vertex?",
        file_ids=[INTEGRATION_FILE],
        qdrant_client=indexed_corpus,
    )

    assert answer.is_grounded
    assert answer.sources[0].page_number == 34
    lowered = answer.text.lower()
    assert "smallest" in lowered or "minimum" in lowered or "priority queue" in lowered


@requires_services
def test_real_answer_declines_when_the_excerpts_do_not_contain_it(
    indexed_corpus,
) -> None:
    """The behavior that separates a knowledge tool from a chatbot."""
    answer = answer_question(
        "What is the author's home address?",
        file_ids=[INTEGRATION_FILE],
        qdrant_client=indexed_corpus,
    )

    lowered = answer.text.lower()
    assert any(
        phrase in lowered
        for phrase in ("not", "no ", "does not", "cannot", "don't", "unable")
    ), f"expected a refusal, got: {answer.text}"


@requires_services
def test_real_answer_replies_in_korean_to_a_korean_question(indexed_corpus) -> None:
    answer = answer_question(
        "다익스트라는 다음 정점을 어떻게 선택하는가?",
        file_ids=[INTEGRATION_FILE],
        qdrant_client=indexed_corpus,
    )

    assert answer.sources[0].page_number == 34
    # A Hangul syllable anywhere in the answer is enough to show it replied in Korean.
    assert any("\uac00" <= character <= "\ud7a3" for character in answer.text)
