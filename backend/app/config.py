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
    #: Origins allowed to call the API from a browser. The Next.js dev server
    #: runs on a different port, so without this every request from it is
    #: blocked by the browser before it reaches FastAPI.
    frontend_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

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

    #: Noye's own log level. Deliberately separate from uvicorn's: raising this
    #: must not raise httpx's, which logs request bodies and would put a user's
    #: question into the log.
    log_level: str = "INFO"
    #: A rotating file under ``data/logs/`` as well as stderr. Off in tests, which
    #: assert on handler output rather than on a file.
    log_to_file: bool = True

    #: Upload ceiling in megabytes. This is a local single-user application, so the
    #: risk is not abuse but accident — dragging a video into the drop zone. The
    #: limit's job is to fail fast and leave nothing on disk, rather than to defend
    #: against anyone. 100 MB clears a large scanned textbook.
    max_upload_mb: int = 100

    @property
    def allowed_origins(self) -> list[str]:
        """The CORS origin list, parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, read from the environment once."""
    return Settings()


def sources_dir() -> Path:
    """Where original uploads are stored. Created on demand.

    These files are Noye's source of truth: the SQLite metadata and the Qdrant
    index are both derived from them and can be rebuilt.
    """
    path = PROJECT_ROOT / "data" / "sources"
    path.mkdir(parents=True, exist_ok=True)
    return path


def documents_dir() -> Path:
    """Where generated, user-editable documents are stored. Created on demand."""
    path = PROJECT_ROOT / "data" / "documents"
    path.mkdir(parents=True, exist_ok=True)
    return path
