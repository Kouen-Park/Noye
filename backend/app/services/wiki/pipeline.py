"""Whole-source bounded section processing with verified excerpt IDs and character spans."""

import json
import re
from collections import Counter

from app.models.wiki import Passage, SectionSummary
from app.services.wiki.local import WikiError, input_budget, request_size, structured


def fragments(passages, max_bytes):
    for passage in passages:
        start = 0
        while start < len(passage.text):
            end, size = start, 0
            while end < len(passage.text):
                width = len(passage.text[end].encode("utf-8"))
                if size + width > max_bytes:
                    break
                size += width
                end += 1
            if end == start:
                raise WikiError("The input budget is too small for a Wiki passage.")
            cut = passage.text.rfind("\n", start + (end - start) // 2, end)
            if end < len(passage.text) and cut >= start:
                end = cut + 1
            yield Passage(
                **{
                    **passage.model_dump(),
                    "id": f"{passage.id}:{start}:{end}",
                    "start": passage.start + start,
                    "end": passage.start + end,
                    "text": passage.text[start:end],
                }
            )
            start = end


def prompt_for(batch, categories):
    return json.dumps(
        {
            "task": "summarize_section",
            "existing_categories": categories,
            "passages": [{"evidence_id": p.id, "text": p.text} for p in batch],
        },
        ensure_ascii=False,
    )


def make_batches(passages, categories, settings):
    budget = input_budget(settings)
    available = min(6000, budget - request_size(prompt_for([], categories), SectionSummary) - 400)
    if available < 128:
        raise WikiError("Increase the local context budget to generate Wiki summaries.")
    batch = []
    for fragment in fragments(passages, max_bytes=max(64, available // 2)):
        candidate = [*batch, fragment]
        if batch and request_size(prompt_for(candidate, categories), SectionSummary) > budget - 400:
            yield batch
            batch = [fragment]
        else:
            batch = candidate
    if batch:
        yield batch


def verify_claim(claim, evidence):
    passage = evidence.get(claim.evidence_id)
    if passage is None or claim.quote not in passage.text:
        raise WikiError("The model returned an unknown passage or non-verbatim quote.")


def classify(sections, categories, manual_category=None):
    if manual_category:
        return manual_category
    votes = Counter(s.primary_category.strip() for s in sections if s.category_confidence >= 0.75)
    if not votes:
        return "Unclassified"
    winner, count = sorted(votes.items(), key=lambda v: (-v[1], v[0] not in categories, v[0]))[0]
    if count * 2 <= len(sections) or not re.fullmatch(r"[^/\\\x00-\x1f]{1,100}", winner):
        return "Unclassified"
    return winner


def summarize(
    passages,
    *,
    categories,
    settings,
    client=None,
    checkpoint=lambda: None,
    progress=lambda completed, total, stage: None,
    manual_category=None,
):
    batches = list(make_batches(passages, categories, settings))
    sections, consumed = [], []
    for position, batch in enumerate(batches):
        checkpoint()
        result = structured(
            prompt_for(batch, categories), SectionSummary, settings=settings, client=client
        )
        for claim in [result.summary, *result.key_points]:
            verify_claim(claim, {p.id: p for p in batch})
        sections.append(result)
        consumed.extend(batch)
        progress(position + 1, len(batches), "summarizing")
        checkpoint()
    return {
        "sections": [s.model_dump() for s in sections],
        "primary_category": classify(sections, categories, manual_category),
        "classification_is_proposal": True,
        "tags": sorted({t.strip() for s in sections for t in s.tags if 0 < len(t.strip()) <= 80})[
            :20
        ],
        "batch_count": len(batches),
        "passage_count": len(passages),
        "fragment_count": len(consumed),
    }, consumed


def render(title, result, evidence):
    positions = {p.id: n for n, p in enumerate(evidence, 1)}
    parts = [
        f"# {title}",
        "Wiki interpretation. Verify exact facts, numbers and exceptions "
        "against original passages.",
        f"Primary category (suggestion): {result['primary_category']}",
        "Tags: " + ", ".join(result["tags"]),
        "## Summary",
    ]
    for section in result["sections"]:
        summary = section["summary"]
        parts.append(f"{summary['text']} [E{positions[summary['evidence_id']]}]")
        parts.extend(
            f"- {p['text']} [E{positions[p['evidence_id']]}]" for p in section["key_points"]
        )
        if section["uncertainties"]:
            parts.append(
                "### Uncertainties\n" + "\n".join(f"- {u}" for u in section["uncertainties"])
            )
    parts.append("## Original evidence")
    for n, p in enumerate(evidence, 1):
        page = f", page {p.page_number}" if p.page_number else ""
        parts.append(
            f"### E{n}: {p.source.name}{page}\n"
            f"Source ID: `{p.source.source_id}`; version: `{p.source.source_version}`\n\n"
            f"Passage {p.passage_index}, characters {p.start}–{p.end}\n\n"
            + "\n".join("> " + line for line in p.text.splitlines())
        )
    return "\n\n".join(parts) + "\n"
