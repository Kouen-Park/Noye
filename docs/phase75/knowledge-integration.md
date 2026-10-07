# Knowledge integration acceptance

Phase 7.5 stage 2 A starts from merged `dc80189` (PR #59) in an isolated
`feat/knowledge-integration` worktree. Existing uploads, answer-driven document
creation and the stage-1 folder/Wiki services remain in place. B's actual source
creation, revision/editor and chat intent services are integrated, not fixture
adapters. The [shared contract](integration-contract.md) and
[document contract](source-documents.md) identify the boundaries.

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

## Automated checks, 2026-10-08

The last full backend regression before B's final request-list presentation fix:
**943 passed, 19 skipped, 10 warnings, 18.68 seconds**. Normal application settings
and production timeouts were retained. A one-off pytest collection plugin explicitly
skipped availability-marked Ollama/Qdrant checks while actual inference was measured
separately. This is not a claim that those skipped service tests passed.

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
Ollama; the uncontended run above passed without extending the three-second test
startup deadline. One earlier retry test also depended on a globally stopped worker;
its fixture now creates a fresh worker. Neither failed run is counted as acceptance.

After B's final history/partial-result fix (`e9a06a9` on A):

- `ruff check app desktop.py`: passed.
- `pytest` for `test_source_documents`, `test_source_session`,
  `test_knowledge_maintenance`, `test_knowledge_portability`, `test_knowledge_query`,
  `test_wiki_jobs_api`, `test_workspace_backup`, `test_local_ollama`:
  **75 passed, 7 warnings, 2.55 seconds**.
- `npm test -- --maxWorkers=1`: **252 passed, 39 files, 22.91 seconds**.
- `npm run lint`, `next typegen`, `tsc --noEmit`: passed after that integration.
- The last historical-navigation fix then passed **11 focused frontend tests**,
  two files, 28.74 seconds, plus lint and TypeScript. All/root navigation now uses
  frozen source IDs; a scoped historical revision opens even if the current page
  gained outside contributors. Current relations are excluded from historical view.

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
original “stores 92 litres.” Treat that historical v6 result as a **quality failure**,
not accepted source fidelity. The final integrated `source-document-v2` pipeline
retains actual verbatim originals when cross-source entailment fails and explicitly
marks unresolved synthesis/translation. Controlled tests verify that behavior;
a fresh real-model acceptance is recorded separately by B. Do not infer successful
quality from an artifact pointer, a model entailment check or processed-character count.

## Desktop build and native observation

Before the final `e9a06a9` request-list/UI wording fix:

- `npm run desktop:prepare`: passed. PyInstaller 6.22.3/Python 3.14.7 frozen arm64
  sidecar build: 31.129 seconds. Next 16.3.8 Webpack static export: 10 routes,
  4.3-second compilation and 2.2-second type check.
- Tauri debug application build: passed, 10.76-second incremental Rust build;
  separate `Noye Knowledge QA.app` bundle, 92.79 MiB. QA identifier
  `com.noye.knowledgeqa20261008` isolates data and Keychain namespace.
- `NOYE_TEST_SIDECAR=<built arm64 sidecar> .venv/bin/python -m pytest
  app/tests/test_desktop.py -q`: **10 passed, 7 warnings, 21.47 seconds**.
  Actual frozen private-control/configuration/start-stop protocol was exercised.

The real native QA window and Settings were observed. Local Ollama/Qdrant service
availability and installed generation/embedding models were visible. The workspace
backup chooser opened, but selection/restore was not confirmed. Subsequent UI calls
failed with “Sky Computer Use service startup request failed” and kernel timeout.
The dedicated QA app/sidecars were then stopped; B's Ollama daemon was retained.

**Not validated in stage 2:** native restore/reconnect → folder query with Wiki links
→ document creation → edit/save → actual Markdown/PDF files; Unicode/long PDF
pagination; physical external-drive removal; broad real-data faithfulness/latency.
Stage-1 native TXT/Markdown/two-page PDF ingestion, moves, interruption and folder
controls remain recorded in [folder acceptance](folder-foundation.md); they were not
rerun here. A file chooser, build or successful print request is not exported-file proof.

## Review and remaining acceptance

The integration self-review corrected publication transaction boundaries, unstable
Wiki URL scope identity, historical link inventory/current-page dependence, paused filing inside the move lock, pending-journal cleanup,
cloud-model alias checks, cloud requests with connected originals, terminal stage
loss, worker-test isolation and restored approved-trigger handling. Their focused
regressions passed. B's own review corrected document entailment fallback, provenance
revision export and conversation history filtering. No independent review is claimed.

The branch already includes B's feature commits and A's final shared wiring. Review
and merge the combined knowledge PR first when separately authorized; avoid duplicate
B migration/registration patches. Remaining acceptance is the actual native full
workflow and fresh/broader model/PDF quality, with B's document validation record.
Phase 7.5 stays incomplete until those checks are recorded. No main merge or history
rewrite is performed by this work.
