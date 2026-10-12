"""Consume A's committed change events. Retries of failed generation remain explicit."""

import threading

from app.db.database import connect
from app.models.wiki import WikiScope
from app.services.wiki import jobs, service, sources
from app.services.workspace_access import WorkspaceBusy, request_access


def ready(connection, event):
    from app.services import knowledge_jobs
    from app.services.folders import root_record
    from app.services.source_catalog import SourceError

    try:
        record = sources.catalog(connection).get(event["source_id"])
    except SourceError:
        return True  # A deleted source cannot block later committed folder events.
    if (
        not record["root_id"]
        or record["availability"] != "available"
        or (record["processing_state"] != "READY")
    ):
        return True
    root = root_record(connection, record["root_id"])
    if not root["connected"] or not root["processing"]:
        return True
    try:
        jobs.source_changed(connection, event)
    except SourceError:
        pass  # Disabled roots await a later committed ready/resumed event.
    except ValueError:
        active = connection.execute(
            "SELECT id FROM knowledge_jobs WHERE dedupe_key=? "
            "AND state IN ('queued','running','cancelling')",
            (f"wiki:{event['source_id']}",),
        ).fetchone()
        if not active:
            raise
        current = knowledge_jobs.get(connection, active["id"])
        frozen = next(
            (p["version"] for p in current["manifest"] if p["source_id"] == event["source_id"]),
            None,
        )
        if current["state"] == "cancelling" or current["cancel_requested"]:
            return False  # Same-version cancellation is not successful deduplication.
        if frozen != record["version"]:
            knowledge_jobs.cancel(connection, active["id"])
            return False
    return True


def cancel_root(connection, root_id):
    from app.services import knowledge_jobs

    for row in connection.execute(
        "SELECT j.id FROM knowledge_jobs j JOIN sources s ON s.file_id=j.subject_id "
        "WHERE j.kind='wiki' AND s.root_id=? "
        "AND j.state IN ('queued','running')",
        (root_id,),
    ).fetchall():
        knowledge_jobs.cancel(connection, row["id"])


def reconcile(connection):
    row = connection.execute("SELECT sequence FROM wiki_consumers WHERE name='sources'").fetchone()
    cursor = row[0] if row else 0
    for event in sources.catalog(connection).changes(cursor):
        if event["kind"] == "ready" and event.get("source_id"):
            if not ready(connection, event):
                return
        elif event["kind"] == "resumed" and event.get("root_id"):
            root_id = event["root_id"]
            scope = WikiScope(mode="chosen", root_ids=[root_id])
            for record in sources.catalog(connection).list_sources(scope.model_dump()):
                name = f"resumed:{root_id}:{record['source_id']}"
                previous = connection.execute(
                    "SELECT sequence FROM wiki_consumers WHERE name=?", (name,)
                ).fetchone()
                if previous and previous[0] == event["sequence"]:
                    continue
                if not ready(
                    connection, {**event, "kind": "ready", "source_id": record["source_id"]}
                ):
                    return
                # Keep per-subject progress if another cancelling task blocks this root event.
                with connection:
                    connection.execute(
                        "INSERT OR REPLACE INTO wiki_consumers VALUES (?,?)",
                        (name, event["sequence"]),
                    )
        elif event["kind"] == "paused" and event.get("root_id"):
            cancel_root(connection, event["root_id"])
        elif event["kind"] in ("missing", "unavailable", "disconnected"):
            root_id = event.get("root_id")
            if root_id:
                if not event.get("source_id"):
                    cancel_root(connection, root_id)
                scope = WikiScope(mode="chosen", root_ids=[root_id])
                affected = (
                    [event["source_id"]]
                    if event.get("source_id")
                    else [
                        r[0]
                        for r in connection.execute(
                            "SELECT file_id FROM sources WHERE root_id=?", (root_id,)
                        )
                    ]
                )
                for identifier in affected:
                    service.refresh_topics(
                        connection, identifier, scope, sources.freeze(connection, scope), root_id
                    )
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO wiki_consumers VALUES ('sources',?)", (event["sequence"],)
            )


class WikiObserver:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            target=self.run, args=(self.stop_event,), name="wiki-events", daemon=True
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def run(self, stop_event):
        from app.logging_config import get_logger

        while not stop_event.is_set():
            try:
                with request_access():
                    connection = connect()
                    try:
                        reconcile(connection)
                    finally:
                        connection.close()
            except WorkspaceBusy:
                pass
            except Exception:  # noqa: BLE001 — keep event failures visible and cursor retryable
                get_logger("wiki_events").exception("Wiki event reconciliation failed")
            stop_event.wait(2)


observer = WikiObserver()
