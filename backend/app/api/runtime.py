"""Bounded, read-only service checks. Never generate, embed or download."""

import asyncio

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/runtime", tags=["runtime"])


class ServicesOut(BaseModel):
    ollama: bool
    qdrant: bool
    generation_model: bool
    embedding_model: bool


def model_installed(configured: str, installed: set[str]) -> bool:
    canonical = configured if ":" in configured else f"{configured}:latest"
    return canonical in installed


@router.get("/services", response_model=ServicesOut)
async def services() -> ServicesOut:
    settings = get_settings()

    async with httpx.AsyncClient(timeout=1.5, follow_redirects=False) as client:
        async def ollama_models() -> tuple[bool, set[str]]:
            try:
                response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
                response.raise_for_status()
                body = response.json()
                names = {model["name"] for model in body["models"]}
                if not all(isinstance(name, str) for name in names):
                    return False, set()
                return True, names
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                return False, set()

        async def qdrant_ready() -> bool:
            try:
                response = await client.get(f"{settings.qdrant_url.rstrip('/')}/healthz")
                return response.is_success
            except httpx.HTTPError:
                return False

        (ollama, names), qdrant = await asyncio.gather(ollama_models(), qdrant_ready())

    return ServicesOut(
        ollama=ollama, qdrant=qdrant,
        generation_model=model_installed(settings.ollama_model, names),
        embedding_model=model_installed(settings.ollama_embedding_model, names),
    )
