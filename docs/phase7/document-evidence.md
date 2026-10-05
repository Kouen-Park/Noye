# Phase 7 item 1: local document drafting from saved excerpts

This branch depends on `codex/phase7-evidence-snapshots` (item 2), which depends on
`feat/index-identity`. Merge those prerequisites first. This PR targets the
evidence branch to keep its document-generation diff focused. Neither branch
changes the ongoing Phase 6 checkout or merges into main.

Local document drafting now receives the saved answer and the exact historical
excerpts captured with that answer. Details omitted from a short answer, including
examples and figures, are available to the draft without querying today's index
or reopening originals. Excerpts retain the original retrieval order. Source
names accompany JSON-encoded excerpt text, and the system prompt treats that text
as material rather than instructions. Page citations remain attached outside the
model's output.

The user's explicit choice is **saved excerpts only to local Ollama** for document
generation. `draft_document` removes evidence from a temporary copy of citations
for cloud context selection; it leaves the stored evidence intact. Cloud drafts
continue using the instruction, saved answer and source names. Local drafting
with saved excerpts requires an HTTP Ollama URL on localhost, 127.0.0.1 or ::1;
a remote Ollama URL is refused before generation. There is no automatic provider
fallback. This restriction concerns the newly expanded document context; it does
not change the existing chat generation provider behavior.

Older answers without snapshots use the answer and references only. Noye does
not reconstruct their past context from current originals. The document UI names
the retained material as evidence from the original answer, because a cloud draft
or a later user edit has not necessarily used every saved excerpt. Saved passages
do not establish that every sentence is supported. The Create document form
explains local and cloud payloads before generation.

Validation on this branch: backend **553 passed, 19 skipped**, including 8 document
context cases, and frontend **137 passed**. Ruff, ESLint, route type generation,
TypeScript and the web production build passed. Synthetic mock Ollama payloads
include figures and Korean text absent from the short answer. Tests cover original
rank order, legacy/mixed citations, immutable storage, remote-Ollama refusal and
exclusion for Gemini, OpenAI and Anthropic context selection. This prerequisite
branch has local-only generation; actual cloud routing belongs to Phase 6 and was
checked separately in the combined preview below.

## Integration with Phase 6

Local preview `codex/phase7-merge-preview` combines Phase 6 through `ab225fd`, the
four earlier Phase 7 branches and both evidence branches. Merge commit `1b3fc01`
records the resolved implementation. It remains a local validation branch.

The Phase 6 merge required preserving the index-compatibility text alongside new
cloud/service setup in README. The new evidence merge had three code conflicts:

- `backend/app/services/documents.py`: keep one `GenerationProvider` argument,
  `get_settings`, the local-only evidence guards and Phase 6's
  `generate(..., provider=provider)`. The API must retain
  `draft_document(..., provider=request.provider)`.
- `frontend/src/components/chat/passages.tsx`: keep Phase 6's `PassageList` and
  inspection-panel layout; display `SavedEvidence` across both grid columns.
- `frontend/src/components/documents/create-document-action.tsx`: retain both
  the provider selector and the disclosure about saved excerpts.

The combined preview passed **743 backend tests (19 skipped)** and **206 frontend
tests**, Ruff, ESLint, route type generation, TypeScript, the web production
build and `npm run desktop:ui` static export. An additional synthetic
`httpx.MockTransport` check executed all four real
generation adapters: Ollama received the saved excerpt; Gemini, OpenAI and
Anthropic each reached the correct mocked destination with the answer/source name
and without the excerpt. Each made one request and left the original snapshot
unchanged. No real API key or external inference request was used.

Native application interaction, live generation quality/context capacity, actual
cloud authorization and cited exports remain unvalidated. This feature does not
archive full binary originals or supply backup/job recovery. SQLite backups must
include these locally retained snapshots. Phase 7 item 12 can reuse the evidence
inspection UI; provenance-inclusive exports and PDF coverage remain separate.
