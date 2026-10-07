"""Grounded answers through local Ollama or explicitly selected Gemini.

The model is given retrieved passages and asked to answer from them only. Two
rules shape this module:

* **The model never produces citations.** It is asked for prose; the sources
  shown to the user are built from the retrieval metadata by
  :mod:`app.services.citations`. A model that writes its own citations will
  eventually invent a page number that looks entirely plausible.
* **Thinking stays off.** ``qwen3.5`` is a reasoning model, and on local
  hardware its thinking tokens cost roughly thirty times the latency for no
  gain at answer length. The default comes from configuration, not from here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from app.config import GenerationProvider, get_settings
from app.services.retrieval import DEFAULT_LIMIT, SearchResult, search

#: Generation is slower than embedding and answers can be long.
DEFAULT_TIMEOUT_SECONDS = 300.0

#: Said to the user when retrieval found nothing worth answering from. Returned
#: without calling the model at all: asking a model to answer from no context
#: is exactly how ungrounded answers happen.
NO_CONTEXT_ANSWER = "I could not find anything about that in your indexed documents."

SYSTEM_PROMPT = """You are Noye, answering questions about the user's own documents.

Rules:
- Answer using only the numbered excerpts provided. They are the only evidence you have.
- If the excerpts do not contain the answer, say so plainly instead of guessing.
- Never invent facts, numbers, names, file names or page numbers.
- Do not write a citation list. Sources are attached automatically outside your answer.
- Answer in the language the question was asked in.
- Be concise and concrete."""


class GenerationError(Exception):
    """An answer could not be generated.

    Wraps provider connection, configuration, quota and response errors so
    callers do not depend on httpx or a provider's response shape.
    """


@dataclass(frozen=True)
class Answer:
    """A generated answer together with the passages it was grounded in.

    ``sources`` is the retrieval result, not something the model reported, so
    the pairing of answer and provenance cannot be hallucinated.
    """

    text: str
    sources: list[SearchResult]

    @property
    def is_grounded(self) -> bool:
        return bool(self.sources)


def answer_question(
    question: str,
    *,
    limit: int = DEFAULT_LIMIT,
    file_ids: list[str] | None = None,
    min_score: float | None = None,
    client: httpx.Client | None = None,
    qdrant_client=None,
    provider: GenerationProvider = "ollama",
    history: str = "",
    retrieval_query: str | None = None,
) -> Answer:
    """Retrieve relevant chunks and answer the question from them.

    Returns an :class:`Answer` whose ``sources`` are the chunks actually used
    as context. When retrieval finds nothing, the model is not called and
    :data:`NO_CONTEXT_ANSWER` is returned with no sources.

    Raises:
        ValueError: ``question`` is empty.
        EmbeddingError: the question could not be embedded.
        IndexingError: Qdrant could not be searched.
        GenerationError: the selected provider could not produce an answer.
    """
    if not question.strip():
        raise ValueError("Cannot answer an empty question")

    results = search(
        retrieval_query or question,
        limit=limit,
        file_ids=file_ids,
        min_score=min_score,
        client=qdrant_client,
    )

    if not results:
        return Answer(text=NO_CONTEXT_ANSWER, sources=[])

    prompt = build_prompt(question, results, history=history)
    text = generate(prompt, client=client, provider=provider)

    return Answer(text=text, sources=list(results))


def build_prompt(question: str, results: Sequence[SearchResult], *, history: str = "") -> str:
    """Render retrieved passages and the question into a single prompt.

    Excerpts are numbered so the model can refer to them while reasoning, and
    each is labelled with its page. The label is context, not a citation
    instruction — the system prompt forbids the model from writing its own
    source list.
    """
    excerpts = []
    for position, result in enumerate(results, start=1):
        # Markdown and text sources have no page; labelling one would suggest a
        # location the model could repeat and the user could not verify.
        label = (
            f"Excerpt {position}"
            if result.page_number is None
            else f"Excerpt {position} — page {result.page_number}"
        )
        excerpts.append(f"[{label}]\n{result.content}")

    joined = "\n\n".join(excerpts)
    context = (
        "Conversation context (only to resolve references; not source evidence):\n"
        f"{history[:2400]}\n\n"
        if history
        else ""
    )
    return (
        f"{context}{joined}\n\nQuestion: {question.strip()}\n\n"
        "Answer using only the excerpts above."
    )


def generate(
    prompt: str,
    *,
    client: httpx.Client | None = None,
    system: str | None = None,
    provider: GenerationProvider = "ollama",
    local_only: bool = False,
) -> str:
    """Send one prompt to the selected provider and return generated text.

    ``system`` overrides :data:`SYSTEM_PROMPT` for callers whose task is not
    answering a question — drafting a document, for instance. The transport,
    timeout, thinking setting and error mapping are the same for every task, so
    they live here rather than being copied per caller.

    Raises:
        ValueError: ``prompt`` is empty.
        GenerationError: the provider could not be reached or returned an unusable
            response.
    """
    if not prompt.strip():
        raise ValueError("Cannot generate from an empty prompt")

    settings = get_settings()
    if local_only and provider != "ollama":
        raise GenerationError("This original-evidence request requires local Ollama.")
    system_prompt = system or SYSTEM_PROMPT
    if provider == "ollama":
        # Conservative byte bound, not an exact tokenizer measurement. Never
        # silently trim historical evidence or the user's instructions.
        available = settings.generation_context_tokens - settings.generation_output_tokens - 512
        if len(prompt.encode("utf-8")) + len(system_prompt.encode("utf-8")) > available:
            raise GenerationError(
                "This request exceeds the local model input budget. "
                "Use fewer excerpts or a shorter instruction."
            )
    if provider not in ("ollama", "gemini", "openai", "anthropic"):
        raise ValueError("Unknown generation provider")
    if provider in ("openai", "anthropic"):
        from app.services.cloud_generation import request_cloud

        if client is None:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS, follow_redirects=False) as owned:
                return request_cloud(owned, provider, prompt, settings, system_prompt)
        return request_cloud(client, provider, prompt, settings, system_prompt)
    request_generation = _request_gemini if provider == "gemini" else _request_generation
    from contextlib import nullcontext

    from app.services.local_ollama import LocalModelError, require_installed_local_model
    from app.services.model_usage import ModelBusyError, inference

    try:
        with inference(settings.ollama_model) if provider == "ollama" else nullcontext():
            if client is None:
                with httpx.Client(
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                    follow_redirects=False,
                    trust_env=provider != "ollama",
                ) as owned_client:
                    if local_only:
                        require_installed_local_model(settings, owned_client)
                    return request_generation(owned_client, prompt, settings, system_prompt)
            if local_only:
                require_installed_local_model(settings, client)
            return request_generation(client, prompt, settings, system_prompt)
    except (ModelBusyError, LocalModelError) as error:
        raise GenerationError(str(error)) from None


def _request_gemini(client: httpx.Client, prompt: str, settings, system_prompt: str) -> str:
    """One cloud request, without retries or fallback to another provider.

    The key goes in a header, never a URL. Upstream bodies and exception messages
    are not surfaced: they can echo the prompt or credentials into persisted
    errors and logs. Only the answer text is returned, never thinking parts.
    """
    key = settings.gemini_api_key.get_secret_value().strip()
    if not key:
        raise GenerationError("Set GEMINI_API_KEY in the backend environment and restart Noye.")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    try:
        response = client.post(
            url,
            headers={"x-goog-api-key": key},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 4096},
            },
        )
    except httpx.RequestError:
        raise GenerationError("Could not reach Gemini. Check your internet connection.") from None

    if response.status_code in (401, 403):
        raise GenerationError("Gemini rejected the API key or permissions. Check your API project.")
    if response.status_code == 429:
        raise GenerationError(
            "Gemini's quota or rate limit was reached. Try again later or select Ollama. "
            "Noye has not switched providers or enabled billing."
        )
    if response.status_code == 404:
        raise GenerationError("Gemini model is unavailable. Check GEMINI_MODEL and project access.")
    if response.status_code >= 400:
        raise GenerationError(f"Gemini returned HTTP {response.status_code}. Try again later.")

    try:
        body = response.json()
        candidate = body["candidates"][0]
        # Refuse blocked or truncated content rather than saving an incomplete draft.
        if candidate.get("finishReason") != "STOP":
            raise GenerationError("Gemini did not finish the answer. Try a shorter request.")
        parts = candidate["content"]["parts"]
        text = "".join(
            part["text"]
            for part in parts
            if not part.get("thought") and isinstance(part.get("text"), str)
        )
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise GenerationError("Gemini returned no usable answer text.") from None
    if not text.strip():
        raise GenerationError("Gemini returned no usable answer text.")
    return text.strip()


def _request_generation(
    client: httpx.Client, prompt: str, settings, system_prompt: str = SYSTEM_PROMPT
) -> str:
    model = settings.ollama_model
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "think": settings.ollama_thinking,
        "options": {
            "num_ctx": settings.generation_context_tokens,
            "num_predict": settings.generation_output_tokens,
        },
    }

    try:
        response = client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise GenerationError(
            f"Could not reach Ollama at {settings.ollama_base_url}. "
            "Check that it is running (brew services start ollama)."
        ) from exc

    if response.status_code == 404:
        raise GenerationError(
            f"Generation model '{model}' is not available in Ollama. "
            f"Pull it first: ollama pull {model}"
        )

    if response.status_code >= 400:
        raise GenerationError(
            f"Ollama returned HTTP {response.status_code} while generating "
            f"with '{model}': {response.text[:200]}"
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise GenerationError("Ollama returned a non-JSON response") from exc

    text = body.get("response")
    if body.get("done") is False or body.get("done_reason") == "length":
        raise GenerationError("The local model reached its output limit. Request a shorter answer.")
    if not isinstance(text, str) or not text.strip():
        raise GenerationError(f"Ollama returned no answer text (keys: {sorted(body)})")

    return text.strip()
