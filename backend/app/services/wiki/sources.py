"""A's real source/evidence services are the only original-reading path."""

import hashlib

from app.models.wiki import Passage, SourceRef
from app.services.wiki.local import WikiError


def catalog(connection):
    from app.services.source_catalog import SourceCatalog

    return SourceCatalog(connection)


def source_ref(record):
    return SourceRef(
        source_id=record["source_id"],
        root_id=record.get("root_id"),
        relative_path=record["relative_path"],
        name=record["name"],
        source_hash=record.get("content_hash") or "unknown",
        source_version=record.get("version") or "unknown",
        availability=record["availability"],
        indexing_status=record["processing_state"],
    )


def freeze(connection, scope):
    return catalog(connection).freeze(scope.model_dump())


def allowed(connection, source_id, scope, manifest=None):
    return catalog(connection).assert_allowed(source_id, scope.model_dump(), manifest=manifest)


def read_all(connection, source_id, version, scope, manifest, checkpoint=lambda: None):
    from app.services.source_catalog import EvidenceReader

    reference = source_ref(allowed(connection, source_id, scope, manifest))
    if reference.source_version != version:
        raise WikiError("The original changed after this job was queued. Start a fresh Wiki job.")
    reader, offset, passages = EvidenceReader(connection), 0, []
    while True:
        checkpoint()
        batch = reader.read(
            source_id, version, scope.model_dump(), manifest=manifest, limit=100, offset=offset
        )
        for item in batch:
            index, text = item["chunk_index"], item["content"]
            identifier = hashlib.sha256(f"{source_id}:{version}:{index}".encode()).hexdigest()[:24]
            passages.append(
                Passage(
                    id=identifier,
                    source=reference,
                    page_number=item["page_number"],
                    passage_index=index,
                    start=0,
                    end=len(text),
                    text=text,
                )
            )
        offset += len(batch)
        if len(batch) < 100:
            break
    if not passages:
        raise WikiError("No extracted passages. Retry source indexing first.")
    return reference, passages


def in_scope(revision, scope):
    if scope.mode == "empty":
        return False
    if scope.mode == "all":
        return True
    return bool(revision["evidence"]) and all(
        p["source"]["source_id"] in scope.source_ids or p["source"]["root_id"] in scope.root_ids
        for p in revision["evidence"]
    )


def eligible_page(connection, revision, scope, manifest=None):
    if not revision["evidence"] or not in_scope(revision, scope):
        return False
    from app.services.source_catalog import EvidenceReader, SourceError

    try:
        for identifier in {p["source"]["source_id"] for p in revision["evidence"]}:
            record = allowed(connection, identifier, scope, manifest)
            if {
                p["source"]["source_version"]
                for p in revision["evidence"]
                if p["source"]["source_id"] == identifier
            } != {record["version"]}:
                return False
            EvidenceReader(connection).read(
                identifier, record["version"], scope.model_dump(), manifest=manifest, limit=1
            )
    except SourceError:
        return False
    return True
