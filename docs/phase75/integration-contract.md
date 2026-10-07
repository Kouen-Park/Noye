# Knowledge integration and document handoff

Stage 2 starts from integrated main `dc80189` (PR #59). A owns shared
infrastructure and migrations; B owns source-driven documents and chat intent.
This contract is the implementation target; validation is recorded separately.

## Source versions and coordination

`SourceCatalog.freeze(scope)` fixes the starting inventory. The scope has explicit
`all`, `empty`, or `chosen` semantics. Chosen source/root IDs are a union; links
never add IDs to the inventory. Descriptors expose IDs, relative paths, SHA-256
versions, availability and ingestion status, never arbitrary server paths.

`SourceSession(connection, scope, manifest=None)` in `services.source_catalog`
uses that inventory. `read(source_id, limit=100, offset=0, chunk_indexes=None)`
returns verified current original passages at the frozen version. `verify(ids)`
rechecks actual original bytes and availability for every consumed source.
`commit_guard(ids)` reserves those sources against application ingestion,
filing, deletion and rebuild, then verifies them and yields for a short artifact
transaction. Do not hold it during model inference. External writes cannot be
locked by Noye; every read and final verification rejects changed bytes.

Store the final manifest and actual consumed passage/version locators with the
artifact. Failed/unavailable sources belong in a coverage report, not evidence.
Retry preserves the original inventory; a changed source requires a fresh task.
Historical snapshots are explicit historical evidence, never a current read.

## Durable jobs

Existing ingestion `jobs` keep their file-specific contract. `knowledge_jobs`
continues to provide `enqueue`, registered handlers, cancellation, interrupted
recovery and explicit retry. A adds persisted stage events and `WorkContext.report`
for stage status/detail; `checkpoint(stage, completed, total)` still works.
Handlers must checkpoint between model calls and save their artifact ID as soon
as an artifact commits, even if later work fails. Returning an artifact ID marks
completion only after the worker checks cancellation again. A retry must reuse
saved artifact identities and preserve user revisions.

B registers kind `source_document`; payload and feature schema belong to B.
Use `context.scope`, `context.manifest` and a SourceSession. All expanded original
and Wiki synthesis context uses loopback Ollama, with no provider fallback.

## Migrations, backup and integration order

A reserves migration **8** for query snapshots/stage events. Migration **9** will
call B's idempotent `app.db.source_documents.install(connection)`. Do not change
released steps 1–7. B supplies feature files first and a separate shared wiring
commit/patch for A to integrate after the feature installer exists.

SQLite backup includes all Wiki revisions, user edits, frozen links/evidence,
query snapshots, document feature tables and both job registries. Portable authored
files are included. External originals are excluded and identified as excluded;
internal immutable original snapshots are included. Restore uses a new workspace,
rebases snapshot paths, interrupts active jobs and disables external roots until
native reconnection. New fields must not relocate `app.db` or document bodies.

## Query/component ownership

A supplies a scoped Wiki-first discovery service and `KnowledgeEvidence` UI
component with Wiki interpretations, immutable revision links and original
citations. B owns chat intent/progress/artifact cards and document/editor/export.
A can wire its evidence component in `message-bubble.tsx`; B owns chat/page.tsx.
Legacy explicit cloud questions retain their original retrieval payload boundary;
Wiki/expanded-original questions use local generation without silent switching.
