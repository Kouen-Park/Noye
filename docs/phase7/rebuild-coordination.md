# Phase 7 item 3: rebuild coordination

Started independently from `main` on 2026-10-05 while Phase 6 continues in its
own checkout. Merge Phase 6 first and refresh this branch before merging it.

A single-process maintenance guard shares the ingestion/deletion reservation
lock. It is acquired before reading the collection dimension and stays held
through the final background file. New uploads, retries, deletes, orphan cleanup
and duplicate rebuilds return 409 while it is held. Cancelling existing queued
or running ingestion remains allowed.

The ordinary rebuild still avoids a collection reset and skips already busy or
missing files. A dimension-changing rebuild refuses any active ingestion/deletion
before resetting. Every eligible file is reserved before the reset; a plan with
no eligible source does not erase the collection. Planning, reset, scheduling and
worker failures release the owned reservations and maintenance guard.

Validated on 2026-10-05:

- Full backend: `python -m pytest app/tests -q -p no:cacheprovider`, **518 passed,
  19 skipped**. Existing service integration checks skipped because Ollama and/or
  the configured Qdrant endpoint were unavailable.
- `python -m ruff check app --no-cache`: passed.
- Regression cases cover busy ingestion/deletion before a dimension reset,
  reservation-before-reset, reset failure cleanup, an empty eligible plan,
  duplicate rebuilds, guard lifetime across files, worker exceptions, rejected
  upload cleanup, retry/delete/orphan-cancel rejection and active cancellation.
- A separate thread holding the guard prevents ingestion/deletion/rebuild entry.

The guard deliberately supports one backend process. It is not a durable job
queue or a multi-worker lock; Phase 7 item 6 owns restart recovery and batch-level
cancellation. Packaged Tauri interaction and live dimension-changing rebuilds
were not tested; no personal index was reset.
