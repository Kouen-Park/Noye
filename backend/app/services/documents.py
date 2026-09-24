"""Turning an answer into a document.

A different task from answering a question, so a different prompt. Answering means
saying the least that is true; drafting a document means giving someone something
structured they can then edit. The same model does both, and asking it to draft
with the QA prompt produces a paragraph where headings were wanted.

Three rules carry over from generation unchanged, because they are what make the
output trustworthy rather than merely fluent:

* **Only the material provided.** The answer and its passages are the evidence.
  Nothing is added from the model's own knowledge, and a gap is left as a gap.
* **The model writes no citations.** Sources are attached outside its output,
  copied from the ones stored with the answer.
* **Thinking stays off**, from configuration, for the same cost reason.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from app.models.conversations import MessageCitation
from app.services.generation import DEFAULT_TIMEOUT_SECONDS, GenerationError, generate

SYSTEM_PROMPT = """You are Noye, drafting a document from material the user already has.

Rules:
- Write Markdown. Use headings, lists and emphasis where they make the structure clearer.
- Use only the answer and excerpts provided. They are the only material you have.
- Do not add facts, examples, numbers or names that are not in that material.
- If the material does not cover part of what was asked, leave that out rather than inventing it.
- Do not write a citation list, a "Sources" section, or page references. Sources are attached automatically outside your output.
- Do not open with a preamble about what you are about to do. Start with the document.
- Write in the language the instruction was given in.
"""


def build_document_prompt(
    instruction: str,
    answer: str,
    citations: Sequence[MessageCitation] = (),
) -> str:
    """Render the instruction, the answer, and its passages into one prompt.

    The passages are included as well as the answer, because a document usually
    wants more detail than the answer gave — the answer was written to be brief,
    and the material behind it is where the substance is.

    Labels name the source without page numbers. A page number in the prompt is
    something the model can repeat into its prose, and a page reference inside the
    body would be one the user could not click.
    """
    if not instruction.strip():
        raise ValueError("Cannot draft a document without an instruction")
    if not answer.strip():
        raise ValueError("Cannot draft a document from an empty answer")

    parts = [f"Answer to work from:\n{answer.strip()}"]

    if citations:
        excerpts = "\n".join(f"- {citation.file_name}" for citation in citations)
        parts.append(f"This answer drew on:\n{excerpts}")

    parts.append(f"Instruction: {instruction.strip()}")
    parts.append("Write the document now, in Markdown.")
    return "\n\n".join(parts)


def draft_document(
    instruction: str,
    answer: str,
    citations: Sequence[MessageCitation] = (),
    *,
    client: httpx.Client | None = None,
) -> str:
    """Draft Markdown from an answer and an instruction.

    Returns the Markdown body only. The caller stores it, along with the answer's
    citations, as a document the user then owns and edits.

    Raises:
        ValueError: the instruction or the answer is empty.
        GenerationError: Ollama could not produce a draft.
    """
    prompt = build_document_prompt(instruction, answer, citations)
    text = generate(prompt, client=client, system=SYSTEM_PROMPT)

    if not text.strip():
        # `generate` already rejects an empty response, so this is belt and
        # braces — but an empty document would be stored as a real one.
        raise GenerationError("The model returned an empty document.")
    return text.strip()


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "SYSTEM_PROMPT",
    "GenerationError",
    "build_document_prompt",
    "draft_document",
]
