"""Grounded answer generation through Ollama.

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

from app.config import get_settings
from app.services.retrieval import DEFAULT_LIMIT, SearchResult, search

#: Generation is slower than embedding and answers can be long.
DEFAULT_TIMEOUT_SECONDS = 300.0

#: Said to the user when retrieval found nothing worth answering from. Returned
#: without calling the model at all: asking a model to answer from no context
#: is exactly how ungrounded answers happen.
NO_CONTEXT_ANSWER = (
    "I could not find anything about that in your indexed documents."
)

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

    Wraps an unreachable Ollama, a model that has not been pulled, and a
    malformed response, so callers do not depend on httpx or on Ollama's
    response shape.
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
) -> Answer:
    """Retrieve relevant chunks and answer the question from them.

    Returns an :class:`Answer` whose ``sources`` are the chunks actually used
    as context. When retrieval finds nothing, the model is not called and
    :data:`NO_CONTEXT_ANSWER` is returned with no sources.

    Raises:
        ValueError: ``question`` is empty.
        EmbeddingError: the question could not be embedded.
        IndexingError: Qdrant could not be searched.
        GenerationError: Ollama could not produce an answer.
    """
    if not question.strip():
        raise ValueError("Cannot answer an empty question")

    results = search(
        question,
        limit=limit,
        file_ids=file_ids,
        min_score=min_score,
        client=qdrant_client,
    )

    if not results:
        return Answer(text=NO_CONTEXT_ANSWER, sources=[])

    prompt = build_prompt(question, results)
    text = generate(prompt, client=client)

    return Answer(text=text, sources=list(results))


def build_prompt(question: str, results: Sequence[SearchResult]) -> str:
    """Render retrieved passages and the question into a single prompt.

    Excerpts are numbered so the model can refer to them while reasoning, and
    each is labelled with its page. The label is context, not a citation
    instruction — the system prompt forbids the model from writing its own
    source list.
    """
    excerpts = []
    for position, result in enumerate(results, start=1):
        excerpts.append(
            f"[Excerpt {position} — page {result.page_number}]\n{result.content}"
        )

    joined = "\n\n".join(excerpts)
    return (
        f"{joined}\n\n"
        f"Question: {question.strip()}\n\n"
        "Answer using only the excerpts above."
    )


def generate(prompt: str, *, client: httpx.Client | None = None) -> str:
    """Send one prompt to Ollama and return the generated text.

    Raises:
        ValueError: ``prompt`` is empty.
        GenerationError: Ollama could not be reached or returned an unusable
            response.
    """
    if not prompt.strip():
        raise ValueError("Cannot generate from an empty prompt")

    settings = get_settings()

    if client is None:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as owned_client:
            return _request_generation(owned_client, prompt, settings)
    return _request_generation(client, prompt, settings)


def _request_generation(client: httpx.Client, prompt: str, settings) -> str:
    model = settings.ollama_model
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "think": settings.ollama_thinking,
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
    if not isinstance(text, str) or not text.strip():
        raise GenerationError(
            f"Ollama returned no answer text (keys: {sorted(body)})"
        )

    return text.strip()
