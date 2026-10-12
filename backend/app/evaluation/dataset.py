"""Validate gold labels before an evaluation can produce misleading metrics."""

from __future__ import annotations

import json
from pathlib import Path


def load_dataset(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not data.get("passages") or not data.get("questions"):
        raise ValueError("Expected a version 1 dataset with passages and questions")
    passages = data["passages"]
    ids = [passage["id"] for passage in passages]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate passage ID")
    for passage in passages:
        if not passage["text"].strip() or not passage["document_id"].strip():
            raise ValueError("Passages need text and document IDs")
    questions = data["questions"]
    query_ids = [question["id"] for question in questions]
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("Duplicate question ID")
    for question in questions:
        if not question["text"].strip() or not question["categories"]:
            raise ValueError("Questions need text and categories")
        gold = question["relevance"]
        if set(gold) - set(ids):
            raise ValueError("Gold label references an unknown passage")
        if any(type(grade) is not int or grade not in (1, 2) for grade in gold.values()):
            raise ValueError("Relevance grades must be 1 or 2")
        if question["unanswerable"] != (not gold):
            raise ValueError("Unanswerable questions must have no relevant passages")
        if not question.get("expected_answer"):
            raise ValueError("Questions need a manual answer-review rubric")
    return data
