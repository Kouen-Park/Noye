# Source-document validation

Branch `feat/prompt-documents` begins at integrated main `dc80189` (PR #59).
Measurements below are from the implementation workspace on Apple M2, macOS,
8 GiB RAM, Python 3.14.7, Node 26.8.1 and Next 16.3.8. They are not claims of
independent review or parity with the SecondBrain agent.

## Automated validation

- Backend feature/portable recovery: `pytest -q app/tests/test_source_documents.py
  app/tests/test_knowledge_portability.py`: 25 passed (23 document, 2 portability).
  These use actual temporary Markdown/TXT files, scanner, ingestion, SourceCatalog,
  SourceSession, persisted Wiki metadata, SQLite and durable worker. Local model
  responses, embedding and vector services are deterministic test doubles.
  Repeated after the v3 fallback deduplication: 25 passed, 8 warnings, 1.18 seconds.
- Full backend: `pytest -q` with loopback binding permitted: **920 passed,
  14 skipped, 10 warnings, 292.30 seconds**. Includes existing live Ollama checks
  when service detection enables them, real desktop sidecar start/stop and folder
  authorization/restart. It does not establish a native GUI/PDF workflow.
  An earlier sandbox run was 912 passed/19 skipped/3 failures: localhost socket
  binding was denied in desktop tests. No timeout or assertion was relaxed.
- Full frontend: `npm test`: **249 passed in 38 files, 7.48 seconds**.
- Final document/chat subset: `npm test -- src/components/documents
  src/lib/source-documents.test.ts src/app/chat/page.test.tsx`: **42 passed in
  7 files, 2.41 seconds**, including the two browser-discovered card regressions.
- `npm run lint`, `npm exec -- tsc --noEmit` and backend `ruff check app` passed.
- Selected editor/export suite: **27 passed**. Tests cover local unsaved draft
  recovery, historical read-only revision, current body/provenance exports,
  rejected print request and legacy answer-to-document behavior.

Feature checks cover bilingual exact quote/locator/version snapshots, entire
frozen collection enumeration and later-file exclusion, relevant discovery with
real scoped Wiki data, empty/chosen scope without link expansion, every fragment
of input over 8,000 characters, original modification during generation, missing
and no-text sources, invalid JSON/IDs/quotes/numerals/synthesis claims, model failure,
cancel/interrupted retry, failed-stage cache recovery, cloud-alias rejection before
private excerpts, stable artifact identity, no resurrection of deleted artifacts,
legacy editing, optimistic edit conflicts, independent chat deletion, selected
revision export, per-conversation task history and byte preservation.

Portable recovery generates and edits a document, backs up actual authored SQLite
bodies, requests, revisions, evidence and job stages, then restores into a new
workspace. External originals are excluded explicitly, roots are disconnected,
source IDs/hashes and user revisions remain. A hostile same-name trigger is refused.

An additional actual-data backup/restore used all three saved local-model
artifacts and the browser-authored user revision `c75a710c0d7a8cb69d4849f2ad979d67`.
The 49,415-byte ZIP restored into a new destination; all three current immutable
revision records, bodies, metadata and evidence compared exactly. The external
root restored disconnected. External originals were explicitly excluded and
internal byte/version snapshots retained. This was the real backup service and
SQLite data, not the native file chooser or a fixture backup.

## Actual local-model runs

The preserved evaluation workspace contains invented reservoir files (not private
user material). They were scanned, indexed with actual local embeddinggemma, read
through the actual catalog/evidence service, and summarized using local
`qwen3.5:4b` via Ollama 0.34.2. Document runs explicitly used context 8,192,
output 2,048, thinking false; the product default was not changed. Vector storage
for the evaluation was an in-memory Qdrant client; the provenance reads are real
persisted extraction/snapshot reads, not mocked passages.

Corpus facts: Alpha stores 37 litres, uses SQLite, stops Sunday writes and backs
up once daily. Beta stores 92 litres, uses append-only logs, allows Sunday writes
and backs up twice daily. An unrelated orchard file tests relevant discovery.

Actual source indexing: English 1.415 s, Korean 0.066 s, unrelated 0.055 s;
all three READY. Actual source Wiki generation: Korean Alpha 84.557 s,
English Beta 57.010 s, with stable IDs and saved source-version evidence.

| Collection attempt | Seconds | Observed result |
| --- | ---: | --- |
| v1 | 105.190 | Unsupported-claim check rejected publication; no artifact |
| v2 | 66.518 | Numeric support rejected publication; no artifact |
| v3 | 43.568 | Numeric support rejected publication; no artifact |
| v4 | 164.498 | Final synthesis rejected stronger “total capacity” wording; no artifact |
| v5 | 171.623 | Final synthesis rejected wording after explicit feedback; no artifact |
| v6 | 239.886 | Saved partial artifact; **manual faithfulness review failed** |

V6 processed 2/2 sources (120/120 English and 95/95 Korean extracted characters),
but an earlier model-approved paraphrase was reused as fallback after the final
verifier rejected it. Manual reading found that Beta's observed stored volume
became “total capacity.” The artifact is not a successful faithfulness acceptance.
The same local model's entailment results were inconsistent. The fix now uses
verbatim ORIGINAL snapshot text as fallback, deduplicates retained paragraphs,
labels unresolved synthesis as partial, shows this limit in the UI, and versions
the prompt as `source-document-v3`. Mechanical checks and model entailment do not
prove semantic accuracy. Empty sections and awkward translation also limit v6.

All failed request reports and the saved partial revision are preserved in the
local evaluation workspace, rather than overwritten by retries. A completed
request cannot overwrite its artifact; corrected evaluation uses a fresh request.

## Remaining acceptance evidence

The actual empty-scope CLI finished in 0.001 seconds, with a sources-required
clarification, no artifact and no model call.

Fresh `source-document-v2` Korean collection generation completed in **366.581 s**:
all 2 selected sources processed (120/120 and 95/95 extracted characters), 5
validated citations and a partial artifact. Manual reading confirmed that the
rejected stronger Beta capacity paraphrase was absent. The actual English original
paragraph was retained instead, but repeated four times. Eight planned sections
contained seven empty boilerplate sections; mixed-language output is not polished
Korean notes acceptance. This run motivated the v3 paragraph deduplication and
compact topical-outline prompt, validated separately by the regression suite.

An actual relevant English report completed in **481.641 s** using v2: the initial
inventory contained 3 sources, discovery selected Alpha/Beta and excluded the
unrelated orchard. Both selected sources were fully processed, with 6 validated
citations and a partial artifact. A final support check rejected even the literal
"Backups run twice a day" inconsistently; the original paragraph was retained.
Manual review found unsupported engineering topics in empty headings and Korean
prose despite the English request. Discovery and coverage worked, but this is
not successful English report quality acceptance. Empty `wiki_hints` in this
plan means no related-page search hits; eligible source-Wiki summaries were still
inspected by the discovery service, independently of original evidence reads.
Both artifacts' 11 saved citations were independently checked against the actual
original byte hashes and quote start/end spans; all matched, with no invented page
numbers. This checks provenance mechanics, not translated prose quality.

Actual v3 collection, project comparison and missing/no-text partial-result runs
are pending coordinated model execution. Actual native document edit/save and
native PDF files (Korean/English and long pagination) are pending. Actual browser
Markdown files are recorded below. A successful artifact or
`window.print()` call does not establish PDF-file success. Native packaged-app results remain separate from browser observations. These acceptance checkboxes remain
open until observed results justify them.

## Browser and export observations

Production static export (`npm run desktop:ui`, Next 16.3.8/webpack) succeeded:
4.3 s compilation, 2.1 s types, all 10 static pages generated. The real API and
this static output were served on isolated loopback ports against invented QA data.
Observed in Chrome: the actual generated artifact opened with 2/2 source coverage,
partial state and revision history. Editing Korean/English text and saving created
an immutable user revision; the generated revision remained read only and its
export link selected that exact historical revision. Actual API Markdown files
were written and verified: edited 410 bytes, edited + provenance 4,245 bytes,
historical 2,797 bytes. Korean and saved evidence were preserved, and the selected
historical body differed from the edited body. These were Markdown files, not PDF.

The explicit chat document checkbox with no selected sources submitted a real
source-driven request, fixed its inventory at zero, and showed sources-required
clarification with no artifact. Browser observations found terminal clarification
still displayed discovery/retry controls; the UI now explains selection was not
completed and requires a new request. Historical partial metadata also prompted
removal of a blanket “verbatim originals retained” claim: old v1 artifacts had a
different fallback and cannot be described by the current implementation.

Initial QA app startup scheduled Wiki refresh work, loading a model even without
an explicit document request. Those synthetic jobs were stopped and preserved as
cancelled, and the synthetic root was paused before repeating browser checks.
This is why app startup, full live tests and explicit generation must be coordinated
on this 8 GiB host; models were not silently attributed to native validation.

A reports a separately identified Tauri QA package/static build and 10 frozen
sidecar tests passed (21.47 s). Native settings/service connection was observed,
but file selection was followed by Sky UI automation errors, so native question →
document edit/save → Markdown/PDF, Unicode PDF and long pagination remain unverified.
This is peer-reported acceptance evidence, not B's independent native observation.

## Reproduce without private data

Activate the backend environment and use a new isolated directory:

```sh
GENERATION_CONTEXT_TOKENS=8192 GENERATION_OUTPUT_TOKENS=2048 OLLAMA_THINKING=false \
  python -m app.evaluation.source_documents --workspace /private/tmp/noye-doc-qa --scenario wiki
GENERATION_CONTEXT_TOKENS=8192 GENERATION_OUTPUT_TOKENS=2048 OLLAMA_THINKING=false \
  python -m app.evaluation.source_documents --workspace /private/tmp/noye-doc-qa --scenario collection
```

Other scenarios are `report`, `comparison`, `partial` (an actual empty TXT plus a
missing source ID), and `empty`. JSON reports include failure/success, timing,
model settings, frozen manifests, coverage and saved revision. The CLI refuses
changed/unknown original intake files, symlinks and another root or upload in its
database. Application-authored `wiki/` output is excluded from original intake,
matching the real scanner.
Run sequentially; the measured 8 GiB host cannot safely combine local model work,
full live test suites and native builds. Existing live regression tests can load
Ollama even when no document evaluation is running; unload idle models afterward.
