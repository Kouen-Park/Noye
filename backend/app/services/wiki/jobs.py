"""Use A's durable worker: Wiki failures/cancellation are independent from source indexing."""

from app.models.wiki import WikiScope
from app.services.wiki import service, sources


def handler(context, payload):
    result = service.generate_source(
        context.connection,
        payload["source_id"],
        WikiScope.model_validate(context.scope),
        context.manifest,
        checkpoint=lambda: context.checkpoint("checking"),
        progress=lambda completed, total, stage: context.checkpoint(stage, completed, total),
    )
    # Output committed before terminal status; even a late cancellation keeps its artifact link.
    with context.connection:
        context.connection.execute(
            "UPDATE knowledge_jobs SET artifact_id=? WHERE id=?",
            (result["wiki_id"], context.job["id"]),
        )
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
