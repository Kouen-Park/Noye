# Knowledge integration and document handoff

Stage 2 starts from integrated main `dc80189` (PR #59). A owns shared
infrastructure, migrations, maintenance and questions. B owns source-driven
creation, chat intent, document revisions and export. The services below are
implemented and integrated; [acceptance](knowledge-integration.md) records what
was actually tested. The stage-1 [source contract](source-contract.md) still applies.

## Catalog, allowed inventory and original versions

`SourceCatalog(connection)` in `app.services.source_catalog` supplies:

- `list_sources(scope)`: source/file ID, nullable root ID for uploads, relative path,
  name/type, SHA-256 hash/version, availability, ingestion status/error, manual
  category and latest ingestion job. These descriptors never grant a file read.
- `freeze(scope)`: the initial IDs, roots, relative paths, versions, availability
  and processing state to persist with an attempt or artifact.
- `assert_allowed(source_id, scope, manifest)`: enforce both selected scope and
  frozen inventory. `get(id)` includes unavailable/disconnected administrative
  provenance; it is not a read authorization.
- `changes(after=0, limit=100)`: ordered committed `source_events` with a sequence,
  kind, source/root IDs, relative path, version and error. Advance a consumer cursor
  only after its idempotent update. Added/changed/moved/ready/failed and root
  availability/pause/reconnect events retain the stage-1 contract.

Scope is explicitly `{mode: all|empty|chosen, source_ids: [], root_ids: []}`.
Chosen IDs/roots form a union; empty remains empty. All includes enabled roots and
uploads and freezes before discovery. A chosen unavailable member remains in
coverage but cannot become evidence. Root membership discovered later and related
links cannot expand the initial inventory. No server path or filesystem tool is
exposed to the model.

`EvidenceReader(connection).read(source_id, version, scope, manifest=None,
chunk_indexes=None, limit=100, offset=0, historical=False)` returns validated
original text with IDs, relative path, hash/version, actual nullable PDF page,
chunk index and an explicit historical flag. Current reads require READY ingestion,
connected/enabled roots and actual original bytes matching the extraction version.
Paginate until exhausted; one bounded batch is not whole-source coverage. Historical
reads are explicit saved-version reads and never establish a current claim.

Errors are `SourceError(code, message)`: `out_of_scope`, `stale_version`,
`unavailable`, `not_ready`, `invalid_path`, `busy`. Inaccessible roots retain their
registry; unavailable is not proof of deletion. Surface the reason and require a
fresh request after a source version change.

## Shared read and publication coordination

`SourceSession(connection, scope=None, manifest=None)` uses the frozen inventory.
`read(source_id, limit=100, offset=0, chunk_indexes=None)` reads the frozen current
version and records the consumed ID. `verify(ids=None)` rechecks actual original
bytes and availability, using consumed IDs when omitted.
`commit_guard(ids=None)` reserves those IDs against application ingestion, filing,
deletion and rebuild, verifies them, and yields for a short artifact transaction.
Do not hold it during inference. External writers are outside this application
lock: verification detects changed bytes at the read/publication checks, but does
not promise an operating-system lock against arbitrary external writes.

Store the consumed locators and final manifest with the artifact. Failed,
missing/unavailable/unindexed sources belong in coverage, not factual evidence.
A retry preserves the original inventory; a changed source requires a fresh task.
Historical snapshots retain their original version even after edits or removal.

## Durable jobs and maintenance

Existing ingestion `jobs` still run the file pipeline; they were not converted to
knowledge tasks. `knowledge_jobs` provides `enqueue`, registered handlers,
cancellation, startup interruption and explicit retry. Job states are
queued/running/cancelling/complete/failed/cancelled/interrupted. A queued attempt
is claimed atomically only if cancellation has not been requested.

`WorkContext.checkpoint(stage, completed=0, total=0)` checks cancellation and
persists running progress. `report(stage, state, detail=None, completed=0, total=0)`
persists running/complete/failed/skipped/cancelled/interrupted events. The public
job includes the latest 100 ordered events. Queued cancellation, startup recovery
and restored active jobs retain terminal stage events. In-flight inference cannot
be cancelled before its response/timeout; check between calls. Startup interrupts
rather than silently replaying work. Explicit retry creates a new attempt with the
same subject, payload, scope and manifest. Save artifact identity immediately after
publication; later failures/retries must preserve committed artifacts and user edits.

A registers the `wiki` maintenance wrapper: B's actual classification/summary
handler, then application-validated filing, then affected relations/topics refresh.
Ingestion, classification/summary, filing and relation/topic results appear separately.
Automatic moves require a currently enabled organization prefix and processing,
no manual category lock, frozen current bytes and an authorized relative destination.
Collision/journal recovery preserve bytes and ID; a path-only move does not re-embed.
B registers `source_document` using this worker and SourceSession. Its payload,
cache, coverage and authored schema are described in [document contract](source-documents.md).

`app.services.local_ollama.require_installed_local_model(settings, client)` checks
loopback and `/api/show` before source text is sent. It requires installed local
model metadata and rejects cloud aliases. Call it while holding model usage.
App-owned Wiki, original-grounded question, source-document, original-embedding and
embedding-identity clients bypass environment proxies (`trust_env=False`) and do
not follow redirects. A spoof proxy cannot supply local-model proof and then receive
originals. These service seams accept trusted injected clients for tests/internal
callers; they are not model or public API transport controls. Explicit legacy cloud
provider requests retain their configured transport behavior.
Wiki, expanded-original questions and source documents have no cloud fallback.
Connected-folder questions with an explicitly selected cloud provider fail visibly
without sending original text or changing the provider. Legacy upload-only cloud
questions retain their existing explicit retrieval payload boundary.

## Questions and evidence UI

`POST /chat` accepts `scope` as an alternative to `file_ids`; sending both is
rejected. Resolve root/source scope before persisting the question and conversation
inventory. `knowledge_query.discover` uses at most four Wiki seeds, one relation hop
and 12 Wiki pages, followed by bounded vector/lexical original discovery. Every
contributor of a consulted page must fit the inventory and current version.
Candidate vector content is re-read through EvidenceReader. Lexical originals can
recover precise terms, exceptions and numbers omitted from a short summary.

Wiki is captured interpretation, not answer proof. Only verified original passages
enter the factual prompt; prior assistant answers never enter as evidence. Wiki
failure falls back to originals with a warning; no usable originals returns explicit
insufficiency without a model call. Verify consumed originals after generation and
under the short publication guard. Persist answer/citations/`message_knowledge` in
one SQLite transaction. Saved Wiki links retain revision IDs and use only the frozen source IDs, even
when the original request selected all sources or a root. A historical revision
remains readable when the current page has expanded outside that inventory; current
relations are not presented as historical links. Current revision/availability
labels do not rewrite the historical snapshot.

A's `KnowledgeEvidence` component in `components/chat/knowledge-evidence.tsx`
presents scoped Wiki revision links/interpretations beside original citations.
B's chat intent/cards consume the same job events and own document/editor/export.

Wiki Markdown uses `wikiLinkHref` at render time for inline, reference-style and
implicit URL links. Local Wiki URLs are rebuilt with the current explicit scope;
a link cannot replace it with all sources. Saved answer navigation uses the frozen
inventory as before. Captured contributor `revision_id`, relation `target_revision`
and backlink `revision_id` open their actual saved revisions. Unknown portable
Markdown targets and other local paths render as text; originals are opened through
the verified evidence controls. External references remain explicit user links.
The stored Markdown, source versions, old artifacts and user drafts are unchanged.
The shared `MarkdownContent.rewriteLink` prop is optional, preserving the existing
chat/document renderer when no Wiki policy is supplied. A chosen root/source union
is reflected in source checkboxes; narrowing it freezes its known members to IDs.

## Migrations, backup and integration order

Migration **8** installs query snapshots and durable stage events. Migration **9**
calls B's idempotent `app.db.source_documents.install(connection)`. Released steps
1–7 are unchanged. Shared initialization, router registration and backup wiring
are integrated by A; do not apply B's equivalent shared patches a second time.

Full SQLite backup includes Wiki revisions/user edits, links/evidence/versions,
query snapshots, document requests/cache/revisions and both job registries.
Portable authored files and internal immutable original snapshots are included.
External originals are explicitly excluded. Restore into a new workspace, rebase
private snapshot paths, interrupt active jobs and leave external roots disconnected
until native reconnection. Derived Wiki/vector indexes require rebuild. Unknown
views/triggers are rejected; the exact application-owned document-edit trigger is
allowed, not merely its name. No app.db or SQLite document body is relocated into
a selected knowledge folder.

Disconnect, remove derived data and physically delete originals remain distinct.
Derived removal requires a paused folder and excludes active readers/jobs, ingestion
and pending move journals. It preserves original IDs/bytes/versions, authored Wiki
revisions and document edits; physical deletion is a separate Finder action.

Integration order: integrated stage 1 → SourceSession → migration 8/stage events →
B document schema/pipeline → migration 9/router/worker/backup wiring → A question/
maintenance/evidence UI plus B chat/editor → recorded combined regression →
Phase 8 native/model/PDF acceptance (deferred by the owner on 2026-10-08).
SourceSession, durable jobs, migration and backup contracts are unchanged by this
acceptance handoff. Known document language/heading/comparison limits and native
restore uncertainty remain open; they are not successful checks.
The knowledge-integration branch already contains B's feature commits. Review the
combined branch; do not separately merge duplicated B shared wiring into main.
