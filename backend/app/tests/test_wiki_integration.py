"""A's real folder/scanner/extraction/catalog with B's real persistence and mock Ollama."""

import json

import httpx
import pytest

from app.config import Settings
from app.db import wiki as store
from app.models.wiki import EditWiki, SaveAnalysis, WikiScope
from app.services import knowledge_jobs
from app.services.source_catalog import SourceCatalog, SourceError
from app.services.wiki import publication, relations, service, sources
from app.services.wiki.local import WikiError
from app.tests.test_folder_foundation import discover, folder, ingest
from app.tests.test_wiki_pipeline import summary


@pytest.fixture
def workspace(folder):
    db, *_ = folder
    store.install(db)
    db.commit()
    return folder


def model(kind="shared_subject", bad_target=False, callback=None):
    def response(request):
        prompt = json.loads(json.loads(request.content)["prompt"])
        if callback:
            callback(prompt)
        if prompt["task"] == "summarize_section":
            p = prompt["passages"][0]
            result = summary(p["evidence_id"], p["text"][:40])
            result["summary"]["text"] = p["text"][:80]
            result["tags"] = ["reservoir", "capacity"]
            result["topics"] = [
                {"title": "Reservoir", "kind": "concept"},
                {"title": "Water Plan", "kind": "project"},
            ]
        else:
            result = {
                "relations": [
                    {
                        "target_id": "invented" if bad_target else prompt["target_id"],
                        "kind": kind,
                        "reason": "Both sources specify reservoir capacity and conditions.",
                        "confidence": 0.9,
                        "origin_evidence_id": prompt["origin"]["evidence_id"],
                        "target_evidence_id": prompt["target"]["evidence_id"],
                    }
                ]
            }
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "response": json.dumps(result, ensure_ascii=False),
            },
        )

    return httpx.Client(transport=httpx.MockTransport(response))


def generate(db, identifier, client=None, scope=None):
    scope = scope or WikiScope()
    return service.generate_source(
        db, identifier, scope, sources.freeze(db, scope), client=client or model()
    )


def test_real_folder_summary_and_classification_proposal(workspace):
    db, root, _, _, _ = workspace
    original = "저수지 용량은 37리터이며 일요일에는 예외입니다."
    record = discover(workspace, "Learning/한국어.md", original)
    before = (root / "Learning/한국어.md").read_bytes()
    result = generate(db, record.id)
    revision = store.revision(db, result["revision_id"])
    assert original in revision["content"]
    assert revision["metadata"]["classification_is_proposal"]
    assert result["classification"] == "Learning"
    assert all(e["page_number"] is None for e in revision["evidence"])
    assert all(e["source"]["source_hash"] == record.content_hash for e in revision["evidence"])
    assert (root / "Learning/한국어.md").read_bytes() == before
    assert publication.disk_path(db, result["wiki_id"]).read_text() == revision["content"]
    assert generate(db, record.id)["reused"]
    assert len(store.revisions(db, result["wiki_id"])) == 1


@pytest.mark.parametrize(
    "kind", ["shared_subject", "supporting_evidence", "alternative", "contradiction"]
)
def test_verified_relation_targets_backlinks_and_topics(workspace, kind):
    db, _, _, _, _ = workspace
    first = discover(workspace, "one.txt", "Reservoir capacity is 37 litres except on Sundays.")
    second = discover(workspace, "two.md", "저수지 용량은 92리터입니다.")
    a = generate(db, first.id)
    b = generate(db, second.id, model(kind))
    links = store.relations(db, b["wiki_id"])
    assert len(links) == 1
    assert links[0]["kind"] == kind and links[0]["target_id"] == a["wiki_id"]
    assert store.relations(db, a["wiki_id"])[0]["origin_id"] == b["wiki_id"]
    topics = [p for p in store.list_pages(db) if p["kind"] in ("concept", "project")]
    assert {p["kind"] for p in topics} == {"concept", "project"}
    assert all(
        len(store.revision(db, p["current_revision"])["metadata"]["contributors"]) == 2
        for p in topics
    )
    generate(db, second.id)
    assert len([p for p in store.list_pages(db) if p["kind"] == "concept"]) == 1


def test_invented_relation_target_does_not_publish(workspace):
    db, _, _, _, _ = workspace
    first = discover(workspace, "one.txt", "Reservoir capacity is 37 litres.")
    second = discover(workspace, "two.txt", "Reservoir capacity is 92 litres.")
    generate(db, first.id)
    with pytest.raises(WikiError, match="unverified"):
        generate(db, second.id, model(bad_target=True))
    assert not store.find(db, f"source:{second.id}")["current_revision"]


def test_topic_reuse_hints_do_not_cross_selected_sources(workspace):
    db, *_ = workspace
    first = discover(workspace, "one.txt", "Reservoir capacity is 37 litres.")
    second = discover(workspace, "two.txt", "Reservoir capacity is 92 litres.")
    generate(db, first.id)
    all_scope = WikiScope()
    root_id = sources.catalog(db).get(first.id)["root_id"]
    assert service.known_topics(db, root_id, all_scope, sources.freeze(db, all_scope))
    chosen = WikiScope(mode="chosen", source_ids=[second.id])
    assert service.known_topics(db, root_id, chosen, sources.freeze(db, chosen)) == []


def test_generation_settings_change_has_a_distinct_revision_identity(workspace, monkeypatch):
    db, *_ = workspace
    record = discover(workspace)
    first = generate(db, record.id)
    settings = Settings(_env_file=None, generation_context_tokens=8192)
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    second = generate(db, record.id)
    assert not second["reused"] and second["revision_id"] != first["revision_id"]
    metadata = store.revision(db, second["revision_id"])["metadata"]
    assert metadata["parameters"]["context_tokens"] == 8192
    assert generate(db, record.id)["reused"]


def test_user_disk_edits_conflict_refresh_and_provenance(workspace):
    db, root, _, scan, _ = workspace
    record = discover(workspace)
    result = generate(db, record.id)
    path = publication.disk_path(db, result["wiki_id"])
    path.write_text("# My edited 한국어 Wiki\n37 is historical.\n")
    (root / "note.txt").write_text("Changed reservoir capacity is 92 litres.")
    scan()
    (identifier,) = scan()
    ingest(db, identifier)
    proposal = generate(db, identifier)
    page = store.page(db, result["wiki_id"])
    current = store.revision(db, page["current_revision"])
    assert current["origin"] == "user" and "My edited" in current["content"]
    assert store.revision(db, proposal["revision_id"])["origin"] == "proposal"
    assert path.read_text() == current["content"]
    assert service.provenance(db, current["evidence"])[0]["current_status"] == "superseded"
    service.adopt(db, page["id"], proposal["revision_id"], current["id"])
    assert "92" in path.read_text()
    assert current["id"] in [r["id"] for r in store.revisions(db, page["id"])]


def test_source_changed_during_inference_and_frozen_inventory(workspace):
    db, root, _, _, _ = workspace
    record = discover(workspace)
    manifest = sources.freeze(db, WikiScope())

    def mutate(prompt):
        (root / "note.txt").write_text("Changed after the scan but before Wiki commit.")

    with pytest.raises(SourceError, match="bytes"):
        service.generate_source(db, record.id, WikiScope(), manifest, client=model(callback=mutate))
    assert not store.find(db, f"source:{record.id}")["current_revision"]


def test_scope_empty_chosen_and_link_traversal(workspace):
    db, _, _, _, _ = workspace
    first = discover(workspace, "one.txt", "Reservoir capacity is 37 litres.")
    second = discover(workspace, "two.txt", "Reservoir capacity is 92 litres.")
    a, b = generate(db, first.id), generate(db, second.id)
    empty = WikiScope(mode="empty")
    assert relations.search(db, "Reservoir", empty, []) == []
    chosen = WikiScope(mode="chosen", source_ids=[second.id])
    manifest = sources.freeze(db, chosen)
    assert relations.traverse(db, b["wiki_id"], chosen, manifest, 2) == [b["wiki_id"]]
    assert a["wiki_id"] not in relations.traverse(db, b["wiki_id"], chosen, manifest, 2)
    with pytest.raises(ValueError, match="2 levels"):
        relations.traverse(db, b["wiki_id"], chosen, manifest, 3)


def test_missing_and_disconnected_provenance_and_recover_projection(workspace):
    from app.services.folders import update_root

    db, root, root_id, scan, _ = workspace
    record = discover(workspace)
    result = generate(db, record.id)
    revision = store.revision(db, result["revision_id"])
    path = publication.disk_path(db, result["wiki_id"])
    path.unlink()
    publication.recover_publications(db)
    assert path.read_text() == revision["content"]
    (root / "note.txt").unlink()
    scan()
    scan()
    assert service.provenance(db, revision["evidence"])[0]["current_status"] == "missing"
    update_root(db, root_id, disconnect=True)
    assert service.provenance(db, revision["evidence"])[0]["current_status"] == "disconnected"
    publication.materialize(db, result["wiki_id"])
    assert store.page(db, result["wiki_id"])["publication_error"]
    assert store.revision(db, result["revision_id"])["content"] == revision["content"]


def test_output_symlink_cannot_overwrite_outside(workspace, tmp_path):
    db, _, _, _, _ = workspace
    record = discover(workspace)
    result = generate(db, record.id)
    path = publication.disk_path(db, result["wiki_id"])
    outside = tmp_path / "outside.txt"
    outside.write_text("Keep")
    path.unlink()
    path.symlink_to(outside)
    publication.materialize(db, result["wiki_id"])
    assert outside.read_text() == "Keep"
    assert store.page(db, result["wiki_id"])["publication_error"]


def test_saved_analysis_has_authored_revision_and_scope_manifest(workspace):
    db, _, _, _, _ = workspace
    record = discover(workspace)
    result = generate(db, record.id)
    identifier = service.save_analysis(
        db,
        SaveAnalysis(
            title="Reusable analysis",
            content="My notes",
            wiki_ids=[result["wiki_id"]],
            scope=WikiScope(mode="chosen", source_ids=[record.id]),
        ),
    )
    current = store.revision(db, store.page(db, identifier)["current_revision"])
    assert current["origin"] == "user" and current["evidence"]
    assert current["metadata"]["manifest"][0]["source_id"] == record.id
