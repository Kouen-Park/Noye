import json

import httpx
import pytest

from app.config import Settings
from app.models.wiki import Passage, SectionSummary, SourceRef, WikiScope
from app.services.wiki import pipeline
from app.services.wiki.local import WikiError, structured


def passage(text, page=None):
    return Passage(
        id="verified",
        source=SourceRef(
            source_id="source",
            root_id=None,
            relative_path="notes.md",
            name="Notes",
            source_hash="a" * 64,
            source_version="a" * 64,
            availability="available",
            indexing_status="READY",
        ),
        page_number=page,
        passage_index=0,
        start=0,
        end=len(text),
        text=text,
    )


def summary(identifier="verified", quote="A test", confidence=0.9):
    return {
        "summary": {"text": "A test summary", "evidence_id": identifier, "quote": quote},
        "key_points": [],
        "uncertainties": ["Synthetic sample"],
        "primary_category": "Learning",
        "category_confidence": confidence,
        "tags": ["test"],
        "topics": [{"title": "Test", "kind": "concept"}],
    }


def mock_client(value, done=True, done_reason="stop"):
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=(
                    {"model_info": {"general.architecture": "synthetic"}}
                    if request.url.path == "/api/show"
                    else {"response": json.dumps(value), "done": done, "done_reason": done_reason}
                ),
            )
        )
    )


@pytest.mark.parametrize(
    "value",
    [
        "plain text",
        {},
        {**summary(), "page_number": 99},
        {**summary(), "category_confidence": "high"},
    ],
)
def test_invalid_model_schema_rejected(value):
    with pytest.raises(WikiError, match="invalid"):
        structured(
            "Test", SectionSummary, client=mock_client(value), settings=Settings(_env_file=None)
        )


def test_remote_local_url_never_receives_evidence():
    with pytest.raises(WikiError, match="loopback"):
        structured(
            "private original",
            SectionSummary,
            settings=Settings(_env_file=None, ollama_base_url="https://example.com"),
        )


@pytest.mark.parametrize("reason,done", [("length", True), ("stop", False)])
def test_unfinished_output_rejected(reason, done):
    with pytest.raises(WikiError, match="finish"):
        structured(
            "Test",
            SectionSummary,
            client=mock_client(summary(), done, reason),
            settings=Settings(_env_file=None),
        )


def test_unknown_or_invented_quote_rejected():
    evidence = {"verified": passage("A test")}
    for identifier, quote in [("made-up", "A test"), ("verified", "nonexistent quote")]:
        with pytest.raises(WikiError, match="unknown"):
            pipeline.verify_claim(
                SectionSummary.model_validate(summary(identifier, quote)).summary, evidence
            )


@pytest.mark.parametrize(
    "text", ["English detail 17.\n" * 3000, "한국어 정확한 수치 17입니다.\n" * 3000]
)
def test_long_input_is_fully_processed_in_bounded_batches(text):
    settings = Settings(_env_file=None)
    original = passage(text, 2)
    batches = list(pipeline.make_batches([original], [], settings))
    fragments = [p for batch in batches for p in batch]
    assert len(batches) > 1
    assert "".join(p.text for p in fragments) == text
    assert fragments[0].start == 0 and fragments[-1].end == len(text)
    assert all(p.page_number == 2 for p in fragments)
    calls = []

    def reply(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"general.architecture": "synthetic"}})
        payload = json.loads(request.content)
        calls.append(payload)
        p = json.loads(payload["prompt"])["passages"][0]
        assert (
            p["evidence_id"]
            in payload["format"]["$defs"]["Claim"]["properties"]["evidence_id"]["enum"]
        )
        assert payload["model"] == settings.ollama_model
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "response": json.dumps(summary(p["evidence_id"], p["text"][:15])),
            },
        )

    result, consumed = pipeline.summarize(
        [original],
        categories=[],
        settings=settings,
        client=httpx.Client(transport=httpx.MockTransport(reply)),
    )
    assert result["batch_count"] == len(calls) == len(batches)
    assert "".join(p.text for p in consumed) == text


def test_uncertain_classification_and_manual_lock():
    section = SectionSummary.model_validate(summary(confidence=0.3))
    assert pipeline.classify([section], ["Learning"]) == "Unclassified"
    assert pipeline.classify([section], [], "Personal") == "Personal"


def test_cancel_between_batches_does_not_finish_generation():
    calls = 0

    def checkpoint():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Cancelled")

    def reply(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"general.architecture": "synthetic"}})
        item = json.loads(json.loads(request.content)["prompt"])["passages"][0]
        return httpx.Response(
            200,
            json={
                "done": True,
                "response": json.dumps(summary(item["evidence_id"], item["text"][:10])),
            },
        )

    with pytest.raises(RuntimeError, match="Cancelled"):
        pipeline.summarize(
            [passage("Large source.\n" * 4000)],
            categories=[],
            settings=Settings(_env_file=None),
            checkpoint=checkpoint,
            client=httpx.Client(transport=httpx.MockTransport(reply)),
        )


def test_explicit_scope_never_infers_all_from_empty():
    assert WikiScope(mode="empty").source_ids == []
    with pytest.raises(ValueError):
        WikiScope(mode="chosen")


def test_taxonomy_hints_are_in_every_complete_bounded_prompt():
    topics = [{"kind": "project", "title": "HELIOS"}]
    batches = pipeline.make_batches(
        [passage("한국어 HELIOS 수치 37.\n" * 3000)],
        ["Learning"],
        Settings(_env_file=None),
        topics,
    )
    for batch in batches:
        prompt = json.loads(pipeline.prompt_for(batch, ["Learning"], topics))
        assert prompt["existing_topics"] == topics
        assert "language" in prompt
        assert all(p["text"] for p in prompt["passages"])
