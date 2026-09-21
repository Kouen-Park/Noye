"""Qdrant indexing.

Qdrant holds derived data: vectors plus enough provenance to point back at the
original file and page. It is never the source of truth, so everything here is
designed to be rebuildable from `data/sources/` — and to be safely re-runnable,
which is why point IDs are derived from the chunk's identity rather than
generated fresh on each insert. Re-indexing a file therefore overwrites its
points instead of silently duplicating them.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import get_settings
from app.services.chunking import Chunk

#: Namespace for deterministic point IDs. Fixed forever: changing it would
#: orphan every point already stored.
_POINT_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

#: Payload keys. Named here so indexing and retrieval cannot drift apart.
FILE_ID = "file_id"
PAGE_NUMBER = "page_number"
CHUNK_INDEX = "chunk_index"
CONTENT = "content"


class IndexingError(Exception):
    """A vector index operation failed.

    Wraps Qdrant transport and API errors so callers do not depend on
    qdrant-client's exception types.
    """


def get_client() -> QdrantClient:
    """Return a Qdrant client for the configured URL."""
    return QdrantClient(url=get_settings().qdrant_url)


def point_id(file_id: str, chunk_index: int) -> str:
    """Return the stable point ID for one chunk of one file.

    Deterministic so that re-indexing a file replaces its points. Qdrant only
    accepts unsigned integers or UUIDs as IDs, hence UUID5 rather than a
    readable string.
    """
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{file_id}:{chunk_index}"))


def ensure_collection(client: QdrantClient | None = None) -> None:
    """Create the configured collection if it does not exist.

    Safe to call repeatedly. Does not touch an existing collection, so it can
    never destroy an index; use :func:`recreate_collection` for that.
    """
    settings = get_settings()
    client = client or get_client()

    try:
        if client.collection_exists(settings.qdrant_collection):
            return
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=models.VectorParams(
                size=settings.qdrant_vector_size,
                distance=models.Distance.COSINE,
            ),
        )
    except (UnexpectedResponse, OSError, ValueError) as exc:
        raise IndexingError(
            f"Could not prepare Qdrant collection "
            f"'{settings.qdrant_collection}' at {settings.qdrant_url}: {exc}"
        ) from exc


def recreate_collection(client: QdrantClient | None = None) -> None:
    """Drop the collection and create it empty.

    Destructive: every stored vector is lost. Intended for the rebuild-index
    flow and for an embedding-model change, where existing vectors are no
    longer comparable with new ones. Source files are untouched, so the index
    can be rebuilt from them.
    """
    settings = get_settings()
    client = client or get_client()

    try:
        if client.collection_exists(settings.qdrant_collection):
            client.delete_collection(settings.qdrant_collection)
    except (UnexpectedResponse, OSError, ValueError) as exc:
        raise IndexingError(
            f"Could not delete Qdrant collection "
            f"'{settings.qdrant_collection}': {exc}"
        ) from exc

    ensure_collection(client)


def index_chunks(
    chunks: Sequence[Chunk],
    vectors: Sequence[Sequence[float]],
    client: QdrantClient | None = None,
) -> int:
    """Store chunk vectors with their provenance, returning the number stored.

    ``vectors[n]`` must be the embedding of ``chunks[n]``; a length mismatch is
    a programming error and raises rather than storing a misaligned index,
    which would attach text to the wrong vector and produce citations that
    point at unrelated pages.

    Raises:
        ValueError: the sequences differ in length, or a vector has the wrong
            dimension.
        IndexingError: Qdrant could not be reached or rejected the write.
    """
    if len(chunks) != len(vectors):
        raise ValueError(
            f"Got {len(chunks)} chunks but {len(vectors)} vectors; "
            "they must correspond one to one"
        )

    if not chunks:
        return 0

    settings = get_settings()
    expected = settings.qdrant_vector_size
    for chunk, vector in zip(chunks, vectors):
        if len(vector) != expected:
            raise ValueError(
                f"Chunk {chunk.chunk_index} of file {chunk.file_id} has "
                f"{len(vector)} dimensions, expected {expected}"
            )

    client = client or get_client()
    ensure_collection(client)

    points = [
        models.PointStruct(
            id=point_id(chunk.file_id, chunk.chunk_index),
            vector=list(vector),
            payload={
                FILE_ID: chunk.file_id,
                PAGE_NUMBER: chunk.page_number,
                CHUNK_INDEX: chunk.chunk_index,
                CONTENT: chunk.content,
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]

    try:
        client.upsert(collection_name=settings.qdrant_collection, points=points)
    except (UnexpectedResponse, OSError, ValueError) as exc:
        raise IndexingError(f"Could not store vectors in Qdrant: {exc}") from exc

    return len(points)


def delete_file_chunks(file_id: str, client: QdrantClient | None = None) -> None:
    """Delete every vector belonging to one file.

    Called when a source is removed. Leaving vectors behind would let a deleted
    document keep answering questions, which is both wrong and a privacy
    problem.
    """
    settings = get_settings()
    client = client or get_client()

    try:
        if not client.collection_exists(settings.qdrant_collection):
            return
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.FilterSelector(filter=_file_filter(file_id)),
        )
    except (UnexpectedResponse, OSError, ValueError) as exc:
        raise IndexingError(
            f"Could not delete vectors for file {file_id}: {exc}"
        ) from exc


def count_chunks(
    file_id: str | None = None, client: QdrantClient | None = None
) -> int:
    """Count stored vectors, for the whole collection or for one file."""
    settings = get_settings()
    client = client or get_client()

    try:
        if not client.collection_exists(settings.qdrant_collection):
            return 0
        result = client.count(
            collection_name=settings.qdrant_collection,
            count_filter=_file_filter(file_id) if file_id else None,
            exact=True,
        )
    except (UnexpectedResponse, OSError, ValueError) as exc:
        raise IndexingError(f"Could not count vectors in Qdrant: {exc}") from exc

    return result.count


def _file_filter(file_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key=FILE_ID, match=models.MatchValue(value=file_id))]
    )
