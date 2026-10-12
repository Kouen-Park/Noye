"""Compare production retrieval with Wiki-original questions using invented HELIOS sources.

Run after releasing other local model work:
python -m app.evaluation.knowledge --reference /path/retained-wiki-qa
    --workspace /path/new-qa --output /path/report.json
The reference must contain the exact invented corpus from app.evaluation.wiki.
Copies it through real backup/restore; never queries or modifies a user workspace.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import time
from contextlib import closing
from pathlib import Path

import httpx
from qdrant_client import QdrantClient

from app.config import get_settings
from app.db.database import connect, init_schema
from app.evaluation.wiki import CORPUS
from app.services import generation, ingestion, knowledge_query, retrieval
from app.services.folder_scanner import FolderScanner
from app.services.folders import register_root, update_root
from app.services.source_catalog import SourceCatalog
from app.services.workspace_backup import create_backup, restore_backup


def timed(call):
    start = time.monotonic()
    result = call()
    return result, round(time.monotonic() - start, 3)


def passages(items):
    return [
        {
            "source_id": item.file_id,
            "version": item.source_hash,
            "passage_index": item.chunk_index,
            "page_number": item.page_number,
            "score": item.score,
            "text": item.content,
        }
        for item in items
    ]


def run(reference, workspace, output):
    reference = reference.resolve(strict=True)
    if workspace.exists():
        raise ValueError("Use a new evaluation workspace.")
    # Reject unknown/private material before a database or model call.
    for relative, text in CORPUS.items():
        if (reference / "knowledge" / relative).read_text(encoding="utf-8") != text:
            raise ValueError("Reference originals do not match the invented HELIOS corpus.")
    workspace.mkdir(parents=True)
    archive = workspace / "reference.zip"
    backup = create_backup(reference / "app", reference / "app/app.db", archive)
    restored = restore_backup(archive, workspace / "app")
    knowledge = workspace / "knowledge"
    shutil.copytree(reference / "knowledge", knowledge)
    prior_env = {key: os.environ.get(key) for key in ("NOYE_DATA_DIR", "DATABASE_URL")}
    os.environ["NOYE_DATA_DIR"] = str(workspace / "app")
    os.environ["DATABASE_URL"] = f"sqlite:///{workspace / 'app/app.db'}"
    get_settings.cache_clear()
    report = {
        "status": "running",
        "corpus": CORPUS,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "backup_external_originals": backup["external_originals"],
        "restore": restored,
        "indexing": [],
        "questions": [],
        "failures": {},
    }

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        with closing(connect()) as db, closing(QdrantClient(":memory:")) as qdrant:
            init_schema(db)
            root = db.execute("SELECT id FROM source_roots").fetchall()
            if len(root) != 1:
                raise ValueError("Expected exactly one invented reference root.")
            root_id = register_root(db, knowledge, "connected", reconnect_id=root[0][0])
            update_root(db, root_id, processing=True)
            clock = [0.0]
            scanner = FolderScanner(clock=lambda: clock[0])
            scanner.scan_root(db, root_id)
            clock[0] = 3.0
            scanner.scan_root(db, root_id)
            sources = SourceCatalog(db).list_sources()
            if {source["relative_path"] for source in sources} != set(CORPUS):
                raise ValueError("Reference database contains an unknown source.")
            by_path = {source["relative_path"]: source["source_id"] for source in sources}
            for source in sources:
                record, seconds = timed(
                    lambda source=source: ingestion.ingest_file(
                        db,
                        source["source_id"],
                        qdrant_client=qdrant,
                        reserved=ingestion.is_ingesting(source["source_id"]),
                    )
                )
                report["indexing"].append(
                    {
                        "source_id": record.id,
                        "status": record.status.value,
                        "seconds": seconds,
                        "version": record.content_hash,
                    }
                )
                if record.status.value != "READY":
                    raise ValueError(record.error)
            settings = get_settings()
            report.update(
                model=settings.ollama_model,
                embedding_model=settings.ollama_embedding_model,
                context_tokens=settings.generation_context_tokens,
                output_tokens=settings.generation_output_tokens,
                thinking=settings.ollama_thinking,
                inventory=SourceCatalog(db).freeze(),
                passage_limit=5,
            )
            report["generation_model_info"] = (
                httpx.post(
                    settings.ollama_base_url + "/api/show",
                    json={"model": settings.ollama_model},
                    timeout=10,
                )
                .json()
                .get("details")
            )
            baseline_id = by_path["Learning/HELIOS-baseline.md"]
            korean_id = by_path["Learning/HELIOS-한국어.md"]
            cases = [
                (
                    "exact_exception",
                    "For HELIOS, what are the capacity and Sunday limit? "
                    "State exact units and exceptions.",
                    {"mode": "all"},
                    "37 litres; 29 litres on Sundays.",
                ),
                (
                    "cross_source",
                    "Compare HELIOS manual and electronic valve designs, "
                    "deployment status and measured price.",
                    {"mode": "all"},
                    "Manual baseline; electronic alternative not deployed; unknown price.",
                ),
                (
                    "chosen_baseline",
                    "What are the HELIOS capacity and Sunday restriction?",
                    {"mode": "chosen", "source_ids": [baseline_id]},
                    "37 litres; Sunday 29 litres; only baseline evidence.",
                ),
                (
                    "korean",
                    "HELIOS의 기본 용량과 일요일 제한, 가격은 얼마인가요? 한국어로 답하세요.",
                    {"mode": "chosen", "source_ids": [korean_id]},
                    "37리터; 일요일 29리터; 가격 미측정, 0원 아님.",
                ),
                (
                    "empty",
                    "What is the HELIOS capacity?",
                    {"mode": "empty"},
                    "No source evidence; no model call.",
                ),
            ]
            pending = []
            # Collect embedding/search measurements first, avoiding repeated model swaps.
            for label, question, scope, expected in cases:
                ids = [item["source_id"] for item in SourceCatalog(db).freeze(scope)]
                baseline, old_time = timed(
                    lambda question=question, ids=ids: retrieval.search(
                        question, file_ids=ids, client=qdrant
                    )
                )
                context, new_time = timed(
                    lambda question=question, scope=scope: knowledge_query.discover(
                        db,
                        question,
                        scope,
                        vector_search=lambda query, **kwargs: retrieval.search(
                            query, client=qdrant, **kwargs
                        ),
                    )
                )
                row = {
                    "id": label,
                    "question": question,
                    "scope": scope,
                    "expected": expected,
                    "baseline": {"passages": passages(baseline), "retrieval_seconds": old_time},
                    "wiki_original": {
                        "passages": passages(context.sources),
                        "retrieval_seconds": new_time,
                        "snapshot": context.snapshot,
                    },
                }
                report["questions"].append(row)
                pending.append((row, baseline, context))
                save()
            for row, baseline, context in pending:
                for route, items in (("baseline", baseline), ("wiki_original", context.sources)):
                    print(f"Answering {row['id']} / {route}", flush=True)
                    try:
                        text, seconds = timed(
                            lambda row=row, context=context, route=route, items=items: (
                                knowledge_query.answer(context, row["question"]).text
                                if route == "wiki_original"
                                else generation.generate(
                                    generation.build_prompt(row["question"], items),
                                    provider="ollama",
                                )
                                if items
                                else generation.NO_CONTEXT_ANSWER
                            )
                        )
                        row[route].update(
                            answer=text, generation_seconds=seconds, model_called=bool(items)
                        )
                    except Exception as exc:  # noqa: BLE001 — retain failed live measurements
                        row[route]["error"] = str(exc)
                    save()
            # Change and missing-source checks affect only this copied invented corpus.
            path = knowledge / "Learning/HELIOS-baseline.md"
            original = path.read_bytes()
            try:
                for name in ("changed", "missing"):
                    if name == "changed":
                        path.write_text("HELIOS capacity changed to 92 litres.", encoding="utf-8")
                    else:
                        path.unlink()
                    result = knowledge_query.discover(
                        db,
                        "HELIOS capacity",
                        {"mode": "chosen", "source_ids": [baseline_id]},
                        vector_search=lambda query, **kwargs: retrieval.search(
                            query, client=qdrant, **kwargs
                        ),
                    )
                    report["failures"][name] = {
                        "passage_count": len(result.sources),
                        "wiki_count": len(result.snapshot["wiki_pages"]),
                        "insufficient": result.snapshot["insufficient_evidence"],
                        "warnings": result.snapshot["warnings"],
                    }
                    if result.sources:
                        raise AssertionError("Stale/missing original was used as current evidence.")
            finally:
                path.write_bytes(original)
            report["original_hashes_after"] = {
                relative: hashlib.sha256((knowledge / relative).read_bytes()).hexdigest()
                for relative in CORPUS
            }
            report["status"] = "complete"
            save()
            print(
                json.dumps(
                    {
                        "status": report["status"],
                        "questions": len(report["questions"]),
                        "output": str(output),
                    }
                ),
                flush=True,
            )
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        save()
        raise
    finally:
        for key, value in prior_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.workspace, args.output)
