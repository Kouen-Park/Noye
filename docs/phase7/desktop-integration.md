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
to another database. Settings also offers the original and previous workspace.

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

- Final integrated backend: 792 passed, 19 skipped; Ruff passed.
- Final frontend: 220 passed; ESLint, Next type generation, TypeScript, default
  Turbopack web build and desktop static Webpack export passed.
- Rust fmt, locked tests (5 passed) and Clippy with warnings denied passed.
- The actual frozen macOS sidecar ran the desktop lifecycle suite: 10 passed,
  including loopback readiness, private settings delivery, shutdown line and parent
  EOF in temporary data directories. No daemon was started or cloud inference sent.
- Unsigned macOS app packaging passed: 67.65 MiB. No Apple identity/notarization
  was used; the bundle is an ignored local preview, not a distribution release.
- A separate synthetic backup/restore check preserved an unfinished job's 16/40
  progress, marked it interrupted, retained saved document edits and originals,
  and required rebuilding before search.
- Integration inspection corrected macOS path aliases by canonicalizing the
  original root, and made the restore receipt the final publication marker.
  The initial Turbopack dependency-symlink issue was resolved by independent
  dependency copies without changing versions or build configuration.

Native GUI restart/download/export, sleep/force-kill during real inference,
very-large-workspace memory/disk behavior, model latency and live provider access
remain Phase 8 acceptance checks. No real user workspace or Keychain entry was
changed during this work.
