"""Noye's FastAPI application.

Local-first and single-user: there is no authentication, by design (see the
plan's MVP scope). The server therefore binds to 127.0.0.1 by default, and CORS
allows only the local frontend — anyone who can reach this port can read and
delete the user's documents, so it must not be exposed on a network interface
without adding authentication first.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import files, search
from app.config import get_settings

app = FastAPI(
    title="Noye API",
    version="0.1.0",
)

settings = get_settings()

# The frontend runs on a different port in development, so browser requests
# from it are blocked before reaching FastAPI without this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(files.router)
app.include_router(search.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
