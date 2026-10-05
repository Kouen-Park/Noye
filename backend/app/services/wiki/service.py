"""Source summaries, root-local concept/project pages and preserved authored analyses."""

import json
import time
import unicodedata
import uuid

from app.config import get_settings
from app.db import wiki as store
from app.services.wiki import pipeline, publication, relations, sources
from app.services.wiki.local import PROMPT_VERSION, WikiError, require_local


def known_categories(connection):
    known = {
        json.loads(p["metadata"]).get("primary_category", "Unclassified")
        for p in store.list_pages(connection)
        if p["metadata"]
    }
    for record in sources.catalog(connection).list_sources():
        parts = record["relative_path"].split("/")[:-1]
        known.update(parts)
        if record.get("manual_category"):
            known.add(record["manual_category"])
    return sorted(known)


def generate_source(
    connection,
    source_id,
    scope,
    manifest,
    *,
    client=None,
    checkpoint=lambda: None,
    progress=lambda completed, total, stage: None,
):
    settings = get_settings().model_copy(deep=True)
    require_local(settings)
    record = sources.allowed(connection, source_id, scope, manifest)
    reference = sources.source_ref(record)
    frozen = next((p for p in manifest if p["source_id"] == source_id), None)
    if frozen is None or frozen["version"] != reference.source_version:
        raise WikiError("The original changed after inventory capture. Queue a fresh job.")
    page = store.ensure_page(connection, "source", f"source:{source_id}", reference.name)
    publication.capture_disk_edit(connection, page["id"])
    expected = store.page(connection, page["id"])["current_revision"]
    key = store.digest(
        store.encode(
            {
                "source": source_id,
                "version": reference.source_version,
                "model": settings.ollama_model,
                "prompt": PROMPT_VERSION,
            }
        )
    )
    for old in store.revisions(connection, page["id"]):
        revision = store.revision(connection, old["id"])
        if revision["origin"] in ("generated", "proposal") and (
            revision["metadata"].get("generation_key") == key
        ):
            publication.materialize(connection, page["id"])
            refresh_topics(connection, source_id, scope, manifest, reference.root_id)
            return {"wiki_id": page["id"], "revision_id": revision["id"], "reused": True}
    started = time.monotonic()
    reference, passages = sources.read_all(
        connection, source_id, reference.source_version, scope, manifest, checkpoint
    )
    result, evidence = pipeline.summarize(
        passages,
        categories=known_categories(connection),
        settings=settings,
        client=client,
        checkpoint=checkpoint,
        progress=progress,
        manual_category=record.get("manual_category"),
    )
    links = relations.infer(
        connection, page["id"], result, evidence, scope, manifest, settings, client, checkpoint
    )
    checkpoint()
    from app.services.source_catalog import EvidenceReader

    # Revalidate actual authorized original bytes after inference, beyond registry identity.
    EvidenceReader(connection).read(
        source_id, reference.source_version, scope.model_dump(), manifest=manifest, limit=1
    )
    publication.capture_disk_edit(connection, page["id"])
    metadata = {
        **result,
        "source": reference.model_dump(),
        "scope": scope.model_dump(),
        "manifest": manifest,
        "output_root_id": reference.root_id,
        "model": settings.ollama_model,
        "prompt_version": PROMPT_VERSION,
        "generated_at": store.now(),
        "processing_seconds": time.monotonic() - started,
        "generation_key": key,
        "relation_candidate_limit": relations.MAX_CANDIDATES,
        "relation_comparisons_per_candidate": relations.MAX_COMPARISONS,
    }
    header = (
        f"<!-- Wiki ID: {page['id']}; model: {metadata['model']}; "
        f"prompt: {PROMPT_VERSION}; generated: {metadata['generated_at']}; "
        f"processing seconds: {metadata['processing_seconds']:.3f} -->\n\n"
    )
    revision = store.write_revision(
        connection,
        page["id"],
        title=reference.name,
        content=header + pipeline.render(reference.name, result, evidence),
        metadata=metadata,
        evidence=[p.model_dump() for p in evidence],
        expected=expected,
        relations=links,
    )
    publication.materialize(connection, page["id"])
    refresh_topics(connection, source_id, scope, manifest, reference.root_id)
    progress(result["batch_count"], result["batch_count"], "complete")
    return {
        "wiki_id": page["id"],
        "revision_id": revision["id"],
        "origin": revision["origin"],
        "classification": result["primary_category"],
        "tags": result["tags"],
        "reused": False,
    }


def normalized(title):
    return " ".join(unicodedata.normalize("NFKC", title).casefold().split())


def refresh_topics(connection, source_id, scope, manifest, root_id):
    memberships, affected = {}, set()
    for page in store.list_pages(connection, limit=1000):
        if not page["current_revision"]:
            continue
        revision = store.revision(connection, page["current_revision"])
        metadata = revision["metadata"]
        if page["kind"] in ("concept", "project") and any(
            p["source"]["source_id"] == source_id for p in revision["evidence"]
        ):
            affected.add(page["identity"])
        if (
            page["kind"] != "source"
            or metadata.get("output_root_id") != root_id
            or not (sources.eligible_page(connection, revision, scope, manifest))
        ):
            continue
        for section in metadata.get("sections", []):
            for topic in section["topics"]:
                identity = f"{topic['kind']}:{root_id or 'uploads'}:{normalized(topic['title'])}"
                memberships.setdefault(identity, (topic, {}))[1][page["id"]] = (page, revision)
                if metadata["source"]["source_id"] == source_id:
                    affected.add(identity)
    for identity in sorted(affected):
        membership = memberships.get(identity)
        if membership:
            topic, contributors = membership
            if len(contributors) < 2 and not store.find(connection, identity):
                continue
            page = store.ensure_page(connection, topic["kind"], identity, topic["title"])
        else:
            page, contributors = store.find(connection, identity), {}
            if page is None:
                continue
        publication.capture_if_accessible(connection, page["id"])
        page = store.page(connection, page["id"])
        evidence, references = {}, []
        parts = [
            f"# {page['title']}",
            "Interpretation across source summaries. Verify exact details in originals.",
        ]
        for contributor, revision in contributors.values():
            references.append({"wiki_id": contributor["id"], "revision_id": revision["id"]})
            parts.append(
                f"## {contributor['title']}\n\n"
                f"[Source Wiki](../sources/{contributor['id']}.md)\n\n"
                + "\n\n".join(s["summary"]["text"] for s in revision["metadata"]["sections"])
            )
            evidence.update({p["id"]: p for p in revision["evidence"]})
            for link in store.relations(connection, contributor["id"]):
                if link["origin_id"] == contributor["id"] and (
                    sources.eligible_page(
                        connection,
                        store.revision(connection, link["target_revision"]),
                        scope,
                        manifest,
                    )
                ):
                    parts.append(f"- {link['kind']}: {link['reason']}")
        if not contributors:
            parts.append(
                "No currently available sources. Previous evidence remains in revision history."
            )
        content = "\n\n".join(parts) + "\n"
        if (
            page["current_revision"]
            and store.revision(connection, page["current_revision"])["content"] == content
        ):
            continue
        store.write_revision(
            connection,
            page["id"],
            title=page["title"],
            content=content,
            metadata={
                "scope": scope.model_dump(),
                "manifest": manifest,
                "output_root_id": root_id,
                "contributors": references,
                "generated_at": store.now(),
                "prompt_version": PROMPT_VERSION,
            },
            evidence=list(evidence.values()),
            expected=page["current_revision"],
        )
        publication.materialize(connection, page["id"])


def edit(connection, identifier, patch):
    publication.capture_if_accessible(connection, identifier)
    page = store.page(connection, identifier)
    prior = store.revision(connection, page["current_revision"])
    links = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM wiki_relations WHERE revision_id=?", (prior["id"],)
        )
    ]
    store.write_revision(
        connection,
        identifier,
        title=patch.title,
        content=patch.content,
        metadata=prior["metadata"],
        evidence=prior["evidence"],
        expected=patch.expected_revision,
        origin="user",
        relations=links,
    )
    publication.materialize(connection, identifier)


def adopt(connection, identifier, revision_id, expected):
    publication.capture_if_accessible(connection, identifier)
    proposal = store.revision(connection, revision_id)
    if proposal["wiki_id"] != identifier or proposal["origin"] != "proposal":
        raise ValueError("Select a proposed revision of this Wiki page.")
    # Explicit user adoption creates a new authored revision; both inputs survive.
    links = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM wiki_relations WHERE revision_id=?", (revision_id,)
        )
    ]
    store.write_revision(
        connection,
        identifier,
        title=proposal["title"],
        content=proposal["content"],
        metadata=proposal["metadata"],
        evidence=proposal["evidence"],
        expected=expected,
        origin="user",
        relations=links,
    )
    publication.materialize(connection, identifier)


def save_analysis(connection, request):
    manifest = sources.freeze(connection, request.scope)
    evidence, contributors, roots = {}, [], set()
    for identifier in dict.fromkeys(request.wiki_ids):
        page = store.page(connection, identifier)
        revision = store.revision(connection, page["current_revision"])
        if not sources.eligible_page(connection, revision, request.scope, manifest):
            raise ValueError(
                "An analysis Wiki is unavailable or outside the selected material scope."
            )
        evidence.update({p["id"]: p for p in revision["evidence"]})
        contributors.append({"wiki_id": identifier, "revision_id": revision["id"]})
        roots.add(revision["metadata"].get("output_root_id"))
    page = store.ensure_page(connection, "analysis", f"analysis:{uuid.uuid4()}", request.title)
    store.write_revision(
        connection,
        page["id"],
        title=request.title,
        content=request.content,
        metadata={
            "contributors": contributors,
            "scope": request.scope.model_dump(),
            "manifest": manifest,
            "output_root_id": next(iter(roots)) if len(roots) == 1 else None,
        },
        evidence=list(evidence.values()),
        expected=None,
        origin="user",
    )
    publication.materialize(connection, page["id"])
    return page["id"]


def provenance(connection, evidence):
    from app.services.source_catalog import EvidenceReader, SourceError

    statuses, cache = [], {}
    for item in evidence:
        reference = item["source"]
        key = reference["source_id"], reference["source_version"]
        if key not in cache:
            try:
                record = sources.catalog(connection).get(reference["source_id"])
                status = record["availability"]
                if status == "available" and record["version"] != reference["source_version"]:
                    status = "superseded"
                elif status == "available":
                    try:
                        EvidenceReader(connection).read(
                            reference["source_id"],
                            reference["source_version"],
                            {"mode": "chosen", "source_ids": [reference["source_id"]]},
                            limit=1,
                        )
                    except SourceError as error:
                        status = "superseded" if error.code == "stale_version" else error.code
            except (SourceError, LookupError):
                status = "missing"
            cache[key] = status
        statuses.append({**item, "current_status": cache[key]})
    return statuses
