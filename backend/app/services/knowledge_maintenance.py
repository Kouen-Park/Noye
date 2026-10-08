"""Application-controlled filing after Wiki work, with explicit per-stage results."""

from pathlib import PurePosixPath

from app.db import wiki as store
from app.models.wiki import WikiScope
from app.services import filing, knowledge_jobs
from app.services.folders import SourceError, relative_parts, root_record
from app.services.source_catalog import SourceCatalog, SourceSession
from app.services.wiki import jobs, service


def organize(context, source_id, wiki_id):
    catalog = SourceCatalog(context.connection)
    record = catalog.assert_allowed(source_id, context.scope, context.manifest)
    version = next(item["version"] for item in context.manifest if item["source_id"] == source_id)
    SourceSession(context.connection, context.scope, context.manifest).read(source_id, limit=1)
    if not record["root_id"]:
        return {"reason": "Uploads retain their existing workspace location."}
    root = root_record(context.connection, record["root_id"])
    prefix = root["organization_prefix"]
    if not prefix or not root["processing"]:
        return {"reason": "Automatic organization is disabled for this folder."}
    if record["manual_category"]:
        return {"reason": "The manually fixed category is preserved."}
    if not PurePosixPath(record["relative_path"]).is_relative_to(PurePosixPath(prefix)):
        return {"reason": "This original is outside the enabled organization area."}
    # Use only a generated/proposal revision at the frozen original version.
    revision = next(
        (
            store.revision(context.connection, item["id"])
            for item in store.revisions(context.connection, wiki_id)
            if item["origin"] in {"generated", "proposal"}
            and store.revision(context.connection, item["id"])["metadata"]
            .get("source", {})
            .get("source_version")
            == version
        ),
        None,
    )
    if revision is None:
        raise SourceError("stale_version", "No classification exists at the frozen source version.")
    category = revision["metadata"].get("primary_category", "Unclassified")
    if not isinstance(category, str) or len(category) > 200:
        raise SourceError("invalid_path", "The classification is not a valid category.")
    relative_parts(category)  # Reject traversal/absolute/control paths; never execute model paths.
    destination = (
        PurePosixPath(prefix) / category / PurePosixPath(record["relative_path"]).name
    ).as_posix()
    if destination == record["relative_path"]:
        return {"reason": "The original already occupies its proposed category."}
    context.checkpoint("filing")
    journal = filing.file_source(context.connection, source_id, destination, version)
    return {"journal_id": journal["id"], "destination": journal["new_path"]}


def handler(context, payload):
    source_id = payload["source_id"]
    context.checkpoint("classification_summary")
    try:
        wiki_id = jobs.handler(context, payload)  # B owns generation and authored revisions.
    except Exception as exc:
        context.report("classification_summary", "failed", {"error": str(exc)})
        raise
    page = store.page(context.connection, wiki_id)
    if page["current_revision"]:
        revision = store.revision(context.connection, page["current_revision"])
        with context.connection:
            store.reindex(
                context.connection,
                wiki_id,
                revision["id"],
                revision["title"],
                revision["content"],
                revision["metadata"],
            )
    context.report("classification_summary", "complete", {"wiki_id": wiki_id})
    context.checkpoint("filing")
    result = organize(context, source_id, wiki_id)
    context.report("filing", "skipped" if "reason" in result else "complete", result)
    context.checkpoint("relations_topics")
    record = SourceCatalog(context.connection).get(source_id)
    service.refresh_topics(
        context.connection,
        source_id,
        WikiScope.model_validate(context.scope),
        context.manifest,
        record["root_id"],
    )
    context.report("relations_topics", "complete")
    return wiki_id


def register():
    # Preserve observer/API kind and dedupe keys. The wrapper extends their real handler.
    knowledge_jobs.register("wiki", handler)
