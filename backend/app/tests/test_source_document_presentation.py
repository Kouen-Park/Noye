"""Output contracts over real catalog/evidence services; no actual model execution."""

import pytest

from app.db import documents
from app.db import source_documents as store
from app.services import knowledge_jobs
from app.services.source_documents import jobs, local, pipeline, presentation
from app.tests.test_folder_foundation import discover, folder
from app.tests.test_source_documents import enqueue, model, run, workspace


@pytest.mark.parametrize(
    "stage", ["outline", "process_original_sections", "cross_source_synthesis"]
)
def test_wrong_output_language_fails_before_any_artifact(workspace, stage):
    db, *_ = workspace
    discover(workspace)

    def wrong_language(payload, result):
        if payload["task"] == stage:
            if stage == "outline":
                result["title"] = "저수지 설계 보고서"
            else:
                result["claims"][0]["text"] = "저수지는 37리터를 저장합니다."

    with pytest.raises(local.DocumentError, match="requested English"):
        run(db, enqueue(db), model(transform=wrong_language)[0])
    assert documents.count_documents(db) == 0


def test_explicit_language_directive_overrides_wrong_model_intent(workspace):
    db, *_ = workspace
    discover(workspace)
    job = enqueue(db, instruction="한국어 자료를 사용하되 write the report in English.")
    artifact = run(db, job, model(language="Korean")[0])
    assert store.current(db, artifact)["metadata"]["intent"]["language"] == "English"
    assert (
        presentation.requested_language("Use English source files, 한국어로 작성", "English")
        == "Korean"
    )


@pytest.mark.parametrize(
    "instruction",
    [
        "Write the report in Korean from notes written in English.",
        "Please explain in Korean the documents written in English.",
        "한국어로 요약해줘. 영어로 작성된 원문을 사용해.",
    ],
)
def test_original_language_description_does_not_override_output_directive(instruction):
    assert presentation.requested_language(instruction, "English") == "Korean"


@pytest.mark.parametrize(
    "instruction",
    [
        "Write a report from notes in English.",
        "Generate a report using documents written in English.",
        "영문으로 된 자료를 요약해줘.",
    ],
)
def test_ambiguous_source_language_keeps_inferred_output_intent(instruction):
    assert presentation.requested_language(instruction, "Korean") == "Korean"


def test_korean_output_directive_handles_the_euro_particle():
    assert presentation.requested_language("영문으로 보고서 작성", "Korean") == "English"


def test_korean_generated_prose_keeps_english_original_quotes(workspace):
    db, *_ = workspace
    source = discover(workspace, "Reservoir.txt", "Reservoir stores 37 litres.")

    def korean(payload, result):
        if payload["task"] == "outline":
            result["title"] = "저수지 보고서"
            result["sections"][0]["title"] = "저장 방식"
        if payload["task"] in {"process_original_sections", "cross_source_synthesis"}:
            for claim in result["claims"]:
                claim["text"] = "저수지는 37리터를 저장합니다."

    artifact = run(
        db, enqueue(db, instruction="한국어로 보고서를 작성해줘."), model(transform=korean)[0]
    )
    revision = store.current(db, artifact)
    assert "저수지는 37리터" in revision["content"]
    citation = revision["metadata"]["citations"][0]
    assert citation["quote"].startswith("Reservoir")
    assert citation["source"]["source_version"] == source.content_hash
    assert revision["metadata"]["output_contract"]["requested_language"] == "Korean"


def test_unsupported_heading_is_replaced_and_empty_section_omitted(workspace):
    db, *_ = workspace
    discover(workspace)

    def unsupported(payload, result):
        if payload["task"] == "outline":
            result["title"] = "No information exists"
            result["sections"][0]["title"] = "No information exists"
            result["sections"].append({"id": "imagined", "title": "Nuclear architecture"})
        if payload["task"] == "verify_heading":
            result["supported"] = [False] * len(payload["passages"])

    artifact = run(db, enqueue(db), model(transform=unsupported)[0])
    revision = store.current(db, artifact)
    assert revision["title"] == "Source document"
    assert "No information exists" not in revision["content"]
    assert "Nuclear architecture" not in revision["content"]
    assert "## Source notes" in revision["content"]
    coverage = revision["metadata"]["coverage"]
    assert coverage["partial"]
    assert {item["code"] for item in coverage["presentation_limits"]} == {
        "unsupported_title",
        "unsupported_heading",
        "empty_section",
    }


def test_heading_quantity_is_rejected_even_if_model_verifier_approves(workspace):
    db, *_ = workspace
    discover(workspace)

    def unsupported_number(payload, result):
        if payload["task"] == "outline":
            result["sections"][0]["title"] = "Stores 999 litres"

    artifact = run(db, enqueue(db), model(transform=unsupported_number)[0])
    revision = store.current(db, artifact)
    assert "999" not in revision["content"]
    assert revision["metadata"]["coverage"]["partial"]


def test_absence_heading_is_rejected_even_if_model_verifier_approves(workspace):
    db, *_ = workspace
    discover(workspace)

    def unsupported_absence(payload, result):
        if payload["task"] == "outline":
            result["sections"][0]["title"] = "No information available"

    artifact = run(db, enqueue(db), model(transform=unsupported_absence)[0])
    revision = store.current(db, artifact)
    assert "No information available" not in revision["content"]
    assert revision["metadata"]["coverage"]["partial"]
    assert presentation.is_absence_heading("자료에 대한 정보 부족")


def test_foreign_language_literal_fallback_is_preserved_as_partial(workspace):
    db, *_ = workspace
    discover(workspace, "한국어.txt", "저수지는 일요일을 제외하고 37리터를 저장합니다.")
    artifact = run(db, enqueue(db), model(invalid="synthesis_support")[0])
    revision = store.current(db, artifact)
    assert "> 저수지는 일요일을 제외하고 37리터를 저장합니다." in revision["content"]
    assert revision["metadata"]["coverage"]["partial"]
    assert revision["metadata"]["intent"]["language"] == "English"


@pytest.mark.parametrize("joint", [False, True])
def test_comparison_requires_supported_multiple_source_synthesis(workspace, joint):
    db, *_ = workspace
    discover(workspace, "alpha.txt", "Reservoir Alpha stores 37 litres.")
    discover(workspace, "beta.txt", "Reservoir Beta stores 92 litres.")

    def combine(payload, result):
        if joint and payload["task"] == "cross_source_synthesis":
            result["claims"] = [
                {
                    "text": "Alpha stores 37 litres; Beta stores 92 litres.",
                    "claim_ids": [c["id"] for c in payload["claims"]],
                }
            ]

    artifact = run(
        db,
        enqueue(db, instruction="Compare the reservoir designs in English."),
        model(transform=combine)[0],
    )
    coverage = store.current(db, artifact)["metadata"]["coverage"]
    limits = {item["code"] for item in coverage.get("presentation_limits", [])}
    assert ("comparison_unresolved" in limits) is not joint
    assert coverage["partial"] is not joint


def test_wrong_language_job_retry_clears_failed_cache_and_preserves_saved_edits(
    workspace, monkeypatch
):
    db, *_ = workspace
    discover(workspace)
    job = enqueue(db)
    generate = pipeline.generate

    def wrong_language(payload, result):
        if payload["task"] == "cross_source_synthesis":
            result["claims"][0]["text"] = "저수지는 37리터를 저장합니다."

    monkeypatch.setattr(
        pipeline,
        "generate",
        lambda context: generate(context, client=model(transform=wrong_language)[0]),
    )
    worker = knowledge_jobs.KnowledgeWorker()
    jobs.register()
    worker.run_one(db, job["id"])
    assert knowledge_jobs.get(db, job["id"])["state"] == "failed"
    assert store.request(db, job["subject_id"])["cache"] == {}
    retry = knowledge_jobs.resume(db, job["id"])
    monkeypatch.setattr(pipeline, "generate", lambda context: generate(context, client=model()[0]))
    worker.run_one(db, retry["id"])
    artifact = knowledge_jobs.get(db, retry["id"])["artifact_id"]
    initial = store.current(db, artifact)
    documents.update_document(db, artifact, content="# User edit\n한국어 should remain unchanged.")
    edited = store.current(db, artifact)
    # Completed artifact identity short-circuits every new output guard and model call.
    assert (
        generate(knowledge_jobs.WorkContext(db, retry), client=model(transform=wrong_language)[0])
        == artifact
    )
    assert store.current(db, artifact) == edited
    assert len(store.revisions(db, artifact)) == 2
    assert initial["id"] != edited["id"]


def test_unsupported_language_is_partial_instead_of_certified(workspace):
    db, *_ = workspace
    discover(workspace)
    artifact = run(db, enqueue(db), model(language="French")[0])
    revision = store.current(db, artifact)
    assert revision["metadata"]["output_contract"]["language_check"] == "unchecked"
    assert revision["metadata"]["coverage"]["partial"]


@pytest.mark.parametrize(
    "text",
    [
        "## Unsupported architecture\nReservoir stores 37 litres.",
        "Unsupported architecture\n===\nReservoir stores 37 litres.",
    ],
)
def test_generated_prose_cannot_inject_an_unreviewed_heading(workspace, text):
    db, *_ = workspace
    discover(workspace)

    def inject(payload, result):
        if payload["task"] == "cross_source_synthesis":
            result["claims"][0]["text"] = text

    with pytest.raises(local.DocumentError, match="unplanned Markdown heading"):
        run(db, enqueue(db), model(transform=inject)[0])
    assert documents.count_documents(db) == 0
