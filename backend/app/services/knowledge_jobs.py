"""Durable local Wiki/document work with explicit retry and a bounded worker."""

import json
import sqlite3
import threading
import uuid
from urllib.parse import urlparse

from app.config import get_settings
from app.db.database import connect
from app.db.jobs import OPEN_STATES, now
from app.services.source_catalog import SourceCatalog, validate_scope
from app.services.workspace_access import WorkspaceBusy, request_access

_handlers = {}


def register(kind, handler):
    """Handler(context, payload) returns an artifact ID. Register at application import."""
    _handlers[kind] = handler


def get(connection, job_id):
    row = connection.execute("SELECT * FROM knowledge_jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise LookupError("This knowledge job no longer exists.")
    result = dict(row)
    for field in ("payload", "scope", "manifest"):
        result[field] = json.loads(result.pop(field + "_json"))
    return result


def enqueue(
    connection, *, kind, subject_id, payload, scope, manifest=None, dedupe_key=None, attempt=1
):
    validate_scope(scope)
    manifest = SourceCatalog(connection).freeze(scope) if manifest is None else manifest
    key = dedupe_key or f"{kind}:{subject_id}"
    identifier = str(uuid.uuid4())
    try:
        with connection:
            connection.execute(
                "INSERT INTO knowledge_jobs(id,kind,subject_id,dedupe_key,payload_json,scope_json,"
                "manifest_json,state,stage,attempt,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,'queued','queued',?,?,?)",
                (
                    identifier,
                    kind,
                    subject_id,
                    key,
                    json.dumps(payload),
                    json.dumps(scope),
                    json.dumps(manifest),
                    attempt,
                    now(),
                    now(),
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("This knowledge task already has active work.") from exc
    return get(connection, identifier)


def cancel(connection, job_id):
    job = get(connection, job_id)
    if job["state"] not in OPEN_STATES:
        raise ValueError("This task is no longer active.")
    with connection:
        connection.execute(
            "UPDATE knowledge_jobs SET cancel_requested=1,state=?,updated_at=? WHERE id=?",
            ("cancelled" if job["state"] == "queued" else "cancelling", now(), job_id),
        )
    return get(connection, job_id)


def resume(connection, job_id):
    job = get(connection, job_id)
    if job["state"] not in {"interrupted", "failed", "cancelled"}:
        raise ValueError("Only interrupted, failed or cancelled work can be retried.")
    return enqueue(
        connection,
        kind=job["kind"],
        subject_id=job["subject_id"],
        payload=job["payload"],
        scope=job["scope"],
        manifest=job["manifest"],
        dedupe_key=job["dedupe_key"],
        attempt=job["attempt"] + 1,
    )


def recover_interrupted(connection):
    with connection:
        connection.execute(
            "UPDATE knowledge_jobs SET state='interrupted',error=?,updated_at=? "
            "WHERE state IN ('queued','running','cancelling')",
            ("Noye stopped. Retry explicitly; no work was replayed.", now()),
        )


class WorkCancelled(RuntimeError):
    pass


class WorkContext:
    def __init__(self, connection, job, stop_event=None):
        self.connection, self.job = connection, job
        self.scope, self.manifest = job["scope"], job["manifest"]
        self.stop_event = stop_event

    def checkpoint(self, stage, completed=0, total=0):
        if get(self.connection, self.job["id"])["cancel_requested"] or (
            self.stop_event and self.stop_event.is_set()
        ):
            raise WorkCancelled("Knowledge processing was cancelled.")
        with self.connection:
            self.connection.execute(
                "UPDATE knowledge_jobs SET stage=?,completed=?,total=?,updated_at=? WHERE id=?",
                (stage, completed, total, now(), self.job["id"]),
            )


class KnowledgeWorker:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            target=self.run, args=(self.stop_event,), daemon=True, name="knowledge-jobs"
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def run_one(self, connection, job_id, stop_event=None):
        job = get(connection, job_id)
        if job["state"] != "queued":
            return
        with connection:
            connection.execute(
                "UPDATE knowledge_jobs SET state='running',updated_at=? WHERE id=?", (now(), job_id)
            )
        context = WorkContext(connection, job, stop_event or self.stop_event)
        try:
            context.checkpoint("starting")
            parsed = urlparse(get_settings().ollama_base_url)
            if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError(
                    "Knowledge jobs require local Ollama; no cloud fallback is available."
                )
            handler = _handlers.get(job["kind"])
            if handler is None:
                raise ValueError("This knowledge task handler is not installed.")
            artifact_id = handler(context, job["payload"])
            context.checkpoint("saving")
            with connection:
                connection.execute(
                    "UPDATE knowledge_jobs SET state=CASE WHEN cancel_requested=1 THEN 'cancelled' "
                    "ELSE 'complete' END,stage=CASE WHEN cancel_requested=1 THEN 'cancelled' "
                    "ELSE 'complete' END,artifact_id=COALESCE(?,artifact_id),"
                    "error=CASE WHEN cancel_requested=1 THEN 'Cancelled after saving artifact.' "
                    "ELSE NULL END,updated_at=? WHERE id=?",
                    (artifact_id, now(), job_id),
                )
        except WorkCancelled as exc:
            with connection:
                connection.execute(
                    "UPDATE knowledge_jobs SET state='cancelled',error=?,updated_at=? WHERE id=?",
                    (str(exc), now(), job_id),
                )
        except Exception as exc:  # noqa: BLE001 — persist failures instead of losing worker tasks
            with connection:
                connection.execute(
                    "UPDATE knowledge_jobs SET state='failed',error=?,updated_at=? WHERE id=?",
                    (str(exc), now(), job_id),
                )

    def run(self, stop_event):
        from app.logging_config import get_logger

        while not stop_event.is_set():
            try:
                with request_access():
                    connection = connect()
                    try:
                        row = connection.execute(
                            "SELECT id FROM knowledge_jobs WHERE state='queued' "
                            "ORDER BY rowid LIMIT 1"
                        ).fetchone()
                        if row:
                            self.run_one(connection, row["id"], stop_event)
                    finally:
                        connection.close()
            except WorkspaceBusy:
                pass
            except Exception:  # noqa: BLE001 — errors do not terminate the polling worker
                get_logger("knowledge_jobs").exception("Knowledge worker failed")
            stop_event.wait(0.5)


worker = KnowledgeWorker()
