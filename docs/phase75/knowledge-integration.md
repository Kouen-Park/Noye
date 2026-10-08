# Knowledge integration acceptance

Phase 7.5 stage 2 A starts from merged `dc80189` (PR #59) in an isolated
`feat/knowledge-integration` worktree. Existing uploads, answer-driven document
creation and the stage-1 folder/Wiki services remain in place. B's actual source
creation, revision/editor and chat intent services are integrated, not fixture
adapters. The [shared contract](integration-contract.md) and
[document contract](source-documents.md) identify the boundaries.

**Owner scope update, 2026-10-08:** remaining verification is deferred to Phase 8
(development plan §17.10). The feature implementations and already measured checks
below remain delivered; native restore/full-workflow, PDF and broader model-quality
acceptance remain unverified. Known language/heading/comparison limits are retained
as Phase 8 quality work. No failed or unconfirmed result is converted into a pass.

## Implemented behavior

- Real scanner/ingestion events enter the existing Wiki observer and durable worker.
  A wraps B's summary/classification service with authorized filing and final
  relation/topic refresh. Stage outcomes, skipped filing, errors and explicit retry
  are separate from ingestion status; partial saved artifacts survive later errors.
- Questions freeze all/empty/chosen source/root inventory before discovery. Wiki and
  one-hop topic links cannot expand it. Original extraction is re-read and hashed;
  lexical lookup finds precise details omitted from summaries. Wiki interpretation
  and old assistant claims cannot substitute for original facts. Stale/unavailable
  sources are excluded, while saved answer/Wiki revisions remain historical.
- SourceSession coordinates short original reads and artifact commits with app
  ingestion, filing, delete and rebuild. Automatic filing rechecks processing
  inside the move lock. Pending move journals block derived cleanup. There is no
  operating-system lock over arbitrary external writers.
- Installed local Ollama proof precedes original-context transmission. Connected
  original questions reject explicitly selected cloud providers instead of changing
  the provider. Upload-only explicit cloud chat retains its previous behavior.
- Additive migrations 8/9, query snapshots, stage events, source-document tables and
  router/handler registrations are integrated. Cancelled/interrupted stages survive
  restart and restore; active work is not automatically replayed.
- Backup includes authored Wiki and document revisions/user edits, link/version/
  source evidence, requests/cache and job histories. Actual external originals are
  excluded and reported. New-destination restore leaves external roots disconnected,
  interrupts active jobs and requires derived-index rebuild. Exact approved edit
  trigger SQL is preserved; an unrelated or hostile trigger is rejected.
- Folder controls distinguish disconnect, derived removal/rebuild and physical
  original deletion. Derived removal preserves original bytes/ID/version and saved
  authored work. Evidence UI shows scoped Wiki revisions beside original passages;
  current unavailability does not relabel a historical snapshot as current proof.

## Implementation follow-up, 2026-10-08

At the owner's request A/B divided remaining implementation while keeping actual
native/model/PDF acceptance in Phase 8. A completed three concrete navigation gaps:

- Wiki body links previously could omit/replace the selected scope. The shared
  renderer now accepts an optional rewrite policy; Wiki/editor/answer previews
  apply it after Markdown parsing, covering inline, reference and automatic URL
  links. Other local paths and unknown portable references render as plain text.
- Captured contributor, relation and backlink references now open the saved
  revision rather than silently displaying a later one. Historical answer links
  retain their frozen source IDs. Bodies, quotes, drafts and saved history are not
  rewritten, and the existing document renderer keeps its default behavior.
- Root-only and root/source-union selections now display correctly in the Wiki
  source controls. Deselecting one source retains the other selected members;
  explicitly empty scope cannot activate leftover root/source IDs.

B's feature commits are integrated as `255d459`, `58feaef`, `9367d66` and
`596562d`. New drafts apply conservative English/Korean script and Markdown-shape
checks to generated prose. A mismatch fails without a new artifact; explicit retry
clears unsafe cached stages. Source quotes and literal fallback retain their own
language. Bounded/cached heading checks plus application numeral/absence guards
replace unsupported titles with neutral labels and partial reasons, omit empty
sections, and mark comparisons without supported multi-source synthesis unresolved.
The document and chat card display these additive `coverage.presentation_limits`;
`metadata.output_contract` records what was checked. Prompt `source-document-v5`
and render `source-document-markdown-v3` apply to new drafts only. Existing saved
artifacts, revisions and user edits retain their prior bodies and metadata.

A's integration review found a source/output-language parsing error: “Write the
report in Korean from notes written in English” could choose the trailing original
language. B restricted overrides to output directives and added the reported
English/Korean regressions before final integration. Script checks are conservative,
can reject foreign names/technical headings, and cannot prove semantic language,
heading correctness or comparison quality. Actual quality and added inference
latency remain Phase 8 acceptance; no live-model claim is made for this follow-up.

Focused deterministic checks, from `frontend`:
`npm test -- --maxWorkers=1 src/lib/wiki.test.ts
src/components/wiki/wiki-editor.test.tsx src/components/wiki/wiki-view.test.tsx
src/components/chat/knowledge-evidence.test.tsx
src/components/documents/document-preview.test.tsx`: **32 passed in five files,
3.55 seconds** for the body-link change. Relation follow-up: **14 passed in two
files, 1.83 seconds**. Root-selection follow-up: **10 passed in one file,
1.37 seconds**. These overlap and are not added together. ESLint and TypeScript
passed after each code change. An initial TypeScript invocation from the repository
root printed usage because it had no tsconfig; the corrected frontend invocation
passed. The body-link commit's Next 16.3.8 static export built all 10 routes
(1,735 ms compilation, 2.2 s types). These checks do not establish new native,
actual-model or PDF acceptance. No model service or native QA app was started.

Final combined follow-up checks through `596562d`:

- From `backend`, `python -m pytest -q app/tests/test_source_documents.py
  app/tests/test_source_document_presentation.py app/tests/test_source_session.py
  app/tests/test_knowledge_portability.py app/tests/test_knowledge_query.py
  app/tests/test_knowledge_maintenance.py`: **68 passed, 8 warnings, 2.30 s**.
  Actual temporary files/catalog/evidence, jobs, SQLite and portability are exercised
  with controlled model responses. `ruff check app desktop.py` passed.
- From `frontend`, `npm test -- --maxWorkers=1 src/lib/wiki.test.ts
  src/components/wiki src/components/chat/knowledge-evidence.test.tsx
  src/components/documents src/lib/source-documents.test.ts src/app/chat/page.test.tsx`:
  **72 passed, 12 files, 8.31 s**; ESLint and `tsc --noEmit` passed.
- `npm run desktop:ui`: **10 static routes**, 1,593 ms compilation, 2.1 s types,
  234 ms page generation. B's last commit changes backend/docs only; the final
  frontend build includes both A's navigation and B's presentation-limit UI.

No fresh full suite, frozen backend/native bundle, actual inference or PDF acceptance
was run. Earlier full-suite and native records below remain historical measurements
of their stated commits. Shared server contracts/migrations are unchanged; new
presentation metadata uses the existing authored JSON/SQLite backup path.

## Automated checks, 2026-10-08

Final combined code through `ada721a`, including scoped per-source observations,
local proxy/redirect protection and model citation-label rejection:
**955 passed, 19 skipped, 10 warnings, 17.99 seconds**.
Normal application settings and production timeouts were retained. A one-off pytest
collection plugin explicitly skipped availability-marked Ollama/Qdrant checks while
actual inference was measured separately. This does not claim those skipped service
tests passed.

```python
import pytest

class SeparateLiveChecks:
    def pytest_collection_modifyitems(self, items):
        for item in items:
            if any(
                any(name in str(marker.kwargs.get("reason", ""))
                    for name in ("Ollama", "Qdrant"))
                for marker in item.iter_markers("skipif")
            ):
                item.add_marker(pytest.mark.skip(
                    reason="Live services measured separately in knowledge evaluation"))

raise SystemExit(pytest.main(["-q", "app/tests"], plugins=[SeparateLiveChecks()]))
```

Run from `backend` with the repository Python environment. An earlier overlapping
run had two desktop lifecycle timeouts while B's tests/startup watcher also loaded
Ollama; the uncontended final run passed without extending the three-second test
startup deadline. An earlier retry test depended on a globally stopped worker;
its fixture now creates a fresh worker. Failed runs are not counted as acceptance.

- `ruff check app desktop.py`: passed, including the subsequent v4 fix.
- `npm test -- --maxWorkers=1`: **259 passed, 40 files, 22.71 seconds**.
- `npm run lint`, `next typegen`, `tsc --noEmit`: passed on that source.
- Historical-navigation and archive-selection regressions also passed in the
  focused UI run: **20 tests, four files, 3.01 seconds**, plus lint/types.
  All/root historical navigation uses frozen source IDs; a saved revision opens
  even if the current page gained outside contributors. Current relations are
  excluded from historical view. Invalid selected archives display the restore
  service error without claiming success or switching workspaces.

After B's `540a740` observation fix was integrated as `c5b14ba`, the controlled
source-document/session, maintenance/portability/query, Wiki-job, workspace-backup
and local-model-boundary suite passed **76 tests, 8 warnings, 2.16 seconds**; Ruff
passed. Its new regression rejects publishing an unsupported per-source “other
project does not exist” observation while retaining source/batch/evidence provenance
and `verified=false` in audit metadata. No model, native app or desktop build was
started during B's reserved model slot.

A subsequent transport audit found that loopback URLs still honored environment
HTTP proxies. B's document fix is integrated as `d8e36ab`; A's `7b20a6a` also makes
owned Wiki/question/original-embedding and installed embedding-digest clients bypass
proxy environment and disable redirects. Explicit legacy cloud-provider transport
behavior is retained. Two real loopback servers (direct and spoof proxy), with
`NO_PROXY` cleared, verify preflight and synthetic original requests reach only the
direct server, and redirects never send them to the other server. These are actual
HTTP transport checks with controlled responses, not real Ollama inference.

After these changes, the local-proof/document/session/query/portability suite passed
**57 tests, 8 warnings, 1.86 seconds**. The generation/cloud/embedding/identity/Wiki
suite passed **96 tests, 7 explicitly separated live skips, 7 warnings, 0.83 seconds**.
Ruff passed for the full app and desktop entrypoint. The actual-document evaluator's
`--help` confirms `--retry-job`; its attempt-specific reports preserve earlier
failures instead of replacing them.

The targeted checks use real synthetic filesystem/SQLite/extraction and controlled
model/search responses. They verify scope escape attempts, empty scope, stale/missing
sources, details omitted from Wiki, previous assistant exclusion, user-edit preservation,
publication conflicts, busy maintenance, paused filing, cancellation/restart histories,
immutable retries, same-artifact edits and restore into a new destination. The combined
portability check saves real folder/Wiki/document/query data and legacy document edits,
then verifies restored histories, quote/version hashes, authored bytes, disconnected
roots and interrupted jobs. Actual frozen-binary lifecycle checks are separate below.

## Actual local-model comparison

[Recorded responses](knowledge-live-v1.json) come from the real production retrieval
and Wiki-original query route on identical invented HELIOS sources and questions.
The reference contains the actual stage-1 Wiki/topic revisions and a user-edited Wiki.
The evaluator creates a real backup, restores into a new temporary workspace,
reconnects only copied invented originals and runs real local extraction/embedding.
It uses in-memory Qdrant with the production retrieval implementation, not the
persistent native Qdrant service. No private user material or cloud model is used.

```sh
GENERATION_CONTEXT_TOKENS=8192 .venv/bin/python -m app.evaluation.knowledge \
  --reference /private/tmp/noye-wiki-ui-v3-20261006 \
  --workspace /private/tmp/noye-knowledge-qa-20261008 \
  --output ../docs/phase75/knowledge-live-v1.json
```

Apple M2, 8 GiB RAM, macOS 27.0.1 arm64; Ollama 0.34.2;
local `qwen3.5:4b` (4.7B, Q4_K_M), `embeddinggemma`, temperature zero,
thinking disabled, 2048 output tokens. QA explicitly uses 8192 context tokens;
the application's 16384 default is unchanged. Three originals indexed READY in
9.957, 9.521 and 18.271 seconds. Source IDs and SHA-256 versions survived backup,
restore and reconnection; the changed/missing check restored the invented bytes.

| Same question/scope | Baseline generation (s) | Wiki-original generation (s) | Observed result |
| --- | ---: | ---: | --- |
| Exact capacity/Sunday exception, all | 22.273 | 16.206 | Both retain 37 litres and 29 litres on Sunday |
| Cross-source designs, all | 20.473 | 38.197 | Manual baseline, electronic alternative not deployed, price unknown |
| Exact detail, chosen baseline | 35.680 | 5.297 | Only the chosen original/source Wiki; no outside topic contributors |
| Korean exact detail, chosen Korean | 23.326 | 4.901 | 37/29, Sunday condition and unknown price retained in Korean |
| Empty | 0 | 0.005 | No Wiki/original passages or model calls |

Retrieval and full outputs are recorded separately in JSON; these figures are
**generation time**, not end-to-end time or a universal speedup. Changed and missing
originals after indexing yield zero current passages and Wiki pages, explicit
insufficiency and stale/unavailable warnings. Controlled tests additionally cover
out-of-scope relation links and changes during generation/publication.

Manual reading confirmed the listed facts, but not every possible claim. The new
English answer adds “daily” to the capacity wording; the baseline cross-source answer
introduces an unnecessary zero-price interpretation before denying it as a fact.
Those outputs need editorial review. Five small synthetic questions do not prove
faithfulness, broad retrieval parity or quality on real PDFs. Wiki is still an
interpretation and exact assertions require original review.

## B document quality evidence

B's real synthetic Alpha/Beta generation reached a saved partial v6 artifact after
rejected attempts. Manual review found “total capacity 92 litres” stronger than the
original “stores 92 litres.” That historical v6 result is a **quality failure**.

Corrected real `source-document-v2` collection/report runs saved explicit partial
artifacts in **366.581** and **481.641 seconds**. Collection processed both selected
originals; report selected two of three initial sources, excluding the unrelated
orchard. All 11 saved citations matched actual original byte hashes and quote spans.
Verbatim fallback avoided the stronger capacity wording, but duplicate paragraphs,
empty headings and requested-language failures prevent document-quality acceptance.
Eight and 14 structured model stages also demonstrate a material latency limit
on this host; coverage is not evidence of comprehension or polished output.

The integrated `source-document-v3` change deduplicates retained original
paragraphs and asks for a compact topical outline. Controlled regressions pass;
B then reported an actual v3 comparison in **164.835 seconds**, with both originals,
three topical sections and seven verified citations, saved as partial. Review found
that per-source “other project information absent” observations were published as
collection conclusions. B's focused fix, integrated as `c5b14ba`, excludes these
unverified observations from authored content, retains scoped audit metadata, and
makes each bounded extraction call's limits explicit. The prompt is now
`source-document-v4`, with `source-document-markdown-v2` rendering. Its controlled
regression passes. B subsequently reported an actual v4 partial retry in
**281.427 seconds**, preserving the same request and four frozen entries: two
readable originals processed, an empty TXT marked indexing_failed and a missing
placeholder marked missing; six valid citations and no published unverified absence
memo. A v4 collection failed closed in **63.834 seconds**; explicit attempt 2 saved
an explicit partial artifact in **104.630 seconds**, processing both originals with
five valid citations and one retained Beta original paragraph. Requested-language,
comparison and heading quality acceptance remains open.

B's final measured record is integrated as `83f2453`: 29 saved v2/v3/v4
citations matched actual original hashes and quote spans. A real v4 user edit and
same-generation-request replay retained the current user revision and document
count. Selected Markdown files were 1,478 / 5,589 / 1,343 bytes. The final 66,923-byte
archive restored all six artifacts, current bodies/revisions, user edits and evidence
exactly into a new destination, with external roots disconnected. These are B's
actual service/artifact checks, distinct from native UI and model-quality acceptance.
[B's validation record](source-document-validation.md) includes the initial browser
observations and final six-artifact recovery. It distinguishes those observations from native/PDF work.
Do not infer successful quality from an artifact pointer, model entailment or a
processed-character count.

## Desktop build and native observation

Final combined code through `ada721a`, including the v4 observations, local
transport and reserved citation-label fixes:

- `npm run desktop:prepare`: passed. PyInstaller 6.22.3/Python 3.14.7 frozen arm64
  sidecar build: **30.941 seconds**. Next 16.3.8 Webpack static export: **10 routes**,
  **1.156-second compilation** and **1.009-second type check**.
- Tauri debug application build: passed, **4.64-second** incremental Rust build;
  separate `Noye Knowledge QA.app` bundle, **92.79 MiB**. QA identifier
  `com.noye.knowledgeqa20261008` isolates application data and Keychain namespace.
- `NOYE_TEST_SIDECAR=<built arm64 sidecar> .venv/bin/python -m pytest
  app/tests/test_desktop.py -q`: **10 passed, 7 warnings, 23.83 seconds**.
  Actual frozen private-control/configuration/start-stop protocol was exercised.

The actual native QA window, Chat and Settings were observed in the archive-fix
build. The final package was rebuilt after the later transport/citation guards;
those build/control checks do not establish additional native UI acceptance.
An earlier session showed running local services and installed models. During the final chooser check,
Ollama/Qdrant were stopped and the UI correctly reported that state; no inference
is attributed to that session.

The original file input's `.zip` accept filter selected a valid backup and displayed
its ZIP preview but left **Open disabled**. A removed this advisory filter; strict
server archive/manifest/hash/path verification remains unchanged. The rebuilt native
chooser selected B's actual **49,415-byte** backup with **Open enabled**, twice.
Both an accessibility Open click and a keyboard Return dismissed the panel, after
which Sky observations/rebinding failed with `timeoutReached` or
`noWindowsAvailable`. Restarting only the isolated QA application restored UI access.
A one-second sample of that application's main thread showed the normal idle AppKit
run loop, which does not establish an application hang or successful file selection.
The native restore result therefore remains **unconfirmed**. The QA app and its own
sidecars were stopped; the model/build slot was returned to B.

**Not validated in stage 2:** native restore/reconnect → folder query with Wiki links
→ document creation → edit/save → actual Markdown/PDF files; Unicode/long PDF
pagination; physical external-drive removal; broad real-data faithfulness/latency.
Actual service/SQLite restore preserved six document artifacts and user edits;
that is distinct from the blocked native chooser workflow. Stage-1 native
TXT/Markdown/two-page PDF ingestion, moves, interruption and folder controls remain
recorded in [folder acceptance](folder-foundation.md); they were not rerun here.
An enabled chooser, build or successful print request is not exported-file proof.

## Review and remaining acceptance

The integration self-review corrected publication transaction boundaries, unstable
Wiki URL scope identity, historical link inventory/current-page dependence, paused filing inside the move lock, pending-journal cleanup,
cloud-model alias checks, cloud requests with connected originals, terminal stage
loss, worker-test isolation, restored approved-trigger handling and native ZIP
selection filtering. Their focused
regressions passed. B's own review corrected document entailment fallback, provenance
revision export, conversation history filtering, per-source observation rendering,
local document proxy bypass and model-written inline citation labels. No independent review is claimed.

The branch already includes B's feature commits and A's final shared wiring. Review
and merge the combined knowledge PR first when separately authorized; avoid duplicate
B migration/registration patches. Phase 7.5 implementation is delivered on this
combined branch. At the owner's instruction, actual native full-workflow
verification and fresh/broader model/PDF quality are open Phase 8 acceptance work,
with B's document validation record preserving observed failures. No main merge,
history rewrite or successful final acceptance is claimed by this work.
