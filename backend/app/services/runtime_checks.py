"""Bounded GET-only local service/model inventory. No inference or downloads."""

import asyncio

import httpx
from pydantic import BaseModel, Field

from app.config import Settings


class ServicesOut(BaseModel):
    ollama: bool
    qdrant: bool
    generation_model: bool
    embedding_model: bool


class InstalledModel(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    size_bytes: int | None = Field(default=None, ge=0)


class ServiceSnapshot(BaseModel):
    services: ServicesOut
    installed_models: list[InstalledModel]


def model_installed(configured: str, installed: set[str]) -> bool:
    canonical = configured if ":" in configured else f"{configured}:latest"
    return canonical in installed


async def inspect_services(settings: Settings) -> ServiceSnapshot:
    async with httpx.AsyncClient(timeout=1.5, follow_redirects=False) as client:
        async def ollama_models() -> tuple[bool, list[InstalledModel]]:
            try:
                response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or not isinstance(body.get("models"), list):
                    return False, []
                if len(body["models"]) > 200:
                    return False, []
                models = []
                for model in body["models"]:
                    name = model["name"]
                    if not isinstance(name, str) or not 0 < len(name) <= 200:
                        return False, []
                    size = model.get("size")
                    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                        size = None
                    models.append(InstalledModel(name=name, size_bytes=size))
                return True, sorted(models, key=lambda model: model.name)
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                return False, []

        async def qdrant_ready() -> bool:
            try:
                response = await client.get(f"{settings.qdrant_url.rstrip('/')}/healthz")
                return response.is_success
            except httpx.HTTPError:
                return False

        (ollama, models), qdrant = await asyncio.gather(ollama_models(), qdrant_ready())

    names = {model.name for model in models}
    return ServiceSnapshot(
        services=ServicesOut(
            ollama=ollama, qdrant=qdrant,
            generation_model=model_installed(settings.ollama_model, names),
            embedding_model=model_installed(settings.ollama_embedding_model, names),
        ),
        installed_models=models,
    )
