# Phase 8 acceptance — 2026-10-17

This continues [the previous record](acceptance-2026-10-16.md) on the owner's
`feat/mvp-end-to-end` branch. The requested final merge remains conditional on
completing the remaining work. **Known P1 factual-quality failures remain; Phase 8,
MVP acceptance and final merge are open.** Successful transport, literal citation
checks, valid JSON and saved artifacts do not establish semantic acceptance.

## Method and implementation

All originals and workspaces used here are invented QA data. Actual inference
uses the installed `qwen3.5:4b` Q4_K_M model, digest
`2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`,
through dedicated loopback Ollama `127.0.0.1:11439`. Evaluation context/output are
8,192/2,048 tokens, thinking disabled and temperature zero; the product's default
context remains unchanged. Model weights were neither downloaded nor modified.
Heavy tests/builds and generation stages run sequentially on the 8 GiB M2 host.
Native UI observations overlapped the initial analysis prototype; some small
Wiki unit runs overlapped later generation. Durations are observations, not a
controlled latency comparison or a peak-memory/leak measurement.

Focused changes precede this record:

- `48201fa`: relation checks read both complete bounded original passages,
  including conditions beyond summaries and short quotes. Bad original references
  fail visibly; optional oversized relation pairs skip without truncation.
- `c0298c0`: source-document v23 audits compare evidence in an analysis field
  before returning support. Audit batches reserve output space and still isolate
  claims with different allowed evidence sets. The application copies the entire
  exact rejected claim into diagnostics; models no longer reconstruct rejection
  fragments, which previously failed literal validation.
- `e3d8b3a`: Wiki v5 relation premises contain originals only, with repeated
  original pairs compared once. Generated summaries are no longer factual premises.
- `5a97f12`: Wiki v6 includes the exact constrained output schema in the actual
  model prompt and UTF-8 input budget, as well as the decoder format.
- `5885c21`: Wiki v7 shares the existing narrow capacity/currently-stored guard
  with source documents, checking each summary/key point against its own original
  before publication. Source-document behavior and model wire requests are unchanged;
  Wiki's generation identity changes so prior unchecked outputs are not reused.

These changes improve evidence handling and make the model contract explicit.
Diagnostic analysis is model output, not independent proof of entailment.

## Source-document support checks

The analysis prototype retained the old model-copied rejection fragments. Its
first run used incorrect evaluator environment names: **22 requests failed before
inference**, including an unload error. The corrected run produced **17/22 valid
semantic responses, all seventeen matching labels**, and five invalid copied
fragments, in **780.413 s**. Raw booleans in those five malformed responses matched
labels but are not accepted semantic results. This motivated application-owned
rejection text rather than weakening literal checks.

Production v23 then returned **14/14 valid judgments, 12/14 matching labels in
321.299 s**. Eight fresh claims were fixed before those calls: **7/8 matched**.
The model falsely rejected a faithful translation of Korean `나흘` as four days,
misreading the original as three days. Six known regressions matched **5/6**:
rated-versus-observed substitution and an unsupported instrument relationship were
correctly refused, while adjoining daily backups were still falsely rejected as
not attached to the named subject. No malformed rejection fragments remained.

### Sampling experiment, declined

Actual Ollama parameters revealed an inherited `presence_penalty: 1.5` despite
application temperature zero. A transport-only experiment added
`presence_penalty: 0`; production settings and prompts did not change. Fourteen
paired request bodies were otherwise identical to recorded v23 requests. Run order
and cache state differed, so wall times do not establish a causal latency result.

The experiment returned **22 valid judgments, 19 matching labels in 269.743 s**:
six fresh controls matched 6/6; known/derived controls matched 13/16. On the exact
fourteen paired controls, **both settings matched 12/14**, trading failures. Zero
penalty corrected the four-day translation but newly approved a rated-to-observed
substitution; the adjoining-backup false rejection persisted. It also approved the
actual unsafe saved comparison described below. This is insufficient evidence for
a sampler change, so the experiment was **not adopted**. Runtime parameters are
supported by the [official Ollama API documentation](https://github.com/ollama/ollama/blob/main/docs/api.md).

## Complete source-document and Wiki attempts

Each row is one fresh explicit attempt with real scanning, extraction, local
embeddings, generation and persistence. The vector store is in memory. Original
invented files include Korean Alpha (37-litre capacity, SQLite, Sunday writes
stopped, daily backups), English Beta (92 litres currently stored, append-only log
files, Sunday writes permitted, twice-daily backups), an unrelated orchard, plus
empty/missing controls. No failed job was automatically retried. Source-document
requests use v23; the Wiki request uses v5, before v6 schema exposure.
Seconds below are the evaluator's generation/processing interval; process wall
times and per-call model metrics are retained separately.

| Scenario | Generation seconds | Observed result | Acceptance |
| --- | ---: | --- | --- |
| English comparison | 465.269 | Saved; “Beta stores 92 litres using append-only log files” joins independent facts into an instrumental relationship; v23 auditor approved it | **P1 factual failure**; repeated facts also remain |
| Korean collection | 243.648 | No artifact; extracted twice-daily backup occurrence became permission to run backups; auditor correctly refused that modal change | Protection works; requested document generation **not delivered** |
| Relevant report | 701.827 | Both relevant languages selected, orchard excluded; 3 inventoried, 2 selected/processed; inspected body facts faithful | Partial; repeated facts and unsupported “Contingency Protocols” heading topic remain P2 |
| Partial/missing | 637.127 | 4 inventoried/selected, 2 processed; empty `indexing_failed`, missing `missing`; inspected facts faithful | Expected partial coverage accepted; repetitive generic organization remains P2 |
| Empty scope | 0.003 | Refused, no artifact, no generation calls | Expected refusal accepted |
| Wiki | 76.606 | Two revisions saved; references and literal quotes valid; Alpha implies SQLite provides capacity, Beta becomes an “append-only system” | **P1 summary meaning failures**; no relation calls qualified in this whole run |

Comparison body SHA-256:
`0fda5805d9a68279727e12b00867e82c9514dd824149d7d34b43013b3e7b2b47`.
Report body SHA-256:
`9aee6de2f5c1c9458c4bdf8696ce38e5157e07a8fa4d74b26118a47472575703`.
Hashes bind inspected output bytes, not a quality verdict. Manual reviews were
performed by the primary agent; no independent reviewer is claimed.

### Latest v6 whole Wiki and v7 quantity protection

A later complete **v6** whole Wiki attempt used the same known invented corpus,
not a fresh holdout. It completed in **96.575 s** with two saved revisions, two
actual summary calls and one actual relation call. The relation proposal correctly
contrasts Alpha/Beta as alternatives. Summary quality still fails: Alpha implies
SQLite provides its capacity; Beta's first key point turns “stores 92 litres” into
“storage capacity of 92 litres.” The latter is an explicit quantity-property drift.

Commit `5885c21` moves the already tested litre-property check into a shared module
and applies it to every Wiki summary and key point. It uses only that claim's cited
passage, so another passage's capacity cannot authorize a stored-amount swap. A
no-model replay of all ten exact v6 claims rejects the bad Beta key point, while
nine pass this narrow check. Those nine include the unsafe Alpha relationship;
passing this check is **not semantic acceptance**. Existing historical/user writing
is preserved, rather than rewritten retroactively.

The first focused test run returned **97 passed, 6 failed**: six new mocked model
responses used the original ID instead of the actual fragment ID, so the existing
reference guard correctly rejected them before the quantity check. Fixtures now
return IDs from the actual sent prompt. The corrected focused run is **103 passed,
7 warnings in 2.38 s**, including source-document guard regressions and a real
folder/persistence test proving rejected regeneration preserves an authored revision
and its exact on-disk file. No production reference validation was relaxed.

The final **v7 actual-model** attempt took **84.772 s** on the same known
invented corpus. It saved Alpha, whose summary still contains the unsupported
SQLite-to-capacity implication. Beta newly phrased its bad value as “The system
stores a capacity of 92 litres”; the guard refused it **before Beta revision
publication**. Its raw output also selected the unrelated existing Alpha project
topic, but that response was not published. There were two actual summary calls,
no relation calls and no automatic retry. The narrow protection is confirmed with
fresh model output; **complete Wiki generation and factual quality still fail**.

### Reusing the support auditor for Wiki, declined

The actual v23 support auditor was tested on the two saved unsafe Wiki summaries
and one faithful key point from each source: **4 valid judgments, 2/4 correct**.
It approved both unsafe summaries as well as both faithful points. This diagnostic
uses known saved regressions, not fresh holdouts or a production Wiki gate. Adding
this same auditor to Wiki publication would not prevent the observed failures, so
no extra inference pass was adopted merely to claim verification.

## Actual Wiki relation controls

Candidate lookup alone is fixed to ensure each pair reaches actual production
relation inference. These component controls are separate from the whole Wiki
attempt above, where candidate qualification yielded no inference calls.

- **v4: 6 valid, 3/6 rubric matches in 91.582 s.** Full originals plus summaries
  still produced a false contradiction by ignoring an inspection exception, and
  missed two required positive relations.
- **v5: 9 valid, 4/9 rubric matches in 65.319 s.** Originals-only input avoided
  false contradictions but returned no relations for every pair, including all
  required positives. An empty result is not successful relation discovery.
- **v6: 12 valid, 7/12 rubric matches in 155.848 s.** Exact-schema exposure restored
  some real contradiction detection, but four false contradictions and one
  missed faithful translated relation remain. In three false-positive cases the
  model's own explanation describes compatibility or different properties while
  its enum says `contradiction`. High confidence does not validate these edges.

The three new v6 controls were fixed before v6 calls. Earlier cases are known
regressions, not fresh holdouts. This small synthetic sample does not establish
representative relation quality.

A no-inference comparison confirms all twelve recorded v6 relation system
instructions, actual prompts and decoder schemas are identical under v7; its
quantity protection changes publication and cache identity, not relation requests.
The v6 relation failures therefore remain applicable. This is compatibility
checking, not twelve new semantic judgments.

### Stance-protocol experiment, declined

A separate prototype requested one positive proposition, comparable conditions and
an `affirmed`/`denied`/`not_stated` stance for each original. Application code then
derived contradiction or support from those stances. It used the actual original-
pair input and transport with an experimental decoder/system and conversion; it
was **not production relation inference or an adopted change**. The inherited
relation rules remained in the input, a limitation of this experiment.

All **15 judgments were valid, 10/15 matched in 293.523 s**. The three fresh cases
matched 2/3; the twelve known v6 cases matched 8/12. Three inspection/upgrade cases
still falsely implied contradiction, and a faithful translated rule now falsely
became a contradiction. The equivalent-negative fresh pair was missed. Typed
shape and a deterministic stance truth table do not correct wrong semantic stance
extraction. No production protocol change follows from this insufficient result.

## Native Original PDF destination

Using CUA and the existing restored invented workspace with the v22 QA bundle,
the saved AT-201 conversation retained its consulted passage, 12 milliseconds,
37 megabytes and original evidence. The app's native Open button handed the
actual source URL with `#page=1` to the default browser. The already-open QA tab
was inspected without manually navigating or reloading that URL.

After explicit user permission for Chrome window inspection with possible unrelated
tab-title exposure, Chrome's PDF viewer reported **AT-201.pdf, page 1 of 1, PDF
load complete**, and the exact binary-heap/12 milliseconds/37 megabytes/8,000
vertices text. This establishes handoff and viewer/text loading. Three screenshot
captures returned white images even after raising the QA window; **pixel appearance
is unconfirmed**. Unrelated private page/tab content is excluded from evidence.

CUA app quit failed with a Sky startup error. Verified QA processes were cleaned
up through permitted CLI lifecycle control; this is not native quit acceptance.

## Current automated validation

- Latest full backend after the quantity fix, source commit `5885c21`: **1,105
  passed, 19 skipped, 27 warnings in 22.52 s**. The corrected runner uses the
  default unit-test environment and restricts QA endpoint/model overrides to the
  actual Wiki stage. Full Ruff passed. Product coverage: **6,482/7,568 lines
  (85.650%)**, **1,687/2,172 branches (77.670%)**; same exclusions as below.
- Earlier full backend at source commit `5a97f12`: **1,097 passed, 19 skipped, 24 warnings
  in 23.49 s**. Command: `python -m pytest -q --cov=app --cov-branch
  --cov-config=/private/tmp/noye-phase8-20261017/coverage.ini` with JSON and terminal
  reports. Production coverage excludes `app/tests`, stores coverage state outside
  the repository and does not include frozen subprocess execution: **6,468/7,554
  lines (85.624%)**, **1,687/2,172 branches (77.670%)**. Warnings include dependency
  deprecations, Qdrant version-check notices and garbage-collected unclosed SQLite
  connections; this run does not establish leak-free operation.
- Full backend Ruff `ruff check app`: **passed**. Focused Wiki v6 tests:
  **43 passed, 7 warnings in 3.54 s**. Earlier source v23 focus: **110 passed,
  8 warnings in 3.06 s**, before two further regressions included in the full run.
- Latest v7 QA bundle at `5885c21`: PyInstaller **31.730 s**, Tauri **21.728 s**,
  strict local signature integrity passed. Actual bundled backend: **12 passed,
  7 warnings in 44.52 s**. Embedded versions are `source-document-v23` and
  `wiki-grounded-v7`; backend SHA-256
  `2062e2d3c477869cd4df1b9d73d33b48415bd523aa165555ccdf77cddda2feb5`.
- Earlier v6 QA bundle at `5a97f12`: PyInstaller **32.181 s**, Tauri **21.283 s**,
  strict local signature integrity passed. The actual bundled backend passed
  **12 desktop/folder tests, 7 warnings in 44.63 s**. Its embedded modules were
  inspected for `source-document-v23` and `wiki-grounded-v6`; backend SHA-256
  `d4b995ee4b59962a169a97409ab37839577a376d58b6113c056999c7b9a1fa03`.
  This uses the development-only ad-hoc QA signing profile; product hardened
  runtime is unchanged. Local signature integrity is not Developer ID distribution,
  notarization or another-device acceptance.
- Frontend and Rust were unchanged in these backend commits. The prior
  **387 frontend tests**, TypeScript/ESLint/static build and **14 Rust tests**,
  formatting and strict Clippy results remain qualified in the preceding ledger;
  they were not rerun merely to increase the check count. The nineteen real-service
  checks from that record do not establish source-document or Wiki semantic quality.

The first combined v7 runner incorrectly exported the QA model, loopback endpoint
and 8,192-token context into **all** stages. It returned **1,103 passed, 7 failed,
14 skipped, 23 warnings in 42.63 s**: the failures concern expected default-model,
default-managed-endpoint and context-change/cache identity behavior. The corrected
runner limits those QA variables to actual Wiki inference; the default-environment
full run above passes. Initial logs and coverage are retained separately. No
production checks or assertions were weakened to get the corrected result.

## Evidence and remaining work

The [publication index](evidence/2026-10-17/publication.json) records each retained
synthetic report, method, review and log with raw/published byte counts and hashes.
Repeated successful model-preflight metadata is omitted with its hash; generation
inputs and outputs remain unchanged. Log formatting normalization is documented.
Strict JSON, inventory hashes and common credential-pattern checks are verified
before publication. No runtime databases, ZIP backups, weights, environment files
or unrelated Chrome content are included. The dedicated QA Ollama listener was
stopped after models were unloaded; the cleanup record is a point-in-time result.

Current P1 failures are the saved source-document instrumental relationship, the
saved Wiki SQLite-to-capacity implication and false contradiction classifications
in the unchanged relation requests. Complete Korean collection delivery and P2
organization also remain. Physical IME/VoiceOver, removable storage/sleep, native
active-token termination, representative retrieval calibration, authorized cloud
quality/latency and trusted distribution retain the prior record's limits. Keep
Phase 8/MVP and the requested conditional merge open; passing automated checks and
the new narrow refusal do not close these remaining requirements.
