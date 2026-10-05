# Phase 7 item 2: historical citation evidence

This branch builds on `feat/index-identity` commit `a46a012`. It uses migration 3
after that branch's migration 2; merge index identity before this work. The
ongoing Phase 6 checkout is separate. A PR targeting the identity branch keeps
the evidence diff focused; retarget it to main after its prerequisite lands.

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

Validation: backend **545 passed, 19 skipped**, including 9 evidence regressions;
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
