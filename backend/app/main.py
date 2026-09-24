"""Noye's FastAPI application.

Local-first and single-user: there is no authentication, by design (see the
plan's MVP scope). The server therefore binds to 127.0.0.1 by default, and CORS
allows only the local frontend — anyone who can reach this port can read and
delete the user's documents, so it must not be exposed on a network interface
without adding authentication first.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, documents, files, search
from app.config import get_settings
from app.logging_config import configure_logging, get_logger

# Before the routers, so anything they log during import is already captured.
# configure_logging is idempotent, which matters here: uvicorn's reloader and the
# test suite both import this module more than once, and each import would
# otherwise add another handler and duplicate every line.
configure_logging()
logger = get_logger("main")

app = FastAPI(
    title="Noye API",
    version="0.1.0",
)

settings = get_settings()

# One startup line naming the services this process will depend on. Worth it
# because the commonest failure in this application is a service that is simply
# not running, and the second commonest is pointing at the wrong one — a log that
# does not say which Ollama it tried cannot distinguish them.
logger.info(
    "Noye starting ollama=%s model=%s embedding=%s qdrant=%s collection=%s dim=%d",
    settings.ollama_base_url,
    settings.ollama_model,
    settings.ollama_embedding_model,
    settings.qdrant_url,
    settings.qdrant_collection,
    settings.qdrant_vector_size,
)

# The frontend runs on a different port in development, so browser requests
# from it are blocked before reaching FastAPI without this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(files.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
