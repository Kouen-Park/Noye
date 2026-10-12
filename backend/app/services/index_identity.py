"""Identity of the processing configuration that produced a vector space.

Model tags can be replaced without changing their name. Resolve the installed
digest through Ollama's local /api/tags endpoint rather than guessing from a tag.
Source revisions are independent and stay in files.content_hash.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import version

import httpx

from app.config import get_settings
from app.services import embeddings
from app.services.embeddings import EmbeddingError

CHUNKER_VERSION = "page-boundary-v1"
EXTRACTOR_VERSION = "pdf-text-utf8-v1"


@dataclass(frozen=True)
class IndexIdentity:
    metadata_json: str

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.metadata_json.encode("utf-8")).hexdigest()


def build_identity(model_digest: str) -> IndexIdentity:
    if not model_digest:
        raise EmbeddingError("The embedding model has no recorded digest.")
    settings = get_settings()
    metadata = {
        "version": 1,
        "embedding_model": normalize_model_tag(settings.ollama_embedding_model),
        "model_digest": model_digest,
        "vector_size": settings.qdrant_vector_size,
        "input_format": embeddings.input_format_version(),
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "chunker_version": CHUNKER_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "pymupdf_version": version("pymupdf"),
    }
    return IndexIdentity(json.dumps(metadata, sort_keys=True, separators=(",", ":")))


def normalize_model_tag(name: str) -> str:
    # A registry port may contain ':', so inspect only the final path segment.
    return name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"


def resolve_model_digest(*, client: httpx.Client | None = None) -> str:
    settings = get_settings()
    owned = client is None
    transport = client or httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False)
    try:
        try:
            response = transport.get(f"{settings.ollama_base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            models = response.json()["models"]
            if not isinstance(models, list):
                raise ValueError("models is not a list")
            wanted = normalize_model_tag(settings.ollama_embedding_model)
            for model in models:
                name = model.get("name") or model.get("model")
                if isinstance(name, str) and normalize_model_tag(name) == wanted:
                    digest = model.get("digest")
                    if isinstance(digest, str) and digest.strip():
                        return digest
                    raise ValueError("digest is missing")
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise EmbeddingError(
                "Could not verify the installed embedding model. Check Ollama "
                "and its model installation before searching or indexing."
            ) from exc
        raise EmbeddingError(
            f"Embedding model '{settings.ollama_embedding_model}' is not installed in Ollama."
        )
    finally:
        if owned:
            transport.close()


def current_index_identity(*, client: httpx.Client | None = None) -> IndexIdentity:
    return build_identity(resolve_model_digest(client=client))
