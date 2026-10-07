# Phase 7.5 Wiki core

Wiki pages interpret local originals. Verify exact facts, numbers and exceptions in the
original passages. Existing upload, search, chat and answer-to-document routes remain in
place. Wiki-first chat and source-driven document generation are subsequent milestones.

## Source and job contracts

Production code uses A's `SourceCatalog` and `EvidenceReader`, without a fixture adapter.
`source_id` is the stable file ID. `root_id` is nullable for uploads. The catalog provides
`relative_path`, `name`, `content_hash`, hash-based `version`, availability, processing
state, manual category and ingestion job. No absolute path enters model prompts or the
Wiki HTTP response. A catalog `get` includes unavailable records for historical status.

`WikiScope` accepts `all`, `empty`, or `chosen` with source/root IDs. A chosen scope is the
union of its explicit IDs. All freezes enabled, connected originals; empty reads none.
Generation, candidate discovery, search and traversal consume a frozen manifest from
`SourceCatalog.freeze`. Original bytes are verified again before a generated revision
commits. Historical reading retains evidence while indicating superseded, missing,
disconnected, unavailable or not-ready originals. Links never grant additional scope.

`EvidenceReader.read` is paginated through the entire extracted source. The application
assigns evidence IDs, preserving source/hash/version, actual nullable PDF page, extraction
chunk index and character interval. Text files receive passage locations, not invented
pages. Every generated claim must cite an input ID and an exact substring of that input.
Quote membership validates provenance, not the semantic truth of a model paraphrase.

`wiki.jobs.register` installs a `wiki` handler in A's durable `knowledge_jobs` worker.
Payload is `{source_id}`; scope and manifest are stored with the job. Terminal state,
stage, batch progress, attempts, errors and artifact ID are independent of source-index
jobs. Retry is explicit and preserves the frozen version inventory; changed sources need
a fresh job. Committed artifacts stay discoverable if later topic refresh fails. Startup
marks interrupted jobs; it does not silently replay model work.

`wiki.observer.observer` consumes ordered catalog changes using `wiki_consumers.sequence`.
Ready folder sources enqueue a root-scoped local Wiki job. Active same-version work is
deduplicated; cancelling work must settle before its ready event is consumed, including
same-version cancellation. Stale work is cancelled before the next version is queued.
Paused/disconnected roots cancel Wiki work. A committed root `resumed` event schedules
enabled READY originals, with per-source `resumed:<root_id>:<source_id>` checkpoints in
`wiki_consumers` so partial progress does not repeat completed subjects. Removed upload
records do not block later events. Missing,
unavailable and disconnected sources refresh affected topic pages and provenance. Start
the observer after migrations, job recovery and handler registration; stop it before the
knowledge worker. Upload summaries are explicitly requested in the Wiki UI.

## Local generation and relationships

The existing AI settings supply model name, context/output budgets and thinking mode.
Requests use Ollama `/api/generate` with a JSON schema and strict Pydantic validation.
Only loopback URLs are accepted; redirects and cloud fallback are disabled. Model input
and upstream response bodies are not logged. Inference uses the existing model semaphore.

UTF-8 fragments cover every character of the extracted source and preserve page/chunk
locations. Batches include all fragments, schemas and taxonomy hints within a conservative
byte budget. Oversized context or unfinished/invalid output fails visibly instead of
trimming input. Every section is retained in Markdown and revision metadata. Cancellation
is checked between extraction batches, model calls and persistence; an in-flight local
request can take up to its 300-second timeout to reach a checkpoint.

Classification is a proposal: one primary category and tags, with Unclassified below the
confidence/consensus threshold. Existing folder/manual categories are preferred. Wiki
code never moves originals. A's filing service independently validates organization opt-in,
expected source version, manual locks, relative destination, collision and move journal.

Prompt `wiki-grounded-v3` explicitly requests reusable subject tags, source-language
summaries and reuse of at most 32 existing topic labels from eligible pages in the same
root and frozen scope. The response schema enumerates only the supplied evidence and
relation target IDs; application validation still rejects forged IDs and non-verbatim
quotes, including responses from a server that ignores the requested schema.
Exact Unicode-normalized topic identities prevent duplicate pages
for the same kind/root/name. Semantic aliases can still form separate concepts; there is
no automatic destructive merge of authored pages.

Candidates require at least two shared tags or a specific shared topic. This only
shortlists them. Local inference must confirm one of `shared_subject`,
`supporting_evidence`, `alternative` or `contradiction`, with a reason, known target ID
and verified evidence IDs on both sides. There are at most eight candidates, four claim
comparisons per candidate and six accepted links. Confidence below 0.8 creates no link.
Backlinks are queried from published edges; historical target revisions remain immutable.
The API supplies `target_revision` and `target_current_revision`; the UI identifies earlier
targets. Traversal stops at two levels and twenty eligible pages. Stale edges do not drive discovery.

Concept/project pages combine attributed source summaries and relationship tensions.
They retain contributor Wiki/revision IDs and original evidence, and need two sources for
initial creation. They are deterministic maintenance of locally generated summaries.
Users can save a reusable interpretation as an authored analysis with frozen provenance.

## Storage, editing and backup handoff to A

`app.db.wiki.install(connection)` owns the additive schema and preserves A's migration
transaction. A registers it as migration 7 after source foundation migration 6. Published
migrations 1–5 are unchanged. Stable Wiki IDs are application UUID5 identities, never
model-selected IDs. Source identity is `source:<source_id>`; topic identity includes kind,
root and normalized title. No evidence foreign key deletes history with a source row.

| Table | Authoritative backup content |
| --- | --- |
| `wiki_pages` | ID, kind, identity, title, current revision, publication hash/error, times |
| `wiki_revisions` | Immutable Markdown/title, generated/user/proposal origin, parent, metadata, time |
| `wiki_evidence` | Revision/evidence ID, source ID/version, complete saved passage snapshot |
| `wiki_relations` | Origin/target IDs, revision, type/reason, both evidence IDs, target revision |
| `wiki_consumers` | Durable source-event cursor and per-source partial resume checkpoints |
| `wiki_index` | Derived text/tags and distinct Wiki revision/content fingerprint |

Revision metadata stores source/root/path/hash/version/availability, scope and manifest,
all section summaries/points/uncertainties, classification/tags/topics, model/prompt
version, context/output/thinking parameters, processing time, generation key and relationship
limits. Settings and manual-category changes invalidate the generation key. Topic/analysis revisions
also store contributor IDs. The lexical `wiki-lexical-v1` identity contains its Wiki
revision/content hash and is independent of the original vector index identity.

SQLite revision history is authoritative. Root pages project to
`<registered root>/wiki/{sources,concepts,projects,analyses}/<wiki_id>.md`. Upload Wiki and
cross-root analyses project to `<app data>/wiki/...`. Model output cannot choose filenames.
Descriptor-relative no-follow filesystem access, fsync and atomic replacement are used.
Root unavailability or failed projection leaves the SQLite revision and visible error.
Startup repairs missing projections and recognizes a completed rename after a crash.

Edits use optimistic `expected_revision`; stale saves return HTTP 409. External Markdown
edits are imported as authored revisions before projection/generation. A changed original
creates a proposal when current content was authored; it never overwrites that edit.
Adopting a proposal is an explicit authored revision preserving both earlier revisions.
Conflicts detected during projection retain the on-disk edit. Dirty UI drafts remain after
a rejected save and do not disappear when an incoming revision changes. Local browser
drafts survive navigation/restart with their original expected revision; save them to
include them in the portable workspace backup.

A's backup must include the complete SQLite snapshot, `<app data>/wiki`, and registered
root `wiki`/`documents` assets under portable `knowledge/<root_id>/...`. Preserve internal
source-version byte snapshots and saved passages. External original folders are not a
portable backup of their whole contents; the manifest states this and lists unavailable
authored roots. Restore disconnects roots, interrupts active jobs and requires explicit
native reconnection. Reconnection keeps existing newer files and retained conflict assets.
Vectors can be rebuilt; authored Markdown, revisions and relationships cannot.

## HTTP and UI

Feature router: `/wiki/sources`, `/wiki/list`, `/wiki/generate`, `/wiki/search`,
`/wiki/analyses`, `/wiki/{id}/read`, scoped revision reads, edits/adoption and `/related`.
Generation returns 202 and a durable job. Failed scope/version/concurrent edits return
409; unknown IDs return 404. Schema-invalid requests return 422. Administrative GETs
retain all-scope historical access; the Wiki client uses explicit scoped POST reads.
A exposes shared `/knowledge-jobs` list/cancel/resume operations.

The static `/wiki?w=<id>` Next.js page displays source-index and Wiki-job states,
all/empty/chosen controls, page content, original evidence/status, links/backlinks,
revisions/proposals, authored editing and saved analyses. Markdown uses the existing safe
renderer with embedded images disabled. Original PDF links use actual known page numbers.
Opening a historical revision binds that content to its read scope; changing the selection
closes that historical view before it can expose material from the previous scope.

Current page-list UI is limited to 200 pages; search, topic maintenance and relationship
candidate inventory inspect up to 1000 pages. Larger workspaces need pagination before
claims of complete cross-workspace topic coverage. Extraction itself is not truncated.

## Validation and integration order

1. A's source catalog/evidence, scanner/filing and durable knowledge-job foundation.
2. Wiki schema, pipeline, relations/revisions, API, observer and dedicated UI.
3. A's migration/router/lifecycle/navigation/backup/native integration.
4. Run combined regression checks, portable Wiki roundtrip and local model/UI acceptance.

Synthetic English/Korean tests use actual folder registration/scanner/ingestion,
SourceCatalog/EvidenceReader, SQLite, Markdown projection and the durable worker with
controlled model output. They cover schema failures, invented citations/target IDs,
complete long inputs, PDF locations, empty/chosen scope, version changes during inference,
external/user edits, proposals, symlink boundaries, model failure, interruption, explicit
retry, cancellation, observer cursor recovery and partial artifact preservation.

Live runs use invented HELIOS files, real local extraction/embeddinggemma, in-memory
Qdrant and qwen3.5:4b. `backend/app/evaluation/wiki.py` reproduces this without accessing
the user's folders. JSON reports contain corpus, exact saved evidence, output, timings
and model-call token/duration data where available. See the reports for actual outcomes;
synthetic test results are distinct from real model quality and speed.

Prompt v1 generated three grounded source summaries in 137.21, 80.35 and 281.82 seconds
under concurrent QA load, preserving 37/29, the Sunday exception and unknown price. It
produced no links/topic aggregation because tags were empty or project titles differed;
it translated the Korean summary into English. This observed limitation motivated v2.
No broad model-quality benchmark, real user PDF quality claim, or Wiki-first chat/document
acceptance is implied by the smoke check. Exact quotes do not guarantee accurate paraphrases.
