"""Tests for semantic retrieval.

Unit tests stub the query embedding so ranking behavior can be asserted
deterministically against an in-memory Qdrant. The integration tests at the
bottom run the real pipeline — real embeddings, real server — and skip when
either service is unavailable.
"""

from __future__ import annotations

import httpx
import pytest
from qdrant_client import QdrantClient

from app.config import get_settings
from app.services import retrieval
from app.services.chunking import Chunk
from app.services.indexing import delete_file_chunks, index_chunks
from app.services.retrieval import SearchResult, search

VECTOR_SIZE = get_settings().qdrant_vector_size


def axis_vector(axis: int) -> list[float]:
    """A unit vector pointing along one axis, so similarity is predictable."""
    vector = [0.0] * VECTOR_SIZE
    vector[axis] = 1.0
    return vector


@pytest.fixture
def client() -> QdrantClient:
    memory_client = QdrantClient(":memory:")
    yield memory_client
    memory_client.close()


@pytest.fixture
def stub_query_embedding(monkeypatch: pytest.MonkeyPatch):
    """Replace the query embedding with a chosen vector."""

    def set_vector(vector: list[float]) -> None:
        monkeypatch.setattr(retrieval, "embed_text", lambda text: vector)

    return set_vector


def chunk(index: int, *, file_id: str = "file-1", page: int = 1, text: str = "") -> Chunk:
    return Chunk(
        file_id=file_id,
        page_number=page,
        chunk_index=index,
        content=text or f"chunk {index}",
    )


def test_returns_the_closest_chunk_first(client, stub_query_embedding) -> None:
    index_chunks(
        [chunk(0, text="on axis zero"), chunk(1, text="on axis one")],
        [axis_vector(0), axis_vector(1)],
        client=client,
    )
    stub_query_embedding(axis_vector(1))

    results = search("anything", client=client)

    assert results[0].content == "on axis one"


def test_results_are_ordered_by_descending_score(client, stub_query_embedding) -> None:
    mixed = [0.0] * VECTOR_SIZE
    mixed[0], mixed[1], mixed[2] = 0.9, 0.5, 0.1
    index_chunks(
        [chunk(0), chunk(1), chunk(2)],
        [axis_vector(0), axis_vector(1), axis_vector(2)],
        client=client,
    )
    stub_query_embedding(mixed)

    results = search("anything", client=client)

    scores = [result.score for result in results]
    assert scores == sorted(scores, reverse=True)


def test_result_carries_full_provenance(client, stub_query_embedding) -> None:
    index_chunks(
        [chunk(7, file_id="algorithms", page=34, text="Dijkstra selects the minimum.")],
        [axis_vector(3)],
        client=client,
    )
    stub_query_embedding(axis_vector(3))

    result = search("anything", client=client)[0]

    assert isinstance(result, SearchResult)
    assert result.file_id == "algorithms"
    assert result.page_number == 34
    assert result.chunk_index == 7
    assert result.content == "Dijkstra selects the minimum."
    assert result.score > 0.9


def test_limit_caps_the_number_of_results(client, stub_query_embedding) -> None:
    index_chunks(
        [chunk(index) for index in range(6)],
        [axis_vector(index) for index in range(6)],
        client=client,
    )
    stub_query_embedding(axis_vector(0))

    assert len(search("anything", limit=2, client=client)) == 2


def test_default_limit_is_applied(client, stub_query_embedding) -> None:
    index_chunks(
        [chunk(index) for index in range(10)],
        [axis_vector(index) for index in range(10)],
        client=client,
    )
    stub_query_embedding(axis_vector(0))

    assert len(search("anything", client=client)) == retrieval.DEFAULT_LIMIT


def test_file_ids_restrict_the_search(client, stub_query_embedding) -> None:
    index_chunks(
        [chunk(0, file_id="wanted"), chunk(1, file_id="ignored")],
        [axis_vector(0), axis_vector(0)],
        client=client,
    )
    stub_query_embedding(axis_vector(0))

    results = search("anything", file_ids=["wanted"], client=client)

    assert {result.file_id for result in results} == {"wanted"}


def test_several_file_ids_are_all_searched(client, stub_query_embedding) -> None:
    index_chunks(
        [chunk(0, file_id="a"), chunk(1, file_id="b"), chunk(2, file_id="c")],
        [axis_vector(0), axis_vector(0), axis_vector(0)],
        client=client,
    )
    stub_query_embedding(axis_vector(0))

    results = search("anything", file_ids=["a", "b"], client=client)

    assert {result.file_id for result in results} == {"a", "b"}


def test_min_score_drops_weak_matches(client, stub_query_embedding) -> None:
    index_chunks(
        [chunk(0, text="aligned"), chunk(1, text="orthogonal")],
        [axis_vector(0), axis_vector(1)],
        client=client,
    )
    stub_query_embedding(axis_vector(0))

    results = search("anything", min_score=0.5, client=client)

    # The orthogonal vector scores 0 under cosine and must be excluded.
    assert [result.content for result in results] == ["aligned"]


def test_search_without_a_collection_returns_nothing(client, stub_query_embedding) -> None:
    stub_query_embedding(axis_vector(0))

    assert search("anything", client=client) == []


def test_search_on_an_empty_collection_returns_nothing(client, stub_query_embedding) -> None:
    index_chunks([], [], client=client)
    stub_query_embedding(axis_vector(0))

    assert search("anything", client=client) == []


def test_empty_query_is_rejected(client) -> None:
    with pytest.raises(ValueError, match="empty query"):
        search("   ", client=client)


@pytest.mark.parametrize("limit", [0, -5])
def test_non_positive_limit_is_rejected(client, limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        search("question", limit=limit, client=client)


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

INTEGRATION_FILE = "integration-search-file"


@pytest.fixture
def indexed_corpus() -> QdrantClient:
    """Index a small real corpus, then remove it."""
    from app.services.embeddings import embed_chunks

    real = QdrantClient(url=get_settings().qdrant_url)
    chunks = [
        Chunk(
            file_id=INTEGRATION_FILE,
            page_number=34,
            chunk_index=0,
            content=(
                "Dijkstra's algorithm repeatedly selects the unvisited vertex with "
                "the smallest distance estimate, using a priority queue."
            ),
        ),
        Chunk(
            file_id=INTEGRATION_FILE,
            page_number=41,
            chunk_index=1,
            content=(
                "Negative edge weights break Dijkstra's correctness guarantee; "
                "Bellman-Ford handles them instead."
            ),
        ),
        Chunk(
            file_id=INTEGRATION_FILE,
            page_number=88,
            chunk_index=2,
            content=(
                "Preheat the oven to 180 degrees, butter a cake tin and sift the "
                "flour with the baking powder."
            ),
        ),
    ]
    index_chunks(chunks, embed_chunks(chunks), client=real)
    yield real
    delete_file_chunks(INTEGRATION_FILE, client=real)
    real.close()


@requires_services
def test_real_search_finds_the_relevant_page(indexed_corpus: QdrantClient) -> None:
    results = search(
        "How does Dijkstra choose the next vertex?",
        limit=1,
        file_ids=[INTEGRATION_FILE],
        client=indexed_corpus,
    )

    assert results[0].page_number == 34


@requires_services
def test_real_search_matches_by_meaning_not_keywords(
    indexed_corpus: QdrantClient,
) -> None:
    # "priority queue" and "shortest path" do not appear together in the query.
    results = search(
        "Which algorithm should I use when some edges have negative costs?",
        limit=1,
        file_ids=[INTEGRATION_FILE],
        client=indexed_corpus,
    )

    assert results[0].page_number == 41


@requires_services
def test_real_search_answers_a_korean_question_about_english_text(
    indexed_corpus: QdrantClient,
) -> None:
    results = search(
        "다익스트라는 다음 정점을 어떻게 선택하는가?",
        limit=1,
        file_ids=[INTEGRATION_FILE],
        client=indexed_corpus,
    )

    assert results[0].page_number == 34


@requires_services
def test_real_search_ranks_the_unrelated_passage_last(
    indexed_corpus: QdrantClient,
) -> None:
    results = search(
        "shortest path selection in a weighted graph",
        limit=3,
        file_ids=[INTEGRATION_FILE],
        client=indexed_corpus,
    )

    assert results[-1].page_number == 88
