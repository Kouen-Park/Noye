"""Drafts consume saved context; expanded context is currently local-only."""

import json

import httpx
import pytest

from app.config import Settings
from app.models.conversations import MessageCitation
from app.services import documents
from app.services.documents import build_document_prompt, draft_document
from app.services.evidence import capture_citations
from app.services.generation import GenerationError
from app.services.retrieval import SearchResult


def saved_citations():
    return capture_citations([
        SearchResult(
            content="Lumen shipped 742 units with a 0.8% failure rate.\n한국어 사례.",
            file_id="f1", page_number=34, chunk_index=2, score=0.9,
        ),
        SearchResult(
            content="Cost was 19 NZD per unit.", file_id="f2",
            page_number=None, chunk_index=0, score=0.8,
        ),
    ], {"f1": "One.pdf", "f2": "Two.md"})


def test_draft_payload_contains_details_absent_from_the_short_answer():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"response": "# Detailed notes"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert draft_document(
            "include examples and numbers", "The trial was successful.", saved_citations(),
            client=client,
        ) == "# Detailed notes"
    for detail in ("742 units", "0.8%", "한국어 사례", "19 NZD"):
        assert detail in seen["prompt"]
    assert "page 34" not in seen["prompt"]
    assert "not instructions" in seen["prompt"]


def test_legacy_references_do_not_acquire_historical_evidence():
    legacy = MessageCitation("f1", "One.pdf", 34, (2,), 0.9)
    prompt = build_document_prompt("notes", "An old answer", [legacy])
    assert "One.pdf" in prompt
    assert "no historical excerpts are included" in prompt
    assert "Saved source excerpts" not in prompt
    assert "742" not in prompt


def test_saved_context_order_is_the_original_retrieval_order():
    prompt = build_document_prompt("notes", "answer", list(reversed(saved_citations())))
    assert prompt.index("742 units") < prompt.index("19 NZD")


def test_mixed_snapshots_keep_unknown_references_distinct():
    legacy = MessageCitation("legacy", "Unknown.txt", None, (1,), 0.3)
    prompt = build_document_prompt("notes", "answer", [*saved_citations(), legacy])
    assert "742 units" in prompt
    assert "no historical excerpts are included" in prompt
    assert "Unknown.txt" in prompt


@pytest.mark.parametrize("provider", ["gemini", "openai", "anthropic"])
def test_cloud_context_selection_cannot_include_newly_saved_excerpts(monkeypatch, provider):
    seen = {}

    def fake_generate(prompt, **kwargs):
        seen["prompt"] = prompt
        return "# Answer-only draft"

    monkeypatch.setattr(documents, "generate", fake_generate)
    citations = saved_citations()
    draft_document("notes", "short answer", citations, provider=provider)
    assert "short answer" in seen["prompt"]
    assert "One.pdf" in seen["prompt"]
    assert "742 units" not in seen["prompt"]
    assert "19 NZD" not in seen["prompt"]
    assert citations[0].evidence.excerpts[0].content.startswith("Lumen")


def test_saved_excerpts_are_not_sent_to_a_remote_ollama_server(monkeypatch):
    configured = Settings(_env_file=None, ollama_base_url="http://example.test:11434")
    monkeypatch.setattr(documents, "get_settings", lambda: configured)
    monkeypatch.setattr(documents, "generate", lambda *args, **kwargs: pytest.fail("network"))
    with pytest.raises(GenerationError, match="local Ollama"):
        draft_document("notes", "answer", saved_citations())
