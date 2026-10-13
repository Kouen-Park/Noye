# Phase 8 acceptance progress — 2026-10-13

This is an incomplete acceptance record, not MVP release approval. Work is on
`feat/mvp-end-to-end`, as requested. The existing published history is preserved;
`06d2296` merges the current implementation into the old end-to-end branch. The
historical September web validation does not certify this packaged application.

## Fixed defects

- **P1, backup preservation:** local staging write/move errors could be treated as
  an unavailable root, allowing an incomplete authored file into a checksummed
  backup. Abort publication on those errors; retain the existing unavailable-root
  report for genuinely inaccessible external folders. Regressions cover partial
  writes, original/copy retention, retry and interrupted restore publication.
- **P2, backup validation:** missing/null/wrong-type manifest fields could escape
  as server errors. Validate the manifest and return a controlled invalid-backup
  response without publishing a destination.
- **P1, generated presentation:** source-language fields could override an
  explicit requested output language, and alternate line endings could hide
  Setext headings. Preserve the requested language, normalize only the checked
  copy, and keep support quotations verbatim in their original language.
- **P1, answer quantities:** actual Korean follow-ups treated an absent count as
  zero or as another subject's count. Generation now distinguishes unknown values
  from zero and still permits arithmetic between two recorded quantities. Local
  chat uses temperature zero. This is a measured prompt improvement, not a
  deterministic guarantee of all answer facts.
- **P1, generated headings:** the local verifier approved “Sunday write policies
  and performance” from permissions and backup schedules alone. Require every
  substantive heading topic, with a conservative performance-context gate before
  inference. Unmeasured performance topics receive neutral headings and partial
  presentation coverage. False rejections remain possible; broad semantic proof
  is not claimed.
- Source-document failure reports now retain actual passages/characters read
  before inference. Unsupported generation can report read coverage without
  claiming that those characters were successfully processed.
- **P1, macOS workspace relaunch:** a confirmed workspace switch left a running
  backend without a visible window. Showing/focusing on Ready alone still failed.
  After backend shutdown and Tauri plugin Exit cleanup, relaunch the executable's
  own `.app` through Launch Services. The destination cannot supply an executable
  path. Development/non-macOS restarts retain the framework behavior. A native
  two-way switch subsequently showed the new windows and responsive screens with
  one app/backend pair; the old restored processes exited and external services
  stayed healthy. OS-launch failure falls back to framework restart and remains
  unexercised. See the [upstream macOS restart report](https://github.com/tauri-apps/tauri/issues/13923)
  for related reports, not proof of the exact cause on this machine.

The evaluation CLI extends the existing worker and transport. It retains exact
generated responses, failures, token/duration measurements, revision hashes and
prompt/pipeline identity; it does not add a product inference engine or relax
evidence, scope, number or quotation checks.

## Environment and retained evidence

Apple M2, 8 GiB, macOS 27.0.1; Ollama 0.34.2; local `qwen3.5:4b` (4.7B, Q4_K_M),
digest `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`;
`embeddinggemma:latest` (307M, BF16), digest
`85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`.
Evaluation generation: 8,192 context tokens, 2,048 output tokens, thinking off.
The application's default 16,384 context is unchanged. Model evaluations ran
sequentially with one loaded model; builds/full suites ran after unloading.
No personal files, cloud credentials or model downloads were used.

Synthetic inputs and reports are in [evidence/2026-10-13](evidence/2026-10-13/),
with `SHA256SUMS`. Source/heading report copies omit only duplicated successful
`/api/show` raw metadata/license, retaining their hashes. Their `publication`
fields identify the unchanged full originals retained under
`/private/tmp/noye-phase8-20261012`. Every generated response, failure and timing
is retained. A body hash identifies a revision; it does not certify its quality.

## Actual local-model results

The original two-case baseline failed Korean count handling. A first prompt
attempt still borrowed another subject's value; a stricter attempt then refused
a valid English arithmetic comparison. Both failed attempts remain available.
The final recorded-arithmetic policy passed the core facts of both cases.

The expanded fixture contains six bounded follow-ups and six unbounded controls.
Direct primary-agent reading found the six bounded answers met their narrow
core-fact rubrics. This is not independent review or a general faithfulness score.

| Bounded case | Retrieval (ms) | Generation (s) | Observed result |
| --- | ---: | ---: | --- |
| English comparison | 18.525 | 7.526 | 12 ms vs 39 ms; difference 27 ms |
| Korean missing-count comparison | 24.737 | 15.731 | Abstains from an unknown difference |
| English poisoned assistant answer | 28.821 | 8.306 | Ignores previous 999/0 claims |
| Korean poisoned assistant answer | 42.258 | 8.294 | Does not adopt zero or difference 87 |
| First approach antecedent | 20.859 | 5.402 | AT-201, 12 ms |
| Independent backup question | 28.395 | 6.744 | 87 conversations, 14 edited notes; vectors excluded |

Cold embedding was 826.35 ms; subsequent retrieval used warm embeddings and an
in-memory Qdrant. These are CLI component times, not desktop request latency.
Korean abstention wording is imprecise about the missing measured count. The
first-approach ranking puts an unrelated Cedar passage first even though the
bounded answer is correct. Its initial gold incorrectly included AT-210; the
exact measured fixture and original metrics remain unchanged, alongside a
corrected fixture and explicitly offline rescored metrics in the review file.
No production retrieval heuristic/threshold/chunking change is claimed.

The English comparison of invented Korean Alpha and English Beta source files
has **not passed** document quality acceptance:

| Attempt | Time (s) | Result |
| --- | ---: | --- |
| Initial | 109.633 | Failed requested English; no artifact |
| Explicit retry 2 | 168.401 | “stores 92 litres” became “capacity 92”; rejected, no artifact |
| Explicit retry 3 | 261.306 | Job completed with a partial document; unresolved cross-source synthesis, repeated Korean literal fallback and unsuitable headings |
| Fresh v8 request | 148.277 | Same unsupported capacity strengthening caught; no artifact |

The completed partial revision read/processed both sources (215/215 characters),
but does not satisfy the requested complete English comparison. Its exact body
and limits are retained. The failed fresh v8 run retained Beta's 120 characters
read and Alpha's 95 characters processed. No automatic retry or cloud fallback
was used.

Six topical-heading checks using the production verifier gave 5/6 expected
results in v7; the false approval was the combined policy/performance heading.
In v8 all six matched: three positive topics, recovery/security rejection, and
performance rejection before inference (0.026 s). There were five model
judgments, not six; each had its own preflight. The other checks took
22.965/7.575/6.530/5.922/7.428 s. This narrow clinic is not complete document quality
acceptance.

The existing Wiki CLI completed both source pages in **108.431 s**
(`wiki-grounded-v3`): Alpha 63.812 s, Beta 44.328 s. Direct reading found the
37/92-litre quantities, Sunday conditions and daily/twice-daily backups retained.
Alpha was suggested as Unclassified, Beta as Course. Beta's summary describes an
“append-only system” where the original says append-only log files; that broader
description has not received independent semantic approval. This is a two-source
CLI generation observation, not native folder/Wiki/relations acceptance or a
requested bilingual output-language test.

## Packaged macOS observations

`Noye Phase8 QA`, identifier `com.noye.desktopphase8qa20261012`, uses isolated app
data and explicitly configured loopback services (Ollama 11439, Qdrant 6339).
The original workspace collection is `noye_phase8_qa_20261012`.

- Native file selection uploaded the invented 1,121-byte `AT-201.pdf`. Library
  reached READY, one page/one chunk; Search displayed its 12 ms/37 MB source
  details. Serving the original returned identical bytes, SHA-256
  `66fd7bba55477564c302b71aaf6596cd539f0d8ec415c1939bb6e51da65a67af`.
  The OS browser destination of the native Original link remains unconfirmed.
- Native local chat over that uploaded PDF returned exactly “12 milliseconds”
  and “37 megabytes.” The consulted-passage dialog showed AT-201 page 1, unchanged
  original status and the saved original excerpt. New chat followed by reopening
  the saved conversation retained its answer and passage button. Native request
  latency was not measured; the six CLI timings above do not apply to this run.
- The native answer-based Create document flow generated an English two-bullet
  note retaining 12 ms/37 MB. The native editor added a Korean marker, Cmd-S saved
  it, and ordinary relaunch retained the edits. Its initial Markdown attempt lost
  automation access and had no identified download. After QA-only relaunch,
  native Window-menu activation and renaming the saved title, the second attempt
  produced `Phase8 generated AT-201.md`: **170 bytes**, exactly matching the saved
  body, SHA-256 `c866296741db841358eff4a64808bd9ecc5fff0a9a2fe19163493737dfd009ac`.
  This is the answer-based flow, not the separate general prompt-driven document
  pipeline or proof of complete multi-source synthesis.
- A manually API-created bilingual document was opened and edited in the native
  editor. Markdown exported the current unsaved Korean marker, then Save retained
  it. The exported/saved body is exactly 4,526 bytes, 20 sections, SHA-256
  `7c13e1dbe9eb9f76ecacf2152db398f5e9085f8c648683625b2e0a390a280fe1`.
  This proves editing/export of synthetic manual content, not native generation.
- Native PDF preview showed three print pages. “Save as PDF” opened the OS save
  panel, but Save remained disabled after filename/location attempts. It was
  cancelled. No saved PDF file, glyph integrity or final pagination was validated
  in that manual-document attempt.
- The short generated document also showed Save as PDF disabled. Its **Open in
  Preview** print action did create a real `Noye.pdf` in the printtool temporary
  Group Container. Native Preview showed one page; the actual screenshot visibly
  retained both measured values and readable Korean glyphs without app navigation.
  Direct file reading was denied by OS permissions, and Preview's separate-save
  panel stayed disabled even after choosing the QA output folder and typing a
  filename. Both save failures were retained and cancelled. No standalone PDF
  copy, byte hash or long-document pagination pass is claimed. PDF rendering has
  this narrow positive observation; direct native PDF saving remains unaccepted.
- Relaunch retained the source bytes and saved body, with a new healthy backend
  port. Normal Cmd-Q stopped the QA app/backend and kept external Ollama/Qdrant
  running. SIGTERM recovery tests are recorded separately from normal quit.
- Native backup produced an 11,417-byte ZIP with a verified v1/schema-10 manifest,
  database and uploaded PDF. ZIP chooser accessibility timed out after Open;
  the human confirmed Restore was enabled, and a later native state showed
  “Backup verified and restored into a new folder.” The record does not attribute
  the restore click to the agent. The restored PDF and document match the original,
  SQLite integrity is `ok`, the original remains READY, and the restore has zero
  chunks with an explicit rebuild-required status. Credentials, `.env` and vectors
  are excluded. This backup had **zero external roots**.
- Verified destination:
  `noye-restored-3265c255-c2f2-43d7-8714-0ba4eaecccd0` under Application Support.
  The native confirmation saved the selected path, stopped the previous backend
  and started the new backend on 51314 with restored files/documents. The initial
  built-in restart had no accessible window; the human confirmed the missing
  window. A later ordinary launch had a blank frame before raising it exposed
  the workspace. Merely showing/focusing on Ready did not fix the next built-in
  restart. These failures remain recorded.
- A subsequent packaged build reopened the restored document with Saved status,
  all 20 sections and the Korean marker. Missing restored service configuration
  was visibly reported; no credentials/environment were silently copied into it.
- With the Launch Services correction, original → previous restored workspace
  and restored → original workspace both automatically created accessible windows.
  Restored Settings showed its actual path and unavailable default services; the
  original reopened with the Chat screen and available QA services. This confirms
  the two native transitions, not every sleep/force-kill lifecycle scenario.

## Automated validation

- Backend `.venv/bin/pytest -q`: **1,030 passed, 19 skipped, 10 warnings**, 19.61 s.
  Skips include opt-in real-service checks; live observations above are separate.
- Backend `.venv/bin/ruff check app`: passed. The four heading/presentation change
  files pass `ruff format --check`; the whole-tree formatter reports 53 files
  requiring formatting, including pre-existing styles. No broad cleanup was made.
- Frontend `npm test`: **49 files, 366 tests passed**; existing React act warnings.
  `npm run lint`, `npx tsc --noEmit`, packaged static Next build: passed earlier
  in this change set; no subsequent product TypeScript edits.
- Native `cargo test`: **8 passed**; `cargo fmt` and
  `cargo clippy --all-targets -- -D warnings`: passed after the launcher change.
- Actual v8 frozen backend `NOYE_TEST_SIDECAR=... pytest app/tests/test_desktop.py`:
  **10 passed, 7 warnings**, 11.22 s. The native-only launcher rebuild reused that
  identical backend and validated static UI; final bundle **68.08 MiB**.
- `git diff --check`: passed. Coverage percentage was not measured. Signing,
  notarization and cross-platform validation were not performed.

## Remaining acceptance

Keep §17.10 and the MVP checklist open. Priorities are native PDF saving and
original-link destination; complete bilingual source-document/Wiki quality;
representative retrieval/chunk calibration; native folder ingestion, filing,
rename/move, stale/history/scoped citations, cancellation/restart and portable
restore with external reconnection; model download failure/cancel/retry and OS
credential/provider persistence; cloud latency with explicit real access; long,
image-only/missing PDFs and physical IME/disconnect/screen-reader checks.

Unit/API checks and this small invented corpus do not replace those workflows.
