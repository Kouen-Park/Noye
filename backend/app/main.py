"""Noye's FastAPI application.

Local-first and single-user: there is no authentication, by design (see the
plan's MVP scope). The server therefore binds to 127.0.0.1 by default, and CORS
allows only the local frontend — anyone who can reach this port can read and
delete the user's documents, so it must not be exposed on a network interface
without adding authentication first.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ai,
    chat,
    desktop_services,
    documents,
    files,
    folders,
    index,
    jobs,
    knowledge_jobs,
    models,
    runtime,
    search,
    source_documents,
    wiki,
    workspace,
)
from app.config import get_settings
from app.db.database import connect, init_schema
from app.db.jobs import recover_interrupted
from app.logging_config import configure_logging, get_logger
from app.services.ingestion import cancel_all_ingestion
from app.services.wiki.jobs import register as register_wiki_jobs
from app.services.source_documents.jobs import register as register_source_document_jobs

# Before the routers, so anything they log during import is already captured.
# configure_logging is idempotent, which matters here: uvicorn's reloader and the
# test suite both import this module more than once, and each import would
# otherwise add another handler and duplicate every line.
configure_logging()
logger = get_logger("main")

register_wiki_jobs()

register_source_document_jobs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Complete schema setup before serving concurrent requests or announcing
    # desktop readiness. Request-time checks remain defensive/idempotent.
    connection = connect()
    try:
        init_schema(connection)
        recover_interrupted(connection)
        from app.services.wiki.publication import recover_publications

        recover_publications(connection)
    finally:
        connection.close()
    from app.services.folder_scanner import watcher
    from app.services.knowledge_jobs import recover_interrupted as recover_knowledge
    from app.services.knowledge_jobs import worker
    from app.services.wiki.observer import observer

    connection = connect()
    try:
        recover_knowledge(connection)
    finally:
        connection.close()
    watcher.start()
    worker.start()
    observer.start()
    desktop_services.manager.closing = False
    try:
        yield
    finally:
        watcher.stop()
        observer.stop()
        worker.stop()
        cancel_all_ingestion()
        await models.manager.cancel()
        await desktop_services.manager.shutdown()
        connection = connect()
        try:
            recover_interrupted(connection)
        finally:
            connection.close()


app = FastAPI(
    title="Noye API",
    version="0.1.0",
    lifespan=lifespan,
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
app.include_router(index.router)
app.include_router(ai.router)
app.include_router(runtime.router)
app.include_router(models.router)
app.include_router(desktop_services.router)
app.include_router(workspace.router)
app.include_router(jobs.router)
app.include_router(folders.router)
app.include_router(knowledge_jobs.router)
app.include_router(wiki.router)
app.include_router(source_documents.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
