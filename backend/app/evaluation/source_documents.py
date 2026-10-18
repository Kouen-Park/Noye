"""Reproducible actual-source/local-model acceptance; preserves failed reports too.

Run with an isolated --workspace. This is synthetic content, real files, scanner,
ingestion, SourceCatalog/SourceSession, Wiki and durable document handlers. It is
not evidence of native picker or native PDF acceptance.
"""

import argparse
import hashlib
import json
import os
import platform
import time
import uuid
from contextlib import closing
from json import loads
from pathlib import Path
from unittest.mock import patch

import httpx
from qdrant_client import QdrantClient

from app.config import get_settings
from app.db import source_documents as store
from app.db import wiki as wiki_store
from app.db.database import connect, init_schema
from app.models.source_documents import GenerateRequest
from app.models.wiki import WikiScope
from app.services import ingestion, knowledge_jobs
from app.services.folder_scanner import FolderScanner
from app.services.folders import register_root, update_root
from app.services.source_catalog import SourceCatalog
from app.services.source_documents import jobs
from app.services.wiki import service, sources

MODEL_FIELDS = (
    "response",
    "done",
    "done_reason",
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)


class MeasuredClient:
    """Evaluation-only transport; exact responses never reach product logs."""

    def __init__(self, client=None, clock=time.monotonic):
        self.client = client or httpx.Client(timeout=300, follow_redirects=False, trust_env=False)
        self.clock, self.calls = clock, []

    def close(self):
        self.client.close()

    def post(self, url, *, json):
        endpoint = httpx.URL(url).path
        task = "model_preflight" if endpoint.endswith("/api/show") else "unknown"
        prompt = json.get("prompt")
        messages = json.get("messages")
        if prompt is None and isinstance(messages, list):
            prompt = next(
                (
                    m.get("content")
                    for m in reversed(messages)
                    if isinstance(m, dict) and m.get("role") == "user"
                ),
                None,
            )
        if prompt is not None:
            try:
                task = loads(prompt).get("task", "unknown")
            except (ValueError, TypeError, AttributeError):
                pass  # Measurement must not change the model request or validation.
        call = {
            "task": task,
            "endpoint": endpoint,
            "model": json.get("model"),
            "http_status": None,
            "raw_response": None,
            **dict.fromkeys(MODEL_FIELDS),
        }
        began = self.clock()
        try:
            response = self.client.post(url, json=json)
            call.update(http_status=response.status_code, raw_response=response.text)
            try:
                body = response.json()
            except ValueError:
                return response
            if isinstance(body, dict):
                call.update({key: body.get(key) for key in MODEL_FIELDS})
            return response
        except Exception as exc:
            call["error"] = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            call["wall_seconds"] = round(self.clock() - began, 6)
            self.calls.append(call)


def measured_document(connection, job, settings, client):
    # The existing worker still owns failure/cancellation/cache/artifact handling.
    # Only this CLI invocation injects its transport; the product function is restored.
    generate = jobs.pipeline.generate
    started = time.monotonic()
    with patch.object(
        jobs.pipeline,
        "generate",
        lambda context: generate(context, settings=settings, client=client),
    ):
        knowledge_jobs.KnowledgeWorker().run_one(connection, job["id"])
    final = knowledge_jobs.get(connection, job["id"])
    revision = store.current(connection, final["artifact_id"]) if final["artifact_id"] else None
    return {
        "seconds": round(time.monotonic() - started, 3),
        "job": final,
        "request": jobs.public_request(connection, job["subject_id"]),
        "model_calls": client.calls,
        "revision": revision,
        "revision_body_sha256": hashlib.sha256(revision["content"].encode("utf-8")).hexdigest()
        if revision
        else None,
    }


def measured_wiki(connection, scope, client):
    started = time.monotonic()
    report = {"state": "complete", "revisions": [], "error": None}
    for identifier in scope.source_ids:
        try:
            result = service.generate_source(
                connection,
                identifier,
                WikiScope(),
                sources.freeze(connection, WikiScope()),
                client=client,
            )
            revision = wiki_store.revision(connection, result["revision_id"])
            report["revisions"].append(
                {
                    "source_id": identifier,
                    **result,
                    "revision": revision,
                    "revision_body_sha256": hashlib.sha256(
                        revision["content"].encode("utf-8")
                    ).hexdigest(),
                }
            )
        except Exception as exc:  # noqa: BLE001 — preserve this failed evaluation, no retry
            report.update(
                state="failed",
                error={
                    "source_id": identifier,
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
            break
    return {**report, "seconds": round(time.monotonic() - started, 3), "model_calls": client.calls}


def save_report(target, report):
    """An explicit repeated attempt cannot replace its previous success or failure."""
    original = target
    while True:
        try:
            with target.open("x", encoding="utf-8") as output:
                output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            return target
        except FileExistsError:
            target = original.with_stem(f"{original.stem}-{uuid.uuid4()}")


def run(workspace, scenario, retry_job=None):
    workspace.mkdir(parents=True, exist_ok=True)
    app_root, originals = workspace / "app", workspace / "knowledge"
    os.environ["NOYE_DATA_DIR"] = str(app_root)
    os.environ["DATABASE_URL"] = f"sqlite:///{app_root / 'app.db'}"
    get_settings.cache_clear()
    settings = get_settings()
    originals.mkdir(exist_ok=True)
    corpus = {
        "Course/01-한국어.md": "# 저수지 Alpha\nAlpha 프로젝트의 저장 용량은 37리터입니다. "
        "Alpha는 SQLite를 사용하며 일요일에는 쓰기를 중지합니다. 백업은 하루에 한 번 실행됩니다.\n",
        "Course/02-English.txt": "Project Beta stores 92 litres. Beta uses append-only log files. "
        "Beta permits writes on Sundays. Backups run twice a day.\n",
        "Unrelated.txt": "The orchard grows apples and pears. Harvest is in autumn.\n",
    }
    if scenario == "partial":
        corpus["NoText/empty.txt"] = ""
    # Never turn this synthetic evaluation into accidental private-file processing.
    expected = {**corpus, "NoText/empty.txt": ""}
    for path in originals.rglob("*"):
        if path.is_symlink():
            raise ValueError("Evaluation originals must not contain symlinks.")
        if path.is_file():
            relative = path.relative_to(originals).as_posix()
            if relative.startswith("wiki/"):
                # Application-authored Wiki output is excluded by the real scanner.
                continue
            if relative not in expected or path.read_text() != expected[relative]:
                raise ValueError("Evaluation originals differ from the invented corpus.")
    for relative, text in corpus.items():
        path = originals / relative
        path.parent.mkdir(exist_ok=True)
        if path.exists() and path.read_text() != text:
            raise ValueError("Existing originals differ from the invented evaluation corpus.")
        if not path.exists():
            path.write_text(text)
    connection = connect()
    init_schema(connection)
    if any(
        Path(row[0]) != originals for row in connection.execute("SELECT path FROM source_roots")
    ):
        raise ValueError("Evaluation database contains another source root.")
    if connection.execute(
        "SELECT 1 FROM files WHERE id NOT IN (SELECT file_id FROM sources)"
    ).fetchone():
        raise ValueError("Evaluation database contains uploaded files outside the invented corpus.")
    root = register_root(connection, originals, "connected")
    update_root(connection, root, processing=True)
    clock = [0.0]
    scanner = FolderScanner(clock=lambda: clock[0])
    scanner.scan_root(connection, root)
    clock[0] = 3.0
    pending = scanner.scan_root(connection, root)
    with closing(QdrantClient(":memory:")) as qdrant:
        for identifier in pending:
            started = time.monotonic()
            result = ingestion.ingest_file(
                connection, identifier, qdrant_client=qdrant, reserved=True
            )
            print(
                json.dumps(
                    {
                        "ingestion": result.name,
                        "state": result.status.value,
                        "seconds": round(time.monotonic() - started, 3),
                    }
                ),
                flush=True,
            )
    catalog = SourceCatalog(connection)
    ids = {s["relative_path"]: s["source_id"] for s in catalog.list_sources()}
    course_scope = WikiScope(
        mode="chosen", source_ids=[ids[k] for k in corpus if k.startswith("Course/")]
    )
    environment = {
        "scenario": scenario,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "model": settings.ollama_model,
        "context_tokens": settings.generation_context_tokens,
        "output_tokens": settings.generation_output_tokens,
        "thinking": settings.ollama_thinking,
        "prompt_version": service.PROMPT_VERSION
        if scenario == "wiki"
        else jobs.pipeline.local.PROMPT_VERSION,
        "pipeline_sha256": hashlib.sha256(
            Path((service.pipeline if scenario == "wiki" else jobs.pipeline).__file__).read_bytes()
        ).hexdigest(),
        "original_hashes": {
            relative: hashlib.sha256((originals / relative).read_bytes()).hexdigest()
            for relative in corpus
        },
        "measurement": "Evaluation-only model responses; synthetic originals. "
        "Durations are Ollama nanoseconds; wall_seconds includes transport/preflight. "
        "Body hashes bind the exact saved revision, not a quality verdict.",
    }
    if scenario == "wiki":
        with closing(MeasuredClient()) as client:
            report = {**environment, **measured_wiki(connection, course_scope, client)}
        target = save_report(workspace / f"wiki-{uuid.uuid4()}.json", report)
        print(
            json.dumps(
                {
                    "state": report["state"],
                    "error": report["error"],
                    "seconds": report["seconds"],
                    "report": str(target),
                }
            ),
            flush=True,
        )
        connection.close()
        return target
    if scenario == "collection":
        instruction = (
            "선택한 모든 강의자료를 사용해 한국어 요약 노트를 작성해 줘. "
            "정확한 수치와 예외를 보존해."
        )
        scope, mode = course_scope, "collection"
    elif scenario == "report":
        instruction = (
            "Write an English report about reservoir storage designs. "
            "Discover relevant material and explain the conditions and backup schedules."
        )
        scope, mode = WikiScope(), "relevant"
    elif scenario == "comparison":
        instruction = (
            "Write an English design comparison of Project Alpha and Project Beta. "
            "Explain storage, Sunday writes and backups with source evidence."
        )
        scope, mode = course_scope, "relevant"
    elif scenario == "partial":
        instruction = (
            "Write an English project comparison using all selected material. "
            "Explain unreadable or missing material and preserve source conditions."
        )
        scope = WikiScope(
            mode="chosen",
            source_ids=[
                *course_scope.source_ids,
                ids["NoText/empty.txt"],
                "missing-synthetic-source",
            ],
        )
        mode = "collection"
    else:
        instruction = "Write an English report using the selected materials."
        scope, mode = WikiScope(mode="empty"), "relevant"
    if retry_job:
        previous = knowledge_jobs.get(connection, retry_job)
        if previous["kind"] != "source_document":
            raise ValueError("Only source-document evaluation jobs can be retried.")
        job = knowledge_jobs.resume(connection, retry_job)
        request_id = job["subject_id"]
        if job["manifest"] != previous["manifest"] or job["scope"] != previous["scope"]:
            raise ValueError("The retry changed its frozen source inventory or scope.")
    else:
        request_id = str(uuid.uuid4())
        job = jobs.enqueue(
            connection,
            GenerateRequest(
                request_id=request_id, instruction=instruction, scope=scope, inventory_mode=mode
            ),
        )
    jobs.register()
    print(
        json.dumps(
            {
                "scenario": scenario,
                "job_id": job["id"],
                "request_id": request_id,
                "retry_of": retry_job,
                "model": settings.ollama_model,
                "context_tokens": settings.generation_context_tokens,
                "output_tokens": settings.generation_output_tokens,
            }
        ),
        flush=True,
    )
    with closing(MeasuredClient()) as client:
        report = {
            **environment,
            "retry_of": retry_job,
            **measured_document(connection, job, settings, client),
        }
    final = report["job"]
    attempt = f"-retry-{job['attempt']}" if retry_job else ""
    target = save_report(workspace / f"{scenario}-{request_id}{attempt}.json", report)
    print(
        json.dumps(
            {
                "state": final["state"],
                "artifact_id": final["artifact_id"],
                "error": final["error"],
                "seconds": report["seconds"],
                "report": str(target),
            }
        ),
        flush=True,
    )
    connection.close()
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--retry-job", help="Explicitly retry an existing failed evaluation job.")
    parser.add_argument(
        "--scenario",
        choices=["wiki", "collection", "report", "comparison", "partial", "empty"],
        required=True,
    )
    args = parser.parse_args()
    if args.retry_job and args.scenario == "wiki":
        parser.error("--retry-job applies only to source-document scenarios")
    run(args.workspace.resolve(), args.scenario, args.retry_job)


if __name__ == "__main__":
    main()
