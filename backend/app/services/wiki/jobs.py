"""Use A's durable worker: Wiki failures/cancellation are independent from source indexing."""

from app.db import wiki as store
from app.models.wiki import WikiScope
from app.services.wiki import service, sources


def handler(context, payload):
    try:
        result = service.generate_source(
            context.connection,
            payload["source_id"],
            WikiScope.model_validate(context.scope),
            context.manifest,
            checkpoint=lambda: context.checkpoint("checking"),
            progress=lambda completed, total, stage: context.checkpoint(stage, completed, total),
        )
    finally:
        # A source revision may commit before topic refresh fails or is cancelled. Preserve
        # its link in the failed job too; only accept output matching the frozen source version.
        page = store.find(context.connection, f"source:{payload['source_id']}")
        frozen = next((s for s in context.manifest if s["source_id"] == payload["source_id"]), None)
        if page and frozen:
            for old in store.revisions(context.connection, page["id"]):
                revision = store.revision(context.connection, old["id"])
                source = revision["metadata"].get("source", {})
                if revision["origin"] in ("generated", "proposal") and (
                    source.get("source_version") == frozen["version"]
                ):
                    with context.connection:
                        context.connection.execute(
                            "UPDATE knowledge_jobs SET artifact_id=? WHERE id=?",
                            (page["id"], context.job["id"]),
                        )
                    break
    return result["wiki_id"]


def register():
    from app.services import knowledge_jobs

    knowledge_jobs.register("wiki", handler)


def enqueue(connection, source_id, scope):
    from app.services import knowledge_jobs

    manifest = sources.freeze(connection, scope)
    sources.allowed(connection, source_id, scope, manifest)
    return knowledge_jobs.enqueue(
        connection,
        kind="wiki",
        subject_id=source_id,
        payload={"source_id": source_id},
        scope=scope.model_dump(),
        manifest=manifest,
        dedupe_key=f"wiki:{source_id}",
    )


def source_changed(connection, event):
    """A calls this only after committing an event; ready schedules local summary maintenance."""
    if not event.get("source_id"):
        return
    root_id = event.get("root_id")
    scope = WikiScope(mode="chosen", root_ids=[root_id]) if root_id else WikiScope()
    if event["kind"] == "ready":
        return enqueue(connection, event["source_id"], scope)
    if event["kind"] in ("missing", "unavailable", "disconnected"):
        service.refresh_topics(
            connection, event["source_id"], scope, sources.freeze(connection, scope), root_id
        )
