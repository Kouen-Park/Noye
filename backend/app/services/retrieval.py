"""Semantic retrieval over indexed chunks.

The query takes the same path as the documents did — embedded by the same
model, compared in the same space — so a question can match a passage that
shares no keywords with it. Every result keeps the provenance stored at index
time, which is what makes a citation possible without asking the language model
to remember where anything came from.
"""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import get_settings
from app.services.embeddings import embed_text
from app.services.indexing import (
    CHUNK_INDEX,
    CONTENT,
    FILE_ID,
    PAGE_NUMBER,
    IndexingError,
    get_client,
)

#: Chunks returned by default. Enough context for an answer without crowding
#: out the generation model's budget.
DEFAULT_LIMIT = 5


@dataclass(frozen=True)
class SearchResult:
    """One retrieved chunk and where it came from.

    ``file_name`` is deliberately absent: the human-readable name lives in
    SQLite alongside the rest of the file metadata, which does not exist yet.
    Callers join on ``file_id`` once it does. Storing the name in the vector
    payload would duplicate it and let a rename leave stale copies behind.
    """

    content: str
    file_id: str
    page_number: int
    chunk_index: int
    score: float


def search(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    file_ids: list[str] | None = None,
    min_score: float | None = None,
    client: QdrantClient | None = None,
) -> list[SearchResult]:
    """Find the chunks most similar in meaning to ``query``.

    Results are ordered by descending similarity. ``file_ids`` restricts the
    search to specific sources; ``min_score`` drops weak matches, which is
    useful because a vector search always returns its nearest neighbours even
    when nothing in the index is actually relevant.

    Raises:
        ValueError: ``query`` is empty, or ``limit`` is not positive.
        EmbeddingError: the query could not be embedded.
        IndexingError: Qdrant could not be searched.
    """
    if not query.strip():
        raise ValueError("Cannot search with an empty query")
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")

    settings = get_settings()
    client = client or get_client()

    query_vector = embed_text(query)

    try:
        if not client.collection_exists(settings.qdrant_collection):
            return []
        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            limit=limit,
            query_filter=_files_filter(file_ids),
            score_threshold=min_score,
            with_payload=True,
        )
    except (UnexpectedResponse, OSError, ValueError) as exc:
        raise IndexingError(f"Could not search Qdrant: {exc}") from exc

    return [_to_result(point) for point in response.points]


def _to_result(point) -> SearchResult:
    payload = point.payload or {}
    return SearchResult(
        content=payload.get(CONTENT, ""),
        file_id=payload.get(FILE_ID, ""),
        page_number=payload.get(PAGE_NUMBER, 0),
        chunk_index=payload.get(CHUNK_INDEX, 0),
        score=point.score,
    )


def _files_filter(file_ids: list[str] | None) -> models.Filter | None:
    if not file_ids:
        return None
    return models.Filter(
        must=[
            models.FieldCondition(key=FILE_ID, match=models.MatchAny(any=list(file_ids)))
        ]
    )
