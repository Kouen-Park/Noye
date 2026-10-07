# Wiki core acceptance record

This record distinguishes deterministic behavior checks from actual local model quality.
All original documents used here are invented English/Korean HELIOS material. No user
folder, private document or cloud model was used for these checks.

## Automated regression, 2026-10-07

- Backend: **887 passed, 19 skipped, 9 warnings, 21.78 seconds**. Normal settings were
  retained; availability-marked Ollama/Qdrant checks were explicitly skipped by the
  one-off collection plugin below because live inference is measured separately.
  Loopback sidecar startup/shutdown tests ran with filesystem/network permission.
- Frontend: `npm test -- --maxWorkers=1`: **242 passed, 36 files, 30.61 seconds**.
- After final preview/navigation fixes: **12 Wiki frontend tests passed**, 3 files,
  2.36 seconds, followed by lint/type checking and a successful desktop static export.
- A's later collision-retry integration: **5 filing tests passed**, 0.56 seconds,
  followed by `ruff check app desktop.py`. The full backend count above precedes that fix.
- `npm run lint`, `next typegen`, `tsc --noEmit`: passed after the revision/scope fixes.
- `ruff check app`: passed; the evaluation harness and recovery files pass formatting.

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
                    reason="Live services measured separately in Wiki evaluation"))

raise SystemExit(pytest.main(["-q", "app/tests"], plugins=[SeparateLiveChecks()]))
```

Run that snippet from `backend` using the project's Python environment. It changes no
production settings or checked-in tests. The skipped checks include native frozen-binary
acceptance requiring an explicit binary path. A records that check separately.

The six Wiki test modules exercise the real folder registry, scanner, extraction,
SourceCatalog/EvidenceReader, immutable SQLite revisions, Markdown publication and durable
worker. Controlled Ollama responses verify complete long English/Korean inputs, fabricated
IDs/non-verbatim quotes, actual synthetic PDF pages, all/empty/chosen scope, changes during
inference, external/user-edit conflicts, cancellation/restart, partial artifact retention,
root resume/cancellation races and portable backup/reconnect conflict preservation.

The final self-review found and corrected same-version cancellation event loss, partial
root resume duplication, old events for removed sources, revision-stale relation display,
  historical content surviving a material-scope change and portable Markdown navigation
  losing its browser target/scope. Focused regression tests verify
each behavior. This was a self-review, not an independent review or security audit.

## Local model measurements

`python -m app.evaluation.wiki --output /path/report.json --workspace /path/synthetic-qa`
uses actual folder scanning, extraction, local `embeddinggemma`, in-memory Qdrant,
the production Wiki pipeline and local `qwen3.5:4b`. `--resume` requires the same retained
corpus/configuration and verifies earlier saved revisions before skipping completed work.
Only this invented corpus's model responses are saved in reports; production code does
not log excerpts or response bodies.

Hardware: Apple M2, 8 GiB RAM. Generation model: `qwen3.5:4b`, local Q4_K_M model;
Ollama 0.34.2 for the resumed run. Generation uses 2048 output tokens, temperature zero
and thinking disabled. The v3 acceptance uses the existing context setting explicitly
set to 8192 for this QA run; the application's default remains 16384. No automatic context
change, clipping, model replacement or cloud fallback occurs.

- [Prompt v1 report](wiki-live-v1.json): three summaries took **137.21, 80.35 and
  281.82 seconds** under concurrent QA load. Saved evidence supports 37 litres,
  29 litres on Sundays and unknown price. Classification was Learning/Unclassified/
  Unclassified. It produced **zero links and no shared topic page**, and translated the
  Korean summary into English. Reusable topic/tag instructions were improved afterward.
- [Prompt v2 request failure](wiki-live-v2-timeout.json): all originals indexed READY;
  no Wiki output published. The pipeline reported local model unavailable/busy. The report
  does not establish the underlying timeout/memory cause or a measured failure duration.
- [Prompt v2 rejected output](wiki-live-v2-invalid.json): an actual completed model
  response failed exact quote/ID validation; no revision published. Validation was retained.
  Prompt v3 strengthened verbatim copying and schema-enumerated allowed IDs.
- [Prompt v3 report](wiki-live-v3.json): initial English baseline completed in **69.65
  seconds**. The retained process was paused for A's native ingestion QA and disappeared
  across interruption; completed output was retained and the harness resumed remaining
  sources with matching settings. English alternative completed in **87.30 seconds** and
  Korean source in **166.08 seconds**, including relation calls. All three originals were
  READY. Three source pages and one shared project page were published with three typed
  edges: alternative → baseline (`alternative`), Korean → baseline (`supporting_evidence`),
  Korean → alternative (`alternative`). The project has three contributor IDs and two
  generated revisions, with no duplicate project identity. Suggestions were Learning /
  Unclassified / Learning. Exact source/hash/version, quote membership and target IDs passed
  production validation. Manual comparison preserved 37/29, the Sunday restriction, manual
  versus electronic valves, not-deployed status and unknown price rather than zero.

The v3 Korean source still received an English summary despite the source-language prompt;
the exact quotes remain Korean. The translation uses “distributed” for deployment. This is
an observed language/wording quality limitation, not a claim of faithful Korean wording.
There was no real-model contradiction example in this corpus; all four relation types are
covered with controlled output in integration tests.

Exact quote membership verifies provenance. It does not prove every paraphrase or relation
interpretation is semantically correct. These small smoke checks are not a broad quality
benchmark or a latency guarantee; the 8 GiB host showed substantial concurrent-load effects.

## Native integration and limits

A confirmed actual packaged native ingestion of TXT, Markdown and a two-page PDF on
2026-10-07, all READY, retaining the pre-existing TXT's ID. A owns native selection,
filesystem filing and the shared worker/migrations/backup. B uses those actual services;
production Wiki code has no fixture adapter. B's synthetic PDF page-grounding test used
real extraction with controlled generation, not a real model quality evaluation of PDFs.

Real user PDF quality, a broad multilingual/model benchmark, physical
external-drive removal and native Wiki PDF export remain unverified. Phase 7.5-4 question
orchestration and 7.5-5 original-driven document generation are outside this implementation.

Earlier broad live-service runs experienced model/sidecar timeouts on this host; a run
with overridden service URLs also invalidated defaults-sensitive tests. Those runs are
not presented as successful regression runs. The final deterministic suite above retained
normal defaults and separated actual model measurements explicitly.

## Actual browser acceptance

The production FastAPI service ran on port 8107 against the retained real synthetic folder
database. The Next.js 16.3.8 desktop static export ran on port 3107:

```sh
NOYE_DESKTOP=1 NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8107 npm run build -- --webpack
```

No mock API was used. Browser QA deliberately set the local model URL to an offline
loopback port after live measurements, to verify visible model errors without concurrent
native inference. Source indexing remained READY. The old baseline generation identity
predated the added manual-category key, so its refreshed job failed against that endpoint;
the existing generated page/artifact survived. The other two source jobs reused committed
revisions and completed. Explicit frozen retry created another visible failed attempt.

Direct Chrome observations on 2026-10-07:

- Source/project lists, Markdown body, original Korean evidence, typed edges and backlinks
  displayed. `Open original` returned HTTP 200 with unchanged Korean bytes.
- A Korean authored draft survived navigation to a different page and back. Save produced
  a `user` revision while retaining the generated revision (history count two) and cleared
  the local draft. Save as analysis created `832b9865-e3bf-5684-a314-2889c91b4d0d` with the
  exact contributor Wiki/revision ID. An API read confirmed its persistence.
- Empty scope hid the body and page list and disabled all generation controls. Selecting
  only the Korean source showed its summary/analysis, omitted the other originals/project
  and exposed no out-of-scope relations.
- The project Markdown's portable `Source Wiki` links were mapped only for verified
  contributor IDs. Clicking one opened the actual source page in a new tab with the same
  explicit chosen scope; no file-like `/sources/...md` route or scope expansion occurred.
  Generated comment metadata is hidden in preview and retained in authored Markdown.
- At 390 × 844 light mode and 1280 × 900 dark mode, document scroll width equaled viewport
  width. The observed narrow mobile error text was corrected: status width became 316px
  and action buttons moved to the following line. The rebuilt export was reloaded and
  visually inspected.
- No JavaScript console errors after the final reload. Three font-preload warnings remained.
  Empty-scope reads intentionally returned a visible HTTP 409 and did not expose content.

Browser acceptance did not exercise a native Wiki window or native Wiki PDF printing.
The real native PDF check reported by A is ingestion, not Wiki generation/print quality.
