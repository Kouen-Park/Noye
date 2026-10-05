"""Capture returned passages, never reconstruct them from today's index."""

import re
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

from app.db import files as file_store
from app.models.conversations import MessageCitation
from app.models.evidence import EvidenceExcerpt, EvidenceSnapshot
from app.services.citations import build_citations
from app.services.integrity import hash_file
from app.services.retrieval import SearchResult


def capture_citations(
    results: Sequence[SearchResult], file_names: dict[str, str]
) -> list[MessageCitation]:
    captured_at = datetime.now(UTC).isoformat()
    ranked = list(enumerate(results, start=1))
    return [
        MessageCitation(
            file_id=citation.file_id,
            file_name=citation.file_name or citation.file_id,
            page_number=citation.page_number,
            chunk_indexes=citation.chunk_indexes,
            best_score=citation.best_score,
            evidence=EvidenceSnapshot(
                captured_at=captured_at,
                excerpts=tuple(
                    EvidenceExcerpt(
                        content=result.content, chunk_index=result.chunk_index,
                        retrieval_rank=rank, score=result.score,
                        source_hash=result.source_hash,
                        index_fingerprint=result.index_fingerprint,
                        index_metadata=result.index_metadata,
                    )
                    for rank, result in ranked
                    if (result.file_id, result.page_number)
                    == (citation.file_id, citation.page_number)
                ),
            ),
        )
        for citation in build_citations(results, file_names=file_names)
    ]


def original_status(db: sqlite3.Connection, citation: MessageCitation) -> str:
    try:
        record = file_store.get_file(db, citation.file_id)
    except file_store.FileRecordNotFound:
        return "missing"
    digest = hash_file(record.path)
    if digest is None:
        return "missing"
    excerpts = citation.evidence.excerpts if citation.evidence else ()
    hashes = [excerpt.source_hash for excerpt in excerpts]
    if any(value and value != digest for value in hashes):
        return "changed"
    if not hashes or any(value is None for value in hashes):
        return "unknown"
    return "unchanged"


def provenance_markdown(citations: list[MessageCitation]) -> str:
    if not citations:
        return ""
    parts = ["## Provenance", "Evidence saved with the first draft, from passages "
             "consulted for its source answer. "
             "These do not validate later edits or every generated claim."]
    for citation in citations:
        # Escape source labels and render excerpts literally, including Markdown/HTML.
        label = re.sub(r"([\\`*_{}\[\]()<>#!|])", r"\\\1", " ".join(citation.label.split()))
        parts.append(f"> {label}\n> Chunks: {', '.join(map(str, citation.chunk_indexes))}")
        if citation.evidence and citation.evidence.excerpts:
            parts.append(f"> Evidence captured: {citation.evidence.captured_at}")
            for excerpt in citation.evidence.excerpts:
                parts.append(f"> Chunk: {excerpt.chunk_index}"
                             f"\n> Source SHA-256: {excerpt.source_hash or 'unknown'}"
                             f"\n> Index fingerprint: {excerpt.index_fingerprint or 'unknown'}")
                runs = re.findall(r"`+", excerpt.content)
                fence = "`" * max(3, 1 + max(map(len, runs), default=0))
                parts.append(f"{fence}text\n{excerpt.content}\n{fence}")
        else:
            parts.append("> No excerpt snapshot was stored for this reference.")
    return "\n\n".join(parts)
