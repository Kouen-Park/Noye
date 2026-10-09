# Source-driven documents

Phase 7.5-5 starts from integrated main `dc80189` (PR #59). The document
feature consumes the real SourceCatalog, frozen SourceSession, Wiki index and
bounded relations. Course notes are one output form; a course label is optional.

## Request and discovery

`POST /source-documents/generate` accepts `request_id`, `instruction`, an explicit
`scope` (`all`, `empty`, `chosen`), optional `conversation_id` and `inventory_mode`
(`auto`, `collection`, `relevant`). It returns HTTP 202 with a durable job and
request record, without a saved assistant-message ID. Repeating the same request
ID returns its latest associated job. Explicit retry creates a new attempt job,
preserving the same request, frozen inventory and artifact identity. A different
instruction/scope using that request ID conflicts.

The request stores its initial allowed inventory before any model call. Existing
conversation scope further restricts the request. Actual prior user turns help
resolve intent; assistant answers are excluded. Conversation context never appears
in original processing or synthesis inputs. Deleting the chat leaves the document.

Local Ollama interprets purpose, topic, type and language. Explicit collection mode
uses every source in the selected scope. A named collection resolves to a unique
registered root or relative folder and enumerates every frozen member; missing or
ambiguous collections require a scope clarification. Relevant reports inspect all
catalog descriptors in bounded batches, using scoped Wiki/relationship hints and
lexical search over frozen extracted text. These hints select candidate IDs; they
do not establish consumption coverage or document facts. New sources discovered
later cannot join the request. Empty scope does not broaden to all.

Discovery limits: initial inventory at most 1,000 sources; at most eight Wiki seeds,
one relation hop, 20 Wiki pages. Larger inventories require a narrower scope.
The pipeline does not grant filesystem tools to the model or use the chat's five
passages as evidence of reviewing a collection.

## Original processing and publication

The stages are intent/discovery → outline → paginated original reads → bounded
per-source sections → cross-source synthesis → final source verification → save.
Every extracted character from each selected readable source is supplied to a
bounded original-processing batch. UTF-8 byte size conservatively bounds model
input; fragments cover the whole passage, including Korean text. Oversized
indivisible prompts fail explicitly instead of clipping input. Synthesis visits all
supported claims in bounded section groups and interleaves sources for comparison.

All expanded context uses configured loopback Ollama and an installed model whose
`/api/show` metadata is checked before source context is sent. Ollama cloud aliases
are rejected. Requests use the configured model,
context/output budgets and thinking setting. There is no cloud provider argument,
redirect following or automatic fallback. Responses must satisfy strict schemas.
Owned document clients ignore proxy environment variables, keeping preflight and
source context on direct loopback transport. Model-written inline citation labels
are rejected in headings and claims; only verified application labels are attached.
Unknown source, evidence, section or synthesis IDs, non-verbatim quotes, invented
numerals, unfinished model output and failed original-processing entailment checks
block saving. If cross-source wording fails the final entailment pass, actual
verbatim original passages replace that wording and the artifact is marked partial.
Earlier model-approved paraphrases are not used as fallback proof. Those original
quotes retain their source language; translated comparison remains unresolved.
Prompt `source-document-v5` prefers one to four topical sections for small source
sets and avoids assuming textbook topics. Retained original paragraphs are
deduplicated within each section, with only their matching evidence labels.
Each original-processing call sees only one source batch; it must not draw
collection-wide conclusions about other sources being absent. Unverified model
observations are retained only in audit metadata with source/batch/evidence IDs.
They are excluded from published document prose. `render_version`
`source-document-markdown-v3` distinguishes this rendering from older artifacts;
completed artifacts and user revisions are never rewritten.
The entailment pass is a model check, not independent proof; source review remains
necessary. The numeral guard checks verified cited original passages and recognizes explicit
English/Korean counts such as “twice” or “두 번” rendered as 2. Other unstated
numerals remain rejected; arithmetic-derived quantities are not automatically proven.

### Output language and document structure

Explicit `in English`/`in Korean`, `language: ...`, and Korean `한국어로`/`영어로`
directives override the model's inferred language; otherwise its intent language is
used. English overrides require a recognizable output action (or an explicit
language field/leading directive); trailing source descriptions such as “notes
written in English” are excluded. Ambiguous source-language clauses preserve model
intent rather than forcing an output language. Korean source descriptions such as
`영어로 작성된` are also excluded. English/Korean aliases normalize to a stable name.
New title, heading and
generated claim text pass conservative script checks before publication: English
rejects Hangul/CJK/Japanese text; Korean requires Hangul and at least one quarter
of alphabetic characters to be Hangul. Mismatches fail the job without an artifact;
the existing worker discards unsafe caches so explicit retry can obtain a new draft.
These checks can reject legitimate foreign names or Latin-only technical labels.
They do not prove fluency or detect other Latin-script languages. Unsupported output
languages are explicitly marked unchecked/partial instead of being certified.
Exact original quotes, saved passage context and literal fallback keep their source
language and are exempt. Completed artifacts and user revisions bypass new drafting
checks and are never rewritten.

The application omits empty planned sections and rejects unplanned ATX/Setext
headings inside generated claims. Document/section labels pass number checks and
bounded, cached local `verify_heading` stages over only their supplied original
evidence. Incorrect verdict cardinality fails safely. Titles claiming missing
information cannot establish collection absence and are rejected independently of
the model verdict; actual missing-material findings belong to the coverage report.
Unsupported labels become neutral source-document/source-notes labels and mark the
result partial. The semantic heading check is fallible and its real latency/quality
remains Phase 8 acceptance, rather than a guarantee of factual accuracy.

For a comparison request, separate source notes are not a completed comparison.
Without an accepted synthesized paragraph whose validated references span multiple
sources, the result is explicitly partial. This is a structural minimum, not proof
of sound comparative reasoning. These limits persist in
`coverage.presentation_limits[]` (`code`, optional `section_id`, `reason`), appear
in the chat artifact card, document details and Markdown coverage/provenance report.
`metadata.output_contract` records the resolved requested language and the limited
checks performed. These are additive JSON fields, with no migration/job/backup
contract changes; old revisions remain readable without claiming the new checks ran.

SourceSession validates frozen versions and actual original bytes on each read.
Its short `commit_guard(consumed_ids)` reserves sources against application
ingestion, filing, deletion and rebuild and rechecks bytes before the artifact
transaction. It is never held during inference. External writes cannot be locked;
changed originals reject current publication. Retry keeps the original inventory;
a changed source requires a fresh request.

The artifact records initial/selected manifests, source/root IDs, relative paths,
SHA-256 versions, availability/indexing state, actual passage/fragment/character
counts, no-text PDF pages, exact quote spans and full processed fragment snapshots.
It also records Wiki revision hints, model, prompt version, parameters and elapsed
generation time. Missing/unavailable/unindexed sources remain coverage entries and
are excluded from factual evidence. A readable subset produces an explicit partial
result; no readable supported material produces a clarification/failure, no document.
Coverage measures extracted input supplied to the model, not comprehension or
proof that every fact or scanned image was covered.

## Durable identity, editing and export

`source_document` is registered with the existing knowledge worker. Jobs retain
scope, frozen inventory, stage events and explicit cancellation/retry. Successful
bounded model stages are checkpointed in the request cache for interrupted retries.
Invalid evidence removes unsafe cached stages so a retry can obtain a new response.
Rejected-claim feedback guides an explicit retry; verified stages can be reused. Cancellation
is checked before/after model calls; an in-flight request can take up to its timeout.
Startup marks interrupted work and does not silently replay it.

Each request has one deterministic artifact ID. Publication atomically inserts the
legacy `documents`/citations, generated revision, head and request artifact pointer.
The job artifact pointer is stored immediately. Retrying committed work preserves
the artifact and all edits; deleting the artifact does not make retry resurrect it.

Existing answer-driven `/documents/generate` remains unchanged. New artifacts appear
in the existing list/editor. `GET /source-documents/{id}` returns current revision,
history, coverage and saved evidence with current availability. PATCH requires
`expected_revision`; concurrent stale edits conflict without discarding the local
draft. A feature-owned trigger also records edits through the legacy document API.
Historical revisions are read only in the UI. Unsaved editor drafts survive
navigation locally; save them before expecting a workspace backup to contain them.
Source-document drafts retain their expected revision. A restored older or
unknown-base draft blocks Save and its keyboard shortcut until the user compares
the latest revision and explicitly reapplies the draft or uses saved content.
Reapplication changes the expected revision, without bypassing the server's
conflict check or automatically merging prose. An acknowledged save advances the
base of additional typing only when both the base revision and editor instance
match; another window's draft is not silently rebased. Choosing saved content
reloads the full document so history, coverage and export metadata also refresh.

`GET /source-documents/{id}/export.md?revision=...&provenance=true` exports the
chosen immutable revision with optional coverage/original snapshot appendix.
The editor exports its displayed body, including unsaved edits, and uses the
existing Preview/print path for PDF. A saved document or a successful print-dialog
request is not confirmation of a PDF file. Native output/pagination acceptance is
recorded separately in `source-document-validation.md`.

## A integration and backup contract

- Migration 8 belongs to A's query/stage infrastructure. Migration 9 calls
  `app.db.source_documents.install(connection)`; released steps 1–7 are unchanged.
- Register `app.api.source_documents.router` and
  `app.services.source_documents.jobs.register()` with the application.
- Feature tables: `source_document_requests`, `source_document_revisions`,
  `source_document_heads`. Full SQLite backup includes requests, cached stages,
  authored bodies, user revisions, manifests and evidence; these are not indexes.
- `APPROVED_TRIGGERS` exports the exact `preserve_source_document_edits` SQL.
  Backup permits only that application-owned definition, rejects arbitrary views
  and rejects a hostile trigger that merely shares its name.
- Restore into a new destination interrupts active jobs and leaves external roots
  disconnected until native reconnection. External originals are explicitly
  excluded; internal byte/version snapshots and authored SQLite documents remain.

Integration order is SourceSession → migration 8/stage events → document schema →
document pipeline/API → migration 9/registration/backup allowlist → chat/editor UI.
A's combined knowledge branch preserves its maintenance and query wiring. The
document-only branch keeps the existing Wiki registration and adapts its backup
test to document data; both consume the same source/version and durable-job contracts.

A has integrated these contracts and feature commits in PR #60. This branch
is a focused document review surface; integrate through that combined branch and
avoid applying its shared migration/router/job/backup commits a second time.
