"""Output contracts over real catalog/evidence services; no actual model execution."""

import pytest

from app.db import documents
from app.db import source_documents as store
from app.services import knowledge_jobs
from app.services.source_documents import jobs, local, pipeline, presentation
from app.tests.test_folder_foundation import discover, folder
from app.tests.test_source_documents import enqueue, model, run, workspace


@pytest.mark.parametrize(
    "text,original",
    [
        ("It stores 37 litres.", "Its capacity is 37 litres."),
        ("Capacity is 92 litres.", "It stores 92 litres."),
        ("Alpha stores 37 litres.", "Alpha의 저장 용량은 37리터입니다."),
        ("용량은 92리터입니다.", "It stores 92 litres."),
    ],
)
def test_volume_property_swaps_are_rejected_even_when_the_number_matches(text, original):
    with pytest.raises(local.DocumentError, match="capacity into an amount stored"):
        presentation.check_volume_properties(text, [original])


@pytest.mark.parametrize(
    "text,originals",
    [
        ("Alpha has a capacity of 37 litres.", ["Alpha의 저장 용량은 37리터입니다."]),
        ("Beta stores 92 litres.", ["Project Beta stores 92 litres."]),
        ("37리터를 저장합니다.", ["It stores 37 litres."]),
        (
            "Capacity is 37 litres; Beta stores 92 litres.",
            ["Capacity: 37 litres.", "Beta stores 92 litres."],
        ),
        ("It stores 37 litres.", ["Capacity is 37 litres. It stores 37 litres."]),
    ],
)
def test_recorded_and_translated_volume_properties_remain_available(text, originals):
    presentation.check_volume_properties(text, originals)


@pytest.mark.parametrize(
    "text,original",
    [
        (
            "Magpie has a capacity of 29 litres, and currently holds 8 litres.",
            "Magpie의 저장 용량은 29리터입니다. 현재 8리터가 저장되어 있습니다.",
        ),
        (
            "Capacity is 17 litres; it currently retains 3 litres.",
            "Capacity is 17 litres. It stores 3 litres.",
        ),
        (
            "It stores 6 litres, and the rated limit is 20 litres.",
            "It stores 6 litres. Capacity is 20 litres.",
        ),
    ],
)
def test_volume_properties_do_not_carry_across_another_quantity(text, original):
    presentation.check_volume_properties(text, [original])


@pytest.mark.parametrize(
    "text,original",
    [
        (
            "Capacity is 29 litres, and capacity is 8 litres.",
            "Capacity is 29 litres. It stores 8 litres.",
        ),
        (
            "It stores 6 litres, and it stores 20 litres.",
            "It stores 6 litres. Capacity is 20 litres.",
        ),
    ],
)
def test_a_later_explicit_volume_property_swap_is_still_rejected(text, original):
    with pytest.raises(local.DocumentError, match="capacity into an amount stored"):
        presentation.check_volume_properties(text, [original])


def test_model_absence_assertion_cannot_replace_actual_coverage():
    with pytest.raises(local.DocumentError, match="missing-evidence"):
        presentation.check_absence_claim(
            "No evidence is supplied regarding Alpha's storage method.",
            ["Beta uses log files."],
        )
    presentation.check_absence_claim("No evidence was recorded.", ["No evidence was recorded."])


@pytest.mark.parametrize("stage", ["process_original_sections", "cross_source_synthesis"])
@pytest.mark.parametrize(
    "text,error,report_key",
    [
        ("Cedar stores 18 litres.", "capacity into an amount stored", "rejected_numeric_claim"),
        (
            "No evidence was supplied for Cedar's storage method.",
            "missing-evidence",
            "rejected_scope_claim",
        ),
    ],
)
def test_unsafe_claim_cannot_publish_even_when_model_verifier_approves(
    workspace, stage, text, error, report_key
):
    db, *_ = workspace
    discover(workspace, content="Cedar has a capacity of 18 litres. Cedar uses SQLite.")

    def unsafe(payload, result):
        if payload["task"] == stage:
            result["claims"][0]["text"] = text

    with pytest.raises(local.DocumentError, match=error):
        run(db, enqueue(db), model(transform=unsafe)[0])
    assert documents.count_documents(db) == 0
    assert store.request(db, "request")["report"][report_key]["text"] == text


@pytest.mark.parametrize(
    "stage", ["outline", "process_original_sections", "cross_source_synthesis"]
)
def test_wrong_output_language_fails_before_any_artifact(workspace, stage):
    db, *_ = workspace
    original = "Reservoir stores 37 litres."
    discover(workspace, content=original)

    def wrong_language(payload, result):
        if payload["task"] == stage:
            if stage == "outline":
                result["title"] = "저수지 설계 보고서"
            else:
                result["claims"][0]["text"] = "저수지는 37리터를 저장합니다."

    with pytest.raises(local.DocumentError, match="requested English"):
        run(db, enqueue(db), model(transform=wrong_language)[0])
    assert documents.count_documents(db) == 0
    if stage == "process_original_sections":
        entry = store.request(db, "request")["report"]["sources"][0]
        assert entry["passages_read"] == 1
        assert entry["characters_read"] == len(original)
        assert entry["characters_processed"] == 0
        assert entry["state"] == "pending"


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


@pytest.mark.parametrize("label", ["Source", "Original", "Input"])
@pytest.mark.parametrize("output,source", [("Korean", "English"), ("English", "Korean")])
def test_source_language_field_does_not_override_requested_output(label, output, source):
    assert (
        presentation.requested_language(
            f"Write the report in {output}. {label} language: {source}.", source
        )
        == output
    )
    assert presentation.requested_language(f"{label} language: {source}.", output) == output


@pytest.mark.parametrize(
    "instruction", ["Language: English", "Write notes. Output language: English"]
)
def test_explicit_output_language_field_remains_authoritative(instruction):
    assert presentation.requested_language(instruction, "Korean") == "English"


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

    client, calls = model(transform=korean)
    artifact = run(db, enqueue(db, instruction="한국어로 보고서를 작성해줘."), client)
    prose_calls = [
        payload
        for payload in calls
        if payload["task"] in {"outline", "process_original_sections", "cross_source_synthesis"}
    ]
    assert prose_calls and all(
        payload.get("output_language") == "Korean" for payload in prose_calls
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


def test_unmeasured_performance_heading_cannot_be_approved_by_the_model(workspace):
    db, *_ = workspace
    discover(workspace, content="Project Alpha stops writes on Sundays. Backups run daily.")

    def unmeasured(payload, result):
        if payload["task"] == "outline":
            result["sections"][0]["title"] = "Sunday write policies and performance"

    artifact = run(db, enqueue(db), model(transform=unmeasured)[0])
    revision = store.current(db, artifact)
    assert "Sunday write policies and performance" not in revision["content"]
    assert "## Source notes" in revision["content"]
    assert any(
        item["code"] == "unsupported_heading"
        for item in revision["metadata"]["coverage"]["presentation_limits"]
    )


@pytest.mark.parametrize(
    "title,originals",
    [
        ("Runtime performance", "The measured runtime was 12 milliseconds."),
        ("Performance", "The measured result was 12 ms."),
        ("성능", "실행 시간은 12ms였다."),
        ("Throughput", "Measured throughput was 37 requests per second."),
        ("Performance", "Trial Cedar finishes in 18 minutes."),
    ],
)
def test_performance_heading_guard_retains_measured_bilingual_topics(title, originals):
    assert presentation.has_performance_context(title, originals)


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
def test_comparison_requires_a_section_with_multiple_verified_sources(workspace, joint):
    db, *_ = workspace
    discover(workspace, "alpha.txt", "Reservoir Alpha stores 37 litres.")
    discover(workspace, "beta.txt", "Reservoir Beta stores 92 litres.")

    def combine(payload, result):
        if payload["task"] == "cross_source_synthesis":
            pytest.fail("Comparison notes must not be rewritten into new factual claims")
        if not joint and payload["task"] == "outline":
            result["sections"] = [
                {"id": "alpha", "title": "Alpha"},
                {"id": "beta", "title": "Beta"},
            ]
        if not joint and payload["task"] == "process_original_sections":
            for claim in result["claims"]:
                claim["section_id"] = "alpha" if "Alpha" in claim["text"] else "beta"

    artifact = run(
        db,
        enqueue(db, instruction="Compare the reservoir designs in English."),
        model(transform=combine)[0],
    )
    revision = store.current(db, artifact)
    coverage = revision["metadata"]["coverage"]
    assert "| Source | Recorded facts |" in revision["content"]
    assert "Reservoir Alpha stores 37 litres." in revision["content"]
    assert "Reservoir Beta stores 92 litres." in revision["content"]
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
        "Unsupported architecture\r\n===\r\nReservoir stores 37 litres.",
        "Unsupported architecture\r===\rReservoir stores 37 litres.",
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
