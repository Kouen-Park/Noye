# Integrating the first Phase 7 changes with Phase 6

Four independent draft PRs were started from `main` commit
`e8dfa912f1c3f5aab7d88b098451761e342c4c25` while desktop implementation continued
in a separate checkout. They do not include or overwrite unfinished Phase 6 work.

| Merge order | Draft PR | Scope |
| --- | --- | --- |
| 1 | Phase 6 desktop implementation | Complete and validate the desktop branch first |
| 2 | [#37](https://github.com/Kouen-Park/Noye/pull/37) | Publish Qdrant REST on localhost only |
| 3 | [#38](https://github.com/Kouen-Park/Noye/pull/38) | Coordinate rebuilds with ingestion and deletion |
| 4 | [#39](https://github.com/Kouen-Park/Noye/pull/39) | Record and enforce index compatibility |
| 5 | [#40](https://github.com/Kouen-Park/Noye/pull/40) | Establish reproducible retrieval comparisons |

Refresh each published Phase 7 branch by merging the updated `origin/main` before
its final review. Resolve conflicts, validate the resulting branch and push the
additional commits normally. Published branches do not need rebasing or force
pushes for this workflow. Keep ongoing desktop changes in their own checkout.

## What the integration preview actually tested

An isolated local branch, `codex/phase7-merge-preview`, started from the committed
Phase 6 snapshot `f1d7ced` (`docs: record desktop setup validation and remaining
work`). PRs #37, #38, #39 and #40 were merged there in that order, producing
`37df892641dfddc35aaef9e1793da4e079a1319f`. That first snapshot passed 644 backend
and 178 frontend tests, plus lint, types and both UI builds.

During validation, Phase 6's model-management, cloud-provider and macOS Keychain
settings changes were committed through `f943875`. Those three additional commits
were merged cleanly into the preview and the complete checks were repeated.
The final tested combined commit is
`c1b92053e129b1d3e4e2a0b602d093305b4b59e5`.

This covers committed Phase 6 code through `f943875`, not subsequent changes or
packaged-app acceptance. It is a local integration check, not a merge into `main`
or a new published feature PR.

PRs #37 and #38 merged cleanly. PR #39 had textual conflicts in four files:

| File | Resolution applied in the preview |
| --- | --- |
| `README.md` | Keep both the index compatibility/rebuild instructions and Phase 6's optional Gemini setup instructions. |
| `backend/app/config.py` | Keep `SecretStr`, desktop data-root settings and cloud generation settings; add `model_validator`, `CHUNK_SIZE` and `CHUNK_OVERLAP` validation. |
| `backend/app/api/chat.py` | Keep compatibility/readiness lookup inside the exception handler so failures are saved as chat turns; keep `provider=request.provider` when calling `answer_question`. |
| `backend/app/api/index.py` | Keep both the maintenance-conflict 409 handler from #38 and the embedding-identity 503 handler from #39. |

These resolutions are recorded in preview commit `11ced1b`. PR #40 then merged
cleanly. Files that merged automatically also need semantic review: ingestion
must retain desktop startup recovery and fingerprint checks, rebuild must retain
the maintenance guard and model preflight, and frontend API types must retain
desktop/provider contracts plus the compatibility fields. The preview retained
Phase 6's Next.js 16.3.8 dependency updates.

## Validation of the combined snapshot

Commands ran from the preview's `backend` or `frontend` directory, respectively.

- `python -m pytest app/tests -x -q --tb=short -p no:cacheprovider`:
  **688 passed, 19 skipped**. The default live-service integration checks skipped.
- `python -m ruff check app --no-cache`: passed.
- `npm test -- --reporter=dot`: **185 passed across 25 test files**.
- `npm run lint`, `npx next typegen`, `npx tsc --noEmit`: passed.
- `npm run build -- --webpack`: passed with Next.js 16.3.8.
- `npm run desktop:ui`: passed; the desktop static UI export completed.
- `git diff --check`: passed after conflict resolution.

The first sandboxed backend run could not open the preview checkout's startup
SQLite database because the managed worktree is outside the default writable
roots. Rerunning with permission to write that isolated worktree produced the
passing result above. This did not require changing production paths or the
user's database.

This preview does not validate a packaged native application, Phase 6 changes
after `f943875`, a real dimension-changing rebuild, or the production library.
Repeat the relevant checks after Phase 6 is complete and after each final merge resolution.
Phase 8 still owns broader stability/quality work and final packaged acceptance.

## Scope completed and remaining

The first independent work implements Phase 7 items **3, 4 and 8** and supplies
the evaluation foundation for item **10**. Item 10 still needs actual generated
answer/abstention review, representative data, embedding-input/chunking
comparisons and a measured decision on reranking. The other eight Phase 7
items remain separate work; this batch does not mark Phase 7 complete.

## Final ordered integration — 2026-10-05

The owner explicitly authorized this sequence after Phase 6 implementation was
complete at `ab225fd`. Original #37–#40 were closed and their `codex/` remote heads
deleted; their `feat/` replacements had exactly the same feature SHAs:

| Original work | Replacement | Original head |
| --- | --- | --- |
| Phase 6 | [#43](https://github.com/Kouen-Park/Noye/pull/43), `feat/tauri-macos` | `ab225fd` |
| #37 | [#44](https://github.com/Kouen-Park/Noye/pull/44), `feat/qdrant-localhost` | `bc21669` |
| #38 | [#45](https://github.com/Kouen-Park/Noye/pull/45), `feat/rebuild-coordination` | `10066cf` |
| #39 | [#46](https://github.com/Kouen-Park/Noye/pull/46), `feat/index-identity` | `a46a012` |
| #40 | [#47](https://github.com/Kouen-Park/Noye/pull/47), `feat/retrieval-evaluation` | `f550315` |

Each Phase 7 head was refreshed with the newly merged main in order, without
rebasing/force-pushing. Local exposure and maintenance merged cleanly. Identity
had the same four textual conflicts listed above; normal merge `9fe73f4` preserved
both sides. In README, "cloud setup" now includes all three providers and model/
service controls, not only the earlier Gemini milestone. Configuration retains
SecretStr, desktop snapshots and chunk validation; chat retains readiness inside
its saved-failure handler and explicit provider forwarding; index retains 409
maintenance and 503 identity preflight handlers. Automatic ingestion/rebuild/types
were inspected, and desktop lifecycle files/dependency manifests remain unchanged.
`38b9d05` adds eight all-provider/failure-preservation regression cases.

The resulting complete implementation is `f1cdc8b`, which also includes retrieval
evaluation. Fresh checks on that source (not the older preview above):

- Backend non-live suite: **734 passed, 19 skipped, 8 warnings**; Ruff passed.
- Frontend: **199 passed across 27 files**; ESLint and TypeScript passed. Route
  types, web Webpack build and desktop UI export passed on the identity snapshot;
  evaluation changes no frontend source, and final static export passed again.
- Native Rust tests: **3 passed** on unchanged native source; format and Clippy
  passed. Final unsigned Apple Silicon packaging: **67.53 MiB**.
- Final frozen backend: **10 passed**, using temporary data to check readiness,
  private configuration acknowledgement, control refusal, CORS and line/EOF exit.
- Model-free lexical CLI: Recall@5 **0.7143**, nDCG@5 **0.7656**, p50/p95
  **0.0467/0.0749 ms**. This is tiny synthetic ranking time, not AI/app latency.
- Compose config still publishes only `127.0.0.1:6333:6333`; diff checks passed.

No GitHub CI checks were reported; these are local checks. Earlier live reports
are historical, not fresh model runs. No personal container/index was recreated,
no model/key lifecycle or cloud inference was used, and no native GUI/PDF workflow
was inspected. Final listener bindings, live dimension-changing rebuilds, actual
generated-answer/abstention review, quality/latency and packaged acceptance remain
open. This integrates only items 3/4/8 and item 10's foundation, not all Phase 7 work.

## Evidence and document follow-up — 2026-10-05

The owner then authorized #41 followed by #42 using the same workflow. Both drafts
were closed and their `codex/` heads deleted, but identical `feat/` heads survived:
`dd04762` on `feat/evidence-snapshots` and `9a962c4` on `feat/document-evidence`.
The first replacement, [#48](https://github.com/Kouen-Park/Noye/pull/48), merged
normally as `5ea0e57`; the document branch refresh builds on that actual main.
An isolated temporary worktree keeps the separately active branch's edits intact.

| Refresh | Actual conflict | Resolution |
| --- | --- | --- |
| Evidence `78791ba` | `frontend/src/components/chat/passages.tsx` | Retain the shared desktop `PassageList` layout and render `SavedEvidence` across both grid columns. |
| Document `bba3864` | `backend/app/services/documents.py` | Keep one typed provider argument, `get_settings`, the loopback-only excerpt guard, cloud snapshot removal from temporary copies, and `generate(..., provider=provider)`. |
| Document `bba3864` | `frontend/src/components/documents/create-document-action.tsx` | Keep the provider selector and the local/cloud/legacy evidence disclosure together. |

Automatic API merges retain `provider=request.provider`. The evidence merge passed
743 backend tests (19 skipped), 207 frontend tests and both UI builds. Initial
environment-delayed timeout runs were repeated successfully without committed
timeout changes; the frontend passed using one thread worker and default limits.

Final implementation `5943ba7` adds four real-adapter mock transport regressions:
each selected provider is called exactly once; only local Ollama receives expanded
excerpts, and stored snapshots remain unchanged. Four creation-form UI regressions
also verify disclosure/selection and fix OpenAI/Claude being labelled local while
writing. Fresh checks on that complete source:

- `.venv/bin/pytest app/tests/ -q -m 'not integration'`: **755 passed, 19 skipped,
  8 warnings**; Ruff passed.
- `npm test -- --reporter=dot --pool=threads --maxWorkers=1`: **211 passed across
  28 files**; ESLint, route type generation and TypeScript passed.
- Web Webpack build and desktop static export passed. Fresh unsigned Apple Silicon
  packaging: **67.54 MiB**. Native Rust source is unchanged from the first batch.
- `NOYE_TEST_SIDECAR=<new app>/Contents/MacOS/noye-backend .venv/bin/pytest
  app/tests/test_desktop.py -q`: **10 passed**, checking the packaged backend with
  temporary data, readiness, private configuration, control/CORS and line/EOF exit.
- PyInstaller analysis includes both evidence modules and PyMuPDF metadata;
  diff checks passed. No personal data, actual model/key operation or cloud call
  was used. No native GUI or actual PDF output is claimed.

Items 1/2's implementations now join items 3/4/8; item 10 remains a foundation and
item 12's exports/PDF coverage remains pending. Final packaged-app acceptance is
still Phase 8, not inferred from a successful build or lifecycle smoke test.
