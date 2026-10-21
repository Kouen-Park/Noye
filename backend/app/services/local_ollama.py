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


def post_structured(client, settings, *, system, prompt, schema):
    """Select one endpoint before inference; never retry or promote reasoning to output.

    Observed Qwen3.5:4b/Ollama 0.34.2 generate/thinking requests can put JSON in the
    reasoning field only. Chat separated reasoning and final JSON in the same control.
    Preserve the existing generate request when thinking is disabled.
    """
    require_loopback(settings)
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "think": settings.ollama_thinking,
        "format": schema,
        "options": {
            "num_ctx": settings.generation_context_tokens,
            "num_predict": settings.generation_output_tokens,
            "temperature": 0,
        },
    }
    if settings.ollama_thinking:
        endpoint = "/api/chat"
        payload["messages"] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
    else:
        endpoint = "/api/generate"
        payload.update(system=system, prompt=prompt)
    return client.post(settings.ollama_base_url.rstrip("/") + endpoint, json=payload)


def structured_text(body, *, thinking):
    # A valid JSON-shaped thinking field is still not a final answer.
    return body["message"]["content"] if thinking else body["response"]
