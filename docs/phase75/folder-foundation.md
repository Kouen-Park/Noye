# Phase 7.5 folder foundation and acceptance

A owns `feat/folder-foundation`: native selection/authorization, source registry,
scanner, filing, folder UI and shared schema/jobs/workspace/backup integration.
B's Wiki feature commits are integrated without editing their inference services.
The [source and work contract](source-contract.md) is the implemented handoff.
This delivers the folder foundation for 7.5-1 and filing in 7.5-2; it does not
complete Phase 7.5's source-driven chat/document/export workflow.

## Storage and access

A native macOS `NSOpenPanel` selects a managed or connected root. Registration
travels over the private Tauri parent/sidecar channel; HTTP clients cannot submit
arbitrary root paths. Root ID, canonical path and filesystem device/inode persist
in SQLite. The folder API exposes IDs and relative locations, not backend paths.
Workspace backup switching remains independent of root registration.

Every source read checks the root identity and opens each relative component with
`O_NOFOLLOW` and descriptor-relative operations. Traversal, absolute paths and
symlinks are rejected. Permission errors, changed root identities and unplugged
roots become unavailable; an incomplete scan cannot imply physical deletion.
App data cannot be selected as a root and overlapping roots are rejected.

Connected folders keep their layout. Managed selection creates `sources/inbox`,
`wiki/sources` and `documents`, without moving `app.db` or existing SQLite document
bodies. Original bytes stay in the selected folder. Stable reads create immutable
internal byte snapshots in the existing workspace for the existing ingestion
pipeline. `source_versions` and `source_passages` retain hash/version and extracted
page/passage evidence independently of current vectors. Uploads keep their
existing ingestion path and can be used through the same scoped catalog.

## Changes, work and recovery

A running watcher polls once per second and coalesces observations for a
two-second quiet period before reading. It checks stat before and after the same
bounded byte copy. Startup reconciliation catches changes made while closed.
There is no closed-app daemon. Generated `wiki`/`documents`, hidden/temp files,
app data and symlinks are excluded. PDF, Markdown and TXT are the initial formats.

A unique same-device/inode/hash move updates path/name with the same file ID and
no new embedding attempt. Equal hashes alone do not merge copies or infer moves.
Uncertain moves/copies receive separate records rather than transferring evidence
incorrectly. Empty files remain visible and get an honest no-text extraction error.

Per-folder pause/resume, explicit ingestion retry, cancellation, reconciliation,
re-selection and disconnect are available with the actual tree and Open in Finder.
Disconnected/unavailable roots retain registered locations and history. Disconnect
cancels associated work and preserves originals and authored outputs. The existing
file-delete API rejects a folder source instead of silently deleting an original.

Ingestion still uses its original durable `jobs`. The added `knowledge_jobs`
worker supports actual Wiki handlers, scoped frozen manifests, checkpoints,
deduplication, artifacts and explicit retries. Restart marks active work
interrupted. Late cancellation preserves an already-saved artifact and reports
cancelled rather than claiming completion. Wiki jobs use loopback Ollama only; a
remote endpoint is rejected and there is no automatic cloud fallback. Root
resume revisits READY subjects after cancelling work settles. Source-driven
document handlers are not yet implemented.

## Filing and backup

Automatic filing is disabled until the user enables a specific existing subfolder
per root. Application code checks both source and destination against that area,
version, root identity, exclusions, busy work and manually fixed categories. The
service accepts B's classification proposal as data, never model filesystem access.
A collision raises an error. macOS exclusive rename prevents overwriting and
preserves bytes/inode/ID. A prepared/moved/complete journal and directory fsync
allow recovery after a move but before the registry update. An exclusive-rename
name collision closes that failed attempt so a different destination can be
tried without removing the colliding file. Ambiguous recovery
remains an error and does not guess from a hash.

Additive migrations 6/7 leave released 1–5 unchanged. Backups include SQLite
registries, original-extraction snapshots, durable work, Wiki versions/links/user
edits, app-data Wiki assets and per-root `wiki`/`documents`. Connected external
originals are explicitly excluded; immutable ingestion snapshots are included.
Unavailable authored roots are reported. Authored-file hashes are checked while
copying and before publication, so a concurrent edit cannot silently disappear.

Restore goes to a new workspace. Roots remain disconnected and work interrupted
until explicit native reconnection. Authored assets remain in the restored
workspace's recovery area; reconnection uses an atomic exclusive publication. A
newer/conflicting external user edit is never overwritten. Snapshots are rebased
inside the restored workspace. No folder connection relocates an existing database
or SQLite document body.

## Validation record

Automated checks use temporary synthetic roots and the real SQLite/services.
Coverage includes traversal/symlinks, stable writes, duplicate coalescing, copies,
renames, empty files, startup reconciliation, inaccessible roots, disconnect,
bytes/ID preservation, scope/version rejection, PDF page extraction, manual locks,
collisions, crash recovery, stale current evidence, historical extraction, additive
upgrades, backup assets/conflicts, local-only inference and late cancellation.

- 2026-10-07, normal-default backend suite with Ollama/Qdrant offline:
  `python -m pytest -q`: **887 passed, 19 skipped**, 17.70 s, 9 warnings (final integration).
- After integrating B's resume/relation corrections, the six Wiki test modules:
  **45 passed**, 5.47 s; `ruff check app desktop.py`: passed.
- Frontend `npm test -- --maxWorkers=1`: **245 passed / 36 files**, 20.62 s
  after all final scope/navigation/disconnected-state corrections. Frontend lint,
  `next typegen` and `tsc --noEmit` also passed.
- Rust `cargo test`: **6 passed**; `cargo clippy --all-targets -- -D warnings`: passed.
- Final `npm run desktop:prepare`: PyInstaller sidecar and desktop static export
  passed. Rust QA `.app` packaging succeeded (92.72 MiB).
- Against the final frozen binary, `NOYE_TEST_SIDECAR=<built binary> python -m
  pytest app/tests/test_desktop.py app/tests/test_native_folder_protocol.py -q`:
  **11 passed**, 36.43 s, 7 warnings. This runs actual process startup/shutdown,
  private root authorization, scanner, rename/new-file catch-up on restart and
  disconnect preservation without AI services.

On 2026-10-06, a separate `Noye Folder QA` app identifier/workspace/Qdrant
collection and synthetic folder were used on Apple M2, 8 GiB RAM, macOS 27.0.1.
No production library or credential namespace was used. The app's real
`NSOpenPanel` connected an existing folder and indexed `sources/inbox/fact.txt`
through extraction, local `embeddinggemma` and Qdrant. Embedding took 1.36 s and
indexing 0.21 s in the log. Temporary files, generated Wiki and a symlink to an
outside synthetic file remained excluded.

The native UI paused processing; a new Markdown file remained unprocessed.
Enabling `sources` as the filing area and moving the original to
`sources/HELIOS/fact.txt` retained source ID
`3156e88f-d256-4f35-8d20-3ca4da590ba2`, inode 16088192 and SHA-256
`ce636b1ef4b182da85d234d0bdebc5fd9e65a653554f43e7ecb12996f0a0b229`.
The journal completed and ingestion attempt count stayed one. Open in Finder
opened the actual synthetic folder. A queued Wiki job was cancelled by pausing.

While the QA app was closed, the TXT was edited and a real two-page PDF was
created. Renaming the root simulated an unavailable drive. On restart the native
UI showed unavailable/paused, retained the nested registered source, disabled
Finder/filing and offered re-selection. SQLite contained no missing event and
still one source. Physical external-drive unplugging was not performed.

On 2026-10-07, reopening and resuming the connected root processed the closed-app
edits: TXT, Markdown and PDF all became READY. TXT kept its original ID and
retained two hash-verified byte snapshots (attempt 2); Markdown had one passage,
and the real PDF had original evidence on pages 1 and 2. Local embedding/index
times were 1.92/0.72 s (TXT), 0.06/0.08 s (Markdown), 0.06/0.08 s (PDF), with
0.14 s PDF extraction. Current bytes matched every saved hash.

Native Disconnect retained all three originals byte-for-byte, kept their READY
index/history and showed disconnected references with Finder/filing disabled.
Selecting an empty managed root through the real picker registered a distinct
managed ID, created the documented layout and left automatic filing opt-in off.
Cancelling the next picker left the registry at exactly two roots. The QA app
was closed after acceptance.

## Limits and remaining acceptance

Permission failure is exercised through a denied scan test; native unavailable
behavior uses a renamed directory, not a physical external-drive unplug. Native
PDF print/export, Unicode output and long-document pagination are unverified.
The complete folder → Wiki links → prompt-driven document → save/export workflow
is not complete. Existing uploads/answer-based documents retain regression tests;
a fresh packaged full end-to-end run of those legacy flows was not performed here.
B records actual generation/faithfulness/link measurements in
[Wiki validation](wiki-validation.md), with checked-in synthetic success/failure
reports. The live Korean input retained exact Korean quotes but received an
English summary; this remains a model-quality limit.

Frozen startup also timed out intermittently at existing 20/30-second readiness
limits when builds/model/native processes competed for RAM. These failures were
recorded rather than hidden by longer test timeouts. The sequential final frozen
run passed as recorded in the validation list.

Earlier live-service broad runs suffered model-memory/timeouts on this 8 GiB
host; overriding global service URLs also invalidated existing defaults tests.
Neither run is described as a passing whole-suite check. Final offline regression
uses the normal defaults; real native inference is measured separately.

## Integration order and next owner

1. A's source contract, migration 6, scanner/catalog/evidence and filing/job APIs.
2. B's idempotent Wiki schema, allocated migration 7, then B's feature services,
   routers and client/components in their focused commits.
3. A's actual lifecycle/handler/router/backup/native/folder UI integration, plus
   B's event resume and revision-aware relation corrections. These are integrated
   in this branch; no temporary adapter or fixture is the production service.
4. Review the draft PR and preserve the focused history. Merge to main, remote
   branch deletion and any published-history rewrite require separate instruction.
5. Continue 7.5-4 query orchestration and 7.5-5 source-driven documents using frozen
   catalog manifests and bounded original evidence. Finish the remaining native
   document/PDF workflow and broader model-quality acceptance before completing
   Phase 7.5.
