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
  Final service/transport/citation guards: **28 passed, 8 warnings, 1.34 seconds**.
  Two real loopback HTTP servers prove configured proxy environments receive
  neither model preflight nor original context. An inline `[E37]` fabricated label
  was reproduced as a failing regression despite a supported number 37, then
  rejected before saving; the entailment test double deliberately approves it.
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

| Early collection attempt | Seconds | Observed result |
| --- | ---: | --- |
| 1 | 105.190 | Unsupported-claim check rejected publication; no artifact |
| 2 | 66.518 | Numeric support rejected publication; no artifact |
| 3 | 43.568 | Numeric support rejected publication; no artifact |
| 4 | 164.498 | Final synthesis rejected stronger “total capacity” wording; no artifact |
| 5 | 171.623 | Final synthesis rejected wording after explicit feedback; no artifact |
| 6 | 239.886 | Saved partial artifact; **manual faithfulness review failed** |

Attempt 6 processed 2/2 sources (120/120 English and 95/95 Korean extracted characters),
but an earlier model-approved paraphrase was reused as fallback after the final
verifier rejected it. Manual reading found that Beta's observed stored volume
became “total capacity.” The artifact is not a successful faithfulness acceptance.
The same local model's entailment results were inconsistent. The fix now uses
verbatim ORIGINAL snapshot text as fallback, deduplicates retained paragraphs,
labels unresolved synthesis as partial, shows this limit in the UI, and versions
the prompt as `source-document-v4`. Literal fallback was introduced in v2,
outline/deduplication in v3, and per-source context/observation handling in v4.
Mechanical checks and model entailment do not prove semantic accuracy. Empty
sections and awkward translation also limited attempt 6.

All failed request reports and the saved partial revision are preserved in the
local evaluation workspace, rather than overwritten by retries. A completed
request cannot overwrite its artifact; corrected evaluation uses a fresh request.

## Discovery, coverage and current-model results

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
Eight successful structured stages were cached for this request.

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
Fourteen successful structured stages were cached for this report. The latency
is a measured limit on this tiny corpus, not a throughput claim for long documents.
Both artifacts' 11 saved citations were independently checked against the actual
original byte hashes and quote start/end spans; all matched, with no invented page
numbers. This checks provenance mechanics, not translated prose quality.

The coordinated subsequent runs used the same actual originals, model and
8,192/2,048/thinking-false parameters. The owned daemon allowed one loaded model
and one parallel request; full live tests, native apps and builds did not run
alongside these evaluations. Targeted peer tests are reported separately.

| Scenario and prompt | Seconds | Result |
| --- | ---: | --- |
| v3 English project comparison | 164.835 | 2/2 sources, 3 topical sections, 7 citations, partial artifact |
| v3 missing/no-text collection | 64.196 | Unsupported per-source comparison absence rejected; no artifact |
| v4 explicit partial retry, same request/manifest | 281.427 | Attempt 2, 2 processed / 1 indexing failure / 1 missing, 6 citations, partial artifact |
| v4 whole Korean collection | 63.834 | Unsupported “information insufficient” claim rejected; no artifact |
| v4 explicit collection retry | 104.630 | Attempt 2, 2/2 sources, 5 citations, partial artifact |

The v3 comparison fixed the eight-section boilerplate, but final synthesis mostly
fell back to actual originals. Per-source model observations such as “other
project information is absent” incorrectly appeared as collection-wide gaps.
The v4 fix keeps these only in audit metadata, with source, batch, evidence IDs
and `verified=false`. Published prose excludes them; empty sections now say
that no verified generated claims were supplied rather than asserting absent
source evidence. Rendering is separately identified as
`source-document-markdown-v2`; older artifacts are preserved.

The actual v4 partial retry retained the same four frozen entries and request ID
while executing the new attempt job ID. Both readable sources supplied all 215
extracted characters. Actual empty TXT indexing failed with “contains no text”;
that failure and the missing source remain separate coverage entries with zero
processed text. All six citations matched actual original hashes and quote spans.
The published document contained no unverified per-source absence observations.
The generated facts retained 37/92, SQLite/append-only logs, Sunday exceptions and
once/twice-daily backups. Korean prose remained despite an English request, so
language/comparison quality acceptance is still open.

The final collection retry retained all two selected sources, exact 120/95
characters and five valid citations. Beta's full literal original appeared once
with combined matching labels; no stronger maximum/total-capacity paraphrase was
published. Its translation remained unresolved, and the model's one-section
heading “자료에 대한 정보 부족” was unsuitable for the available material.
This is a safe partial-output/data-path check, not polished Korean-note acceptance.
Across the five saved v2/v3/v4 artifacts, 29 citation hashes and quote spans matched
actual files; no model-created page numbers were stored.

Retry attempts create a new job ID, not a new request or artifact. A manual
evaluation harness initially invoked the old terminal job and performed no
inference; its diagnostic is excluded from the timing table. The committed CLI
now executes the returned attempt and writes attempt-specific reports, preserving
initial failures. No grounding assertion was relaxed to make a run pass.

Actual model cancellation/restart timing, changed-source handling under actual
inference, real long/image-only PDF processing, and native edit/save/PDF files
(Korean/English and long pagination) remain unvalidated. File-backed controlled
tests cover those lifecycle/scope/version boundaries with model test doubles.
`window.print()` and artifact success do not establish a PDF file. Native results
remain separate from browser/API observations and acceptance stays open.

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
The final B static export after the card fixes also passed: compilation 1,325 ms,
TypeScript 1,468 ms, all 10 pages generated (207 ms for page generation).

After actual v4 generation, the real feature API saved a further user revision
(`b9badeb3ab68077818e45be6f35113f0`) and retained generated revision
`e25764bf-9565-4473-9899-a50cc3b73d5f`. Reposting the same generation request
returned the complete job and preserved the edited revision and document count.
Selected immutable-revision Markdown files were 1,478 bytes (edited), 5,589
(edited + provenance), and 1,343 (generated history). These were ASGI/API checks
on real model artifacts and actual file exports, not a second browser/native pass.
The final 66,923-byte portable archive restored all **six** current artifacts,
bodies, user revisions and evidence exactly into a new destination. External
originals were explicitly excluded; internal byte/version snapshots remained;
external roots restored disconnected. The QA root was paused and the owned
Ollama daemon stopped after evaluation; no synthetic background work was left running.

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

In A's subsequent v3-integrated build, A reports **944 backend passed / 19 live
skips / 10 warnings / 17.89 s**, **259 frontend passed / 40 files / 22.71 s**,
lint/types, static export and Tauri QA bundle rebuilt, and **10 frozen sidecar
tests passed / 19.98 s**. A directly reproduced the native ZIP picker having disabled Open,
removed the advisory client filter while retaining backend archive validation,
and observed Open enabled in the new build with the actual 49,415-byte archive.
Open/Return dismissed the panel, but subsequent Sky state/screenshot/app binding
failed with timeoutReached/noWindowsAvailable. The process stayed alive and a
sample showed an idle AppKit run loop, so this does not establish an application
hang. Restart restored automation access; native restore completion and PDF
success still cannot be claimed. A closed only its isolated QA app/sidecars and
returned the model/build slot before B's actual v3 runs.

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
An explicit failed-job retry uses the same workspace/scenario and
`--retry-job <failed-job-id>`. Its request, scope and manifest are retained; JSON
is saved as `<scenario>-<request-id>-retry-<attempt>.json`. A completed job cannot
be retried to replace a saved document. Reposting a completed request is idempotent.
Run sequentially; the measured 8 GiB host cannot safely combine local model work,
full live test suites and native builds. Existing live regression tests can load
Ollama even when no document evaluation is running; unload idle models afterward.
