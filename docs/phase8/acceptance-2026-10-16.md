# Phase 8 acceptance progress — 2026-10-16–17

This supplements [the October 15–16 record](acceptance-2026-10-15.md), preserving
its failures. Work remains on `feat/mvp-end-to-end`, PR #64. This is progress
evidence, **not Phase 8/MVP completion or conditional final merge acceptance**.

## Environment and method

Apple M2, 8 GiB RAM; Python 3.14.7, Node 26.8.1, Rust 1.99, Next 16.3.8,
Tauri 2.12.1 and Wry 0.57. Generation uses the installed `qwen3.5:4b` Q4_K_M
model and the same 8,192/2,048 context/output limits, thinking off and temperature
0. The product's context default remains 16k. Heavy builds/tests, embeddings and
generation run sequentially. Ollama 11439 reads existing weights; no weights in
that store were downloaded or deleted. All originals and writing are invented QA
data. No cloud request, production credential access or OS security-setting change
was performed.

Curated reports, exact synthetic model requests/responses and normalized command
logs are under [evidence/2026-10-16](evidence/2026-10-16/).
`publication.json` records original/published hashes and transformations. Successful
model-preflight metadata may be omitted with its hash; command/JUnit diagnostic
formatting is normalized with raw-source hashes, while generation inputs/outputs
remain unchanged. Runtime databases, backup ZIPs, weights and environment files
are excluded. Final publication validation on October 17 checked all
268 inventory hashes/byte lengths and 87 strict JSON files, with no unlisted files
or common credential/private-key pattern matches. This bounded hygiene check is
not an independent security audit. The publication and validation methods are
included in the evidence.

## Source-document corrections

- **v15–16: valid structured evidence audits.** The actual prompt includes its
  constrained schema, rather than relying on the transport's output grammar to
  explain field meanings. Support audits identify original passages and literal
  unsupported claim fragments before returning their verdict. The application
  validates cardinality, claim ownership, literal fragments and consistency.
- **v17: metadata-owned source quotations.** The model selects bounded evidence
  IDs and original indexes. The application copies complete bounded passages and
  their exact spans from the frozen SourceSession. It does not ask the model to
  reproduce source quotation bytes. Unknown references and indexes belonging to
  another claim are refused. Complete passages can be less precise than a short
  subquotation; provenance takes priority over model-selected quotation boundaries.
- **v18: multilingual discovery context.** Each scoped source hint includes up to
  360 characters from a frozen original passage. Filename/English keyword overlap
  alone had hidden a relevant Korean source. A preview is untrusted discovery
  context; it does not count as reading or verifying an original. Scope and final
  evidence validation remain enforced.

Regression checks cover reference ownership, invalid indexes/types, inconsistent
audits, exact source spans, duplicate evidence and a Korean preview with no
English lexical overlap. Existing saved artifacts and user edits are unchanged.
The prompt-version change invalidates generated-stage caches for new attempts.

## Earlier live results retained

The v15 production holdout contains 24 fixed synthetic cases. A positive case's
unsupported derived time was corrected **before the first run**; both suite hashes
and the correction are retained. Rubric matches were **22/24 in 1,362.974 s**, but
only **21 were valid semantic decisions**: 20 correct and one false approval of
an unsupported relationship between encrypted storage and Redis. Two audits
failed literal-quotation validation; one negative was rejected mechanically before
inference. Matching refusal is not equivalent to a correct semantic audit.

All 23 actual v15 audit requests were byte-equivalent to the v16 support-verifier
wire format. That inspection does not validate the later v17/v18 index protocol.
Known-case diagnostic runs, including transport/schema/thinking experiments, remain
in the evidence and are not treated as fresh holdouts or production successes.

Every v16 scenario was a fresh explicit attempt, without automatic retry:

| Scenario | Generation seconds | Actual outcome |
| --- | ---: | --- |
| English comparison | 367.305 | Failed; unsupported Beta relationship refused, no artifact |
| Korean collection | 146.224 | Failed literal source quotation, no artifact |
| Relevant English report | 815.972 | Job completed with a partial artifact; manual quality review failed |
| Selected partial corpus | 257.397 | Failed generated missing-evidence assertion, no artifact |
| Empty scope | 0.001 | Refused before inference, as expected |

The completed report still omitted relevant Korean Alpha, repeated neutral section
labels and saved an unsupported “stores … using append-only log files” relationship.
The correct stored volume, Sunday condition and backup frequency do not cancel
these P1 defects. Its saved body/report hashes and manual findings are retained;
no independent review or accepted report quality is claimed.

The comparison/collection/report processes loaded commit `a3be545`; later partial
and empty subprocesses used an exported `a3be545` backend snapshot, after the
working tree advanced. Runtime hashes bind all five to v16. The original and
snapshot-pinned recorder scripts are retained separately. Reproduce the snapshot
with `git archive a3be545 backend/app`; compiled/runtime folders are not published.

## Fresh v18 evidence-audit controls

A separate 16-case suite (eight faithful/eight unsupported statements) was fixed
before the index-reference implementation and its run. Its SHA-256 is
`34c65e09ebc65bf7d2bd5005ada59fb868862d3bc5601279d9dca4f64b8503f8`.
Only source passages and claims reach the model; evaluator labels stay outside
its input. It varies subjects, labelled counts, measured/rated temperature,
translation, lost exceptions, causality, independent instruments and approval state.

The actual production verifier matched **15/16 in 163.028 s**: all eight negatives
and seven positives. All sixteen were valid semantic decisions, with no mechanical
refusals, malformed audits or transport failures. The false rejection was “Kite
retained 11 successful messages,” which follows from its original. That original
also contains a quoted untrusted instruction. Both this false rejection and the
correct rejection of its paired false claim are retained; no cause for the false
rejection is established. No case, expected label, prompt or sampling setting was
changed after seeing these results. This small synthetic result does not establish
general faithfulness or completed document quality.

## Complete v18 scenario attempts

All five current-code attempts finished on the same recorded v18 backend hash,
sequentially without retries. No generated artifact was published:

| Scenario | Generation seconds | Outcome |
| --- | ---: | --- |
| English comparison | 107.542 | Requested-English guard refused Korean extracted claims |
| Korean collection | 54.201 | Capacity/stored-amount guard refused a mistranslation |
| Relevant English report | 104.198 | Requested-English guard refused Korean extracted claims |
| Selected partial corpus | 103.803 | Requested-English guard refused Korean extracted claims |
| Empty scope | 0.001 | Expected refusal before inference |

Comparison, collection and report selected both relevant Korean/English originals;
the report excluded the unrelated orchard source. This corrects the observed
v16 report omission on this fixture, not representative discovery accuracy.
Reference-owned quotations caused no literal-quotation mismatch in these attempts,
but successful refusal still does not deliver a usable document.

The English intent was correctly resolved; failure occurred when extraction copied
Korean factual prose. Prompt v19 now binds the concrete target language in the
generation system instruction and generated `text`/`title`/`gaps` field descriptions.
The support-audit wire format and literal fragments are unchanged. Seven regressions
cover each generation stage/language, reference preservation, schema isolation and
unchanged audit instructions. No language guard, provenance guard, sampling setting
or acceptance criterion was relaxed. A separate eight-case cross-language suite
was fixed before this correction, SHA-256
`02f968b88d7d53193bb666f576f42981b6909e9b437e4ace1d1b2bcd96ec0efd`.

## Cross-language controls and quantity-guard correction

The eight fresh component extractions completed in **147.026 s**. All eight
passed the conservative script-language checks; seven passed the then-current
quantity guard. Primary-agent manual review accepted **6/8** for factual meaning.
One Korean output corrupted the separate Falcon subject to “페이커ン”; another
English output linked independent encrypted-report and B-tree-index facts with
an unsupported “using” relationship. These are retained model-quality failures,
not accepted translations. Other outputs sometimes combine independent assertions
despite the request for atomic claims. A malformed test-client context manager
failed before any model call; its log is retained and `closing` corrected the
diagnostic harness before the actual run.

The remaining guard refusal was a faithful “capacity 29 litres, currently holds
8 litres” translation. Inspection showed a capacity anchor leaking past the first
quantity into the independently worded second quantity. The matcher now stops
its prefix at the preceding quantity. Five regressions cover faithful later
amounts and later explicit swaps that must still fail. Unknown wording remains
subject to semantic verification; the narrow guard does not approve a claim.
Prompt/cache version v20 records this validation-policy correction.

Replaying the exact eight recorded outputs through the corrected guard passes
8/8 mechanically; manual semantic acceptance remains **6/8**. This replay is not
a new model run. Reconstructing the current system/prompt/schema confirmed exact
wire equality for all eight v19 extraction calls and sixteen v18 audit calls.
The model instructions, sampling and recorded outputs were unchanged by the
quantity-boundary correction. Neither a replay nor byte equality cures the two
observed semantic failures.

## Complete v20 scenario attempts

All five reports bind the same recorded v20 pipeline hash. These were fresh
sequential attempts; no failed job was automatically retried:

| Scenario | Generation seconds | Actual outcome |
| --- | ---: | --- |
| English comparison | 343.299 | Saved partial; storage/Sunday conclusions replaced by bilingual originals |
| Korean collection | 387.773 | Saved partial; neutral/repeated headings and a faithful backup sentence falsely rejected |
| Relevant English report | 465.976 | Saved partial; inspected facts faithful, repeated content and neutral headings remain |
| Selected partial corpus | 340.849 | Expected partial scope reported correctly; inspected prose faithful, presentation repetitive |
| Empty scope | 0.001 | Expected refusal before inference |

The comparison's backup-frequency contrast is faithful. Its storage synthesis
introduced an unsupported “using append-only log files” relationship and was
correctly refused. Its Sunday contrast was faithful but falsely rejected. The
accepted backup audit selected only one of two required originals; final E1/E2
citations remain application-owned and complete, so this is an audit-explanation
finding rather than a missing final citation.

The collection includes the principal Alpha/Beta facts but uses awkward “92 리터의
용량을 저장” wording. The storage verb makes a definite capacity-change judgment
uncertain; it remains a manual quality finding rather than grounds for another
fixture-specific classifier. A faithful Beta backup paragraph was falsely rejected,
leaving a repeated English original. The report selects both relevant bilingual
sources and excludes the orchard; its inspected facts preserve quantities,
conditions and independent log-file use without the earlier unsupported instrument.
It still repeats content and replaces two headings with neutral labels.

The selected partial corpus correctly reports inventory/selected/processed as
4/4/2, with empty and missing inputs separately unprocessed. Its inspected
comparisons preserve capacity versus stored amount, technology, Sunday conditions
and backup frequencies without inventing a numeric capacity difference. This
accepts the expected partial-scope control on this fixture, not complete document
presentation: neutral labels, empty-section omissions and repetition remain.
Manual reports bind each verdict to its exact saved body and raw generation report.

## v21 audit input correction

Actual multi-claim calls reused local original index 0 for different texts and
repeated the same original for multiple statements. v21 now supplies one exact-text
table per batch: an index identifies the same text throughout, and each claim lists
its own allowed indexes. The application rejects selected indexes outside that
claim's allowed set and copies audit quotations from the shared table. Text is
deduplicated in model input; distinct source IDs/final citations remain intact.
Instructions explicitly require considering the union of a claim's allowed
passages while rejecting new causal/instrumental relationships. This is a prompt/
reference correction, not evidence that the verifier now reasons correctly.

The new real-service controls were fixed before this correction: fourteen
multi-original cases, SHA-256
`d66ba5c78e72f0f39478b54fcb6c754056025bf8ac6a3963fe00c9cee6846f68`,
and six multi-claim batches/twelve claims, SHA-256
`48530344ac5711ade1b8a26d31f55549daed343d88cd43fecabaea178b8eeede`.
Evaluator labels are not model input. The fourteen multi-original calls completed
in **349.561 s**, matching **12/14**, all valid semantic decisions. The model
falsely approved a rated temperature limit as an observed temperature and falsely
rejected a faithful translated maintenance/weekday condition. The seven accepted
positive claims selected all required originals, including first-only/second-only
controls. Thus reference selection is observed on this suite while semantic
reliability remains unaccepted. The first read-only review inspected the HTTP
envelope instead of its `response` field and failed before writing; the corrected
review did not rerun inference or modify any case. The six multi-claim batches completed in **242.503 s**, matching **10/12**
claims with six valid audits. An independent encrypted-storage/map pair was falsely
approved as an instrumental relationship; only a neighboring subject's original
established that relationship. Selected indexes stayed within the declared list,
so structural reference checks cannot detect possible semantic borrowing. Its
cause is not established. A faithful daily-backup claim from the shared original's
second sentence was also falsely rejected.

A component replay of six preserved v20 candidates through v21 matched **5/6 in
129.230 s**. All five faithful statements passed, including the earlier Sunday,
Korean-backup and Beta subject false rejections. The unsupported storage/“using”
statement was now falsely approved. This is a known-case component replay, not
fresh generation or acceptance of the original v20 artifacts.

## v22 evidence-context isolation

An allowed-reference index does not prevent a model reasoning from other visible
originals. v22 therefore splits adjacent claims with different exact original sets
into separate support calls. Every original visible in one support call is now
allowed for every claim in that call. Identical sets can still share a bounded
call; shared-table deduplication, final distinct source citations and verdict order
remain intact. Mixed-source synthesis can require more inference calls. Prompt/
cache version v22 prevents reuse of prior generated-stage decisions.

A regression client deliberately borrows a weekday from any visible original:
the unsupported claim must now fail, neighboring faithful claims pass in their
input order, and caller evidence is unchanged. The existing invalid-index,
cardinality, source-ID, duplicate-text and durable-job checks remain in the suite.

Four new two-claim batches were fixed before this correction, SHA-256
`e4b84ba2c8301c094e87f7b5d58d06208d3adbf80d6539dc2c505106d6845079`.
Actual model calls matched **7/8 in 277.432 s**, all four valid audits. All three
unsupported instrument, lost-maintenance-condition and allocated/observed-memory
statements were correctly rejected. Four of five faithful statements passed;
the shared original's hourly audit-log sentence was falsely rejected. This does
not establish general accuracy or remove the earlier single-claim failures.

A no-inference MockTransport replay confirmed **all 28 recorded HTTP request
bodies** from the v21 fourteen-case single-claim suite are exactly equal under v22
and reproduce the recorded verdicts. Those rated/observed-temperature false
approval and translated-condition false rejection therefore remain applicable to
this unchanged path; they are not rerun successes. The twelve known multi-claim cases were then rerun: **11/12 in 648.838 s**, with
six valid batch outcomes and eleven actual generation calls. The independent
Skua instrument claim was correctly refused, while its explicitly supported
neighbor remained accepted. The Gannet daily-backup false rejection persisted.
The earlier run took 242.503 s and six generation calls. This was not a controlled
latency benchmark; the increased call count has a real cost, while the full
wall-time change cannot be assigned solely to the correction.

## Packaging and startup findings

A QA ad-hoc build with hardened runtime enabled passed strict signature integrity
but its bundled Python sidecar exited 255: the compressed Python library and
mapping process had incompatible Team IDs. This was a QA signing-profile error,
not a model-code startup failure. The temporary ad-hoc QA profile now explicitly
uses development conditions (`hardenedRuntime: false`); the product configuration
is unchanged. The resulting bundle opened the restored workspace and retained its
saved conversation/passages. Its 279 PyInstaller payload entries matched the
pre-bundle sidecar exactly, despite different outer signatures.

For actual signed distribution, `build-backend.mjs` now forwards a non-ad-hoc
`APPLE_SIGNING_IDENTITY` to PyInstaller so its compressed libraries are signed
before Tauri signs the app. Three stub-executable checks confirm argument routing
for unset, ad-hoc and synthetic identity values. These checks do not validate a
real certificate. [PyInstaller's signing documentation](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing)
explains why signing only the outer executable cannot sign its embedded libraries.
Trusted signing/notarization remains unvalidated.

Import profiling measured `app.main` at 1.192 s with the model unloaded. Controlled
startup probes measured source startup at 0.723–1.063 s and frozen startup at
5.161–5.597 s, including a two-worker CPU-load probe. All probes became healthy
and exited normally. This does **not** erase the earlier 20-second readiness
failure under a concurrent Rust build or establish physical cold-boot/memory-
pressure acceptance. No speculative import refactor was made.

## Native Original command

Desktop originals now use a semantic command button with pending, OS-handoff
acknowledgment and error feedback. Repeated activation while pending is blocked.
Normal web navigation remains an anchor; a print-only anchor retains the actual
destination while command/status UI is hidden in print.

In the rebuilt native QA app, the saved AT-201 conversation retained 12 ms/37 MB
and its original passage. The accessibility tree exposed a button; Tab from the
drawer's Close button focused it, and Return produced “Sent the original to your
default browser.” A screenshot confirmed its layout and the retained excerpt.
This establishes command execution and OS launch acknowledgment. A filtered
browser/app inventory still contained no AT-201/source-ID destination, so actual
browser PDF loading remains **unaccepted**. No private browser page was operated
or manual URL navigation counted as handoff acceptance. The QA app quit normally.

The first frontend test attempt used stale link-role queries after the deliberate
button change. Its failure log is retained; corrected tests verify keyboard use,
pending/duplicate handling, explicit cancellation, errors/retry and web/print
destinations. This was a test-query correction, not a hidden product fix.

### Native PDF link regression

An API-seeded invented document was opened in the native editor, switched to
Preview and exported through macOS Save. Activating its Original button first
also exercises removal of the visible handoff status from print. The initial
one-page PDF retained its correct clickable URI, Korean, 12 ms/37 MB and sentinel,
but MuPDF extracted the displayed URL with `tt` mapped to `!` and `fi` to a
ligature. Its render was readable; literal URL copying was not accepted.

Printed URL suffixes now disable ligatures and use the bundled monospace face.
A second native export retained the exact URI **in both the PDF link annotation
and extracted text**, with Korean, measured values and sentinel intact. Pending/
sent messages were absent and the saved Markdown hash was unchanged. Both page
renders were visually reviewed without clipping or overlap. Before/after PDFs are
17,856/19,570 bytes; their hashes, text, link annotations and renders are retained.
The second fixture differs only in its temporary active backend port; the first
fixture/document remains unchanged. This does not establish OS browser loading.

The first read-only inspector could not JSON-serialize MuPDF Rect objects after
rendering; serialization was corrected without changing the PDF. More significantly,
both initial save panels left Save disabled, including after a foreground Raise
and a later screenshot/full-tree check. The remembered QA directory existed.
Re-selecting that same directory enabled Save without a filename edit. The saves
are accepted only with that qualification; the earlier first-panel success does
not establish general resolution of this newly reproduced issue.

The native save correction configures the filename after the other panel options
and calls public `validateVisibleColumns` before `runModal`. In the first PDF
panel after a fresh launch of that build, Save was enabled immediately and saved
the unchanged default filename into the unchanged remembered QA directory. The
resulting one-page PDF retained its heading, measured values and Korean and was
visually reviewed. No filename edit, Tab validation or folder reselection was
used. This resolves the reproduced flow on this host; other directories/OS
conditions remain unaccepted. Rust **14 tests passed**, formatting and strict
all-target Clippy passed before the native observation. Ordinary prose in that
PDF still exposed font ligature mappings, separately from the fixed URL suffix;
document-wide print ligatures are now disabled as well. An actual fresh native
export retains the literal `<!-- Phase8 Markdown fidelity -->`, `->`, measured
values and Korean in one page (20,639 bytes). The long mixed-language fixture
remains seven pages (57,833 bytes): all forty table rows, forty wrapped code
lines, sixteen list items, quotation, final sentinel and local image survive.
All eight final page renders were inspected. The image heading, image and caption
remain together on page 6; stored Markdown is unchanged. The initial contiguous
code-token inspector failed on visual line wrapping; whitespace-normalized checks
and page inspection confirmed all tokens, without altering the PDFs.

On this fresh launch the first Save panel was enabled on its initial observation.
The second panel initially reported Save disabled, then became enabled on the
next screenshot/AX observation without any filename or directory edit and saved
normally. This is a transient activation delay, distinct from the earlier persistent
failure that required folder reselection; general instantaneous activation is not
claimed. The earlier persistent-failure records remain available.

## Native folder/Wiki scope and history observations

The rebuilt v22 app opened the restored invented folder. `Alpha-renamed.md`
remained ready and manually fixed to `Course/Reviewed`; filing was skipped to
preserve that choice. Opening its Wiki retained the chosen root in the URL.
Four revisions were visible. Selecting the old generated revision showed a
historical-snapshot banner, saved evidence and no editing controls; returning to
current restored the saved Korean user memo. The old evidence was marked
`superseded`, retained its saved version/span and offered no live Original control.

Selecting No originals removed the old body/pages and disabled every summary
button. Selecting AT-201 alone left the Alpha page unreadable with an explicit
outside-scope message. The native select menu required Return to commit; the
intermediate menu state was not counted as scope acceptance. These observations
do not cover every folder mutation, proposal adoption or stale/error path.

The retained old graph also exposes unaccepted relation classifications: differing
Alpha/Beta Sunday policies were labelled a contradiction despite different subjects,
and Gamma's lack of an Alpha mention was labelled a contradiction with Alpha's
capacity fact. Both links correctly target their saved origin revisions and mark
an earlier target revision; that historical precision does not establish the
classification's semantic accuracy. These are stored October 13 outputs, not fresh
current-model relation-generation results. Relation UI now calls them AI suggestions
and removes the misleading “verified related pages” wording. On October 17, native
AX and screenshot confirmed the suggested-relation labels and readable instruction
to compare both original passages. The saved memo/revision links were unchanged.
Wiki component tests **22 passed in 2.04 s**; ESLint, TypeScript, desktop static
build, native bundle and strict local signature verification passed. The final
UI-only rebundle retained the exact v22 sidecar hash that passed twelve tests. Copy clarification does not fix relation inference or
rewrite saved history.

## Previously skipped real-service tests

The nineteen existing availability-gated tests were run with actual Ollama and
cached official Qdrant v1.19.1, a dedicated loopback container on port 16339 and
unique database/files roots and collections per test. This keeps arbitrary-vector
server checks separate from actual embedding identities and personal indexes.
Cloud-key environment values were empty, no model weights were pulled/deleted,
and telemetry was disabled before the tests.

Initial result: **16 passed, 3 failed, 0 skipped**. The citation fixture and shared
answer-generation fixture indexed vectors without the current embedding fingerprint;
production retrieval correctly excluded these legacy/unknown points. The negative
answer test also passed through the canned no-results answer, so that initial
pass does not establish model refusal. The fixtures now attach the actual observed
identity/fingerprint/metadata. The refusal check additionally requires retrieved
context and a response other than the canned no-context text.

All four affected checks passed on actual-service rerun: citation page 2,
source-backed answer, model refusal with retrieved context and Korean answer.
The other fifteen passing checks were not repeated. JUnit reports confirm
**nineteen distinct tests accepted, zero skipped/failing after correction**.
Both initial failures and corrected logs/XML are retained. Related default-env
unit tests: **33 passed, 4 service-gated skipped, 5 warnings in 0.51 s**; Ruff and
format checks passed. These automated assertions do not close broader generated-
document or relation semantic quality. The dedicated container was stopped after
verification, with failed-run temporary records retained outside Git.

## Current automated validation

- Full v18 backend: **1,072 passed, 19 skipped, 27 warnings in 24.91 s**.
- Full v19 backend after explicit-language binding: **1,079 passed, 19 skipped,
  10 warnings in 21.32 s**; related source-document tests **109 passed, 8 warnings
  in 2.74 s**. Changed-file Ruff/format checks passed.
- Full v20 backend after the quantity-boundary correction: **1,084 passed,
  19 skipped, 10 warnings in 21.00 s**; related source-document tests **114 passed,
  8 warnings in 2.63 s**. Changed-file Ruff/format and diff checks passed.
- Full v21 backend after batch-consistent original references: **1,085 passed,
  19 skipped, 10 warnings in 21.66 s**; related tests **115 passed, 8 warnings
  in 2.70 s**. Ruff/format and diff checks passed.
- Full v22 backend after evidence-context isolation: **1,086 passed, 19 skipped,
  10 warnings in 23.31 s**; source-document/presentation tests **109 passed,
  8 warnings in 3.23 s**. Ruff/format and diff checks passed. The seven evaluation
  tests are included in the full suite, not the focused 109 count.
- Product coverage, excluding `app/tests`: **6,434/7,512 lines (85.650%)** and
  **1,665/2,156 branches (77.226%)**. Frozen subprocess execution is not included.
- Focused v18 source-document suite: **102 passed, 8 warnings in 2.64 s**.
- Pre-bundle frozen v18 suite: **12 passed, 7 warnings in 46.91 s**.
- Actual bundled backend: desktop tests **10 passed, 7 warnings in 24.20 s**;
  native folder protocol **2 passed, 5 warnings in 22.04 s**. These ran in separate
  sequential commands against `Noye Phase8 QA.app/Contents/MacOS/noye-backend`.
- Latest v20 actual bundled backend: **12 passed, 7 warnings in 43.89 s**.
  The subsequent print-only UI rebuild retained the exact tested sidecar SHA-256.
- Latest v21 actual bundled backend: **12 passed, 7 warnings in 43.80 s**;
  SHA-256 `06badf44d25056df456edebe9fedca05c7a62ea83cb41fe98ed8f41b44b7d83d`.
  The native PDF observations used this exact bundled sidecar, with the final print
  stylesheet; static UI build and strict local signature verification passed.
- Latest v22 QA bundle: PyInstaller **33.655 s**, Tauri **24.393 s** and strict
  local signature verification passed. Actual bundled backend **12 passed,
  7 warnings in 49.47 s**. SHA-256
  `9e19ddb96a7e8c3e00d6570c621aafa5bd448a639f71ebcaff2f996bf41f29eb`.
  This later backend change does not re-establish whole-document quality; the
  earlier PDF observations apply to its unchanged UI/print implementation.
- Original-command frontend regressions: **8 passed**; full frontend:
  **387 passed across 52 files in 8.63 s**. ESLint, TypeScript and static desktop
  UI build passed. The QA app rebuilt successfully at **68.23 MiB** and strict
  signature integrity passed; this is local ad-hoc integrity only.

## Acceptance still open

The current v22 protocol still needs complete document quality review. The fresh
controls retain a false rejection; earlier false approvals and failed/partial generation remain P1
findings until those checks establish otherwise. Native Original browser
destination, full folder/Wiki/history and stale-citation paths, physical IME and
VoiceOver, native active-token termination, removable storage/sleep, representative
retrieval calibration, authorized cloud quality/latency and trusted distribution
also remain open. Physical-device/certificate/cloud checks cannot be replaced by
mocks. Keep the Phase 8/MVP roadmap and conditional final merge open.
