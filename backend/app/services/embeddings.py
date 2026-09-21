"""Local embeddings through Ollama.

Everything Noye searches is compared as a vector, so this is the one place that
turns text into one. Two properties are enforced here rather than discovered
later:

* the returned dimension matches the configured vector size, because a silent
  mismatch would only surface as a rejected Qdrant insert or, worse, as
  meaningless search results;
* a failure to reach Ollama raises :class:`EmbeddingError` instead of an httpx
  exception, so callers can map it to a ``FAILED`` processing state without
  knowing which HTTP library is in use.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from app.config import get_settings
from app.services.chunking import Chunk

#: Texts sent per Ollama request. Ollama accepts a list and returns embeddings
#: in the same order, so batching cuts request overhead; the cap keeps a large
#: document from becoming one enormous request.
DEFAULT_BATCH_SIZE = 16

#: Embedding a batch on local hardware is slow enough that the default httpx
#: timeout of 5 seconds is not workable.
DEFAULT_TIMEOUT_SECONDS = 120.0


class EmbeddingError(Exception):
    """Text could not be embedded.

    Covers an unreachable Ollama, a model that has not been pulled, a malformed
    response, and a vector whose dimension disagrees with the configuration.
    """


def embed_text(text: str, *, client: httpx.Client | None = None) -> list[float]:
    """Embed a single string.

    Raises:
        ValueError: ``text`` is empty or whitespace only. An empty embedding is
            never useful, and silently returning a zero vector would pollute
            search results.
        EmbeddingError: Ollama could not be reached or returned an unusable
            response.
    """
    if not text.strip():
        raise ValueError("Cannot embed empty text")

    return embed_texts([text], client=client)[0]


def embed_texts(
    texts: Sequence[str],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    client: httpx.Client | None = None,
) -> list[list[float]]:
    """Embed several strings, returning one vector per input in the same order.

    Raises:
        ValueError: ``batch_size`` is not positive, or any text is empty.
        EmbeddingError: Ollama could not be reached or returned an unusable
            response.
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")

    for index, text in enumerate(texts):
        if not text.strip():
            raise ValueError(f"Cannot embed empty text at index {index}")

    if not texts:
        return []

    settings = get_settings()
    vectors: list[list[float]] = []

    if client is None:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as owned_client:
            for batch in _batched(texts, batch_size):
                vectors.extend(_request_embeddings(owned_client, batch, settings))
    else:
        for batch in _batched(texts, batch_size):
            vectors.extend(_request_embeddings(client, batch, settings))

    return vectors


def embed_chunks(
    chunks: Sequence[Chunk],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    client: httpx.Client | None = None,
) -> list[list[float]]:
    """Embed chunk contents, returning one vector per chunk in the same order.

    The vector at position *n* belongs to ``chunks[n]``; pairing them is the
    caller's job, which keeps this function free of storage concerns.
    """
    return embed_texts(
        [chunk.content for chunk in chunks], batch_size=batch_size, client=client
    )


def _batched(texts: Sequence[str], size: int) -> list[Sequence[str]]:
    return [texts[start : start + size] for start in range(0, len(texts), size)]


def _request_embeddings(
    client: httpx.Client, batch: Sequence[str], settings
) -> list[list[float]]:
    model = settings.ollama_embedding_model
    url = f"{settings.ollama_base_url.rstrip('/')}/api/embed"

    try:
        response = client.post(url, json={"model": model, "input": list(batch)})
    except httpx.RequestError as exc:
        raise EmbeddingError(
            f"Could not reach Ollama at {settings.ollama_base_url}. "
            "Check that it is running (brew services start ollama)."
        ) from exc

    if response.status_code == 404:
        raise EmbeddingError(
            f"Embedding model '{model}' is not available in Ollama. "
            f"Pull it first: ollama pull {model}"
        )

    if response.status_code >= 400:
        raise EmbeddingError(
            f"Ollama returned HTTP {response.status_code} while embedding "
            f"with '{model}': {response.text[:200]}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise EmbeddingError("Ollama returned a non-JSON response") from exc

    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, list) or not embeddings:
        raise EmbeddingError(
            f"Ollama response contained no embeddings (keys: {sorted(payload)})"
        )

    if len(embeddings) != len(batch):
        raise EmbeddingError(
            f"Ollama returned {len(embeddings)} embeddings for {len(batch)} inputs"
        )

    expected = settings.qdrant_vector_size
    for vector in embeddings:
        if len(vector) != expected:
            raise EmbeddingError(
                f"Embedding model '{model}' returned {len(vector)} dimensions but "
                f"the configured vector size is {expected}. Update "
                "QDRANT_VECTOR_SIZE and recreate the Qdrant collection, or "
                "switch back to the model the collection was built with."
            )

    return embeddings
