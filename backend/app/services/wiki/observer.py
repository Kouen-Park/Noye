"""Consume A's committed change events. Retries of failed generation remain explicit."""

import threading

from app.db.database import connect
from app.models.wiki import WikiScope
from app.services.wiki import jobs, service, sources
from app.services.workspace_access import WorkspaceBusy, request_access


def reconcile(connection):
    from app.services import knowledge_jobs
    from app.services.source_catalog import SourceError

    row = connection.execute("SELECT sequence FROM wiki_consumers WHERE name='sources'").fetchone()
    cursor = row[0] if row else 0
    for event in sources.catalog(connection).changes(cursor):
        if event["kind"] == "ready" and event.get("source_id"):
            record = sources.catalog(connection).get(event["source_id"])
            # Automatic maintenance belongs to enabled folders. Upload summaries remain explicit.
            if (
                record["root_id"]
                and record["availability"] == "available"
                and (record["processing_state"] == "READY")
            ):
                try:
                    jobs.source_changed(connection, event)
                except SourceError:
                    pass  # Root paused/disconnected since event commit; a later ready can retry.
                except ValueError:
                    active = connection.execute(
                        "SELECT id FROM knowledge_jobs WHERE dedupe_key=? "
                        "AND state IN ('queued','running','cancelling')",
                        (f"wiki:{event['source_id']}",),
                    ).fetchone()
                    if active:
                        current = knowledge_jobs.get(connection, active["id"])
                        frozen = next(
                            (
                                p["version"]
                                for p in current["manifest"]
                                if p["source_id"] == event["source_id"]
                            ),
                            None,
                        )
                        if frozen != record["version"]:
                            knowledge_jobs.cancel(connection, active["id"])
                            return  # Revisit this event after the stale attempt settles.
                    else:
                        raise
        elif event["kind"] in ("missing", "unavailable", "disconnected"):
            root_id = event.get("root_id")
            if root_id:
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
