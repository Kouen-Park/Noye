# MVP validation — 26 September 2026

This pass follows merged PR #35, starting at `e8dfa91`. It verifies the local
stack, not a packaged desktop build. It does **not** certify the entire MVP.

## Environment and isolation

- Qdrant 1.19.1, started with `docker compose up -d qdrant`.
- Existing Ollama 0.34.2, `embeddinggemma` (768 dimensions) and `qwen3.5:4b`.
- API on loopback port 8000; production Next.js server on loopback port 3000.
- Dedicated SQLite databases under `/private/tmp/noye-mvp-*-20260926.db` and
  Qdrant collections `noye_mvp_validation_20260926` and
  `noye_mvp_browser_20260926`; the user's library database was not used.
- Synthetic three-page PDF: graph basics, Dijkstra's priority queue rule on
  page 2, and a three-step release checklist on page 3.

## Automated checks

| Check | Observed result |
| --- | --- |
| Backend suite with unavailable service URLs | 507 passed, 19 skipped, 8 warnings in 4.37 s |
| Real citation pipeline and generated-document API, isolated rerun | 2 passed, 7 warnings in 89.60 s |
| Indexing suite against live Qdrant | 20 passed, 5 warnings in 3.31 s |
| Fresh-database startup regression | 1 passed |
| Backend Ruff | All checks passed |
| Frontend Vitest | 127 passed in 15 files |
| Frontend ESLint | Passed |
| Production webpack build and TypeScript | Passed |

Commands were run from their respective backend/frontend directories:

```sh
OLLAMA_BASE_URL=http://127.0.0.1:1 QDRANT_URL=http://127.0.0.1:1 \
  DATABASE_URL=sqlite:////private/tmp/noye-mvp-unit-20260926.db \
  LOG_TO_FILE=false .venv/bin/pytest app/tests/ -q -rs
.venv/bin/pytest app/tests/test_startup.py -q
.venv/bin/ruff check app
npm run test -- --run
npm run lint
npm run build -- --webpack
npx tsc --noEmit
```

Live tests used `QDRANT_COLLECTION=noye_mvp_validation_20260926`,
`DATABASE_URL=sqlite:////private/tmp/noye-mvp-validation-20260926.db` and
`LOG_TO_FILE=false`, with these pytest targets:

```text
app/tests/test_citations.py::test_full_pipeline_cites_the_page_the_fact_was_written_on
app/tests/test_documents_api.py::test_a_real_draft_is_markdown_and_editable
app/tests/test_indexing.py
```

The full live suite did **not** complete successfully. The first run was
interrupted after 644.76 s with 238 passed and 2 failed: an embedding timeout
and an Ollama generation HTTP 500 (`health ... EOF`). Both failed tests passed
when rerun in isolation. Memory pressure was observed (8% free), but this is
not proof of the failures' sole cause. A second full attempt was interrupted
after 119.48 s and 27 passes when Ollama became unresponsive again. The
service-disabled suite's skips are intentional, not live-service passes.

## Browser observations

- Created a document, edited Markdown including Korean text, saved with Cmd-S,
  reloaded, and confirmed persisted content. Preview rendered its heading,
  paragraph, list and Korean text.
- At a 390 × 844 viewport, the document Preview had `scrollWidth=390` and
  `innerWidth=390`; this is a narrow overflow check, not a full responsive audit.
- Clicked Markdown export and independently verified the HTTP export content
  matched the saved Markdown. A completed download on disk was not inspected.
- Uploaded the synthetic PDF through the API because the browser file chooser
  timed out. Initial ingestion failed during the Ollama slowdown. Browser Retry
  then reached READY with 3 pages and 3 passages.
- Browser deep index check reported a healthy index and all expected passages.
- Search for “How does Dijkstra choose the next vertex?” returned 3 results,
  with the matching fact on page 2 ranked first.
- Chat answered that Dijkstra selects the unvisited vertex with the smallest
  tentative distance using a priority queue. Its expanded consulted-passages
  list included page 2, and the answer persisted after reload.
- Created a three-bullet AI document from that answer in the browser. Edited
  the generated Markdown, clicked Save, and reloaded: edits and the three
  original citation labels remained.
- Deleted only the synthetic source through the API (HTTP 204). `/files` became
  empty, SQLite file/chunk counts became 0, and live Qdrant point count became
  0. The stored source copy was absent. Library showed its empty state;
  the generated document and its citation labels still existed. SQLite retained
  3 message citations and 3 document citations. Browser deletion-button behavior
  was not tested in this pass. The synthetic PDF can be recreated; no user
  source was deleted.

## Defect fixed

On a fresh database, the browser's concurrent `/files` and `/index/status`
requests raced while enabling SQLite WAL. `/files` returned HTTP 500 with
`sqlite3.OperationalError: database is locked`; the UI appeared disconnected.

`backend/app/main.py` now initializes WAL/schema in FastAPI lifespan before
accepting requests. `backend/app/tests/test_startup.py` asserts initialization
before the first request, then checks both library endpoints concurrently.
This addresses first startup in the normal single-process local server; it is
not a guarantee about simultaneous independent server processes.

## Remaining uncertainty and next work

- Complete full live-suite run under stable Ollama resource availability.
- Browser-native file selection/upload: chooser events timed out in this tool.
- PDF citation landing: correct `#page=2` URL observed, but the embedded browser
  showed a blank PDF surface. The visible target page was not verified.
- Printed PDF: Export PDF was clicked, but no print dialog/output was exposed
  by the embedded browser. Inspect a real printed PDF in a normal browser.
- No complete accessibility, light/dark visual-regression, or desktop packaging
  audit was performed.
- Phase 6 still carries follow-up question rewriting, similarity-threshold
  calibration and chunking measurements. Do not treat this report as Phase 7
  readiness or mark the printed-PDF acceptance item complete.
