"""Fixed unseen controls through the production guards and evidence audit.

Labels and case names are evaluator-only. Invalid audits are separate from
semantic rejection, even when the resulting refusal matches a negative label.
"""
import hashlib
import json
import platform
import sqlite3
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from app.config import get_settings
from app.db import source_documents as store
from app.db.database import init_schema
from app.evaluation.source_documents import MeasuredClient
from app.services.source_documents import local, pipeline


class RecordedClient(MeasuredClient):
    def post(self, url, *, json):
        before = len(self.calls)
        try:
            return super().post(url, json=json)
        finally:
            if len(self.calls) > before:
                self.calls[-1]["request"] = json


case_file, target = map(Path, sys.argv[1:])
if target.exists():
    raise FileExistsError(target)
suite = json.loads(case_file.read_text())
settings = get_settings()
with closing(sqlite3.connect(":memory:")) as db, closing(RecordedClient()) as client:
    db.row_factory = sqlite3.Row
    init_schema(db)
    identifier = str(uuid.uuid4())
    db.execute(
        "INSERT INTO source_document_requests"
        "(id,request_json,manifest_json,created_at,updated_at) "
        "VALUES (?,'{}','[]','test','test')",
        (identifier,),
    )
    req = store.request(db, identifier)
    events = []
    context = SimpleNamespace(
        connection=db,
        checkpoint=lambda *args: None,
        report=lambda *args, **kw: events.append(
            {"stage": args[0], "state": args[1], **kw}
        ),
    )
    report = {
        "method": __doc__,
        "suite": suite,
        "case_file_sha256": hashlib.sha256(case_file.read_bytes()).hexdigest(),
        "prompt_version": local.PROMPT_VERSION,
        "model": settings.ollama_model,
        "context_tokens": settings.generation_context_tokens,
        "output_tokens": settings.generation_output_tokens,
        "thinking": settings.ollama_thinking,
        "platform": platform.platform(),
        "production_hashes": {
            Path(module.__file__).name: hashlib.sha256(
                Path(module.__file__).read_bytes()
            ).hexdigest()
            for module in (pipeline, local)
        },
        "rows": [],
        "model_calls": client.calls,
    }
    began = time.monotonic()
    try:
        for position, (label, expected, text, originals) in enumerate(suite["cases"]):
            one = time.monotonic()
            before = len(client.calls)
            stage, reason, actual = "semantic", None, None
            try:
                pipeline.check_numbers(context, req, text, originals)
            except local.DocumentError as exc:
                actual, reason, stage = False, str(exc), "mechanical"
            if actual is None:
                try:
                    actual = pipeline.verify(
                        context, req, f"control-{position}",
                        [{"text": text, "quotes": originals, "original_passages": originals}],
                        settings, client, strict=False,
                    )[0]
                except local.DocumentError as exc:
                    actual, reason, stage = False, str(exc), "invalid_audit_or_transport"
            row = {
                "id": label,
                "expected": expected,
                "supported": actual,
                "matches_rubric": actual == expected,
                "valid_semantic_decision": stage == "semantic",
                "decision_stage": stage,
                "reason": reason,
                "model_calls": len(client.calls) - before,
                "seconds": round(time.monotonic() - one, 3),
            }
            report["rows"].append(row)
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps(row), flush=True)
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        report["seconds"] = round(time.monotonic() - began, 3)
        report["events"] = events
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({
            "matches": sum(row["matches_rubric"] for row in report["rows"]),
            "count": len(report["rows"]),
            "valid_semantic": sum(row["valid_semantic_decision"] for row in report["rows"]),
            "seconds": report["seconds"],
            "error": report.get("error"),
        }), flush=True)
