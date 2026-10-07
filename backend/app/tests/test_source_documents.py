"""Real folder/catalog/Wiki/version services; deterministic local model responses."""

import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import documents as legacy_api
from app.api import source_documents as api
from app.api.deps import get_db
from app.config import Settings
from app.db import conversations, documents
from app.db import source_documents as store
from app.models.conversations import Role
from app.models.source_documents import GenerateRequest, Selection
from app.models.wiki import WikiScope
from app.services import knowledge_jobs
from app.services.source_documents import jobs, local, pipeline
from app.services.wiki import service as wiki_service
from app.services.wiki import sources
from app.tests.test_folder_foundation import discover, folder, ingest
from app.tests.test_wiki_integration import model as wiki_model


@pytest.fixture
def workspace(folder):
    store.install(folder[0])
    folder[0].commit()
    return folder


def model(
    *,
    callback=None,
    invalid=None,
    selected=None,
    language="English",
    intent_mode="relevant",
    collection_query="",
):
    calls = []
    synthesized = [False]

    def response(request):
        body = json.loads(request.content)
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"general.architecture": "qwen3"}})
        payload = json.loads(body["prompt"])
        calls.append(payload)
        if callback:
            callback(payload)
        task = payload["task"]
        if task == "interpret_intent":
            result = {
                "purpose": "Explain designs",
                "topic": "Reservoir",
                "document_type": "report",
                "language": language,
                "inventory_mode": intent_mode,
                "collection_query": collection_query,
                "clarification": None,
            }
        elif task == "discover_sources":
            result = {
                "source_ids": [
                    s["source_id"]
                    for s in payload["inventory"]
                    if selected is None or s["source_id"] in selected
                ]
            }
        elif task == "outline":
            result = {
                "title": "Reservoir 설계 비교",
                "sections": [{"id": "design", "title": "Designs"}],
            }
        elif task == "process_original_sections":
            result = {
                "claims": [
                    {
                        "section_id": "design",
                        "text": p["text"][:100],
                        "supports": [
                            {
                                "evidence_id": "invented" if invalid == "id" else p["evidence_id"],
                                "quote": "made up" if invalid == "quote" else p["text"][:100],
                            }
                        ],
                    }
                    for p in payload["passages"]
                ],
                "gaps": [],
            }
            if invalid == "number":
                result["claims"][0]["text"] = "Capacity is 999999 litres."
            if invalid == "synthesis_support":
                result["claims"][0]["text"] = "An earlier overconfident paraphrase."
                other = json.loads(json.dumps(result["claims"][0]))
                other["supports"][0]["quote"] = other["supports"][0]["quote"][1:]
                result["claims"].append(other)
        elif task == "cross_source_synthesis":
            synthesized[0] = True
            result = {
                "claims": [{"text": c["text"], "claim_ids": [c["id"]]} for c in payload["claims"]]
            }
            if invalid == "synthesis":
                result["claims"][0]["claim_ids"] = ["invented"]
            if invalid == "synthesis_support":
                result["claims"][0]["text"] = "An unsupported universal guarantee."
        elif task == "verify_support":
            result = {
                "supported": [
                    invalid != "unsupported"
                    and not (invalid == "synthesis_support" and synthesized[0])
                ]
                * len(payload["claims"])
            }
        else:
            raise AssertionError(task)
        if invalid == "json":
            result = {"unexpected": True}
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "response": json.dumps(result, ensure_ascii=False),
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(response))
    return client, calls


def enqueue(db, scope=None, identifier="request", mode="collection", conversation_id=None):
    return jobs.enqueue(
        db,
        GenerateRequest(
            request_id=identifier,
            instruction="Write a design report.",
            scope=scope or WikiScope(),
            inventory_mode=mode,
            conversation_id=conversation_id,
        ),
    )


def run(db, job, client=None, settings=None):
    client = client or model()[0]
    return pipeline.generate(knowledge_jobs.WorkContext(db, job), client=client, settings=settings)


def test_real_originals_full_collection_bilingual_evidence_and_legacy_editor(workspace):
    db, root, *_ = workspace
    first = discover(
        workspace, "Course/lecture1.txt", "Reservoir Alpha stores 37 litres except on Sundays."
    )
    second = discover(
        workspace, "Course/lecture2.md", "저수지 Beta는 92리터를 저장하고 일요일에도 작동합니다."
    )
    before = {p.name: p.read_bytes() for p in (root / "Course").iterdir()}
    job = enqueue(db)
    identifier = run(db, job)
    head = store.current(db, identifier)
    assert head["metadata"]["coverage"]["inventory_mode"] == "collection"
    assert {s["source_id"] for s in head["metadata"]["coverage"]["sources"]} == {
        first.id,
        second.id,
    }
    assert all(s["state"] == "processed" for s in head["metadata"]["coverage"]["sources"])
    assert "37" in head["content"] and "92" in head["content"]
    for citation in head["metadata"]["citations"]:
        passage = next(p for p in head["metadata"]["evidence"] if p["id"] == citation["id"])
        assert citation["quote"] in passage["text"]
        assert citation["page_number"] is None
        assert citation["source"]["source_version"] in {first.content_hash, second.content_hash}
    documents.update_document(db, identifier, content="# 사용자 편집\nKeep my changes.")
    edited = store.current(db, identifier)
    assert edited["origin"] == "user" and edited["parent_id"] == head["id"]
    assert run(db, job) == identifier
    assert store.current(db, identifier)["content"] == edited["content"]
    assert len(store.revisions(db, identifier)) == 2
    conversations.delete_conversation(
        db, store.request(db, job["subject_id"])["request"]["conversation_id"]
    )
    assert documents.get_document(db, identifier).source_message_id is None
    assert {p.name: p.read_bytes() for p in (root / "Course").iterdir()} == before
    documents.delete_document(db, identifier)
    assert run(db, job) == identifier
    assert not db.execute("SELECT 1 FROM documents WHERE id=?", (identifier,)).fetchone()


def test_relevant_discovery_uses_scoped_wiki_relations_not_wiki_as_evidence(workspace):
    db, *_ = workspace
    first = discover(workspace, "Alpha.txt", "Reservoir Alpha capacity is 37 litres.")
    second = discover(workspace, "Beta.txt", "Reservoir Beta capacity is 92 litres.")
    for source in (first, second):
        wiki_service.generate_source(
            db, source.id, WikiScope(), sources.freeze(db, WikiScope()), client=wiki_model()
        )
    scope = WikiScope(mode="chosen", source_ids=[first.id])
    job = enqueue(db, scope, mode="relevant")
    client, calls = model(selected=[first.id])
    identifier = run(db, job, client)
    metadata = store.current(db, identifier)["metadata"]
    assert metadata["wiki_hints"][first.id]
    assert {s["source_id"] for s in metadata["selected_manifest"]} == {first.id}
    assert all(second.id not in json.dumps(c) for c in calls)
    assert metadata["coverage"]["inventory_mode"] == "relevant"


def test_empty_scope_requires_sources_without_model_call(workspace):
    db, *_ = workspace
    discover(workspace)
    job = enqueue(db, WikiScope(mode="empty"))
    client, calls = model()
    with pytest.raises(pipeline.ClarificationRequired, match="No sources"):
        run(db, job, client)
    assert calls == [] and documents.count_documents(db) == 0


def test_missing_and_indexing_failure_are_partial_coverage(workspace):
    db, root, _, scan, _ = workspace
    first = discover(workspace, "ready.txt", "Reservoir Alpha stores 37 litres.")
    missing = discover(workspace, "missing.md", "Reservoir Beta stores 92 litres.")
    (root / "missing.md").unlink()
    scan()
    scan()
    (root / "no-text.txt").write_bytes(b"")
    scan()
    (failed,) = scan()
    from app.services import ingestion

    ingestion.ingest_file(db, failed, reserved=True)
    job = enqueue(
        db, WikiScope(mode="chosen", source_ids=[first.id, missing.id, failed, "deleted-id"])
    )
    identifier = run(db, job)
    coverage = store.current(db, identifier)["metadata"]["coverage"]
    assert coverage["partial"]
    assert {s["source_id"]: s["state"] for s in coverage["sources"]} == {
        first.id: "processed",
        missing.id: "missing",
        failed: "indexing_failed",
        "deleted-id": "missing",
    }
    assert "Partial result" in documents.get_document(db, identifier).content


@pytest.mark.parametrize("invalid", ["id", "quote", "number", "synthesis", "unsupported", "json"])
def test_invalid_model_output_never_saves_artifact(workspace, invalid):
    db, *_ = workspace
    discover(workspace)
    with pytest.raises(local.DocumentError):
        run(db, enqueue(db), model(invalid=invalid)[0])
    assert documents.count_documents(db) == 0


def test_long_inputs_all_fragments_processed_no_silent_truncation(workspace):
    db, *_ = workspace
    discover(workspace, "long.txt", ("Reservoir capacity is 37 litres except Sunday.\n" * 180))
    client, calls = model()
    identifier = run(
        db, enqueue(db), client, Settings(_env_file=None, generation_context_tokens=8192)
    )
    meta = store.current(db, identifier)["metadata"]
    source = meta["coverage"]["sources"][0]
    assert source["characters_read"] > 8000
    assert source["characters_read"] == source["characters_processed"]
    assert len([c for c in calls if c["task"] == "process_original_sections"]) > 1
    assert all(local.size(c, Selection) < 8192 for c in calls)


def test_original_edit_during_inference_and_retry_never_mixes_versions(workspace):
    db, root, _, scan, _ = workspace
    record = discover(workspace)
    job = enqueue(db)

    def mutate(payload):
        if payload["task"] == "cross_source_synthesis":
            (root / "note.txt").write_text("New limit is 92.")

    with pytest.raises(Exception, match="bytes no longer match"):
        run(db, job, model(callback=mutate)[0])
    assert documents.count_documents(db) == 0
    scan()
    (identifier,) = scan()
    ingest(db, identifier)
    assert identifier == record.id
    with pytest.raises(local.DocumentError, match="original changed"):
        run(db, job)
    assert store.request(db, job["subject_id"])["manifest"][0]["version"] == record.content_hash


def test_cancellation_restart_and_explicit_retry_use_durable_cache(workspace, monkeypatch):
    db, *_ = workspace
    discover(workspace)
    job = enqueue(db)
    with db:
        db.execute("UPDATE knowledge_jobs SET state='running' WHERE id=?", (job["id"],))

    def cancel(payload):
        if payload["task"] == "process_original_sections":
            knowledge_jobs.cancel(db, job["id"])

    monkeypatch.setattr(jobs.pipeline, "generate", pipeline.generate)
    with pytest.raises(knowledge_jobs.WorkCancelled):
        run(db, job, model(callback=cancel)[0])
    assert documents.count_documents(db) == 0
    knowledge_jobs.recover_interrupted(db)
    assert knowledge_jobs.get(db, job["id"])["state"] == "interrupted"
    retry = knowledge_jobs.resume(db, job["id"])
    assert retry["manifest"] == job["manifest"] and retry["attempt"] == 2
    client, calls = model()
    identifier = run(db, retry, client)
    assert not any(c["task"] == "outline" for c in calls)
    assert documents.get_document(db, identifier)


def test_intent_context_user_only_and_conversation_scope_cannot_expand(workspace):
    db, *_ = workspace
    first = discover(workspace, "one.txt", "Reservoir 37 litres.")
    discover(workspace, "two.txt", "Secret unrelated 999 litres.")
    conversation = conversations.create_conversation(db, first_question="Research")
    conversations.add_message(
        db, conversation.id, role=Role.USER, content="Compare Reservoir designs"
    )
    conversations.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="Assistant invented 999 litres"
    )
    conversations.set_source_scope(db, conversation.id, [first.id])
    job = enqueue(db, conversation_id=conversation.id)
    assert [s["source_id"] for s in job["manifest"]] == [first.id]
    client, calls = model()
    run(db, job, client)
    intent = next(c for c in calls if c["task"] == "interpret_intent")
    assert intent["intent_context_not_evidence"] == ["Compare Reservoir designs"]
    assert all("Assistant invented" not in json.dumps(c) for c in calls)


def test_api_edit_conflict_selected_revision_export_and_old_api_compatibility(workspace):
    db, *_ = workspace
    discover(workspace)
    identifier = run(db, enqueue(db))
    app = FastAPI()
    app.include_router(api.router)
    app.include_router(legacy_api.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        initial = client.get(f"/source-documents/{identifier}").json()
        patch = {
            "expected_revision": initial["revision"]["id"],
            "title": "한국어 편집",
            "content": "# 한국어\nSaved edit",
        }
        saved = client.patch(f"/source-documents/{identifier}", json=patch)
        assert saved.status_code == 200 and saved.json()["revision"]["origin"] == "user"
        assert client.patch(f"/source-documents/{identifier}", json=patch).status_code == 409
        current_export = client.get(f"/source-documents/{identifier}/export.md")
        assert current_export.text == patch["content"]
        historical = client.get(
            f"/source-documents/{identifier}/export.md",
            params={"revision": initial["revision"]["id"], "provenance": True},
        )
        assert "Saved original evidence" in historical.text and "Saved edit" not in historical.text
        assert "filename*=UTF-8''" in current_export.headers["content-disposition"]
        assert client.get(f"/documents/{identifier}").json()["content"] == patch["content"]
        assert client.get("/documents").status_code == 200


def test_repeated_generation_request_returns_one_job_and_one_user_message(workspace):
    db, *_ = workspace
    discover(workspace)
    a = enqueue(db)
    b = enqueue(db)
    assert a["id"] == b["id"]
    assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 1
    run(db, a)
    assert enqueue(db)["id"] == a["id"]
    assert documents.count_documents(db) == 1


def test_chat_task_history_filters_conversation_before_applying_display_limit(workspace):
    db, *_ = workspace
    discover(workspace)
    older = enqueue(db, identifier="older-conversation-request")
    conversation_id = store.request(db, older["subject_id"])["request"]["conversation_id"]
    for position in range(101):
        enqueue(db, identifier=f"unrelated-{position}")
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        tasks = client.get(
            "/source-documents/requests",
            params={
                "conversation_id": conversation_id,
            },
        ).json()
    assert [task["request"]["id"] for task in tasks] == [older["subject_id"]]


def test_named_collection_enumerates_every_member_and_freezes_later_discoveries(workspace):
    db, *_ = workspace
    a = discover(workspace, "Course/one.txt", "Reservoir capacity is 37 litres.")
    b = discover(workspace, "Course/two.txt", "Reservoir capacity is 92 litres.")
    discover(workspace, "Elsewhere/other.txt", "A different collection.")
    job = enqueue(db, mode="auto")
    later = discover(workspace, "Course/later.txt", "Discovered after the request started.")
    client, calls = model(intent_mode="collection", collection_query="Course")
    artifact = run(db, job, client)
    manifest = store.current(db, artifact)["metadata"]["selected_manifest"]
    assert {s["source_id"] for s in manifest} == {a.id, b.id}
    assert all(later.id not in json.dumps(c) for c in calls)
    assert not any(c["task"] == "discover_sources" for c in calls)


def test_model_failure_job_can_retry_without_reusing_invalid_evidence_cache(workspace, monkeypatch):
    db, *_ = workspace
    discover(workspace)
    job = enqueue(db)
    original = pipeline.generate
    worker = knowledge_jobs.KnowledgeWorker()
    jobs.register()
    monkeypatch.setattr(
        pipeline, "generate", lambda context: original(context, client=model(invalid="quote")[0])
    )
    worker.run_one(db, job["id"])
    assert knowledge_jobs.get(db, job["id"])["state"] == "failed"
    assert store.request(db, job["subject_id"])["cache"] == {}
    retry = knowledge_jobs.resume(db, job["id"])
    monkeypatch.setattr(pipeline, "generate", lambda context: original(context, client=model()[0]))
    worker.run_one(db, retry["id"])
    assert knowledge_jobs.get(db, retry["id"])["state"] == "complete"
    assert documents.count_documents(db) == 1


def test_local_only_and_array_schema_constraints():
    schema = local.output_schema(Selection, {"source_ids": ["a", "b"]})
    assert schema["properties"]["source_ids"]["items"]["enum"] == ["a", "b"]
    settings = Settings(_env_file=None, ollama_base_url="https://remote.example")
    client, calls = model()
    with pytest.raises(Exception, match="local loopback"):
        local.structured({"task": "interpret_intent"}, Selection, settings=settings, client=client)
    assert calls == []


def test_translated_explicit_counts_are_supported_but_unstated_numerals_are_rejected():
    pipeline.verify_numbers("백업은 하루 2번 실행됩니다.", "Backups run twice a day.")
    pipeline.verify_numbers("Backups run 1 time daily.", "백업은 하루에 한 번 실행됩니다.")
    with pytest.raises(local.DocumentError, match="number absent"):
        pipeline.verify_numbers("Backups run 9 times daily.", "Backups run twice a day.")


def test_loopback_cloud_alias_is_rejected_before_source_context_is_sent():
    seen = []

    def response(request):
        seen.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "model_info": {"architecture": "remote"},
                "remote_host": "https://ollama.com",
                "remote_model": "cloud",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        with pytest.raises(local.DocumentError, match="installed local model"):
            local.structured(
                {"task": "test", "original": "Private excerpt"}, Selection, client=client
            )
    assert seen == ["/api/show"]


def test_unverified_synthesis_retains_verbatim_originals_as_explicit_partial(workspace):
    db, *_ = workspace
    discover(workspace)
    artifact = run(db, enqueue(db), model(invalid="synthesis_support")[0])
    revision = store.current(db, artifact)
    assert "unsupported universal guarantee" not in revision["content"]
    assert "earlier overconfident paraphrase" not in revision["content"]
    assert "37" in revision["content"]
    original = revision["metadata"]["evidence"][0]["text"]
    assert revision["content"].count("> " + original.splitlines()[0]) == 1
    assert "[E1, E2]" in revision["content"]
    assert revision["metadata"]["coverage"]["partial"]
    assert revision["metadata"]["coverage"]["synthesis_limits"]
    assert "comparative conclusions" in revision["content"]
