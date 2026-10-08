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
from pathlib import Path

from qdrant_client import QdrantClient

from app.config import get_settings
from app.db import source_documents as store
from app.db.database import connect, init_schema
from app.models.source_documents import GenerateRequest
from app.models.wiki import WikiScope
from app.services import ingestion, knowledge_jobs
from app.services.folder_scanner import FolderScanner
from app.services.folders import register_root, update_root
from app.services.source_catalog import SourceCatalog
from app.services.source_documents import jobs
from app.services.wiki import service, sources


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
    if scenario == "wiki":
        for identifier in course_scope.source_ids:
            print(
                json.dumps(
                    service.generate_source(
                        connection, identifier, WikiScope(), sources.freeze(connection, WikiScope())
                    )
                ),
                flush=True,
            )
        connection.close()
        return
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
    started = time.monotonic()
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
    knowledge_jobs.KnowledgeWorker().run_one(connection, job["id"])
    final = knowledge_jobs.get(connection, job["id"])
    report = {
        "scenario": scenario,
        "retry_of": retry_job,
        "seconds": round(time.monotonic() - started, 3),
        "job": final,
        "request": jobs.public_request(connection, request_id),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "model": settings.ollama_model,
        "context_tokens": settings.generation_context_tokens,
        "output_tokens": settings.generation_output_tokens,
        "thinking": settings.ollama_thinking,
        "original_hashes": {
            relative: hashlib.sha256((originals / relative).read_bytes()).hexdigest()
            for relative in corpus
        },
    }
    if final["artifact_id"]:
        report["revision"] = store.current(connection, final["artifact_id"])
    attempt = f"-retry-{job['attempt']}" if retry_job else ""
    target = workspace / f"{scenario}-{request_id}{attempt}.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2))
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
