# Phase 7 item 2: historical citation evidence

This work originally built on `feat/index-identity` commit `a46a012`. Its
prerequisites are now on main through the ordered integration in PRs #43–#47.
The replacement for closed #41 uses `feat/evidence-snapshots`, targets main and
preserves the original feature commits. Migration 3 follows index identity's
migration 2; item 1's document drafting lands after this evidence foundation.

Answers now store the exact returned excerpts with retrieval rank, chunk index,
similarity score, capture time, original SHA-256 and observed index identity.
The text comes from returned search results, not a second query or a live file
read after generation. Source/hash/index metadata travel on Qdrant points so a
concurrent re-ingestion cannot relabel an old passage with a new SQLite revision.
Extraction hashes and parses the same temporary byte copy, so transient path
edits cannot change the text underneath its recorded revision. A post-extraction
hash check also refuses a detected edit of the live original. This copy is held
in memory only during extraction, bounded by the upload ceiling for normal uploads.

Additive SQLite columns store versioned JSON on message and document citations.
Old citations retain names/pages/chunks but have null evidence: Noye does not
invent their historical text. Existing compatible vectors without source hashes
can supply a saved excerpt, but its original version remains unknown. Re-ingestion
adds source identity without changing the embedding space or automatically
rebuilding the library.

Document creation copies evidence independently of the conversation. Source
edits/re-indexing/deletion, conversation deletion and later document edits do not
change those copies. Deleting the owning conversation/document deletes its own
evidence; deleting an original intentionally retains historical copies in saved
writing. The library removal confirmation states that retention.

Chat and document views show saved excerpts as plain text, with version details.
They identify legacy records explicitly. An explicit “Check original” action
calls `GET /files/{id}/source-status` and compares the current byte hash with saved
revisions. It reports changed, missing, matching, unknown or uncheckable originals.
The endpoint enforces the existing source-directory boundary, including symlinks;
ordinary conversation reads do not hash full original files or query Qdrant.
Saved evidence describes context provided to a model, not proof that every answer
or subsequent user edit is supported.

Historical branch validation: backend **545 passed, 19 skipped**, including 9 evidence regressions;
frontend **137 passed**, including 7 evidence UI cases. Ruff, ESLint, Next route
type generation, TypeScript and the web production build passed. Tests use real
SQLite and in-memory Qdrant with synthetic content and mocked model vectors;
they cover migration/reload, source edits/deletion, independent document copies,
source-directory protection, original status and escaped rendering. No personal
database/index was modified. Default live-service checks skipped; native package
interaction, live generation quality and cited exports are unvalidated.

Item 1 builds on these saved excerpts for drafting. Item 12 can reuse this
inspection UI, but provenance-inclusive exports and PDF coverage are separate
pending work. Item 5 must back up SQLite: originals alone cannot reconstruct
conversations, edited documents or these evidence snapshots.

## Main integration validation

The refreshed branch passed **743 backend tests (19 skipped, 8 warnings)** and
**207 frontend tests across 28 files**, plus Ruff, ESLint, route type generation,
TypeScript and the web production build. Main's four-provider selection, saved
identity failure handling and coordinated ingestion remain intact. The one
textual conflict in the shared chat passage panel was resolved by keeping its
desktop grid and rendering saved evidence across both columns; a new regression
exercises the actual shared component.

Initial parallel checks timed out at unchanged UI test/startup limits during
environment delays. A single thread worker with default frontend test limits
passed the entire suite; the unchanged desktop startup suite passed all 10 tests,
then the full backend rerun passed. No timeout changes were committed. Tests still
use temporary workspaces, synthetic sources and mocked/in-memory dependencies.
Native GUI interaction, live models/cloud credentials, actual PDF output and
large-file memory measurements remain unvalidated.
