"""Reproducible live Wiki smoke check. Invented sources only; no user workspace access.

Run: python -m app.evaluation.wiki --output /path/to/report.json
Uses real extraction/embeddings/local generation, in-memory Qdrant and a new temporary folder.
"""

import argparse
import json
import os
import platform
import tempfile
import time
from contextlib import closing, nullcontext
from json import loads
from pathlib import Path

import httpx
from qdrant_client import QdrantClient

from app.config import get_settings
from app.db import wiki as store
from app.db.database import connect, init_schema
from app.models.wiki import WikiScope
from app.services import ingestion
from app.services.folder_scanner import FolderScanner
from app.services.folders import register_root
from app.services.wiki import service, sources
from app.services.wiki.local import PROMPT_VERSION

CORPUS = {
    "Learning/HELIOS-baseline.md": """# Project HELIOS reservoir
The HELIOS reservoir's capacity is 37 litres. On Sundays the permitted capacity
is 29 litres. These are measured operating limits, not a count of containers.
The baseline design uses a manual valve. No cost measurement is available.
""",
    "Learning/HELIOS-alternative.txt": """Project HELIOS reservoir alternative
This alternative retains the capacity of 37 litres and Sunday's limit of 29 litres.
It uses an electronic valve instead of the baseline manual valve.
This alternative has not been deployed. Its price is unknown.
""",
    "Learning/HELIOS-한국어.md": """# Project HELIOS reservoir 실험 기록
HELIOS 저수지의 기본 용량은 37리터이며 일요일에는 29리터로 제한한다.
기본 설계는 수동 밸브를 사용한다. 전자 밸브 대안은 아직 배포되지 않았다.
가격은 측정하지 않았으므로 0원으로 해석하면 안 된다.
""",
}


class MeasuredClient:
    def __init__(self):
        self.client = httpx.Client(timeout=300, follow_redirects=False)
        self.calls = []

    def close(self):
        self.client.close()

    def post(self, url, *, json):
        response = self.client.post(url, json=json)
        body = response.json()
        self.calls.append(
            {
                "task": loads(json["prompt"])["task"],
                "done_reason": body.get("done_reason"),
                "response": body.get("response"),
                **{
                    field: body.get(field)
                    for field in (
                        "total_duration",
                        "load_duration",
                        "prompt_eval_count",
                        "prompt_eval_duration",
                        "eval_count",
                        "eval_duration",
                    )
                },
            }
        )
        return response


def run(output, workspace=None, resume=False):
    previous = json.loads(output.read_text()) if resume else None
    if resume and workspace is None:
        raise ValueError("Resuming requires the retained synthetic workspace.")
    original_env = {key: os.environ.get(key) for key in ("NOYE_DATA_DIR", "DATABASE_URL")}
    try:
        manager = (
            tempfile.TemporaryDirectory(prefix="noye-wiki-evaluation-")
            if workspace is None
            else nullcontext(str(workspace))
        )
        with manager as temporary:
            root = Path(temporary)
            os.environ["NOYE_DATA_DIR"] = str(root / "app")
            os.environ["DATABASE_URL"] = f"sqlite:///{root / 'app/app.db'}"
            get_settings.cache_clear()
            knowledge = root / "knowledge"
            knowledge.mkdir(parents=True, exist_ok=True)
            for name, text in CORPUS.items():
                target = knowledge / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if resume:
                    if target.read_text(encoding="utf-8") != text:
                        raise ValueError("The retained synthetic corpus changed.")
                else:
                    target.write_text(text, encoding="utf-8")
            with (
                closing(connect()) as db,
                closing(QdrantClient(":memory:")) as qdrant,
                closing(MeasuredClient()) as client,
            ):
                init_schema(db)
                store.install(db)
                db.commit()
                if resume:
                    root_id = db.execute(
                        "SELECT id FROM source_roots WHERE path=?", (str(knowledge.resolve()),)
                    ).fetchone()[0]
                else:
                    root_id = register_root(db, knowledge, "connected")
                moment = [0.0]
                scanner = FolderScanner(clock=lambda: moment[0])
                scanner.scan_root(db, root_id)
                moment[0] = 3
                scanner.scan_root(db, root_id)
                identifiers = [
                    r["source_id"]
                    for r in sources.catalog(db).list_sources(
                        {"mode": "chosen", "root_ids": [root_id]}
                    )
                ]
                identifiers.sort(
                    key=lambda identifier: list(CORPUS).index(
                        sources.catalog(db).get(identifier)["relative_path"]
                    )
                )
                timings = previous["indexing"] if previous else []
                for identifier in identifiers:
                    if (
                        resume
                        and sources.catalog(db).get(identifier)["processing_state"] == "READY"
                    ):
                        continue
                    began = time.monotonic()
                    record = ingestion.ingest_file(
                        db, identifier, qdrant_client=qdrant, reserved=True
                    )
                    timings.append(
                        {
                            "source_id": identifier,
                            "indexing_seconds": time.monotonic() - began,
                            "indexing_status": record.status.value,
                        }
                    )
                scope = WikiScope(mode="chosen", root_ids=[root_id])
                manifest = sources.freeze(db, scope)
                outputs = previous["outputs"] if previous else []
                settings = get_settings()
                if previous and (
                    previous["prompt"] != PROMPT_VERSION
                    or previous["model"] != settings.ollama_model
                    or previous["context_tokens"] != settings.generation_context_tokens
                    or previous["output_tokens"] != settings.generation_output_tokens
                    or previous["thinking"] != settings.ollama_thinking
                ):
                    raise ValueError("Resume must retain the measured generation configuration.")
                client.calls = previous["model_calls"] if previous else []
                report = {
                    "model": settings.ollama_model,
                    "prompt": PROMPT_VERSION,
                    "platform": platform.platform(),
                    "machine": platform.machine(),
                    "context_tokens": settings.generation_context_tokens,
                    "output_tokens": settings.generation_output_tokens,
                    "thinking": settings.ollama_thinking,
                    "corpus": CORPUS,
                    "indexing": timings,
                    "outputs": outputs,
                    "model_calls": client.calls,
                    "status": "running",
                }

                def save_report():
                    report["pages"] = [
                        {"id": p["id"], "kind": p["kind"], "title": p["title"]}
                        for p in store.list_pages(db)
                    ]
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(
                        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                    )

                for identifier in identifiers:
                    prior = next((p for p in outputs if p["source_id"] == identifier), None)
                    if prior:
                        page = store.page(db, prior["wiki_id"])
                        revision = store.revision(db, page["current_revision"])
                        if revision["metadata"] != prior["metadata"] or (
                            sources.catalog(db).get(identifier)["version"]
                            != prior["metadata"]["source"]["source_version"]
                        ):
                            raise ValueError("A previously measured revision changed.")
                        continue
                    print(f"Generating {sources.catalog(db).get(identifier)['name']}", flush=True)
                    began = time.monotonic()
                    try:
                        result = service.generate_source(
                            db, identifier, scope, manifest, client=client
                        )
                    except Exception as exc:
                        report.update(
                            status="failed",
                            error=str(exc),
                            failed_elapsed_seconds=time.monotonic() - began,
                        )
                        save_report()
                        raise
                    revision = store.revision(db, result["revision_id"])
                    outputs.append(
                        {
                            "wiki_id": result["wiki_id"],
                            "source_id": identifier,
                            "elapsed_seconds": time.monotonic() - began,
                            "metadata": revision["metadata"],
                            "content": revision["content"],
                            "relations": store.relations(db, result["wiki_id"]),
                            "evidence": revision["evidence"],
                        }
                    )
                    save_report()
                report["status"] = "complete"
                save_report()
                print(
                    json.dumps(
                        {
                            "sources": len(outputs),
                            "pages": len(report["pages"]),
                            "relations": sum(len(p["relations"]) for p in outputs),
                            "generation_seconds": [round(p["elapsed_seconds"], 2) for p in outputs],
                            "output": str(output),
                        },
                        ensure_ascii=False,
                    )
                )
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, help="Keep a synthetic workspace for UI QA")
    parser.add_argument(
        "--resume", action="store_true", help="Continue the same retained corpus/configuration"
    )
    args = parser.parse_args()
    run(args.output, args.workspace, args.resume)
