"""Immutable, versioned copies of the retrieved context, independent of files."""

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EvidenceExcerpt:
    content: str
    chunk_index: int
    retrieval_rank: int
    score: float
    source_hash: str | None = None
    index_fingerprint: str | None = None
    index_metadata: str | None = None


@dataclass(frozen=True)
class EvidenceSnapshot:
    captured_at: str
    excerpts: tuple[EvidenceExcerpt, ...]
    version: int = 1


def encode_evidence(evidence: EvidenceSnapshot | None) -> str | None:
    return json.dumps(asdict(evidence), ensure_ascii=False) if evidence is not None else None


def decode_evidence(raw: str | None) -> EvidenceSnapshot | None:
    if raw is None:
        return None
    body = json.loads(raw)
    if body["version"] != 1:
        raise ValueError("Unsupported evidence snapshot version")
    return EvidenceSnapshot(
        captured_at=body["captured_at"],
        excerpts=tuple(EvidenceExcerpt(**item) for item in body["excerpts"]),
    )
