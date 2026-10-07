"""Same real source corpus for baseline and Wiki-original discovery; scope and stale failures."""

import pytest

from app.db import knowledge as snapshots
from app.db import wiki as store
from app.models.wiki import EditWiki
from app.services import generation, knowledge_query
from app.services.retrieval import SearchResult
from app.services.source_catalog import SourceError
from app.services.wiki import service
from app.tests.test_folder_foundation import discover, folder
from app.tests.test_wiki_integration import generate, workspace


def vector_for(db, ids, content="UNTRUSTED VECTOR CONTENT"):
    return [
        SearchResult(content, row["file_id"], row["page_number"], row["chunk_index"], 0.6)
        for row in db.execute("SELECT * FROM chunks")
        if row["file_id"] in ids
    ]


def test_details_omitted_from_wiki_are_read_from_original_not_vector_payload(workspace):
    db, *_ = workspace
    original = (
        "Reservoir operating notes. "
        + "Background conditions. " * 12
        + "Capacity is 37 litres except on Sundays; exact term is Manual Gate."
    )
    record = discover(workspace, content=original)
    result = generate(db, record.id)
    revision = store.revision(db, result["revision_id"])
    assert "37" not in revision["metadata"]["sections"][0]["summary"]["text"]
    context = knowledge_query.discover(
        db,
        "Reservoir capacity Sundays Manual Gate",
        vector_search=lambda q, **kw: vector_for(db, kw["file_ids"]),
    )
    assert context.snapshot["wiki_state"] == "matched"
    assert any("37 litres except on Sundays" in item.content for item in context.sources)
    assert all(item.source_hash == record.content_hash for item in context.sources)
    assert "UNTRUSTED" not in str(context.sources)


def test_chosen_and_empty_scope_never_follow_outside_link(workspace):
    db, *_ = workspace
    first = discover(workspace, "one.txt", "Reservoir capacity is 37 litres except on Sundays.")
    second = discover(workspace, "two.txt", "Reservoir capacity is 92 litres.")
    a = generate(db, first.id)
    b = generate(db, second.id)
    assert store.relations(db, b["wiki_id"])
    calls = []

    def vector(q, **kw):
        calls.append(kw["file_ids"])
        return vector_for(db, [first.id, second.id])  # Even a broken search cannot widen scope.

    scope = {"mode": "chosen", "source_ids": [first.id]}
    context = knowledge_query.discover(db, "Reservoir capacity", scope, vector_search=vector)
    assert {item.file_id for item in context.sources} == {first.id}
    assert all(ids == [first.id] for ids in calls)
    assert all(page["source_ids"] == [first.id] for page in context.snapshot["wiki_pages"])
    assert a["wiki_id"] in {p["wiki_id"] for p in context.snapshot["wiki_pages"]}
    calls.clear()
    empty = knowledge_query.discover(
        db, "Reservoir capacity", {"mode": "empty"}, vector_search=vector
    )
    assert not calls and not empty.sources and not empty.snapshot["wiki_pages"]


def test_unobserved_change_missing_and_wiki_failure_exclude_current_evidence(
    workspace, monkeypatch
):
    db, root, *_ = workspace
    record = discover(workspace)
    generate(db, record.id)

    def search(q, **kw):
        return vector_for(db, kw["file_ids"])

    (root / "note.txt").write_text("Capacity changed to 92.")
    context = knowledge_query.discover(db, "capacity", vector_search=search)
    assert not context.sources and not context.snapshot["wiki_pages"]
    assert context.snapshot["insufficient_evidence"]
    assert any("stale_version" in warning for warning in context.snapshot["warnings"])
    (root / "note.txt").unlink()
    assert not knowledge_query.discover(db, "capacity", vector_search=search).sources


def test_user_wiki_interpretation_and_assistant_claims_never_become_facts(workspace, monkeypatch):
    db, *_ = workspace
    record = discover(workspace, content="Reservoir capacity is exactly 37 litres.")
    page = generate(db, record.id)
    service.edit(
        db,
        page["wiki_id"],
        EditWiki(
            expected_revision=page["revision_id"],
            title="Reservoir interpretation",
            content="The capacity is 999 litres.",
        ),
    )
    prompts = []
    monkeypatch.setattr(
        generation, "generate", lambda prompt, **kw: prompts.append(prompt) or "37 litres."
    )
    context = knowledge_query.discover(
        db, "Reservoir capacity", vector_search=lambda q, **kw: vector_for(db, kw["file_ids"])
    )
    assert "999" in str(context.snapshot["wiki_pages"])
    assert knowledge_query.answer(context, "What capacity?").text == "37 litres."
    assert "999" not in prompts[0] and "37" in prompts[0]
    current = store.page(db, page["wiki_id"])
    assert store.revision(db, current["current_revision"])["origin"] == "user"


def test_wiki_error_falls_back_to_original_and_change_during_answer_refuses_publish(
    workspace, monkeypatch
):
    db, root, *_ = workspace
    discover(workspace)

    def broken(*args, **kwargs):
        raise ValueError("Wiki unavailable")

    monkeypatch.setattr(knowledge_query.relations, "search", broken)
    context = knowledge_query.discover(
        db, "limit", vector_search=lambda q, **kw: vector_for(db, kw["file_ids"])
    )
    assert context.sources and context.snapshot["wiki_state"] == "unavailable"

    def changed(*args, **kwargs):
        (root / "note.txt").write_text("New limit: 92.")
        return "The limit is 37."

    monkeypatch.setattr(generation, "generate", changed)
    with pytest.raises(SourceError):
        knowledge_query.answer(context, "What is the limit?")
