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
