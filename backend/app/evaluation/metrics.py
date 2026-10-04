"""Ranking metrics with explicit handling of unanswerable questions."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from statistics import mean


def ranking_metrics(ranking: Sequence[str], relevance: Mapping[str, int], k: int) -> dict:
    if k < 1:
        raise ValueError("k must be positive")
    if len(ranking) != len(set(ranking)):
        raise ValueError("Ranking contains duplicate passage IDs")
    retrieved = list(ranking[:k])
    relevant = {key for key, grade in relevance.items() if grade > 0}
    if not relevant:
        return {"recall": None, "precision": None, "mrr": None, "ndcg": None,
                "negative_returned_context": bool(retrieved)}
    hits = [key for key in retrieved if key in relevant]
    reciprocal = next((1 / rank for rank, key in enumerate(retrieved, 1) if key in relevant), 0)
    dcg = sum((2 ** relevance.get(key, 0) - 1) / math.log2(rank + 1)
              for rank, key in enumerate(retrieved, 1))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2 ** grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal, 1))
    return {"recall": len(hits) / len(relevant),
            "precision": len(hits) / k,
            "mrr": reciprocal, "ndcg": dcg / idcg if idcg else 0.0,
            "negative_returned_context": None}


def summarize(rows: Sequence[dict]) -> dict:
    def average(field):
        values = [row[field] for row in rows if row[field] is not None]
        return mean(values) if values else None
    return {"questions": len(rows), "answerable": sum(r["recall"] is not None for r in rows),
            "negatives": sum(r["recall"] is None for r in rows),
            **{field: average(field) for field in
               ("recall", "precision", "mrr", "ndcg", "negative_returned_context")}}


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], *, constant: int = 60) -> list[str]:
    if constant < 1:
        raise ValueError("Fusion constant must be positive")
    scores: dict[str, float] = {}
    for ranking in rankings:
        if len(ranking) != len(set(ranking)):
            raise ValueError("Ranking contains duplicate passage IDs")
        for rank, passage_id in enumerate(ranking, 1):
            scores[passage_id] = scores.get(passage_id, 0) + 1 / (constant + rank)
    return sorted(scores, key=lambda key: (-scores[key], key))


def diversify(ranking: Sequence[str], documents: Mapping[str, str]) -> list[str]:
    first, remaining, seen = [], [], set()
    for passage_id in ranking:
        document = documents[passage_id]
        if document in seen:
            remaining.append(passage_id)
        else:
            seen.add(document)
            first.append(passage_id)
    return first + remaining
