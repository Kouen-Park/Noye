# Phase 7 item 7: desktop workflow integration

This change builds on Phase 6's existing app-data root, owned sidecar lifecycle,
service controls, model installation/cancellation and Keychain preferences.

## Restored workspace selection

Settings → Workspace can explicitly open a verified restore. Save document edits
and confirm the switch; Noye stops its owned backend/services, then requests a
native restart. Both folders remain on disk. The selected path and previous path
are stored atomically in workspace-selection.json under the original app-data
root. AI preferences and Keychain credentials remain global to that installation,
outside the backup and independently of the selected data directory.

The chooser accepts the original location or a canonical, non-linked restored
sibling with the complete payload and valid versioned receipt. Backup restore
publishes the receipt last. Missing/invalid selected folders produce a startup
error and an explicit Reopen original workspace action; there is no silent switch
to another database. Settings also offers the original and previous workspace,
including returning to the previous restore after reopening the original location.

Existing desktop workspaces retain the noye_desktop collection. Each restored
receipt supplies a new UUID-derived collection, so its explicit rebuild cannot
reset or query another workspace's vectors. Existing advanced QDRANT_COLLECTION
overrides remain authoritative; choose distinct overrides when sharing Qdrant.
Restored originals remain FAILED until explicit re-indexing; saved writing and
historical evidence can be opened immediately.

## Readiness and generation limits

/runtime/setup distinguishes configured names, service availability, installed
models, indexing readiness and local generation readiness. Saved cloud-key
configuration does not prove API access: checking readiness makes no paid
generation request. Service/model controls remain explicit.

AI Settings loads secure preferences separately from runtime probes. A failed
readiness check leaves Workspace backup accessible and offers refresh. The
settings overlay preserves mounted chat/document drafts; only an explicitly
confirmed workspace restart closes unsaved text.

Local generation defaults to 16384 context tokens and 2048 output tokens, with
validated GENERATION_CONTEXT_TOKENS (2048–32768) and GENERATION_OUTPUT_TOKENS
(128–4096). Output plus a 512-token formatting reserve must fit in the context.
Noye rejects a prompt/system UTF-8 byte sum above the remaining budget before
inference, then supplies num_ctx/num_predict to Ollama. This conservative input
estimate is not exact tokenization or a measurement of the selected model's
maximum context; it may refuse some otherwise fitting multilingual requests.
Choose bounds suitable for the installed model and hardware. Noye does not trim
source evidence or retry/switch providers. Explicit unfinished/output-limited
local responses are rejected rather than saved as a complete answer.

The runtime fields follow the official
[Ollama generate API](https://docs.ollama.com/api/generate) and
[ModelOptions schema](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml).
Cloud output limits and the local-only historical-excerpt drafting policy are
unchanged. Durable ingestion progress/cancellation is described in
[durable-jobs.md](durable-jobs.md).

## Validation and acceptance boundaries

Fresh validation of integrated implementation bfc1d6d (later checkpoint commits
change documentation only):

- Backend: `.venv/bin/pytest app/tests/ -q -m 'not integration'` — 793 passed,
  19 skipped, 8 warnings; `.venv/bin/ruff check app/ desktop.py` passed.
- Frontend: `npm test -- --reporter=dot --pool=threads --maxWorkers=1` —
  221 passed in 31 files. ESLint, `next typegen`, `tsc --noEmit`, explicit
  `npm run build -- --webpack` and desktop static export passed.
- Rust: `cargo fmt --check`, `cargo test --locked` (5 passed), and
  `cargo clippy --locked --all-targets -- -D warnings` passed with the existing
  project-local toolchain.
- `npm run desktop:build -- --no-sign -- --locked` produced a fresh unsigned
  Apple Silicon Noye.app at 67.65 MiB. No Apple identity/notarization was used;
  the bundle is an ignored local preview, not a distribution release.
- The newly packaged app's actual frozen backend, selected with
  `NOYE_TEST_SIDECAR`, ran `pytest app/tests/test_desktop.py -q`: 10 passed,
  7 warnings. Includes loopback readiness, private settings delivery, control
  refusal, CORS, shutdown line and parent EOF in temporary data directories.
  No daemon was started or cloud inference sent.
- PyInstaller analysis includes jobs, workspace backup, runtime checks, saved
  evidence modules and PyMuPDF distribution metadata.
- A new reproducible backup/job regression preserves an unfinished attempt's
  identity and 16/40 progress, marks it interrupted without replay, retains
  edited writing, historical citations and original bytes, requires rebuilding,
  and leaves the source workspace unchanged. All 18 backup cases passed.
- Same-agent integration inspection found that returning to the original hid
  the previous restore. A new UI case reproduced the failure before the fix
  and passed in the full suite afterward; saved-edit confirmation remains
  required. No separate reviewer or native GUI pass ran.
- Existing canonical-root handling and final receipt publication were retained.
  Dependencies were reused through worktree symlinks with explicit Webpack;
  no dependency versions, lockfiles or build configuration changed.
- `git diff --check` passed. GitHub reported no status checks; local results
  do not claim a CI pass or native GUI acceptance.

Ordered replacement PRs: [#53](https://github.com/Kouen-Park/Noye/pull/53)
(closed #50), [#54](https://github.com/Kouen-Park/Noye/pull/54) (closed #51),
then [#55](https://github.com/Kouen-Park/Noye/pull/55) (closed #52). Each
successor targets main after an ordinary history-preserving main refresh.

Native GUI restart/download/export, sleep/force-kill during real inference,
very-large-workspace memory/disk behavior, model latency and live provider access
remain Phase 8 acceptance checks. No real user workspace or Keychain entry was
changed during this work.
