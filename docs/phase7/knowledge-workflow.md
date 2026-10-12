# Phase 7 knowledge workflow — 2026-10-05

Implemented on `feat/knowledge-workflow-completion` for items 9–12. During this
work, main merged items 1/2 as #48/#49. Normal merge `5aa5416` integrates main
`ce01d3f` and reuses its versioned `EvidenceSnapshot`, source metadata, byte-copy
extraction and shared evidence panel. Local drafting retains saved excerpts;
cloud drafting retains the existing answer/instruction/file-name payload policy.

## Embedding inputs and evaluation

Queries and documents now enter separate embedding functions. The optional
EmbeddingGemma retrieval prefixes are part of the index identity; raw-v1 remains
the default because two corpora do not show a consistent prefix improvement.
Changing the chosen format requires an explicit re-index. Original excerpts never
acquire model-input prefixes. The full formatted batch is checked before inference,
and `truncate=false` delegates the actual token boundary to Ollama.

The [evaluation record](retrieval-evaluation.md) retains real local comparisons,
actual answers and explicit Codex rubric inspection, including failures. It also
records why simple hybrid/diversity and another reranking model were declined.
The Atlas fixtures resemble bilingual study workflows but remain small, invented
and pre-chunked; no personal document or production database was used.
Retained inference runs precede #55's generation context/output bounds. Their
source hashes identify the measured baseline; final-package AI quality was not
re-measured after that integration.

## Bounded follow-ups and source scope

The last four stored messages without errors are read with a bounded SQL query. Only recent
user questions enter generation context, capped at 2400 characters overall and
800 per message. For recognizable references/comparisons, retrieval also includes
up to two recent user questions, capped at 400 characters each. No additional
model call rewrites the question. Generated answers are excluded from both context
and retrieval after a comparison exposed contamination from a prior AI claim.

`file_ids` has three distinct meanings: null is all compatible ready files, an
empty list is no search, and a list restricts to those IDs. Omitting the field on
an existing conversation reuses its saved selection. A separate scope PUT saves
checkbox changes before the next question; the UI waits for that write. Missing,
unready and incompatible IDs never expand to an unrestricted search. An empty
selection avoids inference and readiness probes entirely. New-chat selections are
saved with the first question, when the conversation obtains an ID.

Cloud disclosure in the chat selector, setup guide and settings includes the
bounded recent user questions. No automatic cloud fallback or model download was
added. Real cloud requests were not made during validation.

## Historical evidence and extraction coverage

Normal merges `a94d6a6` and `f29aca4` retain main's #53/#54 workspace backup/durable
jobs and #55 desktop readiness/workspace integration.
Additive SQLite migration 5 adds scope and PDF coverage after main's released
evidence/job migrations 3/4. Old references
remain readable with unknown snapshots/revisions. Each new answer saves the exact
retrieved text and point-carried source hash/index fingerprint; it never reconstructs
historical evidence from current chunks or mutable file rows. Those snapshots are
copied into documents and survive source or conversation deletion. Original status
is checked independently against current bytes. Evidence is associated with the
original answer/first draft and does not verify every generated claim or later edit.

Extraction records physical PDF pages with no text. Coverage can contain a blank
page or an image-only page; neither is automatically labelled a scan and no OCR
is performed. Failed re-extraction clears stale coverage. Main's parser hashes
and extracts the same immutable byte copy and checks the live original afterward;
points retain the revision
actually extracted even if the original changes later.

## Exports

The editor supplies its current body to both Markdown download and PDF preview,
including unsaved edits. Include provenance adds portable labels, source SHA-256,
index fingerprint, chunk IDs and literal saved excerpts. Source Markdown/HTML is
escaped or fenced; no localhost source link is appended. A direct API download
uses saved text, with `?provenance=true` selecting the same backend formatter.

Native inspection found missing Tauri print permission and a stylesheet selector
that hid the document's own descendants. Printing now has only the needed
`core:webview:allow-print` permission, reports rejected requests, preserves the
document subtree and releases screen grids/scroll containers for pagination.
Long-file inspection also reproduced a truncated appendix. Provenance now starts
on its own printed page, with literal excerpts allowed to wrap across pages.
No general frontend filesystem or shell permission was added.

## Validation and limits

Full integrated checks after `f29aca4` recorded 808 backend tests passed,
19 skipped and 8 warnings; 227 frontend tests passed across 32 files. Ruff,
ESLint and TypeScript passed. Rust format, five tests and Clippy passed. Native
export inspection used a 67.57-MiB unsigned Apple Silicon
QA app under a distinct identifier and a new synthetic workspace. The personal
Noye workspace was neither imported nor modified. These UI observations preceded
#55's integration, which did not change the document/export code.

Final `npm run desktop:build -- --no-sign -- --locked` after #55's integration
produced a 67.66-MiB unsigned Apple Silicon `Noye.app`, including desktop static
export. `npm run build -- --webpack` also passed separately for web mode.
The final app's actual frozen backend passed
`NOYE_TEST_SIDECAR=... .venv/bin/pytest app/tests/test_desktop.py -q -p no:cacheprovider`:
10 passed, 7 warnings in 12.22 seconds. The initial run alongside the web build
had 9 passes and one first-start timeout at the test's 20-second limit; the
standalone retry used the same unmodified tests. This is not a guarantee of cold
startup time under load.

Native observations confirmed restored selected/missing source IDs, immutable
English/Korean excerpts, changed/missing original labels and pageless metadata.
Final Markdown downloads retained current unsaved English/Korean text and all
96 repeated body sentences: 6611 bytes for body-only and 7377 bytes with provenance.
The latter included both literal saved excerpts and no localhost links. The original
stored title/body remained unchanged after quitting. An earlier repeat of the same
filename blocked WebKit's main thread inside a sandbox-extension call; that owned
QA process was stopped. Both final unique-name downloads passed, but repeat-name
reliability is not established.

Actual native Save as PDF output was read with PyMuPDF, normalizing whitespace
only for comparison. Body-only output was 3 pages / 25,792 bytes; cited output
was 4 pages / 35,988 bytes. Both preserved all 96 repeated sentences, the final
section and unsaved Korean content without application chrome. Only cited output
included the provenance appendix, both source hashes/fingerprints and both saved
English/Korean excerpts. The final appendix was rendered and visually inspected
for readable wrapping. This closes the long-file export check for item 12; it does
not establish arbitrary-document or operating-system coverage.

Regression coverage includes migration/legacy reads, all/empty/chosen scope,
deleted sources, bounded pronouns/comparisons, exact snapshot retention after
original edits/deletion, source-version payloads, PDF coverage and export toggles.
Actual local answers expose numerical faithfulness and language failures; these
remain Phase 8 quality work. Independent human review, representative real PDFs,
chunking comparisons, live Gemini, other operating systems and the full packaged
RAG/backup/recovery acceptance flow have not been validated.
