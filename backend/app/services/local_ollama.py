"""Prove a local Ollama model before sending original evidence; no fallback."""

from urllib.parse import urlsplit

import httpx


class LocalModelError(RuntimeError):
    pass


def require_loopback(settings):
    url = urlsplit(settings.ollama_base_url)
    if (
        url.scheme not in {"http", "https"}
        or url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or url.username
        or url.password
    ):
        raise LocalModelError("Original evidence requires local loopback Ollama.")


def require_installed_local_model(settings, client):
    """Caller holds model usage. Only the model name is sent during preflight."""
    require_loopback(settings)
    try:
        response = client.post(
            settings.ollama_base_url.rstrip("/") + "/api/show",
            json={"model": settings.ollama_model},
        )
        if response.status_code != 200:
            raise LocalModelError("The configured local generation model is not installed.")
        descriptor = response.json()
    except (httpx.RequestError, ValueError):
        raise LocalModelError("Could not confirm that the Ollama model is local.") from None
    if (
        not isinstance(descriptor, dict)
        or not isinstance(descriptor.get("model_info"), dict)
        or not descriptor["model_info"]
        or descriptor.get("remote_host")
        or descriptor.get("remote_model")
    ):
        raise LocalModelError(
            "Original evidence requires an installed local model, not a cloud alias."
        )
