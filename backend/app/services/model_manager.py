"""One app-owned Ollama pull at a time; no shells, automatic retries or cleanup."""

import asyncio
import json
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from app.config import get_settings
from app.services.model_recommendations import GENERATION_MODELS, GIB
from app.services.model_usage import deletion
from app.services.runtime_checks import inspect_services, model_installed


def local_server():
    settings = get_settings()
    url = urlsplit(settings.ollama_base_url)
    if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(400, "Model management requires a local Ollama server.")
    return settings


class ModelManager:
    def __init__(self):
        self.task = None
        self.lock = asyncio.Lock()
        self.job = {"state": "idle", "model": "", "completed": 0, "total": 0, "error": None}

    async def pull(self, model: str, storage_path: str):
        async with self.lock:
            local_server()
            if self.task and not self.task.done():
                raise HTTPException(409, "A model operation is already running.")
            sizes = {item.name: item.approximate_download_bytes for item in GENERATION_MODELS}
            embedding = get_settings().ollama_embedding_model
            if embedding in {"embeddinggemma", "embeddinggemma:latest", "embeddinggemma:300m"}:
                sizes[embedding] = 622_000_000
            if model not in sizes:
                raise HTTPException(400, "Choose a supported recommended model.")
            path = Path(storage_path).expanduser()
            try:
                if not path.is_absolute() or not path.is_dir():
                    raise ValueError()
                free = shutil.disk_usage(path).free
            except (OSError, ValueError):
                raise HTTPException(
                    400, "Enter an existing folder on Ollama's model-storage volume."
                ) from None
            if free < sizes[model] * 2 + GIB:
                raise HTTPException(
                    400, "Not enough free space on the confirmed model-storage volume."
                )
            self.job = {
                "state": "downloading",
                "model": model,
                "completed": 0,
                "total": 0,
                "error": None,
            }
            self.task = asyncio.create_task(self._download(model))
            return self.job.copy()

    async def _download(self, model):
        settings = get_settings()
        try:
            async with (
                asyncio.timeout(1800),
                httpx.AsyncClient(
                    timeout=httpx.Timeout(30, connect=5),
                    follow_redirects=False,
                ) as client,
            ):
                async with client.stream(
                    "POST",
                    f"{settings.ollama_base_url.rstrip('/')}/api/pull",
                    json={"model": model, "stream": True},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if len(line) > 16_384:
                            raise ValueError()
                        body = json.loads(line)
                        if not isinstance(body, dict) or body.get("error"):
                            raise ValueError()
                        if body.get("status") == "success":
                            snapshot = await inspect_services(settings)
                            if not model_installed(
                                model, {m.name for m in snapshot.installed_models}
                            ):
                                raise ValueError()
                            self.job.update(state="complete")
                            return
                        # Ollama reports a layer, not an overall download percentage.
                        total, completed = body.get("total", 0), body.get("completed", 0)
                        if (
                            type(total) is int
                            and type(completed) is int
                            and 0 <= completed <= total <= 10**12
                        ):
                            self.job.update(total=total, completed=completed)
                    raise ValueError()
        except asyncio.CancelledError:
            self.job.update(state="cancelled")
            raise
        except (httpx.HTTPError, ValueError, TimeoutError):
            self.job.update(
                state="failed",
                error="Download did not finish. Check Ollama, storage and connection, then retry.",
            )

    async def cancel(self):
        async with self.lock:
            if self.task and not self.task.done():
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
                if self.job["state"] == "downloading":
                    self.job.update(state="cancelled")
            return self.job.copy()

    async def delete(self, model):
        async with self.lock:
            if self.task and not self.task.done():
                raise HTTPException(409, "Wait for or cancel the current model operation.")
            settings = local_server()
            if model_installed(settings.ollama_model, {model}) or model_installed(
                settings.ollama_embedding_model, {model}
            ):
                raise HTTPException(
                    409,
                    "The selected generation or embedding model cannot be deleted. "
                    "Switch generation models first.",
                )
            with deletion(model):
                snapshot = await inspect_services(settings)
                if model not in {m.name for m in snapshot.installed_models}:
                    raise HTTPException(404, "The model is not installed.")
                try:
                    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                        response = await client.request(
                            "DELETE",
                            f"{settings.ollama_base_url.rstrip('/')}/api/delete",
                            json={"model": model},
                        )
                        response.raise_for_status()
                except httpx.HTTPError:
                    raise HTTPException(
                        502, "Ollama could not delete the model. Check its status and try again."
                    ) from None


manager = ModelManager()
