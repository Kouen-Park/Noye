"""Single-shot official cloud APIs. No retries, tools or provider fallback."""

import httpx

from app.services.generation import GenerationError


def request_cloud(client, provider, prompt, settings, system):
    name = "OpenAI" if provider == "openai" else "Claude"
    key = getattr(settings, f"{provider}_api_key").get_secret_value()
    if not key:
        raise GenerationError(f"Add a {name} API key in Settings before using this provider.")
    model = getattr(settings, f"{provider}_model")
    if provider == "openai":
        url = "https://api.openai.com/v1/responses"
        headers = {"Authorization": f"Bearer {key}"}
        payload = {
            "model": model,
            "instructions": system,
            "input": prompt,
            "max_output_tokens": 4096,
            "store": False,
        }
    else:
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        payload = {
            "model": model,
            "system": system,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
    try:
        response = client.post(url, headers=headers, json=payload, follow_redirects=False)
    except httpx.RequestError:
        raise GenerationError(f"Could not reach {name}. Check your internet connection.") from None
    if response.status_code >= 300:
        if response.status_code in (401, 403):
            reason = "rejected the API key or permissions"
        elif response.status_code == 429:
            reason = "reached its quota or rate limit; no automatic retry or fallback occurred"
        else:
            reason = f"returned HTTP {response.status_code}; check model access and try later"
        raise GenerationError(f"{name} {reason}.")
    try:
        body = response.json()
        if provider == "openai":
            if body.get("status") != "completed" or body.get("error"):
                raise ValueError()
            texts = [
                part["text"]
                for item in body["output"]
                if item.get("type") == "message" and item.get("role") == "assistant"
                for part in item["content"]
                if part.get("type") == "output_text"
            ]
        else:
            if body.get("stop_reason") != "end_turn":
                raise ValueError()
            texts = [part["text"] for part in body["content"] if part.get("type") == "text"]
        if not texts or not all(isinstance(text, str) for text in texts):
            raise ValueError()
        text = "\n".join(texts).strip()
        if not text:
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        raise GenerationError(
            f"{name} returned no complete usable answer. Nothing was retried."
        ) from None
    return text
