from app.models.conversations import Message, MessageCitation, Role
from app.models.evidence import EvidenceExcerpt, EvidenceSnapshot
from app.services.conversation_context import recent_context, retrieval_question
from app.services.evidence import provenance_markdown
from app.services.generation import build_prompt
from app.services.retrieval import SearchResult


def test_history_has_a_hard_budget_and_assistant_text_is_not_retrieval_evidence():
    messages = [Message(str(i), "c", Role.USER if i % 2 == 0 else Role.ASSISTANT,
                        "User topic" if i % 2 == 0 else "invented prior claim" * 200)
                for i in range(50)]
    context = recent_context(messages)
    assert len(context) <= 2400
    assert "invented prior claim" not in context
    query = retrieval_question("What about it?", messages)
    assert "User topic" in query
    assert "invented prior claim" not in query
    prompt = build_prompt("What about it?", [SearchResult("actual evidence", "f", 1, 0, .9)],
                          history=context)
    assert "not source evidence" in prompt
    assert "actual evidence" in prompt


def test_english_and_korean_comparisons_reuse_user_topics():
    for previous, question in [("Compare AT-201 and AT-210.", "Which was faster?"),
                               ("DB-318과 DB-381의 결과", "그럼 두 결과의 차이는?")]:
        messages = [Message("u", "c", Role.USER, previous),
                    Message("a", "c", Role.ASSISTANT, "unverified assistant detail")]
        query = retrieval_question(question, messages)
        assert previous in query
        assert "unverified assistant detail" not in query
        assert retrieval_question("A separate standalone question", messages) == \
            "A separate standalone question"


def test_provenance_keeps_source_markdown_literal():
    raw = "![tracking](https://example.invalid/image)\n```\n<div>source</div>"
    citation = MessageCitation("f", "[link].md", None, (0,), .9,
                               evidence=EvidenceSnapshot("2026-10-05T00:00:00+00:00", (
                                   EvidenceExcerpt(raw, 0, 1, .9),)))
    exported = provenance_markdown([citation])
    assert raw in exported
    assert "````text\n" + raw + "\n````" in exported
    assert "\\[link\\].md" in exported
