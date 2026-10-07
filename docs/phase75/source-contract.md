# Phase 7.5 source and work contract (v1)

Owner A: `feat/folder-foundation`. B owns Wiki/classification/generation services.
Migration 6 belongs to A (roots, sources, versions, change events, filing journal,
knowledge jobs); released migrations 1–5 must remain unchanged. B supplies its
feature schema as an idempotent function in `app/db/wiki.py`; A allocates migration
7 installs it; both additive migrations are implemented and tested. Do not edit shared initialization/routers in the feature commit.

## SourceCatalog and EvidenceReader

Implemented entry point: `app.services.source_catalog.SourceCatalog(connection)`.
`list_sources(scope)` returns descriptors with `source_id == file_id`, nullable
`root_id` (uploads), `relative_path`, name/type, `content_hash`, `version` (SHA-256),
`availability` (`available`, `unavailable`, `missing`, `disconnected`), ingestion
`processing_state`, `error`, manual category and latest ingestion job. It never
returns a server path. `freeze(scope)` returns the immutable inventory of IDs and
versions to save with a job. `assert_allowed(source_id, scope, manifest=None)`
rejects any source outside the scope or frozen inventory. Scope is explicitly
`{mode: all|empty|chosen, source_ids: [], root_ids: []}`; chosen IDs/roots form a
union, empty is always empty. An all request freezes its inventory at job start;
links cannot enlarge that inventory. Disconnected/paused/unavailable roots are
excluded from enabled scope, but retained in administrative folder listing.

`EvidenceReader(connection).read(source_id, version, scope, manifest=None,
chunk_indexes=None, limit=100, offset=0)` returns original extracted passages with
`source_id`, `root_id`, `relative_path`, hash/version, actual nullable page number,
chunk index, content and current/historical flag. Current reads validate the
original version and ingestion readiness; stale/missing/unavailable sources raise
`SourceError(code, message)`. Historical reads require `historical=True` explicitly
and return saved extraction labelled historical, never current claims. PDFs retain
real page numbers; Markdown/TXT have null pages. Enumerate bounded batches for
whole-source coverage; a limit is not proof of complete coverage. Internal snapshot
paths are private to application services and must never enter a model tool schema.

`changes(after=0, limit=100)` returns ordered committed events: `sequence`, kind
(`added`, `changed`, `moved`, `missing`, `unavailable`, `disconnected`, `reconnected`,
`ready`, `failed`, `paused`, `resumed`), root/source IDs, relative path, source
version and error. Save a consumer cursor only after an idempotent update. `ready`/`failed` are
committed with ingestion status. `paused`/`resumed` are root events; a consumer
revisits enabled READY subjects on resume and retains per-subject progress while
a cancelling attempt settles. Reconnection emits `ready` again only after current
bytes and indexed version are verified, without re-embedding unchanged content.
Error codes include
`out_of_scope`, `stale_version`, `unavailable`, `not_ready`, `invalid_path`, `busy`.

## Durable work

Existing `jobs` remain ingestion attempts attached to files; folder intake queues
that real pipeline. Wiki/document work uses `knowledge_jobs`, because ingestion's
released schema requires a file FK and cannot represent an all-source document.
`app.services.knowledge_jobs`: register a handler by kind, enqueue with kind,
subject_id, JSON payload, explicit scope/frozen manifest, and dedupe key; worker
provides progress/checkpoint cancellation. States match ingestion:
queued/running/cancelling/complete/failed/cancelled/interrupted. Startup marks active
work interrupted; retry is explicit and creates a new attempt, preserving payload
and manifest. Local-only jobs validate loopback Ollama before inference; no cloud
fallback. B registers the implemented `wiki` handler; source-driven document
generation remains a later milestone. Persist output/artifact identity before marking complete; retries must not replace user edits.

## Filing and generated outputs

`app.services.filing.file_source(connection, source_id, destination, expected_version,
manual=False)` accepts a relative destination inside the same registered root.
Application code checks opt-in organization prefix, manual category lock, current
version, path components, exclusions, busy work and collisions. It never overwrites
or rewrites bytes. A persisted journal makes an interrupted move recoverable; path
updates preserve file ID and do not queue embedding for unchanged bytes.
Classification only proposes a path; models have no filesystem capability.
`app.services.folders.output_path(connection, root_id, relative_path)` is an
application-only helper restricted to `wiki/` or `documents/`, with root/path safety.
B publishes output revisions atomically, records provenance and preserves edited
Markdown as revisions/proposals.

## Backup and integration

SQLite backup includes all registries, evidence, jobs and B's feature tables.
Connected originals are excluded explicitly; ingestion's immutable internal byte
snapshots are included. Managed/connected root `wiki/` and `documents/` files are
copied into a portable `knowledge/<root-id>/...` backup area (including user edits).
Restore retains these assets inside the NEW workspace, disconnects all external
roots and requires native re-selection to reconnect; it never resumes jobs or moves
app.db / SQLite document bodies into a knowledge folder. Missing/unavailable Wiki
assets are reported, never described as backed up. B's schema must keep authored
revisions distinct from generated/proposed revisions and avoid cascading deletion
of authored work on disconnect/source removal.

Integration order: A contract/foundation → B feature schema migration 7 → B services
and routers/handler registration → B clients/components → full shared checks and
real folder/evidence flow. Shared patches are separate commits. B's implementation
and model measurements retain their authorship; A validates shared integration.
See [Wiki contract](wiki-core.md) for B's feature behavior and recorded evidence.

## Implemented integration and operating limits

`/folders` exposes administrative trees and controls; `SourceCatalog` and
`EvidenceReader` are internal services consumed by B's `/wiki` feature router.
`/knowledge-jobs` exposes durable work state. There is no arbitrary-file reader API.
Folder registration has no HTTP POST path API. Native commands return only IDs;
selected paths arrive over the private parent/sidecar stdin protocol. A model
receives IDs, relative locators and validated excerpts, never a server path.

Migrations 6 and 7, Wiki router/handler/event observer, folder watcher and shared
workspace shutdown/backup hooks are integrated in `feat/folder-foundation`.
B's feature commits retain separate ownership and authorship. Existing ingestion
`jobs` still run extraction/embedding/indexing; the added worker actually executes
Wiki jobs, reports checkpoints and records artifacts independently of ingestion.

The watcher polls while the app runs (one-second poll, two-second stable-write
window); startup repeats reconciliation. Equal hashes alone never establish a
rename: only an unambiguous same-device/inode/hash move preserves an ID. A copy
receives a new ID. Empty supported files are registered and fail extraction
honestly. Inaccessible scans retain records; deletion requires a complete
accessible scan and stable absence. All symlinks are excluded, including internal
ones. External originals are not a portable-backup promise; users must back those
up separately. See [folder acceptance](folder-foundation.md) for observed checks
and remaining native/model limits.
