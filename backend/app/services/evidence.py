"""Capture returned passages, never reconstruct them from today's index."""

from collections.abc import Sequence
from datetime import UTC, datetime

from app.models.conversations import MessageCitation
from app.models.evidence import EvidenceExcerpt, EvidenceSnapshot
from app.services.citations import build_citations
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
