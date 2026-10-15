# Phase 8 acceptance progress — 2026-10-15–16

This supplements [the October 13–14 record](acceptance-2026-10-13.md), preserving
its failures and accepted cases. Work remains on `feat/mvp-end-to-end`, PR #64.
Origin was fetched again on October 16: `origin/main` is an ancestor of this
branch. This is progress evidence, **not Phase 8/MVP completion or merge approval**.

## Environment and isolation

Apple M2, 8 GiB RAM; Python 3.14.7, Node 26.8.1, Rust 1.99, Next 16.3.8,
Tauri 2.12.1 and Wry 0.57.0. Actual document runs use installed
`qwen3.5:4b`, Q4_K_M, digest
`2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.
QA context/output limits are 8,192/2,048 tokens, thinking off and temperature 0.
The product's 16k context default was not changed. Generation, embeddings and
heavy builds/tests run sequentially, with only one model loaded. These are
component measurements, not complete native request latency.

Ollama on loopback 11439 reads existing installed weights; no model there was
downloaded or deleted. Model-management tests use a separate store on 11449.
Sources, documents, conversations and keys below are invented QA data. No real
cloud request, production credential access, personal browser operation or OS
security-setting change was made.

Curated reports, source-response bodies, PDF renders and normalized command logs
are under [evidence/2026-10-15](evidence/2026-10-15/). `publication.json` records
original/published hashes and transformations. Repeated successful model-preflight
metadata is omitted with its original hash; generation responses remain unchanged.
Frozen-sidecar assertion output has its ephemeral QA control token redacted.
Runtime databases, model weights, environment files and backup ZIPs are excluded.

## Corrected failures

- **Proxy routing:** model pull/delete and local readiness requests inherited the
  process proxy environment. Owned HTTP clients now use `trust_env=False`.
  Regression checks use real loopback sockets and a rejecting fake proxy, rather
  than only inspecting constructor arguments. The initial two failing tests and
  the later readiness failure remain in the evidence. The final focused setup/
  proxy run passed 50 tests, 7 warnings, in 12.44 s.
- **Generated quantity properties:** the actual model sometimes changed explicitly
  stated capacity into actual stored volume, and approved its own mistake.
  Numeric-litre property guards now reject that swap independently of the model.
  Generated missing-evidence assertions also fail unless literally present in an
  original; the application owns read coverage. These narrow guards do not prove
  subject attribution, all units or arbitrary semantic entailment. Four pipeline
  regressions reject extraction/synthesis even when a fake verifier approves.
- **PDF image heading:** a seven-page native export put the image heading alone
  on page 5 and the figure on page 6. The standalone image and its heading now
  share an atomic print group, with a print-only 150 mm image-height bound.
  Original Markdown nodes and screen rendering are preserved. A renderer
  regression covers heading, image, caption and mixed inline image content.

## Actual document quality — still failing

The bilingual Alpha/Beta fixture distinguishes Alpha's **capacity of 37 litres**
from Beta's **92 litres stored**, different Sunday-write conditions and daily/
twice-daily backup schedules. An unrelated orchard source tests discovery scope.
The whole request and every model response are retained, including failures.

| Run | Seconds | Actual result |
| --- | ---: | --- |
| v11 English comparison | 291.878 | Partial; altered quantity and unsupported absence wording were approved |
| v12 English comparison | 378.332 | Partial; correct separate source notes did not form a comparison |
| v13 English comparison | 326.545 | Partial; storage synthesis rejected, original fallback retained |
| v14 English comparison | 263.209 | Failed, no artifact; capacity-to-stored swap rejected |
| v14 Korean whole collection | 267.126 | Failed, no artifact; same property swap at synthesis |
| v14 relevant English report | 85.347 | Failed, no artifact; same property swap rejected |
| v14 selected partial corpus | 164.795 | Failed, no artifact; generated wording violated requested English |
| v14 empty scope | 0.019 | Refused before inference, no artifact, explicit source selection required |

The v11 single-claim clinic matched 8/8 narrow rubrics in 51.908 s, but did not
predict whole-document quality. A later **14-case holdout matched 11/14** in
107.510 s: two faithful statements were falsely rejected and one unsupported
“stores … using log files” relationship was approved. The holdout changes
subjects, quantities and conditions; it is still a small synthetic sample.

A diagnostic with thinking enabled kept the same model and request limits.
All eleven semantic calls returned an empty `response` field and JSON-like text
in `thinking`, so the strict parser refused them. Three other cases were rejected
by deterministic guards. Total 137.777 s. Its eight matching negative rubrics
**are not eight successful semantic judgments**. No thought-channel salvage,
automatic retry, provider fallback or product-default change was introduced.

The current guards prevent these observed corrupt drafts from becoming new
documents; they do not make document generation successful. **P1: complete
bilingual comparison/collection quality and verifier false approval remain open.**
Do not weaken comparison acceptance, remove the guard or fit more phrases to this
fixture just to obtain a passing result.

## Actual inference and source controls

These use copied invented originals, real production handlers/SourceSession,
durable SQLite jobs and actual Ollama POSTs. They are not native force-quit or
physical power-loss tests.

- **Cancel:** cancel requested 0.404 s after an actual POST began. The in-flight
  call finished at 78.924 s; total 79.428 s. State moved cancelling → cancelled,
  no artifact was published and existing documents/messages/conversations matched
  their prior hashes. Cancellation is checked around model calls and is not an
  immediate HTTP abort.
- **Worker termination:** SIGKILL stopped only the owned QA Python worker after
  its POST began. Recovery marked the running job interrupted, did not replay it,
  preserved writing, and retained scope/manifest for explicit retry attempt 2.
  Server evidence shows this kill occurred during model loading, so it does not
  prove a kill during active token generation. The queued retry was cancelled.
- **Token-observed worker termination:** a later QA-only transport sent the same
  production intent request with `stream=True` to observe actual output bytes.
  After the first nonempty response token (one byte), the parent killed only its
  owned worker. Measured token-to-kill time was **1.741 s**; the script's nominal
  sleep was 0.5 s and is not the actual elapsed measurement. Recovery again moved
  running → interrupted, preserved all prior writing, did not replay, and retained
  scope/manifest for explicit retry attempt 2, then cancelled the queued retry.
  The raw report's note describes the nominal delay; the companion observation
  records this measured correction. Production remains `stream=False`; this is
  stronger CLI evidence, not packaged-app/physical power-loss acceptance.
- **Edit during inference:** the selected Beta original changed during an actual
  original-processing call. After 386.741 s, final publication refused the changed
  bytes; no artifact was created, prior writing remained exact and a current
  SourceSession read returned `stale_version`. The invented original was restored.
- Actual scope reads included all three sources and one explicitly chosen source;
  two outside-scope reads and an empty scope were refused. This is service-level
  evidence, not acceptance of every historical/native citation path.

### Actual PDF extraction, chunking and score probes

The production extractor and chunker processed the fixed seven-page native PDF
and ten text files assembled from the existing invented Atlas paragraphs. The
existing `app.evaluation.run.evaluate` dense-ranking harness measured eleven
hand-selected questions: nine answerable (including bilingual/cross-source,
two PDF table rows and the final sentinel), two negatives. Gold Atlas evidence
requires the full original paragraph in a chunk; PDF gold requires all specified
row/value/condition/token markers together. All sizes use 150-character overlap.
No personal library or production index was opened, and no answers were generated.

| Chunk size | Chunks | Recall@5 | nDCG@5 | Warm p50 / p95 ms |
| ---: | ---: | ---: | ---: | ---: |
| 500 | 42 | 0.8889 | 0.8889 | 16.95 / 20.96 |
| 1,000 (default) | 21 | 1.0000 | 0.9590 | 16.75 / 18.17 |
| 1,500 | 21 | 1.0000 | 1.0000 | 17.06 / 18.67 |

The 500-character variant missed the Korean T040 table question's gold within
five results. Additional full-ranking cosine probes at 0.3–0.9 found no sampled
cutoff that both refused the two negatives and retained gold for all answerable
questions. At the default size, 0.4 still admitted one negative; 0.5 rejected both
negatives but lost all gold for three answerable questions. Scores are not truth
probabilities. The short Atlas files often do not change shape between sizes.
Keep the default 1,000/150 and no newly imposed threshold. This closes a narrow
actual-PDF/chunker comparison, **not representative calibration**; eleven invented
documents and two negative questions cannot justify a general parameter change.

### Image-only, corrupt and missing PDF controls

A raster-only PDF embedded the seven reviewed native page PNGs without a text
layer. All seven rendered raster pages were rechecked visually. Actual scanner/
ingestion, SQLite, local embedding requests and in-memory Qdrant processed it
beside the text-layer original and a deliberately truncated 48-byte PDF.
This is a service/file test, not native picker or representative model quality.

The text PDF became READY in **2.296 s**, produced **11 points**, and SourceSession
retained all seven page numbers and the final sentinel. The image-only PDF failed
in **0.080 s**, with all seven pages empty to text extraction and an explicit
“needs OCR, which Noye does not do yet” message. The corrupt PDF failed in
**0.001 s**. Neither failed input produced vector points; current source reads
refused both as `not_ready`. A missing PDF raised `ExtractionError`.

The first QA inspector incorrectly accessed SourceSession dictionaries as objects,
after ingestion had already produced the expected READY/FAILED states. That
inspector failure/source are retained; the corrected inspector passed in a fresh
isolated workspace. It was a QA script fix, not a product extraction fix.

## Native PDF and first-open save panel

An API-seeded, editable 9,635-byte Markdown document was opened in the packaged
QA app and exported through Preview → Export PDF → macOS Save. It contains
Korean/English, a six-column/40-row table, 40 long wrapped code lines, 16 list
items, a quotation, bundled local SVG and final sentinel. It is independent of
the still-failing source-document generator.

Before: seven pages, 57,817 bytes. Fixed: **seven pages, 57,833 bytes**, SHA-256
`1a2c8b5ce9ff89f557c8d16688626e70de778533d2488b4fd2b5e743d4ed7b64`.
All fourteen before/after page renders were inspected. In the fixed output the
heading, complete image and caption share page 6. Every table row, code begin/end
marker, list item and final sentinel remains; Korean is readable, with no observed
clipped text or app chrome. Markdown's original hash remained unchanged.

An initial exact-substring diagnostic incorrectly marked wrapped `END\n-C001`
tokens missing. Whitespace-normalized diagnostics and visual inspection resolved
that test error; no code-clipping fix is claimed. Continued table pages do not
repeat their header, and long code may wrap across pages. This does not certify
arbitrary wide tables, external images, every printer or other operating systems.

The first earlier save panel needed filename edit + Tab to activate Save; its
cause was not isolated. A repeat panel enabled Save with the default name and was
cancelled successfully. The **first PDF panel in the freshly relaunched fixed
app enabled Save immediately**, and its default name saved without changing the
remembered QA directory. This narrows the first-open issue without establishing
universal destination behavior. The OS Original-link browser destination remains
unconfirmed; an HTTP 200 and valid original bytes do not prove OS navigation.

## Native first-run, preferences and model management

A separate compiled identifier, `com.noye.phase8firstrun20261015`, started without
a database, AI preferences, dismissed guide or credentials. Only loopback service
endpoints and the QA request limits were preconfigured in `.env`; this is not an
all-factory-default service-install test.

- The first guide selected local mode, recommended the installed 0.8b model,
  disclosed tight memory (8 GiB total, 1.4 GiB available estimate), reported missing
  embedding/Qdrant readiness and left the configured uninstalled 4b model unchanged.
  No automatic installation occurred.
- Native Settings saved installed `qwen3.5:0.8b`, then an explicitly created
  `noye-phase8-alias:qa` alias of the **same weights**. This checks switching and
  persistence, not two-model quality. An invented manual document and empty-scope
  conversation remained exactly equal before/after the model change and relaunch.
  The dismissed guide stayed closed and the saved alias remained selected.
- A broken proxy on **only the isolated Ollama server** caused native download
  failure and an explicit retry instruction. Removing that server proxy and
  clicking Download again completed the cached 0.8b installation check. It was
  not another full weight transfer.
- The real 2b pull reached an observed 0.35 GB of its 2.01 GB layer. Native Cancel
  showed cancelled and disclosed retained partial files. A new explicit pull was
  started, then the app quit while downloading. Its owned sidecar stopped, the
  external QA Ollama server remained and 2b was not installed.
- After relaunch there was no active/cancel-download control or automatic pull;
  the alias, document and conversation persisted. The original server had stopped
  when this session resumed: its log stayed at the prior three pull requests;
  the replacement owned server on the same store received zero pulls. This
  downtime qualifies the observation. A direct unauthenticated `/models/job`
  probe returned 403 as designed; Settings and server logs supplied the result.

Separate actual CLI lifecycle checks also preserve an initial retry failure
(67.621 s, cause unclassified), its later explicit cached retry (1.259 s), and a
second full run: forced failure 0.041 s, cancel 2.325 s after 4,287,476 bytes,
retry 23.682 s, then deletion of only the isolated QA model. A passing repeat does
not erase the first failure. Native deletion was not performed.

A fresh, synthetic Keychain service/item survived a child-process read, then was
deleted and confirmed absent. This checks the platform keyring, **not packaged
provider-key entry/authorization**. Native cloud keys remained absent; no cloud
requests or plaintext credentials were created.

No valid Developer ID identity was available. The linker-only QA bundle initially
failed strict bundle verification for a missing resource envelope. Adding an
ad-hoc envelope to only the FirstRun QA bundle passed `codesign --verify --deep
--strict`. This is a local development check, not trusted signing, notarization or
Gatekeeper distribution acceptance.

## Automated validation and build scope

| Check | Observed result |
| --- | --- |
| Full backend `pytest` with product coverage | 1,058 passed, 19 skipped, 26 warnings, 34.71 s |
| Final source-document regressions | 88 passed, 8 warnings, 14.01 s |
| Full locked frontend after image change | 52 files, 386 tests passed, 9.25 s |
| Focused image/preview/export controls | 19 tests passed, 1.27 s |
| Ruff, changed-Python formatting, ESLint, TypeScript | Passed |
| Rust tests / formatting / strict Clippy | 14 passed / passed / passed |
| Final frozen sidecar, overlapping Rust build | 1 failed, 11 passed, 47.52 s; 20 s readiness timeout |
| Same frozen sidecar, idle rerun | 12 passed, 7 warnings, 32.62 s |

Backend coverage excludes tests and does not enable subprocess coverage: lines/
statements **6,405/7,484 (85.58%)**, branches **1,651/2,144 (77.01%)**. Frontend
product coverage, measured **before** the final image change/386th test: statements
79.58%, branches 77.75%, functions 73.51%, lines 82.77%. A temporary matching
Vitest coverage provider changed transitive dependencies; `npm ci` restored the
committed lock tree before final tests/lint/types/build. No dependency manifest or
lockfile change is included. This is not final-image coverage or proof of live
model/native behavior. No configured backend type checker was run.

Final backend preparation: PyInstaller 32.025 s, static Next compilation 62 s plus
TypeScript 3.0 s; subsequent image build 63 s plus 3.1 s. Image bundle release
18.80 s; FirstRun bundle 19.46 s; each QA app about 68.31 MiB. The unbundled sidecar
is 57,227,360 bytes, SHA-256
`9eee463c6426b14fc42473e51047d723958f9f9199c771644ea148b651eed689`.
The busy-start failure is retained; broader cold/contention startup latency
acceptance remains open. An idle pass does not cancel that failure.

Final publication checks parsed the JSON reports, verified **117 evidence-file
hashes** and all **90 curated-copy hashes**, and found no credential-pattern
matches or unexpected runtime artifacts. The frozen failure's one ephemeral
control token was redacted before publication; its original hash remains.
`git diff --check` and a separate strict ad-hoc QA bundle verification passed.
PR #64 was still draft/open and reported no CI checks at inspection; absence of
checks is not a CI pass. The primary agent inspected the three focused fix diffs;
no new independent review pass is claimed.

## Remaining acceptance and merge condition

Keep §17.10 and the MVP checklist open. The explicit instruction was to merge
**after** all validations and fixes finish. P1 generated-document quality has not
met that condition. No completion or merge is claimed.

Still open: representative document/chunk/threshold calibration; broader
original/Wiki discovery and summary/link accuracy; full native folder/history/
stale-citation and failure paths; active-token native termination and physical
removable-drive/sleep behavior; physical IME/VoiceOver; OS Original-link destination;
packaged protected-provider credential authorization and actual cloud quality/
latency; trusted signing/notarization and other-platform distribution. Real cloud
tests require explicit test credentials/provider access and a spending limit;
distribution requires an available signing identity. Synthetic controls, a local
ad-hoc signature and automated skips do not satisfy those checks.
