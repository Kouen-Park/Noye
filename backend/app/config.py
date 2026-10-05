"""Application settings, loaded from the project's ``.env``.

Model names, service URLs, and the vector size are configuration rather than
constants: the embedding model in particular determines the vector dimension,
so hardcoding either one would let them drift apart silently.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Repository root — this file is ``<root>/backend/app/config.py``.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

GenerationProvider = Literal["ollama", "gemini", "openai", "anthropic"]


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

    # Optional cloud generation only; embeddings always remain local.
    gemini_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    gemini_model: str = Field(default="gemini-3.8-flash", pattern=r"^[A-Za-z0-9._-]+$")
    openai_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    openai_model: str = Field(default="gpt-4.1-mini", pattern=r"^[A-Za-z0-9._-]+$")
    anthropic_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    anthropic_model: str = Field(default="claude-haiku-4-5", pattern=r"^[A-Za-z0-9._-]+$")

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "noye"
    #: Must match the output dimension of ``ollama_embedding_model``.
    qdrant_vector_size: int = 768

    database_url: str = "sqlite:///./data/app.db"
    #: Desktop supplies an absolute app-data directory. The web defaults stay
    #: unchanged; neither app bundles nor temporary extraction dirs hold data.
    noye_data_dir: Path | None = None

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
def _base_settings() -> Settings:
    """Return the process-wide settings, read from the environment once."""
    data_root = os.environ.get("NOYE_DATA_DIR")
    settings = Settings(_env_file=Path(data_root) / ".env") if data_root else Settings()
    if settings.noye_data_dir and "qdrant_collection" not in settings.model_fields_set:
        # A new desktop workspace must not rebuild/drop the web workspace's
        # derived index. Explicit advanced configuration can still override it.
        settings.qdrant_collection = "noye_desktop"
    return settings


_desktop_settings: Settings | None = None


def get_settings() -> Settings:
    # Replace whole snapshots, never mutate settings held by an in-flight job.
    return _desktop_settings or _base_settings()


def apply_desktop_configuration(values: dict) -> None:
    global _desktop_settings
    allowed = {
        "ollama_model",
        "gemini_model",
        "openai_model",
        "anthropic_model",
        "gemini_api_key",
        "openai_api_key",
        "anthropic_api_key",
    }
    if not _base_settings().noye_data_dir or not isinstance(values, dict) or set(values) - allowed:
        raise ValueError("Invalid desktop configuration")
    merged = get_settings().model_dump()
    merged.update(values)
    updated = Settings.model_validate(merged)
    from app.services.model_usage import canonical, deleting, lock

    with lock:
        if canonical(updated.ollama_model) in deleting:
            raise ValueError("The selected model is being deleted")
        _desktop_settings = updated


def _clear_settings() -> None:
    global _desktop_settings
    _desktop_settings = None
    _base_settings.cache_clear()


get_settings.cache_clear = _clear_settings


def data_directory() -> Path:
    """Persistent storage root, independent of the process working directory."""
    configured = get_settings().noye_data_dir
    return configured.expanduser().resolve() if configured else PROJECT_ROOT / "data"


def sources_dir() -> Path:
    """Where original uploads are stored. Created on demand.

    These files are Noye's source of truth: the SQLite metadata and the Qdrant
    index are both derived from them and can be rebuilt.
    """
    path = data_directory() / "sources"
    path.mkdir(parents=True, exist_ok=True)
    return path


def documents_dir() -> Path:
    """Where generated, user-editable documents are stored. Created on demand."""
    path = data_directory() / "documents"
    path.mkdir(parents=True, exist_ok=True)
    return path
