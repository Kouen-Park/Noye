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
- **P1, native Markdown input:** macOS text substitutions changed `-->` into
  `—>`, breaking an existing Wiki's Markdown preview after a native edit.
  Disable autocorrection, capitalization and spellcheck on both Markdown editors.
  The same native whole-field edit subsequently saved the exact expected Wiki
  body, including the comment terminator and Korean memo; a document retained
  literal `--`, quotes and `->`. Physical typing/IME behavior remains untested.
- **P1, native exports:** a backup Blob download left the QA app inaccessible
  while its backend remained healthy. The one-second process sample showed the
  main thread waiting in WebKit sandbox-extension/download-policy work; this is
  an observation, not proof of the precise cause. macOS Markdown and backup
  exports now use an OS save panel and staged exclusive publication. The selected
  existing destination is preserved; cancellation/errors release the export slot.
  Backup ZIP bytes remain in the sidecar, reached only through private IPC, not
  an HTTP endpoint accepting a path. Web exports retain their download behavior.
  Native cancellation followed by saving succeeded for the backup; Markdown saved
  current unsaved text without requiring available AI services. Apple documents
  the panel in [NSSavePanel](https://developer.apple.com/documentation/appkit/nssavepanel);
  the command boundary follows [Tauri commands](https://v2.tauri.app/develop/calling-rust/).
- **P2, progress and counts:** completed checkpoint events no longer display as
  running; cancelled/interrupted checkpoints display stopped while explicit
  verdicts and skipped reasons remain visible. Native completion showed finished
  1/1. Disconnected roots no longer render a stray numeric `0`, confirmed in the
  restored native folder options. Search now distinguishes matching passages
  from the number of files searched; its targeted regression passed. The last
  packaged build predates that wording-only Search change.
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

## Native external folders and portable restore

The following used only the invented Alpha/Beta/Gamma/Delta/Orchard folder and
the earlier uploaded AT-201 PDF. The original folder and relocated copy are
separate test fixtures; reports are retained in
[native-folders](evidence/2026-10-13/native-folders/).

- Native folder selection detected the initial files and created source Wikis.
  Organization was enabled only inside `Course`; Beta and Gamma were filed to
  `Course/Unclassified`, while Orchard/Delta stayed outside the enabled area.
  A manual Alpha move/rename retained its source ID, bytes and manual category.
- A native user Wiki edit was saved before the original changed. Adding the
  Saturday read-only condition to Alpha produced a separate generated proposal;
  the current user title, body and revision remained unchanged. Native Details
  identified the older evidence as superseded, and the proposal exposed the new
  condition and Adopt action. It was inspected, not adopted.
- Native pause → disconnect → reselect retained the root and source IDs, Wikis
  and paused state. After normal quit, Delta was added to the invented folder;
  relaunch detected it but left it waiting while processing was paused. Resuming
  reached READY and created its Wiki. This is normal restart catch-up, not a
  sleep/wake or physically unplugged-drive test.
- The first attempted cancellation arrived after completion and does not count
  as a cancellation pass. A later changed Delta job was actually cancelled.
  Native Retry created a new job at attempt 2, retained the frozen manifest and
  completed. The cancelled record remained, the new Tuesday backup condition
  appeared, and filing stayed skipped outside `Course`.
- Native Save workspace backup was cancelled once, then saved after validating
  the test folder in the OS panel. The ZIP is **53,542 bytes**, SHA-256
  `af5065825656e12a508612778e4710c6fabc94be2b109b479579dbfd89e0ce6f`.
  Its 16 entries passed all manifest hashes and included the external root's
  authored assets. Credentials, `.env` and vector data were excluded.
- The agent selected that ZIP and clicked Restore into a new folder. SQLite
  integrity was `ok`; the five external source IDs and exact current user Wiki
  remained, roots were disconnected, and chunks were zero. Opening destination
  `noye-restored-d657aa45-ef26-4e86-a8c1-1263e8be83c2` created a responsive native
  window. Settings reported the actual path and unavailable default services.
- Native reconnection selected a relocated folder containing only the five
  synthetic originals, with no Wiki files copied into it. The same root ID was
  reconnected while paused; backup-authored Wiki files were recovered, including
  the exact user body SHA-256
  `61850315a3c5f46430e665f5d9667cac7c6f3b174e98422942a6aac6a8904b12`.
- A fresh secret-free QA `.env` was deliberately written afterward and the app
  normally restarted, using collection `noye_phase8_qa_restore_20261013`. This is
  manual test setup, not native service-settings acceptance or copied backup
  configuration. Native Retry rebuilt the PDF; Rebuild from original rebuilt each
  of the five reconnected sources. All six reached READY with one chunk each;
  Qdrant had six points. Both external fixture copies retained identical original
  bytes, source IDs/manual category survived, and the user Wiki revision remained
  current. Resume alone intentionally does not restore deleted indexes.
- Native Search displayed five passages from six searched files, with current
  Alpha first and both 37 litres and Saturday read-only intact. The identical API
  recheck is retained separately; native request latency was not measured. Clicking
  the original PDF link did not expose a destination in enabled browser/app
  inventory, so OS destination acceptance remains open.
- With restored AI services still unavailable, native Markdown export saved the
  current **unsaved** document text: **308 bytes**, SHA-256
  `72bd99d8ed1f742af07fd3cec14bb468ccccb39ffca889719cf6501d771d2008`.
  The saved notice appeared while the editor remained dirty; the database still
  held the previous body. Native Save then persisted the draft, and ordinary
  restart retained it. These exports are exact current-body copies, not an
  independent semantic approval of later user edits.
- The latest native PDF retry showed one print page. Save as PDF stayed disabled
  even after exact Go to Folder validation and filename input. Both dialogs were
  cancelled; no PDF file was retained. The earlier Preview rendering observation
  remains valid, but direct PDF saving is still unaccepted. Normal Cmd-Q closed
  the QA app/backend at the end of this pass.

Portable native ZIP restore with external reconnection and explicit index rebuild
is accepted for this synthetic case. The larger folder, generation, PDF, deletion
and device acceptance workflows remain open.

## Automated validation

- Backend `.venv/bin/pytest -q`: **1,039 passed, 19 skipped, 10 warnings**, 23.15 s.
  Skips include opt-in real-service checks; live observations above are separate.
- Backend `.venv/bin/ruff check app desktop.py`: passed. The four heading/presentation change
  files pass `ruff format --check`; the whole-tree formatter reports 53 files
  requiring formatting, including pre-existing styles. No broad cleanup was made.
- Later backup exclusive-publication/fsync refinements passed the focused
  **37-test** service run and final frozen-sidecar rerun below. The full backend
  suite above preceded those refinements.
- Frontend full `npm test`: **52 files, 379 tests passed**, 10.58 s; that run had
  no React act warnings. Later native backup-label changes passed 14 targeted
  tests, TypeScript and lint. Search wording passed its seven targeted tests,
  TypeScript and lint; it adds one test after that full suite.
- Native `cargo test`: **12 passed**; `cargo fmt` and
  `cargo clippy --all-targets -- -D warnings`: passed for native exports.
- Actual native-export frozen backend
  `NOYE_TEST_SIDECAR=... pytest app/tests/test_desktop.py`: the first run had
  **11 passed, 1 failed**, 56.76 s; cold managed-service startup exceeded 20 s
  while overlapping the static Next build. An idle rerun had **12 passed,
  7 warnings**, 32.84 s. The failed log is retained; broader startup latency
  acceptance remains open. PyInstaller took 31.0 s, static Next build 42 s,
  Rust release build 19.61 s; resulting native QA bundle **68.23 MiB**.
- `git diff --check`: passed. Coverage percentage was not measured. Signing,
  notarization and cross-platform validation were not performed.

## Remaining acceptance

Keep §17.10 and the MVP checklist open. Priorities are native PDF saving and
original-link destination; complete bilingual source-document/Wiki quality;
representative retrieval/chunk calibration; native folder ingestion, filing,
stale/history/scoped citations, unstable writes and interrupted inference;
broader backup/reconnection failures and removable volumes; model download failure/cancel/retry and OS
credential/provider persistence; cloud latency with explicit real access; long,
image-only/missing PDFs and physical IME/disconnect/screen-reader checks.

Unit/API checks and this small invented corpus do not replace those workflows.
