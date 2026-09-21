"""Application settings, loaded from the project's ``.env``.

Model names, service URLs, and the vector size are configuration rather than
constants: the embedding model in particular determines the vector dimension,
so hardcoding either one would let them drift apart silently.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Repository root — this file is ``<root>/backend/app/config.py``.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration.

    Defaults mirror ``.env.example`` so the backend and its tests run without
    an ``.env`` present. Anything environment-specific belongs in ``.env``,
    which is not committed.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_embedding_model: str = "embeddinggemma"
    #: qwen3.5 is a reasoning model; thinking stays off for RAG answers because
    #: it costs roughly 30x the tokens and latency for no gain at answer length.
    ollama_thinking: bool = False

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "noye"
    #: Must match the output dimension of ``ollama_embedding_model``.
    qdrant_vector_size: int = 768

    database_url: str = "sqlite:///./data/app.db"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, read from the environment once."""
    return Settings()
