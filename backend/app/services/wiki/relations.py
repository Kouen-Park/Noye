"""Evidence-verified relations over bounded candidates; links cannot widen a frozen scope."""

import json
import re

from app.db import wiki as store
from app.models.wiki import RelationsOutput
from app.services.wiki import sources
from app.services.wiki.local import WikiError, structured

MAX_CANDIDATES, MAX_RELATIONS, MAX_COMPARISONS = 8, 6, 4
MAX_DEPTH, MAX_NODES = 2, 20


def claims(metadata):
    return [
        claim
        for section in metadata.get("sections", [])
        for claim in [section["summary"], *section["key_points"]]
    ]


def topics(metadata):
    return {t["title"].casefold() for s in metadata.get("sections", []) for t in s["topics"]}


def candidates(connection, identifier, result, scope, manifest):
    tags, topic_names = {t.casefold() for t in result["tags"]}, topics(result)
    ranked = []
    for page in store.list_pages(connection, limit=1000):
        if page["id"] == identifier or not page["current_revision"]:
            continue
        revision = store.revision(connection, page["current_revision"])
        if not sources.eligible_page(connection, revision, scope, manifest):
            continue
        metadata = revision["metadata"]
        overlap = len(tags & {t.casefold() for t in metadata.get("tags", [])})
        shared_topics = len(topic_names & topics(metadata))
        if overlap >= 2 or shared_topics:
            ranked.append((overlap + shared_topics * 3, page, revision))
    return sorted(ranked, key=lambda row: (-row[0], row[1]["id"]))[:MAX_CANDIDATES]


def infer(
    connection,
    identifier,
    result,
    evidence,
    scope,
    manifest,
    settings,
    client=None,
    checkpoint=lambda: None,
):
    verified = []
    origin_ids = {p.id for p in evidence}
    for _, page, revision in candidates(connection, identifier, result, scope, manifest):
        if len(verified) >= MAX_RELATIONS:
            break
        target_ids = {p["id"] for p in revision["evidence"]}
        comparisons, accepted = 0, None
        for origin in claims(result):
            for target in claims(revision["metadata"]):
                if comparisons >= MAX_COMPARISONS:
                    break
                checkpoint()
                comparisons += 1
                prompt = json.dumps(
                    {
                        "task": "verify_relation",
                        "origin_id": identifier,
                        "target_id": page["id"],
                        "origin": origin,
                        "target": target,
                    },
                    ensure_ascii=False,
                )
                response = structured(
                    prompt,
                    RelationsOutput,
                    settings=settings,
                    client=client,
                    constraints={
                        "target_id": [page["id"]],
                        "origin_evidence_id": [origin["evidence_id"]],
                        "target_evidence_id": [target["evidence_id"]],
                    },
                )
                for proposed in response.relations:
                    if (
                        proposed.target_id != page["id"]
                        or proposed.origin_evidence_id not in origin_ids
                        or proposed.target_evidence_id not in target_ids
                        or proposed.origin_evidence_id != origin["evidence_id"]
                        or proposed.target_evidence_id != target["evidence_id"]
                    ):
                        raise WikiError(
                            "The model returned an unverified relation target/evidence ID."
                        )
                    if proposed.confidence >= 0.8:
                        accepted = {**proposed.model_dump(), "target_revision": revision["id"]}
                        break
                if accepted:
                    break
            if accepted or comparisons >= MAX_COMPARISONS:
                break
        if accepted:
            verified.append(accepted)
    return verified


def terms(text):
    return set(re.findall(r"[\w가-힣]{2,}", text.casefold()))


def search(connection, query, scope, manifest, limit=20):
    hits, wanted = [], terms(query)
    for page in store.list_pages(connection, limit=1000):
        if not page["current_revision"]:
            continue
        revision = store.revision(connection, page["current_revision"])
        if not sources.eligible_page(connection, revision, scope, manifest):
            continue
        row = connection.execute(
            "SELECT text,fingerprint FROM wiki_index WHERE wiki_id=?", (page["id"],)
        ).fetchone()
        score = len(wanted & terms(row["text"])) if row else 0
        if score:
            hits.append(
                {
                    "id": page["id"],
                    "title": page["title"],
                    "score": score,
                    "index_identity": row["fingerprint"],
                }
            )
    return sorted(hits, key=lambda hit: (-hit["score"], hit["id"]))[:limit]


def traverse(connection, identifier, scope, manifest, depth=1, limit=20):
    if not 0 <= depth <= MAX_DEPTH or not 1 <= limit <= MAX_NODES:
        raise ValueError("Wiki traversal permits at most 2 levels and 20 pages.")
    found, frontier = set(), [identifier]
    for _ in range(depth + 1):
        following = []
        for current in frontier:
            if current in found or len(found) >= limit:
                continue
            page = store.page(connection, current)
            if not page["current_revision"] or not sources.eligible_page(
                connection, store.revision(connection, page["current_revision"]), scope, manifest
            ):
                continue
            found.add(current)
            for relation in store.relations(connection, current):
                # Frozen target revision is honest history; stale edges do not drive discovery.
                if (
                    store.page(connection, relation["target_id"])["current_revision"]
                    != (relation["target_revision"])
                ):
                    continue
                following.append(
                    relation["target_id"]
                    if relation["origin_id"] == current
                    else relation["origin_id"]
                )
        frontier = following
    return sorted(found)
