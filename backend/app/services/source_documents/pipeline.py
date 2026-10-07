"""Outline, complete bounded original processing, then grounded cross-source sections."""

import hashlib
import json
import re
import time
from collections import defaultdict

from app.config import get_settings
from app.db import source_documents as store
from app.db import wiki as wiki_store
from app.db.wiki import now
from app.models.conversations import MessageCitation
from app.models.evidence import EvidenceExcerpt, EvidenceSnapshot
from app.models.source_documents import (
    Extraction,
    Intent,
    Outline,
    Selection,
    Synthesis,
    Verification,
)
from app.models.wiki import Passage, WikiScope
from app.services.source_catalog import SourceCatalog, SourceError, SourceSession
from app.services.source_documents import discovery, local
from app.services.wiki import relations, sources
from app.services.wiki.pipeline import fragments


class ClarificationRequired(local.DocumentError):
    pass


def batches(items, payload, schema, settings, constraints=lambda items: None):
    """Every input item is visited; an oversized indivisible item fails visibly."""
    group = []
    for item in items:
        candidate = [*group, item]
        if local.size(payload(candidate), schema, constraints(candidate)) > local.budget(settings):
            if not group:
                raise local.DocumentError(
                    "An item exceeds the document stage budget. No input was cut."
                )
            yield group
            group = [item]
            if local.size(payload(group), schema, constraints(group)) > local.budget(settings):
                raise local.DocumentError(
                    "An item exceeds the document stage budget. No input was cut."
                )
        else:
            group = candidate
    if group:
        yield group


def _checkpoint(context, stage, completed=0, total=0):
    context.checkpoint(stage, completed, total)


def _call(context, req, key, payload, schema, settings, client, constraints=None):
    """Cache successful model stages across explicit retries; no hidden replay on startup."""
    _checkpoint(context, payload["task"])
    rejected = req["report"].get("rejected_support_check", {})
    if rejected.get("stage") == key and payload["task"] in (
        "process_original_sections",
        "cross_source_synthesis",
    ):
        payload = {
            **payload,
            "validation_feedback": {
                "previous_claims": [
                    {"text": claim["text"], "supported": supported}
                    for claim, supported in zip(
                        rejected["claims"], rejected["supported"], strict=False
                    )
                ],
                "rules": "Correct the rejected factual wording before producing a new draft. "
                "Observed stored volume does not imply maximum capacity; avoid adding total, "
                "maximum, guarantees or stronger conditions absent from the originals. "
                "Preserve source attribution and exact quoted wording. Do not omit valid sources.",
            },
        }
    cache_key = (
        key
        + ":"
        + hashlib.sha256(
            (
                key
                + store.encode(payload)
                + settings.ollama_model
                + local.PROMPT_VERSION
                + str(settings.generation_context_tokens)
                + str(settings.generation_output_tokens)
                + str(settings.ollama_thinking)
            ).encode()
        ).hexdigest()
    )
    if cache_key in req["cache"]:
        return schema.model_validate(req["cache"][cache_key])
    result = local.structured(
        payload, schema, settings=settings, client=client, constraints=constraints
    )
    _checkpoint(context, payload["task"])
    req["cache"][cache_key] = result.model_dump()
    store.save_request(context.connection, req["id"], cache=req["cache"])
    return result


def discover(context, req, settings, client):
    db, scope, manifest = (
        context.connection,
        WikiScope.model_validate(context.scope),
        context.manifest,
    )
    if scope.mode == "empty" or not manifest:
        raise ClarificationRequired(
            "No sources are allowed. Choose files or a collection to create a document."
        )
    if len(manifest) > 1000:
        raise ClarificationRequired(
            "This inventory exceeds 1,000 sources. Choose a smaller collection."
        )
    request = req["request"]
    intent = _call(
        context,
        req,
        "intent",
        {
            "task": "interpret_intent",
            "instruction": request["instruction"],
            "intent_context_not_evidence": request["intent_context"],
            "rules": "Resolve purpose, topic, document type and output language. "
            "No course label is "
            "required. Choose collection only for requests to review "
            "an entire named/selected "
            "collection. collection_query is empty for all selected materials. "
            "Clarify only genuinely "
            "unresolved requests or collection ambiguity; "
            "do not ask for optional formatting preferences.",
        },
        Intent,
        settings,
        client,
    )
    if intent.clarification:
        raise ClarificationRequired(intent.clarification)
    if request["inventory_mode"] != "auto":
        intent.inventory_mode = request["inventory_mode"]
        # Explicit collection means all files within the selected scope.
        if request["inventory_mode"] == "collection":
            intent.collection_query = ""

    # Wiki search/relations discover IDs only. Interpretations never become document facts.
    hints = {}
    pages = set()
    for hit in relations.search(db, intent.topic, scope, manifest, limit=8):
        pages.update(relations.traverse(db, hit["id"], scope, manifest, depth=1, limit=20))
        if len(pages) >= 20:
            break
    for identifier in sorted(pages)[:20]:
        page = wiki_store.page(db, identifier)
        revision = wiki_store.revision(db, page["current_revision"])
        for passage in revision["evidence"]:
            source_id = passage["source"]["source_id"]
            hints.setdefault(source_id, []).append(
                {"wiki_id": identifier, "revision_id": revision["id"], "title": page["title"]}
            )
    text_hints = discovery.search_hints(
        db, intent.topic, manifest, lambda: _checkpoint(context, "searching frozen extraction")
    )
    descriptors = {s["source_id"]: s for s in SourceCatalog(db).list_sources(context.scope)}
    candidates = [
        {
            **item,
            "name": descriptors.get(item["source_id"], {}).get("name", item["relative_path"]),
            "wiki_hints": hints.get(item["source_id"], [])[:4],
            "text_search": text_hints.get(item["source_id"]),
        }
        for item in manifest
    ]
    if intent.inventory_mode == "collection" and intent.collection_query:
        # Whole-collection membership is application-controlled, never top-k/model-selected.
        def normalize(value):
            return re.sub(r"[^\w가-힣]", "", value.casefold())

        wanted = normalize(intent.collection_query)
        collections = defaultdict(list)
        root_names = {r["id"]: r["name"] for r in db.execute("SELECT id,name FROM source_roots")}
        for item in manifest:
            if normalize(root_names.get(item["root_id"], "")) == wanted:
                collections[(item["root_id"], "")].append(item["source_id"])
            components = item["relative_path"].split("/")[:-1]
            for depth, label in enumerate(components, 1):
                if normalize(label) == wanted or normalize("/".join(components[:depth])) == wanted:
                    collections[(item["root_id"], "/".join(components[:depth]))].append(
                        item["source_id"]
                    )
        if len(collections) != 1:
            raise ClarificationRequired(
                "Choose one collection folder: the named collection is missing or ambiguous "
                "within this scope. Selecting its sources explicitly also works."
            )
        selected = next(iter(collections.values()))
    elif intent.inventory_mode == "collection":
        selected = [s["source_id"] for s in manifest]
    else:
        expanded = []
        for item in candidates:
            expanded.append(item)
            page = wiki_store.find(db, "source:" + item["source_id"])
            if not page or not page["current_revision"]:
                continue
            revision = wiki_store.revision(db, page["current_revision"])
            if not sources.eligible_page(db, revision, scope, manifest):
                continue
            # Every source-summary claim is discoverable in bounded entries. No
            # truncated Wiki body or original fact is used for document drafting.
            for section in revision["metadata"].get("sections", []):
                for claim in [section["summary"], *section["key_points"]]:
                    expanded.append(
                        {
                            **item,
                            "wiki_discovery_interpretation": claim["text"],
                            "wiki_revision": revision["id"],
                        }
                    )

        def payload(group):
            return {
                "task": "discover_sources",
                "intent": intent.model_dump(),
                "inventory": group,
                "rules": "Select relevant IDs only from this batch. For a collection include "
                "EVERY member matching the collection, including missing "
                "or failed sources. "
                "For a report select candidates relevant to the goal; "
                "no claim of reviewing all files.",
            }

        selected = []
        for position, group in enumerate(
            batches(
                expanded,
                payload,
                Selection,
                settings,
                lambda group: {"source_ids": [s["source_id"] for s in group]},
            )
        ):
            result = _call(
                context,
                req,
                f"discovery:{position}",
                payload(group),
                Selection,
                settings,
                client,
                {"source_ids": [s["source_id"] for s in group]},
            )
            allowed = {s["source_id"] for s in group}
            if not set(result.source_ids) <= allowed:
                raise local.DocumentError(
                    "The model selected a source outside the frozen inventory."
                )
            selected.extend(result.source_ids)
    selected = sorted(set(selected))
    if not selected:
        raise ClarificationRequired(
            "No matching material was found within this scope. Choose sources or clarify the topic."
        )
    plan = {
        "intent": intent.model_dump(),
        "selected_ids": selected,
        "selected_manifest": [s for s in manifest if s["source_id"] in selected],
        "wiki_hints": {s: hints.get(s, [])[:4] for s in selected},
    }
    store.save_request(db, req["id"], plan=plan, clarification=None)
    req["plan"] = plan
    return plan


def verify_numbers(text, support):
    # A second local entailment pass follows this mechanical guard.
    def numbers(value):
        found = set(re.findall(r"\d+(?:[.,]\d+)*", value))
        # Faithful bilingual rendering can turn an explicit word count into a digit.
        for pattern, number in (
            (r"\b(?:once|one)\b|한\s*번|하나", "1"),
            (r"\b(?:twice|two)\b|두\s*번|둘", "2"),
            (r"\bthree\b|세\s*번|셋", "3"),
        ):
            if re.search(pattern, value, re.IGNORECASE):
                found.add(number)
        return found

    if not numbers(text) <= numbers(support):
        raise local.DocumentError("A generated claim contains a number absent from its evidence.")


def check_numbers(context, req, text, originals):
    try:
        verify_numbers(text, " ".join(originals))
    except local.DocumentError:
        report = store.request(context.connection, req["id"])["report"]
        report["rejected_numeric_claim"] = {"text": text, "originals": originals}
        store.save_request(context.connection, req["id"], report=report)
        raise


def verify(context, req, key, claims, settings, client, *, strict=True):
    payload = {
        "task": "verify_support",
        "claims": claims,
        "rules": "For EACH claim return whether the supplied original passages and exact quotes "
        "support every fact, comparison, number, condition and exception in the text. "
        "Use adjoining original sentences to resolve the subject of a quote. No outside knowledge. "
        "False for unsupported conclusions or contradictory evidence. "
        "Return one boolean per claim.",
    }
    groups = list(
        batches(claims, lambda group: {**payload, "claims": group}, Verification, settings)
    )
    verdicts = []
    for position, group in enumerate(groups):
        result = _call(
            context,
            req,
            f"verify:{key}:{position}",
            {**payload, "claims": group},
            Verification,
            settings,
            client,
        )
        if len(result.supported) != len(group):
            raise local.DocumentError("The local evidence check returned an invalid verdict count.")
        verdicts.extend(result.supported)
        if not all(result.supported):
            report = store.request(context.connection, req["id"])["report"]
            report["rejected_support_check"] = {
                "stage": key,
                "claims": group,
                "supported": result.supported,
            }
            store.save_request(context.connection, req["id"], report=report)
            context.report(key, "failed", detail=report["rejected_support_check"])
            if strict:
                raise local.DocumentError(
                    "The local evidence check rejected an unsupported conclusion. "
                    "No artifact was saved."
                )
    return verdicts


def coverage_entry(item):
    return {
        **item,
        "state": "pending",
        "reason": None,
        "passages_read": 0,
        "fragments_processed": 0,
        "characters_read": 0,
        "characters_processed": 0,
        "no_text_pages": [],
    }


def coverage_markdown(report):
    parts = [
        "## Source and coverage report",
        "Partial result." if report["partial"] else "Selected source text processed.",
        (
            "Collection inventory fixed at request start."
            if report["inventory_mode"] == "collection"
            else "Relevant sources discovered within the initial scope; "
            "the whole library was not reviewed."
        ),
        f"Initial inventory: {report['inventory_count']}; selected: {len(report['sources'])}; "
        f"processed: {sum(s['state'] == 'processed' for s in report['sources'])}.",
    ]
    for item in report["sources"]:
        parts.append(
            f"- {item['relative_path']}: {item['state']}; "
            f"{item['passages_read']} passages, {item['characters_processed']}/"
            f"{item['characters_read']} extracted characters processed. "
            + (item["reason"] or "")
            + (
                f" No extracted text on pages {item['no_text_pages']}."
                if item["no_text_pages"]
                else ""
            )
        )
    parts.append(
        "Coverage describes extracted text supplied to the model, not comprehension or "
        "proof that every fact was included. Scanned images and extraction omissions may remain."
    )
    if report.get("synthesis_limits"):
        parts.append(
            "Some cross-source wording did not pass evidence verification. "
            "Verbatim original passages were retained in their original language; "
            "comparative conclusions "
            "for those items remain unresolved."
        )
    return "\n\n".join(parts)


def provenance_markdown(metadata):
    parts = [
        coverage_markdown(metadata["coverage"]),
        "## Saved original evidence",
        "Historical snapshots from the first draft; user edits are not re-verified.",
    ]
    for n, item in enumerate(metadata["citations"], 1):
        source = item["source"]
        page = f", page {item['page_number']}" if item["page_number"] else ""
        parts.append(
            f"### E{n}: {source['name']}{page}\n\nSource `{source['source_id']}`; "
            f"root `{source['root_id']}`; relative path `{source['relative_path']}`; "
            f"SHA-256/version `{source['source_version']}`; passage {item['passage_index']}, "
            f"characters {item['quote_start']}–{item['quote_end']}.\n\n"
            + "\n".join("> " + line for line in item["quote"].splitlines())
            + "\n\nSaved original passage context (characters "
            + f"{item['start']}–{item['end']}):\n\n"
            + "\n".join("> " + line for line in item["text"].splitlines())
        )
    return "\n\n".join(parts) + "\n"


def generate(context, *, settings=None, client=None):
    settings = settings or get_settings()
    started, db = time.monotonic(), context.connection
    req = store.request(db, context.job["subject_id"])
    if req["artifact_id"]:
        return req["artifact_id"]  # Includes a deliberately deleted artifact: never resurrect it.
    local.require_local(settings)
    try:
        plan = req["plan"] or discover(context, req, settings, client)
    except ClarificationRequired as exc:
        store.save_request(db, req["id"], clarification=str(exc))
        raise
    intent = plan["intent"]
    outline = _call(
        context,
        req,
        "outline",
        {
            "task": "outline",
            "intent": intent,
            "instruction": req["request"]["instruction"],
            "selected_source_count": len(plan["selected_ids"]),
            "rules": "Plan concise topical sections in the requested language. "
            "Prefer one to four focused sections for two or fewer sources; at most eight "
            "for larger collections. Organize supported source notes, requested comparisons "
            "and uncertainties. Do not assume textbook definitions, statistics, debates or "
            "external examples. Headings are topical labels, not factual conclusions or "
            "numbers. Use unique section IDs.",
        },
        Outline,
        settings,
        client,
    )
    section_ids = [s.id for s in outline.sections]
    if len(set(section_ids)) != len(section_ids):
        raise local.DocumentError("The model returned duplicate outline section IDs.")
    coverage = {s["source_id"]: coverage_entry(s) for s in plan["selected_manifest"]}
    report = {
        "inventory_count": len(context.manifest),
        "inventory_mode": intent["inventory_mode"],
        "sources": list(coverage.values()),
        "partial": False,
    }
    all_claims, evidence, gaps = [], {}, []
    session = SourceSession(db, context.scope, context.manifest)
    consumed = []
    for position, source_id in enumerate(plan["selected_ids"]):
        _checkpoint(context, "reading originals", position, len(plan["selected_ids"]))
        entry = coverage[source_id]
        try:
            reference = sources.source_ref(SourceCatalog(db).get(source_id))
            passages, offset = [], 0
            while True:
                _checkpoint(context, "reading originals", position, len(plan["selected_ids"]))
                group = session.read(source_id, limit=100, offset=offset)
                for item in group:
                    text, index = item["content"], item["chunk_index"]
                    identifier = hashlib.sha256(
                        f"{source_id}:{entry['version']}:{index}".encode()
                    ).hexdigest()[:24]
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
                offset += len(group)
                if len(group) < 100:
                    break
        except SourceError as exc:
            if exc.code == "stale_version":
                entry.update(state="version_changed", reason=str(exc))
                store.save_request(db, req["id"], report=report)
                raise local.DocumentError(
                    "An original changed. Start a fresh document request; "
                    "retry keeps the old inventory."
                ) from exc
            entry.update(
                state=(
                    "missing"
                    if entry["availability"] == "missing"
                    else "unavailable"
                    if exc.code in {"unavailable", "out_of_scope"}
                    else "indexing_failed"
                ),
                reason=str(exc),
            )
            store.save_request(db, req["id"], report=report)
            continue
        row = db.execute("SELECT no_text_pages FROM files WHERE id=?", (source_id,)).fetchone()
        entry["no_text_pages"] = json.loads(row[0]) if row and row[0] else []
        entry["passages_read"] = len(passages)
        entry["characters_read"] = sum(len(p.text) for p in passages)

        def payload(group):
            return {
                "task": "process_original_sections",
                "intent": intent,
                "outline": outline.model_dump(),
                "passages": [{"evidence_id": p.id, "text": p.text} for p in group],
                "rules": "Extract only relevant supported claims, assign an outline section_id, "
                "and attach exact verbatim quotes. Empty claims are allowed for irrelevant text. "
                "Do not write pages or citation labels. Preserve numbers and exceptions.",
            }

        # Bound each character fragment before grouping; nothing is silently discarded.
        overhead = local.size(payload([]), Extraction)
        available = local.budget(settings) - overhead - 800
        if available < 128:
            raise local.DocumentError("Increase the local context budget for document processing.")
        inputs = list(
            batches(
                fragments(passages, max_bytes=min(3000, available // 3)),
                payload,
                Extraction,
                settings,
                lambda group: {"evidence_id": [p.id for p in group], "section_id": section_ids},
            )
        )
        for batch_number, group in enumerate(inputs):
            result = _call(
                context,
                req,
                f"source:{source_id}:{batch_number}",
                payload(group),
                Extraction,
                settings,
                client,
                {"evidence_id": [p.id for p in group], "section_id": section_ids},
            )
            known = {p.id: p for p in group}
            claims = []
            for claim in result.claims:
                if claim.section_id not in section_ids:
                    raise local.DocumentError("The model invented an outline section.")
                for support in claim.supports:
                    if (
                        support.evidence_id not in known
                        or support.quote not in known[support.evidence_id].text
                    ):
                        raise local.DocumentError("The model invented an excerpt or evidence ID.")
                check_numbers(
                    context, req, claim.text, [known[s.evidence_id].text for s in claim.supports]
                )
                claims.append(
                    {
                        "text": claim.text,
                        "quotes": [s.quote for s in claim.supports],
                        "original_passages": [known[s.evidence_id].text for s in claim.supports],
                    }
                )
            verify(context, req, f"source:{source_id}:{batch_number}", claims, settings, client)
            gaps.extend({"source_id": source_id, "text": gap} for gap in result.gaps)
            for claim in result.claims:
                all_claims.append(
                    {**claim.model_dump(), "id": f"C{len(all_claims) + 1}", "source_id": source_id}
                )
            evidence.update({p.id: p.model_dump() for p in group})
            entry["fragments_processed"] += len(group)
            entry["characters_processed"] += sum(len(p.text) for p in group)
            store.save_request(db, req["id"], report=report)
            _checkpoint(context, "processing original sections", batch_number + 1, len(inputs))
        entry["state"] = "processed"
        consumed.append(source_id)
        store.save_request(db, req["id"], report=report)
    if not consumed or not all_claims:
        raise ClarificationRequired(
            "The selected sources have insufficient extracted evidence for this request. "
            "Retry ingestion or choose other material."
        )
    report["partial"] = any(
        s["state"] != "processed" or s["no_text_pages"] for s in report["sources"]
    )
    rendered, citations, synthesis_limits = [], [], []
    for heading in outline.sections:
        relevant = [c for c in all_claims if c["section_id"] == heading.id]
        # Interleave sources so each bounded synthesis can compare across originals.
        by_source = defaultdict(list)
        for claim in relevant:
            by_source[claim["source_id"]].append(claim)
        interleaved = [
            group[n]
            for n in range(max(map(len, by_source.values()), default=0))
            for group in by_source.values()
            if n < len(group)
        ]

        def payload(group, heading=heading):
            return {
                "task": "cross_source_synthesis",
                "intent": intent,
                "heading": heading.title,
                "claims": group,
                "rules": "Write concise editable paragraphs or comparison "
                "points for this section in the requested language. Cite supplied claim_ids "
                "supporting EVERY fact. Discuss differences only if evidence supports comparable "
                "conditions; no new conclusions or facts. Do not invent citation labels.",
            }

        paragraphs, original_quotes = [], {}
        for group_number, group in enumerate(
            batches(
                interleaved,
                payload,
                Synthesis,
                settings,
                lambda group: {"claim_ids": [c["id"] for c in group]},
            )
        ):
            result = _call(
                context,
                req,
                f"synthesis:{heading.id}:{group_number}",
                payload(group),
                Synthesis,
                settings,
                client,
                {"claim_ids": [c["id"] for c in group]},
            )
            known = {c["id"]: c for c in group}
            checks, outputs = [], []
            for claim in result.claims:
                if not set(claim.claim_ids) <= known.keys():
                    raise local.DocumentError("The model invented a synthesis reference.")
                supports = [
                    s for identifier in claim.claim_ids for s in known[identifier]["supports"]
                ]
                check_numbers(
                    context, req, claim.text, [evidence[s["evidence_id"]]["text"] for s in supports]
                )
                checks.append(
                    {
                        "text": claim.text,
                        "quotes": [s["quote"] for s in supports],
                        "original_passages": [evidence[s["evidence_id"]]["text"] for s in supports],
                    }
                )
                labels = []
                for support in supports:
                    passage = evidence[support["evidence_id"]]
                    start = passage["start"] + passage["text"].index(support["quote"])
                    citation = {
                        **passage,
                        "quote": support["quote"],
                        "quote_start": start,
                        "quote_end": start + len(support["quote"]),
                    }
                    if citation not in citations:
                        citations.append(citation)
                    labels.append(f"E{citations.index(citation) + 1}")
                outputs.append(claim.text + " [" + ", ".join(dict.fromkeys(labels)) + "]")
            verdicts = verify(
                context,
                req,
                f"synthesis:{heading.id}:{group_number}",
                checks,
                settings,
                client,
                strict=False,
            )
            for claim, output, supported in zip(result.claims, outputs, verdicts, strict=True):
                if supported:
                    paragraphs.append(output)
                else:
                    # Use original bytes if final synthesis cannot be verified.
                    # An earlier model-approved paraphrase can still be overconfident.
                    for identifier in claim.claim_ids:
                        original = known[identifier]
                        for support in original["supports"]:
                            label = next(
                                n
                                for n, citation in enumerate(citations, 1)
                                if citation["id"] == support["evidence_id"]
                                and citation["quote"] == support["quote"]
                            )
                            text = evidence[support["evidence_id"]]["text"]
                            original_quotes.setdefault(text, []).append(f"E{label}")
                    synthesis_limits.append(
                        {
                            "section_id": heading.id,
                            "claim_ids": claim.claim_ids,
                            "reason": "Unverified synthesis replaced with verbatim originals.",
                        }
                    )
        paragraphs.extend(
            "\n".join("> " + line for line in text.splitlines())
            + " ["
            + ", ".join(dict.fromkeys(labels))
            + "]"
            for text, labels in original_quotes.items()
        )
        rendered.append(
            "## "
            + heading.title
            + "\n\n"
            + (
                "\n\n".join(dict.fromkeys(paragraphs))
                or "Insufficient extracted evidence for this section."
            )
        )
    if not citations:
        raise local.DocumentError("The model produced no supported document content.")
    if synthesis_limits:
        report["partial"] = True
        report["synthesis_limits"] = synthesis_limits
    metadata = {
        "schema_version": 1,
        "request_id": req["id"],
        "intent": intent,
        "scope": context.scope,
        "initial_manifest": context.manifest,
        "selected_manifest": plan["selected_manifest"],
        "wiki_hints": plan["wiki_hints"],
        "coverage": report,
        "evidence": list(evidence.values()),
        "citations": citations,
        "uncertainties": gaps,
        "model": settings.ollama_model,
        "prompt_version": local.PROMPT_VERSION,
        "parameters": {
            "context_tokens": settings.generation_context_tokens,
            "output_tokens": settings.generation_output_tokens,
            "thinking": settings.ollama_thinking,
        },
        "processing_seconds": round(time.monotonic() - started, 3),
        "validation": "exact ID/quote/locator/number checks plus local-model entailment check",
    }
    content = (
        "# " + outline.title + "\n\n" + "\n\n".join(rendered) + "\n\n" + coverage_markdown(report)
    )
    if gaps:
        content += "\n\n## Evidence gaps reported during processing\n\n" + "\n".join(
            "- " + gap["text"] for gap in gaps
        )
    legacy_citations = [
        MessageCitation(
            file_id=p["source"]["source_id"],
            file_name=p["source"]["name"],
            page_number=p["page_number"],
            chunk_indexes=(p["passage_index"],),
            best_score=1.0,
            evidence=EvidenceSnapshot(
                captured_at=now(),
                excerpts=(
                    EvidenceExcerpt(
                        content=p["quote"],
                        chunk_index=p["passage_index"],
                        retrieval_rank=n,
                        score=1.0,
                        source_hash=p["source"]["source_version"],
                    ),
                ),
            ),
        )
        for n, p in enumerate(citations, 1)
    ]
    _checkpoint(context, "verifying frozen originals", len(consumed), len(plan["selected_ids"]))
    store.save_request(db, req["id"], report=report)
    _checkpoint(context, "saving document")
    with session.commit_guard(consumed):
        artifact = store.publish(db, req["id"], outline.title, content, metadata, legacy_citations)
    # Record immediately: cancellation after commit must not hide or duplicate saved work.
    with db:
        db.execute(
            "UPDATE knowledge_jobs SET artifact_id=? WHERE id=?", (artifact, context.job["id"])
        )
    return artifact
