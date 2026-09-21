"""Tests for Qdrant indexing.

Most tests run against qdrant-client's in-memory mode, which is real Qdrant
behavior without Docker. The integration tests at the bottom use the running
server and skip when it is unreachable.
"""

from __future__ import annotations

import httpx
import pytest
from qdrant_client import QdrantClient

from app.config import get_settings
from app.services.chunking import Chunk
from app.services.indexing import (
    CONTENT,
    FILE_ID,
    PAGE_NUMBER,
    count_chunks,
    delete_file_chunks,
    ensure_collection,
    index_chunks,
    point_id,
    recreate_collection,
)

VECTOR_SIZE = get_settings().qdrant_vector_size
COLLECTION = get_settings().qdrant_collection


@pytest.fixture
def client() -> QdrantClient:
    memory_client = QdrantClient(":memory:")
    yield memory_client
    memory_client.close()


def vector(fill: float) -> list[float]:
    return [fill] * VECTOR_SIZE


def chunk(index: int, *, file_id: str = "file-1", page: int = 1, text: str = "") -> Chunk:
    return Chunk(
        file_id=file_id,
        page_number=page,
        chunk_index=index,
        content=text or f"chunk {index} content",
    )


def test_ensure_collection_creates_it(client: QdrantClient) -> None:
    ensure_collection(client)

    assert client.collection_exists(COLLECTION)


def test_ensure_collection_is_idempotent(client: QdrantClient) -> None:
    ensure_collection(client)
    index_chunks([chunk(0)], [vector(0.1)], client=client)
    ensure_collection(client)

    # Calling it again must not wipe what is already stored.
    assert count_chunks(client=client) == 1


def test_collection_uses_the_configured_dimension(client: QdrantClient) -> None:
    ensure_collection(client)

    info = client.get_collection(COLLECTION)
    assert info.config.params.vectors.size == VECTOR_SIZE


def test_index_chunks_stores_one_point_per_chunk(client: QdrantClient) -> None:
    chunks = [chunk(0), chunk(1), chunk(2)]
    vectors = [vector(0.1), vector(0.2), vector(0.3)]

    stored = index_chunks(chunks, vectors, client=client)

    assert stored == 3
    assert count_chunks(client=client) == 3


def test_payload_carries_full_provenance(client: QdrantClient) -> None:
    source = chunk(4, file_id="algorithms", page=34, text="Dijkstra selects the minimum.")

    index_chunks([source], [vector(0.5)], client=client)

    points = client.query_points(COLLECTION, query=vector(0.5), limit=1).points
    payload = points[0].payload
    assert payload[FILE_ID] == "algorithms"
    assert payload[PAGE_NUMBER] == 34
    assert payload[CONTENT] == "Dijkstra selects the minimum."


def test_reindexing_the_same_chunks_does_not_duplicate(client: QdrantClient) -> None:
    chunks = [chunk(0), chunk(1)]
    vectors = [vector(0.1), vector(0.2)]

    index_chunks(chunks, vectors, client=client)
    index_chunks(chunks, vectors, client=client)

    assert count_chunks(client=client) == 2


def test_reindexing_updates_content_in_place(client: QdrantClient) -> None:
    index_chunks([chunk(0, text="old text")], [vector(0.1)], client=client)
    index_chunks([chunk(0, text="new text")], [vector(0.1)], client=client)

    points = client.query_points(COLLECTION, query=vector(0.1), limit=5).points
    assert len(points) == 1
    assert points[0].payload[CONTENT] == "new text"


def test_point_id_is_stable_and_distinct() -> None:
    assert point_id("file-1", 0) == point_id("file-1", 0)
    assert point_id("file-1", 0) != point_id("file-1", 1)
    assert point_id("file-1", 0) != point_id("file-2", 0)


def test_indexing_nothing_stores_nothing(client: QdrantClient) -> None:
    assert index_chunks([], [], client=client) == 0


def test_mismatched_lengths_are_rejected(client: QdrantClient) -> None:
    with pytest.raises(ValueError, match="correspond one to one"):
        index_chunks([chunk(0), chunk(1)], [vector(0.1)], client=client)


def test_wrong_dimension_is_rejected(client: QdrantClient) -> None:
    with pytest.raises(ValueError, match="expected"):
        index_chunks([chunk(0)], [[0.1, 0.2, 0.3]], client=client)


def test_delete_removes_only_the_named_file(client: QdrantClient) -> None:
    index_chunks(
        [chunk(0, file_id="keep"), chunk(1, file_id="remove")],
        [vector(0.1), vector(0.2)],
        client=client,
    )

    delete_file_chunks("remove", client=client)

    assert count_chunks(file_id="remove", client=client) == 0
    assert count_chunks(file_id="keep", client=client) == 1


def test_delete_on_a_missing_collection_is_harmless(client: QdrantClient) -> None:
    delete_file_chunks("never-indexed", client=client)


def test_delete_of_an_unknown_file_is_harmless(client: QdrantClient) -> None:
    index_chunks([chunk(0, file_id="keep")], [vector(0.1)], client=client)

    delete_file_chunks("not-there", client=client)

    assert count_chunks(client=client) == 1


def test_count_on_a_missing_collection_is_zero(client: QdrantClient) -> None:
    assert count_chunks(client=client) == 0


def test_count_can_be_scoped_to_one_file(client: QdrantClient) -> None:
    index_chunks(
        [chunk(0, file_id="a"), chunk(1, file_id="a"), chunk(2, file_id="b")],
        [vector(0.1), vector(0.2), vector(0.3)],
        client=client,
    )

    assert count_chunks(file_id="a", client=client) == 2
    assert count_chunks(file_id="b", client=client) == 1
    assert count_chunks(client=client) == 3


def test_recreate_collection_empties_it(client: QdrantClient) -> None:
    index_chunks([chunk(0)], [vector(0.1)], client=client)

    recreate_collection(client)

    assert client.collection_exists(COLLECTION)
    assert count_chunks(client=client) == 0


def test_recreate_collection_works_when_none_exists(client: QdrantClient) -> None:
    recreate_collection(client)

    assert client.collection_exists(COLLECTION)


# --- Integration: requires the Qdrant container ------------------------------


def qdrant_is_available() -> bool:
    try:
        response = httpx.get(f"{get_settings().qdrant_url}/", timeout=2.0)
    except httpx.RequestError:
        return False
    return response.status_code == 200


requires_qdrant = pytest.mark.skipif(
    not qdrant_is_available(), reason="Qdrant is not running"
)


@pytest.fixture
def server_client() -> QdrantClient:
    """A real-server client whose test data is removed afterwards."""
    real = QdrantClient(url=get_settings().qdrant_url)
    yield real
    for file_id in ("integration-test-file", "integration-test-other"):
        delete_file_chunks(file_id, client=real)
    real.close()


@requires_qdrant
def test_real_server_round_trip(server_client: QdrantClient) -> None:
    source = chunk(0, file_id="integration-test-file", page=12, text="Round trip text.")

    stored = index_chunks([source], [vector(0.25)], client=server_client)

    assert stored == 1
    assert count_chunks(file_id="integration-test-file", client=server_client) == 1

    points = server_client.query_points(
        COLLECTION,
        query=vector(0.25),
        limit=1,
        query_filter=None,
    ).points
    assert any(point.payload[CONTENT] == "Round trip text." for point in points)


@requires_qdrant
def test_real_server_delete_is_scoped_to_the_file(server_client: QdrantClient) -> None:
    index_chunks(
        [
            chunk(0, file_id="integration-test-file"),
            chunk(0, file_id="integration-test-other"),
        ],
        [vector(0.3), vector(0.4)],
        client=server_client,
    )

    delete_file_chunks("integration-test-file", client=server_client)

    assert count_chunks(file_id="integration-test-file", client=server_client) == 0
    assert count_chunks(file_id="integration-test-other", client=server_client) == 1
