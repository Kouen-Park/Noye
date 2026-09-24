"""Tests for the document drafting service.

The prompt is the whole of this module's behaviour, so these tests are mostly
about what goes into it and what deliberately does not.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.models.conversations import MessageCitation
from app.services.documents import SYSTEM_PROMPT, build_document_prompt, draft_document
from app.services.generation import GenerationError


def citation(*, file_name: str = "Algorithms.pdf", page: int | None = 34) -> MessageCitation:
    return MessageCitation(
        file_id="f1",
        file_name=file_name,
        page_number=page,
        chunk_indexes=(5,),
        best_score=0.7,
    )


def ollama(*, text: str = "# Notes\n\n- one\n", status: int = 200, capture: dict | None = None):
    """A stub Ollama that records the request body."""

    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture.update(json.loads(request.content))
        if status != 200:
            return httpx.Response(status, text="boom")
        return httpx.Response(200, json={"response": text})

    return httpx.Client(transport=httpx.MockTransport(handler))


# --- the prompt --------------------------------------------------------------


def test_the_prompt_carries_the_answer_and_the_instruction() -> None:
    prompt = build_document_prompt("Make revision notes", "An answer about graphs.")
    assert "An answer about graphs." in prompt
    assert "Make revision notes" in prompt


def test_the_prompt_names_the_sources_the_answer_drew_on() -> None:
    prompt = build_document_prompt("notes", "answer", [citation(file_name="Algorithms.pdf")])
    assert "Algorithms.pdf" in prompt


def test_the_prompt_omits_page_numbers() -> None:
    """A page number in the prompt is something the model can repeat into its
    prose, and a page reference inside the body is one the user cannot click."""
    prompt = build_document_prompt("notes", "answer", [citation(page=34)])
    assert "page 34" not in prompt
    assert "34" not in prompt


def test_the_prompt_works_without_sources() -> None:
    prompt = build_document_prompt("notes", "answer")
    assert "drew on" not in prompt
    assert "answer" in prompt


def test_an_empty_instruction_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_document_prompt("   ", "answer")


def test_an_empty_answer_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_document_prompt("notes", "   ")


# --- the system prompt ------------------------------------------------------


def test_the_system_prompt_asks_for_markdown_and_forbids_citations() -> None:
    assert "Markdown" in SYSTEM_PROMPT
    assert "Sources" in SYSTEM_PROMPT
    assert "do not" in SYSTEM_PROMPT.lower()


def test_drafting_uses_the_document_system_prompt_not_the_qa_one() -> None:
    """Answering says the least that is true; drafting gives structure to edit."""
    captured: dict = {}
    draft_document("notes", "an answer", client=ollama(capture=captured))
    assert captured["system"] == SYSTEM_PROMPT
    assert "answering questions about" not in captured["system"]


# --- drafting ---------------------------------------------------------------


def test_a_draft_is_returned_stripped() -> None:
    result = draft_document("notes", "answer", client=ollama(text="\n\n# Notes\n\n"))
    assert result == "# Notes"


def test_an_unreachable_model_raises() -> None:
    with pytest.raises(GenerationError):
        draft_document("notes", "answer", client=ollama(status=500))


def test_an_empty_draft_raises_rather_than_being_stored() -> None:
    with pytest.raises(GenerationError):
        draft_document("notes", "answer", client=ollama(text="   "))
