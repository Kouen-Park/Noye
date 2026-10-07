"""Wiki-guided discovery with current original passages as the only answer evidence."""

import heapq
from dataclasses import dataclass

from app.db import wiki as wiki_store
from app.models.wiki import WikiScope
from app.services import generation, retrieval
from app.services.source_catalog import SourceCatalog, SourceError, SourceSession
from app.services.wiki import relations
from app.services.wiki.local import WikiError, require_local

STOP_WORDS = {
    "what",
    "which",
    "the",
    "are",
    "was",
    "does",
    "and",
    "for",
    "from",
    "this",
    "that",
    "how",
    "is",
    "in",
    "to",
    "of",
    "on",
    "with",
    "about",
    "it",
}
MAX_WIKI_PAGES = 12


@dataclass
class KnowledgeContext:
    sources: list
    snapshot: dict
    session: SourceSession


def _terms(query):
    return relations.terms(query) - STOP_WORDS


def _lexical(connection, identifiers, wanted, limit):
    """Stream the scoped extraction, including details omitted from Wiki summaries."""
    best = []
    for offset in range(0, len(identifiers), 200):
        selected = identifiers[offset : offset + 200]
        placeholders = ",".join("?" for _ in selected)
        for row in connection.execute(
            f"SELECT file_id,chunk_index,content,page_number FROM chunks "
            f"WHERE file_id IN ({placeholders})",
            selected,
        ):
            score = len(wanted & _terms(row["content"]))
            if not score:
                continue
            item = (score, row["file_id"], row["chunk_index"])
            heapq.heappush(best, item)
            if len(best) > limit:
                heapq.heappop(best)
    return sorted(best, reverse=True)


def discover(
    connection, query, scope=None, manifest=None, *, file_ids=None, limit=5, vector_search=None
):
    """Resolve scope/inventory before searching Wiki or following bounded links.

    Wiki text is returned as interpretation for display. It is never passed to
    the answer model as primary evidence. Every ranked candidate is reread through
    the version-aware original reader; vector payload text is not trusted.
    """
    if not query.strip() or not 1 <= limit <= 10:
        raise ValueError("Provide a question and a passage limit between 1 and 10.")
    session = SourceSession(connection, scope, manifest)
    permitted = {item["source_id"] for item in session.manifest}
    if file_ids is not None:
        permitted &= set(file_ids)
    descriptors = {
        item["source_id"]: item
        for item in SourceCatalog(connection).list_sources(scope)
        if item["source_id"] in permitted
        and item["processing_state"] == "READY"
        and item["availability"] == "available"
    }
    snapshot = {
        "version": 1,
        "route": "wiki_original",
        "scope": session.scope,
        "manifest": session.manifest,
        "wiki_pages": [],
        "warnings": [],
        "wiki_state": "no_matches",
        "insufficient_evidence": False,
        "traversal": {"depth": 1, "page_limit": MAX_WIKI_PAGES},
        "consumed_source_ids": [],
    }
    if not descriptors:
        snapshot["insufficient_evidence"] = True
        return KnowledgeContext([], snapshot, session)
    wiki_sources, seen = set(), set()
    wiki_scope = WikiScope.model_validate(session.scope)
    try:
        hits = relations.search(connection, query, wiki_scope, session.manifest, limit=4)
        for hit in hits:
            for identifier in relations.traverse(
                connection, hit["id"], wiki_scope, session.manifest, depth=1, limit=MAX_WIKI_PAGES
            ):
                if identifier in seen or len(seen) >= MAX_WIKI_PAGES:
                    continue
                page = wiki_store.page(connection, identifier)
                revision = wiki_store.revision(connection, page["current_revision"])
                contributor_ids = {item["source"]["source_id"] for item in revision["evidence"]}
                # Index-compatible inventory restrictions also apply to a whole topic page.
                if not contributor_ids <= set(descriptors):
                    continue
                seen.add(identifier)
                wiki_sources.update(contributor_ids)
                snapshot["wiki_pages"].append(
                    {
                        "wiki_id": identifier,
                        "revision_id": revision["id"],
                        "title": revision["title"],
                        "kind": page["kind"],
                        "origin": revision["origin"],
                        "interpretation": revision["content"],
                        "source_ids": sorted(contributor_ids),
                        "revision_status": "unchanged",
                        "contributors": revision["metadata"].get("contributors", []),
                    }
                )
        snapshot["wiki_state"] = "matched" if seen else "no_matches"
    except (WikiError, SourceError, ValueError, LookupError):
        snapshot["wiki_state"] = "unavailable"
        snapshot["warnings"].append("Wiki discovery failed; using verified original passages.")

    search = vector_search or retrieval.search
    ids = sorted(descriptors)
    ranked = {}
    try:
        vector = search(query, file_ids=ids, limit=limit * 3)
        if wiki_sources:
            vector += search(query, file_ids=sorted(wiki_sources), limit=limit * 2)
        for hit in vector:
            if hit.file_id in descriptors:
                ranked[(hit.file_id, hit.chunk_index)] = hit.score
    except (retrieval.EmbeddingError, retrieval.IndexingError):
        snapshot["warnings"].append("Semantic search unavailable; using original text matches.")
    wanted = _terms(query)
    for _, identifier, index in _lexical(connection, ids, wanted, limit * 3):
        ranked.setdefault((identifier, index), 0.0)
    candidates = []
    for (identifier, index), vector_score in ranked.items():
        try:
            (passage,) = session.read(identifier, chunk_indexes=[index], limit=1)
        except SourceError as exc:
            snapshot["warnings"].append(f"Source {identifier} excluded: {exc.code}.")
            continue
        overlap = len(wanted & _terms(passage["content"])) / max(1, len(wanted))
        priority = overlap + vector_score + (0.05 if identifier in wiki_sources else 0)
        candidates.append(
            (
                priority,
                retrieval.SearchResult(
                    content=passage["content"],
                    file_id=identifier,
                    page_number=passage["page_number"],
                    chunk_index=index,
                    score=vector_score,
                    source_hash=passage["version"],
                ),
            )
        )
    candidates.sort(key=lambda item: (-item[0], item[1].file_id, item[1].chunk_index))
    # Give a relevant connected source one place before filling remaining detail passages.
    selected, used = [], set()
    for _, passage in candidates:
        if passage.file_id not in used and len(selected) < limit:
            selected.append(passage)
            used.add(passage.file_id)
    for _, passage in candidates:
        if passage not in selected and len(selected) < limit:
            selected.append(passage)
    session.consumed = {item.file_id for item in selected}
    snapshot["consumed_source_ids"] = sorted(session.consumed)
    snapshot["insufficient_evidence"] = not bool(selected)
    snapshot["warnings"] = list(dict.fromkeys(snapshot["warnings"]))
    return KnowledgeContext(selected, snapshot, session)


def answer(context, question, *, history="", client=None):
    if not context.sources:
        return generation.Answer(generation.NO_CONTEXT_ANSWER, [])
    require_local(generation.get_settings())
    text = generation.generate(
        generation.build_prompt(question, context.sources, history=history),
        client=client,
        provider="ollama",
    )
    context.session.verify()
    return generation.Answer(text, context.sources)
