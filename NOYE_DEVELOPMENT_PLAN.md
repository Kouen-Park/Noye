# Noye Development Plan

> **Your knowledge, at your command.**

Noye is a **local-first AI knowledge workspace** that turns personal
files into searchable, source-grounded, reusable knowledge.

**AI AGENTS: READ THIS ENTIRE FILE BEFORE MAKING CHANGES TO THE
PROJECT.**

This document is the working development plan for Noye. It captures the
product decisions, architecture, MVP scope, development order, and
longer-term direction established so far.

------------------------------------------------------------------------

# 0. AI Agent Operating Rules

> **This section is mandatory for every AI coding agent working on
> Noye.**
>
> Before making any code change, the agent must read this entire
> document. This file is the project's source of truth for product
> scope, architecture, implementation order, and engineering workflow.
> If a user instruction conflicts with this document, the user's latest
> explicit instruction wins, but the agent should identify the conflict
> before making a major architectural change.

## 0.1 Required workflow before coding

Every AI agent must:

1.  Read this file completely before starting work.
2.  Inspect the current repository state instead of assuming this plan
    reflects the latest implementation.
3.  Run `git status` and identify the current branch.
4.  Inspect the files relevant to the requested task before editing
    them.
5.  Determine which roadmap phase and milestone the task belongs to.
6.  Keep the requested change as small and focused as practical.
7.  Preserve existing working behavior unless the task explicitly
    requires changing it.
8.  Run relevant tests or validation after implementation.
9.  Report exactly what changed, what was tested, and anything that
    remains incomplete.

Never claim that a feature works unless it has been implemented and
reasonably validated.

## 0.2 Source-of-truth hierarchy

When deciding what to do, use this priority:

``` text
Latest explicit user instruction
        ↓
Current repository/code state
        ↓
This development plan
        ↓
Existing README/documentation
        ↓
Agent assumptions
```

Never overwrite working code merely because an older section of this
plan describes something differently.

If the code and this plan have materially diverged, preserve the code
unless instructed otherwise and update/document the plan when
appropriate.

## 0.3 Architecture rules

Agents must preserve the core architecture unless explicitly asked to
change it:

``` text
Next.js / TypeScript
        ↓
FastAPI / Python
   ┌────┼────┐
   ↓    ↓    ↓
SQLite Qdrant Ollama
   ↓
Local filesystem
```

Do not introduce a different framework, database, vector database, cloud
AI provider, or major infrastructure dependency merely because it is
convenient.

In particular:

-   Do not replace FastAPI with another backend framework without
    approval.
-   Do not replace SQLite as the application metadata database without
    approval.
-   Do not replace Qdrant as the planned vector database without
    approval.
-   Do not make an external AI API mandatory for the core product.
-   Do not introduce authentication, payments, collaboration, cloud
    sync, or agent frameworks into the MVP unless explicitly requested.
-   Build Tauri in Phase 6 after the relevant existing unit/API/UI checks,
    lint, types and builds pass. Phase 7 implements the twelve approved core
    workflow improvements. Phase 7.5 adds folder-based knowledge, maintained wiki
    pages and prompt-driven source documents; Phase 8 follows with stability/quality
    refinement and final packaged-app acceptance. Validate each change as it lands.
-   Do not copy Memex or another project's implementation wholesale.
    Noye should remain independently implemented.

## 0.4 Local-first rules

Local-first is a product requirement, not just a preference.

Agents must:

-   Prefer local processing for user documents.
-   Treat original source files as the source of truth.
-   Treat embeddings/vector indexes as derived, rebuildable data.
-   Avoid silently uploading user documents to third-party services.
-   Never add telemetry or external data transmission without making it
    explicit.
-   Keep Ollama-compatible local inference as the default core AI path.

If an optional cloud provider is added in the future, it must not
silently replace local mode.

**Scope update, 2026-10-03:** the user requested both local inference and an
API-key option to address local generation latency. Optional Gemini generation is
now in scope for the MVP. Ollama remains the default; each chat/document request
explicitly chooses a provider. Extraction, embeddings, Qdrant and persistence stay
local. The key is server-only environment configuration in the web MVP. The UI
discloses what leaves the computer before cloud use. There is no automatic fallback,
retry or billing activation. Desktop credential entry and secure storage are Phase 6.

**Scope update, 2026-10-05:** the user explicitly requested in-app model
installation/deletion and OpenAI (ChatGPT), Claude and Gemini key settings.
Optional OpenAI Responses and Anthropic Messages generation are now in scope.
Desktop credentials use macOS Keychain, not plaintext preferences, and only
availability is returned to the UI. Local remains the first-launch default;
subsequent work can use an explicitly saved default provider. No automatic
provider fallback, inference on key save, tools or embedding switch is added.

**Scope update, 2026-10-05 (Phase 7.5 planning):** the owner requested user-selected
local knowledge folders, automatic source classification, maintained source/topic
wiki pages and related-document links. Chat should interpret a general prompt,
discover and inspect relevant files within the user's enabled source scope, and
create an editable document with Markdown/PDF export without requiring a prior
assistant answer. Course-note synthesis is an example, not a course-only feature.
This is approved planned work after Phase 7 and before Phase 8; no implementation
is claimed. See §16A for ownership, local processing and acceptance requirements.

## 0.5 Citation and provenance rules

Citation provenance is one of Noye's most important requirements.

Agents must never design a pipeline where the LLM invents or guesses
source citations.

Every retrievable chunk must preserve enough metadata to trace it back
to its source, including at minimum:

``` text
file_id
page_number (when applicable)
chunk_index
content
```

Citation mapping must come from retrieved source metadata.

For PDF content, preserve page information through:

``` text
Extraction
   ↓
Chunking
   ↓
Embedding
   ↓
Qdrant
   ↓
Retrieval
   ↓
Generation
   ↓
Citation display
```

Do not discard provenance at an intermediate stage.

Phase 7.5 extends this rule to wiki summaries, links and synthesized documents:
preserve source IDs, versions and actual original locations through every derived
layer. Wiki links and generated prose are not substitutes for original evidence;
map citations from validated source metadata, not invented model references.

## 0.6 Data safety rules

Agents must be conservative with user data.

-   Never mutate original source files unless explicitly requested.
-   Generated/editable documents belong separately from original
    sources.
-   Phase 7.5 automatic filing may move originals only inside an area the user
    enabled for organization; never rewrite their bytes or overwrite collisions.
    Connected existing folders retain their structure by default. Disconnecting
    a folder does not authorize deleting its files. Preserve user-edited wiki pages.
-   File deletion must eventually clean associated metadata and vectors.
-   Destructive operations should be explicit.
-   Never commit personal source documents, generated databases,
    embeddings, secrets, `.env` files, or local model data to Git.
-   Respect `.gitignore`.
-   Never place API keys, tokens, passwords, or secrets directly in
    source code.
-   Use environment variables/configuration for environment-specific
    values.

## 0.7 Code design rules

Prefer straightforward code over speculative abstraction.

Do:

-   Keep API routes thin.
-   Put domain/application logic in focused services.
-   Use clear names.
-   Add types where useful.
-   Keep functions reasonably small and testable.
-   Reuse existing project patterns.
-   Handle expected failures explicitly.
-   Keep dependencies minimal.
-   Write code that another student/developer can understand.

Avoid creating layers such as:

``` text
repositories/
interfaces/
factories/
providers/
managers/
adapters/
```

unless the project has a concrete need for them.

Do not build abstractions solely because they might be useful later.

## 0.8 Scope-control rules

Agents should implement the requested task, not redesign the entire
application.

Before adding a feature, ask:

> Does this help turn the user's own files into searchable, trustworthy,
> reusable knowledge?

If not, it probably does not belong in the MVP.

Do not opportunistically add unrelated features during a focused task.

If a useful improvement is outside scope, mention it after completing
the requested task instead of silently expanding the implementation.

## 0.9 Dependency rules

Before adding a dependency:

1.  Check whether the existing stack can solve the problem.
2.  Confirm the package is actually needed.
3.  Prefer mature, actively maintained packages.
4.  Add it to the appropriate dependency manifest.
5.  Explain non-obvious dependencies in the completion summary.

Avoid adding large libraries for trivial tasks.

## 0.10 Testing rules

Every meaningful behavior change should have appropriate validation.

Agents should:

-   Add or update tests for important backend logic.
-   Prioritize tests for extraction, chunking, retrieval, citation
    mapping, deletion cleanup, and API behavior.
-   Run relevant tests after changes.
-   Run broader tests when a change affects shared infrastructure.
-   Never delete or weaken a failing test simply to make the suite pass
    unless the test itself is demonstrably obsolete and the change is
    explained.

For a bug fix, add a regression test when practical.

## 0.11 Error-handling rules

Failures should be visible and diagnosable.

Do not silently swallow exceptions.

User-facing processing should eventually map failures to meaningful
states such as:

``` text
UPLOADING
EXTRACTING
CHUNKING
EMBEDDING
READY
FAILED
```

Backend logs may contain technical details, while UI/API errors should
remain understandable.

## 0.12 Documentation rules

When a change materially affects setup, architecture, commands,
environment variables, supported formats, or user-facing behavior,
update the relevant documentation.

Do not mark roadmap items complete until the implementation actually
exists and has been validated.

Do not describe planned functionality as already implemented.

## 0.13 Git rules for AI agents

Unless the user explicitly says otherwise:

-   Never work directly on `main` for a new feature or non-trivial fix.
-   Start from an up-to-date `main`.
-   Create a focused branch using the branch strategy in this document.
-   Do not mix unrelated work into the same branch.
-   Use Conventional Commit messages.
-   Do not rewrite published history or force-push without explicit
    approval.
-   Do not merge a PR merely because code was generated; validate it
    first.
-   Do not commit secrets, local databases, uploaded source files,
    vector storage, virtual environments, or build output.

If the agent does not have permission or tooling to create
branches/commits, it should still structure its work as though it
belongs to the appropriate branch and tell the user the recommended
branch name.

## 0.14 Definition of done for an agent task

A task is not complete merely because code was written.

Before reporting completion, check:

``` text
Requested behavior implemented
        ↓
Relevant tests/validation performed
        ↓
No obvious unrelated breakage
        ↓
Docs/config updated if required
        ↓
Git diff reviewed
        ↓
Result summarized clearly
```

The final report should include:

-   **Changed:** key files/behavior modified.
-   **Validated:** tests or commands actually run.
-   **Not validated:** anything the agent could not verify.
-   **Next:** only the most relevant follow-up, if one exists.

Never fabricate test results, command output, or implementation status.

## 0.15 When uncertain

If uncertainty affects architecture, data safety, destructive
operations, security, or product scope, ask before proceeding.

For small implementation details that do not materially affect those
areas, use the simplest option consistent with this document and
continue.

------------------------------------------------------------------------

# 1. Product Vision

Noye should help a user take scattered knowledge --- PDFs, Markdown
notes, text files, project documentation, lecture material, and research
--- and turn it into a private knowledge workspace.

The core experience should be:

``` text
Files
  ↓
Extract
  ↓
Understand / Index
  ↓
Search
  ↓
Ask
  ↓
Cited Answer
  ↓
Reusable Document
```

Noye is **not** intended to be another generic "chat with PDF"
application.

The differentiator is the full workflow:

**source files → searchable knowledge → source-grounded answers →
editable reusable documents**

**Planned Phase 7.5 experience:** choose a local knowledge folder, add files in
Finder, and let Noye maintain source summaries and related topic pages. A prompt
can ask the AI to discover relevant files and produce a report, comparison or study
note directly from them. Original passages remain available for exact details and
provenance. This extends the current upload/RAG/answer-to-document workflow; it is
not implemented yet.

### Product principles

1.  **Local-first**
    -   Core document processing should work locally.
    -   Personal files should not require cloud storage.
    -   External AI APIs should not be required for the core local mode.
2.  **Sources over hallucinations**
    -   Answers should preserve where information came from.
    -   File and page references are a core feature, not an optional
        extra.
3.  **Original files are the source of truth**
    -   Vector indexes are derived data.
    -   Noye should eventually be able to rebuild its index from the
        original source files.
4.  **Generated content remains editable**
    -   AI output should never be treated as a final immutable artifact.
    -   Users should be able to modify generated Markdown before saving
        or exporting.
5.  **Clarity over complexity**
    -   Avoid unnecessary abstractions and premature architecture.
    -   Build the smallest useful version first.

------------------------------------------------------------------------

## 2. Target User

Initial persona:

> A student, developer, researcher, or creator with many scattered PDFs,
> notes, project documents, and reference files who wants AI to search
> and reuse that knowledge without repeatedly providing the same
> context.

Example Noye use cases:

-   Search university lecture PDFs by meaning.
-   Ask questions across several course documents.
-   Find information from old project documentation.
-   Generate study notes from selected sources.
-   Planned in Phase 7.5: ask for a document in chat and let AI find and inspect
    relevant local sources, including but not limited to lecture collections.
-   Turn research into an editable Markdown document.
-   Search personal technical notes.
-   Produce a cited summary from multiple documents.

------------------------------------------------------------------------

## 3. MVP Scope

### Included

-   [x] Upload PDF files
-   [x] Upload Markdown files
-   [x] Upload TXT files
-   [x] Extract text
-   [x] Preserve PDF page numbers
-   [x] Chunk extracted content
-   [x] Generate embeddings locally
-   [x] Store vectors in Qdrant
-   [x] Semantic search
-   [x] Ask questions over indexed knowledge
-   [x] Local LLM generation through Ollama
-   [x] Optional Gemini generation for chat and documents, selected per request;
    automated transport/API/UI tests pass. Live Gemini validation requires a key.
-   [x] File citations
-   [x] Page citations
-   [x] Conversation history — stored and re-readable; the model does not
    receive earlier turns (see §12.6)
-   [x] Generate Markdown documents from answers/retrieved knowledge
-   [x] Edit generated Markdown
-   [x] Preview Markdown
-   [x] Export Markdown
-   [x] Export PDF — via the browser's print path; the print stylesheet is
    written and its opt-in attribute is tested, but nobody has inspected an
    actual printed page (see §13.6)
-   [x] Visible processing states
-   [x] Delete files and associated vectors
-   [x] Basic error handling

### Approved Phase 7.5 extension (planned)

-   [ ] User-selected knowledge folders, connected sources and change detection
-   [ ] Automatic filing, source summaries, related links and maintained topic wiki
-   [ ] Wiki-first questions with inspectable original evidence
-   [ ] Prompt-driven source discovery and document generation from chat
-   [ ] Compatible backup/recovery and source-based Markdown/PDF output

Existing completed MVP items above retain their status. See §16A for delivery
order and §17.10 for the expanded final acceptance.

### Explicitly out of scope for the first MVP

-   Multi-user collaboration
-   Payments/subscriptions
-   Mobile application
-   Voice
-   Complex autonomous agents
-   Model fine-tuning
-   Google Drive integration
-   Notion integration
-   Web search
-   Authentication for the initial local single-user version

These can be reconsidered after the core knowledge workflow works well.

------------------------------------------------------------------------

## 4. Technology Stack

### Frontend

-   Next.js
-   React
-   TypeScript
-   Tailwind CSS

Scaffolded 2026-09-21 with `create-next-app`: Next.js 16.3.5,
React 19.2.8, Tailwind CSS 4, ESLint, the App Router, and a `src/`
directory with the `@/*` import alias.

Tailwind is an addition to the originally planned stack. It is
`create-next-app`'s default styling layer and Phases 2 to 5 are almost
entirely UI work, so hand-rolling CSS would cost more than it saves.
Replace it only deliberately.

Note that `frontend/AGENTS.md`, generated by `next dev`, warns that
Next.js 16 changed APIs, conventions, and file structure. Read the
relevant guide in `node_modules/next/dist/docs/` before writing
frontend code rather than relying on older Next.js knowledge.

### Backend

-   FastAPI
-   Python

### Local AI

-   Ollama

### Document Processing

-   PyMuPDF

### Metadata / Application Database

-   SQLite

### Vector Database

-   Qdrant

### Infrastructure

-   Docker / Docker Compose

### Desktop Packaging --- Later

-   Tauri

The development path should be:

``` text
Local Web Application
        ↓
Phase 6: Tauri Desktop Application
        ↓
Phase 7: Twelve Core Workflow Improvements
        ↓
Phase 7.5: Knowledge Wiki and Source-Driven Documents
        ↓
Phase 8: Reliability, Quality and Final Acceptance
```

Build the knowledge workflow first, then the desktop app and the twelve approved
workflow improvements, then Phase 7.5's folder/wiki and prompt-driven document
workflow, followed by stability/quality refinement and final acceptance. Validate
each change as it lands rather than postponing all testing to Phase 8.

------------------------------------------------------------------------

## 5. High-Level Architecture

``` text
                 User
                  │
                  ▼
           Next.js / React
                  │
                  ▼
               FastAPI
        ┌─────────┼─────────┐
        │         │         │
        ▼         ▼         ▼
     SQLite     Qdrant    Ollama
    Metadata    Vectors   Local AI
        │
        ▼
  Local Filesystem
```

Responsibilities should stay clear:

### Next.js

Responsible for:

-   UI
-   Library
-   Chat
-   Document editor
-   Upload interactions
-   Processing status display

### FastAPI

Responsible for:

-   File APIs
-   Document processing
-   Search
-   Retrieval
-   Chat orchestration
-   Citation mapping
-   Document generation

### SQLite

Stores:

-   file metadata
-   conversations
-   messages
-   generated documents
-   application relationships/state

### Qdrant

Stores:

-   embeddings
-   vector IDs
-   chunk retrieval metadata

Qdrant should **not** be the source of truth.

### Ollama

Responsible for local:

-   embeddings
-   LLM inference

### Local filesystem

Stores:

-   original user files
-   generated documents/exports

------------------------------------------------------------------------

## 6. File Storage Philosophy

Keep original sources separate from AI/user-generated documents.

The initial upload layout below is retained for compatibility. Current generated
and edited document bodies live in SQLite; `documents/` may contain portable files.
Phase 7.5's user-selected folders and Markdown wiki are planned separately in
§16A.2. Folder selection is not permission to move an existing workspace database
or reorganize all connected originals.

Initial layout:

``` text
data/
├── sources/
│   ├── Algorithms.pdf
│   ├── Assignment.pdf
│   └── notes.md
├── documents/
│   ├── dijkstra-notes.md
│   └── exam-summary.md
└── app.db
```

### `sources/`

Original user files.

Noye should avoid mutating these.

### `documents/`

Content produced through Noye and edited by the user.

### `app.db`

Metadata, relationships, conversations, messages, etc.

### Qdrant

A rebuildable derived search index.

Future feature:

``` text
Rebuild Index
      ↓
Read sources/
      ↓
Extract
      ↓
Chunk
      ↓
Embed
      ↓
Recreate Qdrant collection
```

------------------------------------------------------------------------

## 7. Core Data Models

### File

``` text
id
name
file_type
path
size
status
created_at
```

Suggested processing statuses:

``` text
UPLOADING
EXTRACTING
CHUNKING
EMBEDDING
READY
FAILED
```

### Chunk

``` text
id
file_id
chunk_index
content
page_number
vector_id
```

`file_id`, `page_number`, and `chunk_index` are especially important
because citations depend on them.

### Conversation

``` text
id
title
created_at
```

### Message

``` text
id
conversation_id
role
content
sources
created_at
```

### Document

``` text
id
title
content_markdown
created_at
updated_at
```

### Implemented data layer

`File` and `Chunk` exist in `backend/app/models/files.py`, with persistence in
`backend/app/db/`. `Conversation`, `Message`, and `Document` are deliberately
not implemented yet — nothing uses them until Phases 4 and 5.

Three decisions, settled 2026-09-22:

-   **Standard-library `sqlite3`, not an ORM.** The schema is two tables and one
    relationship, so an ORM would add a dependency and a mapping layer without
    removing work. Persistence is thin functions over SQL, each taking its
    connection explicitly so a request handler, the background ingestion task,
    and a test can pass their own.
-   **Ingestion runs in the background; the client polls.** `POST /files`
    returns immediately with a file id in `UPLOADING`, and the pipeline advances
    the status behind it. A synchronous upload would hold an HTTP request open
    for minutes on a large PDF, and the plan's staged processing UI only means
    anything if the stages are observable while they happen.
-   **Markdown and text files cite by filename, with no page.** They have no
    pages, so `Chunk.page_number` is nullable and a citation reads `notes.md`
    rather than inventing a page number a reader could not verify.

Beyond the plan's field list, `File` also carries:

-   `error` — why a `FAILED` file failed. Setting `FAILED` without a message
    raises, because a failure the UI cannot explain is worse than none; any
    other status clears it, so a retried file shows no stale reason.
-   `page_count` and `chunk_count` — extraction and chunking results, for
    display.

Storage details that protect the index: `PRAGMA foreign_keys` is enabled (off
by default in SQLite), so deleting a file cascades to its chunk rows instead of
orphaning them; `(file_id, chunk_index)` is UNIQUE, so two chunks cannot claim
the same position; chunk writes replace rather than append, matching the
deterministic Qdrant point ids so re-ingestion stays idempotent; and WAL
journal mode lets the background task write while a request reads the file
list.

------------------------------------------------------------------------

# 8. Development Roadmap

## Phase 0 --- Foundation

Goal: create a reliable local development environment.

### Completed

-   [x] Create GitHub repository
-   [x] Create initial README
-   [x] Create `.gitignore`
-   [x] Create `.env.example`
-   [x] Create initial backend structure
-   [x] Create `data/sources`
-   [x] Create `data/documents`
-   [x] Add Docker Compose configuration for Qdrant
-   [x] Add basic FastAPI application
-   [x] Add `/health` endpoint

### Next

-   [x] Run FastAPI locally
-   [x] Verify `/health` returns `{"status":"ok"}`
-   [x] Install/start Docker
-   [x] Start Qdrant
-   [x] Install/configure Ollama
-   [x] Select embedding model
-   [x] Select initial local generation model
-   [x] Bootstrap Next.js frontend

### Phase 0 exit condition

The following services can run locally without errors:

``` text
Next.js
FastAPI
Qdrant
Ollama
```

------------------------------------------------------------------------

# 9. Phase 1 --- Knowledge Engine

This is the most important development phase.

Do **not** focus heavily on UI until this pipeline works.

``` text
PDF
 ↓
Extract
 ↓
Chunk
 ↓
Embed
 ↓
Qdrant
 ↓
Search
 ↓
Retrieve
 ↓
LLM
 ↓
Answer + Citation
```

## 9.1 PDF Extraction

Create:

``` text
backend/app/services/extraction.py
```

Use PyMuPDF.

Import it as `import pymupdf`. The older `import fitz` alias still works but
is deprecated and warns on use.

Requirements:

-   [x] Accept PDF path
-   [x] Open PDF
-   [x] Iterate through pages
-   [x] Extract page text
-   [x] Preserve page number
-   [x] Handle empty pages
-   [x] Handle invalid/corrupt PDF
-   [x] Return structured extraction result

Implemented as `extract_pdf(path) -> list[ExtractedPage]`, where
`ExtractedPage` carries a 1-based `page_number` and stripped `content`.
Empty pages are returned with empty content rather than dropped, so a page
number always refers to the same physical page. Every failure path raises
`ExtractionError` instead of leaking a PyMuPDF exception type, which lets
callers map failures to the `FAILED` processing state.

Example internal result:

``` text
[
  {
    page_number: 1,
    content: "..."
  },
  {
    page_number: 2,
    content: "..."
  }
]
```

### Test

-   [x] Known PDF produces expected page count
-   [x] Page numbers are correct
-   [x] Extracted text is non-empty where expected
-   [x] Invalid PDF produces controlled error

Covered by `backend/app/tests/test_extraction.py` (13 tests). Fixture PDFs
are generated at test time with PyMuPDF rather than committed as binaries.

### Markdown and text extraction

`extract_text_file(path)` returns the whole file as a **single**
`ExtractedPage`, and `extract_file(path, file_type)` dispatches between it and
`extract_pdf`.

-   **One page, not artificial pages.** Slicing a text file into fixed-length
    "pages" would reset chunk overlap at boundaries the source does not have,
    and would attach page numbers no reader could verify.
-   **The page number is a placeholder that never escapes ingestion.** For a
    format whose `FileType.has_pages` is false, ingestion rewrites every chunk
    with `page_number=None` *before* embedding, so the Qdrant payload — which
    is what citations are built from — carries no page either. Clearing it only
    in the database rows is not enough: the first implementation did exactly
    that and still produced `study-notes.md — page 1`.
-   **UTF-8 only, with the BOM stripped.** A byte-order mark would otherwise
    become an invisible character at the head of chunk 0. Anything that is not
    valid UTF-8 fails with a message telling the user to re-save the file
    rather than being decoded into mojibake that would poison retrieval
    silently.
-   **CRLF and lone CR are normalised to LF**, so Windows files do not carry
    stray carriage returns into chunk text and citations.
-   `page_count` is left unset for these formats; reporting "1 page" would be
    noise.
-   A whitespace-only file fails with "The file contains no text to index" —
    the OCR wording is reserved for PDFs, where it is the likely cause.

Covered by `backend/app/tests/test_extraction_text.py` (17 tests), including
Korean content, a CP949 file that must fail, and the dispatcher.

------------------------------------------------------------------------

## 9.2 Chunking

Create:

``` text
backend/app/services/chunking.py
```

Input:

``` text
extracted pages
```

Output:

``` text
chunks
```

Every chunk should retain:

``` text
file_id
page_number
chunk_index
content
```

Example:

``` text
Algorithms.pdf
    │
    └── page 14
          ├── chunk 0
          ├── chunk 1
          └── chunk 2
```

Requirements:

-   [x] Define chunk size
-   [x] Define overlap
-   [x] Avoid losing page provenance
-   [x] Produce deterministic chunk ordering

Do not over-engineer sophisticated semantic chunking initially.

Start simple, measure retrieval quality, then improve.

### Implemented design

`chunk_pages(pages, *, file_id, chunk_size, overlap) -> list[Chunk]`, where
`Chunk` carries `file_id`, `page_number`, `chunk_index`, and `content`.

-   **Chunks never span two pages.** Each page is split independently. A chunk
    covering the end of page 3 and the start of page 4 could not be cited as
    either page, so page-level citation requires this. The cost is that a
    sentence straddling a page break is divided.
-   **`chunk_index` counts across the whole file**, not per page, so it
    identifies a chunk within the file on its own. Page-local ordering is
    recoverable by grouping on `page_number`.
-   **Defaults: 1000 characters with 150 overlap.** The size is bounded by the
    embedding model rather than by taste: `embeddinggemma` has a 2048-token
    context and truncates silently past it, which would drop the tail of an
    oversized chunk from the index with no error. 1000 characters stays inside
    that limit even for Korean, which spends far more tokens per character
    than English.
-   **Boundaries snap to the nearest paragraph, line, or sentence break** in
    the last 40% of the window, falling back to a hard cut for unbroken text
    such as a long URL or table row. Full-width CJK punctuation is included,
    since those sentences end without a following space.
-   **Empty pages produce no chunks** but do not disturb later page numbers.

### Test

Covered by `backend/app/tests/test_chunking.py` (27 tests), including that
chunks are verbatim slices of the page advancing without gaps, that no chunk
mixes text from two pages, and that Korean text chunks correctly.

------------------------------------------------------------------------

## 9.3 Embeddings

Create:

``` text
backend/app/services/embeddings.py
```

Pipeline:

``` text
chunk content
     ↓
Ollama embedding model
     ↓
embedding vector
```

Requirements:

-   [x] Connect FastAPI backend to Ollama
-   [x] Embed a single text string
-   [x] Embed document chunks
-   [x] Handle Ollama connection errors
-   [x] Configure model using environment variables

Avoid hardcoding model names throughout the application.

### Implemented design

`embed_text(text)`, `embed_texts(texts)`, and `embed_chunks(chunks)` in
`backend/app/services/embeddings.py`, returning one vector per input in input
order. Configuration comes from `app/config.py` (`pydantic-settings`), which
reads the project `.env`; no model name appears in application code.

-   **Batched.** Ollama's `/api/embed` accepts a list and returns embeddings in
    order, so texts are sent 16 at a time. The cap keeps a large document from
    becoming one enormous request.
-   **Dimension is verified on every response.** A vector whose length differs
    from `QDRANT_VECTOR_SIZE` raises `EmbeddingError` naming the remediation.
    Without this check, swapping the embedding model would surface later as a
    rejected Qdrant insert or, worse, as silently meaningless search results.
-   **Empty text is refused** rather than embedded. A zero-ish vector for an
    empty string would match everything and pollute retrieval.
-   **Failures raise `EmbeddingError`, never an httpx exception**, so callers
    can map them to `FAILED` without depending on the HTTP library. An
    unreachable Ollama and a model that was never pulled produce distinct
    messages, the latter naming the `ollama pull` command.
-   The default timeout is 120 seconds; local embedding is far slower than
    httpx's 5-second default.

### Selected local models (verified 2026-09-21)

Measured on an Apple M2 (Metal, 5.3 GiB usable VRAM) with Ollama 0.34.2:

  ------------------------------------------------------------------------
  Role            Model               Notes
  --------------- ------------------- ------------------------------------
  Embeddings      `embeddinggemma`    621 MB, **768 dimensions**,
                                      100+ languages -- suits mixed
                                      Korean/English sources

  Generation      `qwen3.5:4b`        3.4 GB, ~22 tokens/sec
  ------------------------------------------------------------------------

Two consequences for implementation:

1.  `QDRANT_VECTOR_SIZE=768` must match the embedding model. Switching
    embedding models requires recreating the Qdrant collection and
    re-embedding every chunk.
2.  `qwen3.5` is a reasoning model. Thinking must be **disabled** for RAG
    answers by passing `"think": false` to the Ollama API. With thinking
    enabled, a one-sentence answer cost ~1550 tokens / 82s; with it
    disabled, ~30 tokens / 3s. A Korean RAG-style prompt answered
    correctly from the supplied excerpt in ~6s.

------------------------------------------------------------------------

## 9.4 Qdrant Indexing

Qdrant runs from `docker-compose.yml` with its image **pinned** to
`qdrant/qdrant:v1.19.1` (the version this setup was verified against).
Keep it pinned rather than tracking `latest`: a future release can change
API or collection behavior and silently break a local index. Bump the pin
deliberately and re-verify collection creation when doing so.

Store each chunk vector in Qdrant.

Payload should include enough provenance to recover the original source.

Example:

``` text
vector
file_id
page_number
chunk_index
content
```

Requirements:

-   [x] Create Noye collection
-   [x] Insert vectors
-   [x] Retrieve vectors — search implemented in section 9.5
-   [x] Delete vectors belonging to a file
-   [x] Recreate/rebuild collection

### Implemented design

`backend/app/services/indexing.py`: `ensure_collection`,
`recreate_collection`, `index_chunks`, `delete_file_chunks`, `count_chunks`.

-   **Point IDs are deterministic**, derived as UUID5 of
    `"{file_id}:{chunk_index}"`. Re-indexing a file therefore overwrites its
    points instead of duplicating them, which makes ingestion safe to retry
    and the rebuild-index flow idempotent. The namespace UUID must never
    change: doing so would orphan every stored point.
-   **The payload carries `file_id`, `page_number`, `chunk_index`, and
    `content`**, so a search result can be cited and displayed without a
    second lookup. Payload keys are module constants so indexing and
    retrieval cannot drift apart.
-   **Vector/chunk misalignment raises before anything is written.** Storing a
    vector against the wrong chunk's text would produce citations pointing at
    unrelated pages — a silent correctness failure, so it is a hard error.
-   **`ensure_collection` never destroys an index**; the destructive path is
    the separately named `recreate_collection`, for rebuilds and embedding
    model changes.
-   Deletion is filtered on `file_id`. Leaving vectors behind after a source
    is deleted would let a removed document keep answering questions.

### Test

`backend/app/tests/test_indexing.py` (20 tests) runs against
qdrant-client's in-memory mode — real Qdrant behavior without Docker — plus
two integration tests against the running server that clean up after
themselves.

------------------------------------------------------------------------

## 9.5 Semantic Search

Create:

``` text
backend/app/services/retrieval.py
```

Flow:

``` text
User query
    ↓
Query embedding
    ↓
Qdrant similarity search
    ↓
Top K chunks
```

Search result should expose:

``` text
content
file_id
file_name
page_number
similarity score
```

Initial goal:

> Ask a question about a known PDF and see the correct section among the
> top results.

### Implemented design

`search(query, *, limit=5, file_ids=None, min_score=None)` in
`backend/app/services/retrieval.py`, returning `SearchResult` objects ordered
by descending similarity.

-   **`file_name` is deliberately not returned.** The human-readable name
    belongs to the file metadata in SQLite, which does not exist yet; callers
    join on `file_id` once it does. Copying the name into the vector payload
    would leave stale duplicates behind after a rename.
-   **`min_score` exists because vector search always answers.** A nearest
    neighbour is returned even when nothing in the index is relevant, so a
    threshold is how "we don't know" becomes representable.
-   `file_ids` scopes a search to chosen sources, which also lets tests share
    one collection without interfering.

### Test

`backend/app/tests/test_retrieval.py` (17 tests). Unit tests stub the query
embedding and use unit axis vectors so ranking is exactly predictable;
integration tests run the real pipeline and confirm that

-   a question retrieves the correct page (34) rather than a nearby one;
-   a question sharing no keywords with the passage still finds it — "negative
    costs" retrieves the Bellman-Ford page (41);
-   **a Korean question retrieves the right page of an English document**,
    which is the cross-language behavior `embeddinggemma` was chosen for;
-   an unrelated passage ranks last.

------------------------------------------------------------------------

## 9.6 Local RAG

Once retrieval works:

``` text
question
   ↓
retrieve relevant chunks
   ↓
construct context
   ↓
Ollama
   ↓
answer
```

Generation rules should encourage the model to:

-   use supplied context;
-   avoid inventing unsupported information;
-   say when retrieved context is insufficient;
-   preserve source relationships.

### Implemented design

`answer_question(question, *, limit, file_ids, min_score)` in
`backend/app/services/generation.py`, returning an `Answer` with `text` and the
`sources` it was grounded in.

-   **The model never writes citations.** The system prompt forbids a source
    list, and `Answer.sources` is the retrieval result rather than anything the
    model reported. A model allowed to cite will eventually produce a page
    number that looks entirely plausible and is wrong.
-   **No results means the model is not called at all.** A fixed
    `NO_CONTEXT_ANSWER` is returned instead. Handing a model an empty context
    and asking it to answer is precisely how ungrounded answers are produced.
-   **Thinking is off**, taken from `OLLAMA_THINKING`. Locally, thinking cost
    roughly thirty times the latency for no gain at answer length.
-   Excerpts are numbered and labelled with their page so the model can reason
    about them; the label is context, not permission to cite.
-   Failures raise `GenerationError`, never an httpx exception, with distinct
    messages for an unreachable Ollama and a model that was never pulled.

### Test

`backend/app/tests/test_generation.py` (19 tests). Unit tests assert prompt
construction, the `think: false` payload, and every failure path. Integration
tests against the real model confirm that

-   an answer uses the retrieved passage rather than model knowledge;
-   **the model declines when the excerpts do not contain the answer** — the
    behavior separating a knowledge tool from a chatbot;
-   a Korean question is answered in Korean from English source text.

------------------------------------------------------------------------

## 9.7 Citation Mapping

Create:

``` text
backend/app/services/citations.py
```

Noye should be able to display something like:

``` text
Dijkstra's algorithm assumes non-negative edge weights.

Sources:
Algorithms.pdf — page 34
Lecture-07.pdf — page 12
```

Citation mapping must originate from retrieved chunk metadata rather
than asking the LLM to invent citations.

### Implemented design

`build_citations(results, *, file_names=None)` and
`format_citations(citations)` in `backend/app/services/citations.py`.

-   **Citations are computed, not generated.** They derive entirely from the
    provenance attached at index time, so a citation can be wrong only if the
    index is wrong — never because a model guessed a plausible page number.
-   **Chunks sharing a file and page collapse into one citation**, since
    several retrieved chunks routinely come from the same page and a user does
    not want "page 34" listed three times. Each citation keeps its
    `chunk_indexes`, so the exact passages stay inspectable.
-   **Ordered by best score within each group**, so the citation list mirrors
    how relevant each source was; ties break on file then page for
    determinism.
-   `file_name` is optional and supplied through a `file_names` map, because
    the display name belongs to SQLite file metadata that does not exist yet.
    An unknown id keeps the id as its label rather than raising.
-   `format_citations` returns an empty string for no citations, so an
    ungrounded answer shows no stray "Sources:" heading.

### Phase 1 exit condition — met

`backend/app/tests/test_citations.py` ends with a test that runs the entire
pipeline against a PDF written during the test: a three-page document whose
answer appears only on page 2. Extraction, chunking, embedding, indexing,
search, generation and citation all run for real, and the resulting citation
reads `graphs.pdf — page 2`.

From the backend alone:

1.  [x] Give Noye a PDF.
2.  [x] Extract it.
3.  [x] Chunk it.
4.  [x] Embed it.
5.  [x] Index it.
6.  [x] Ask a question.
7.  [x] Retrieve relevant chunks.
8.  [x] Generate an answer.
9.  [x] Return correct source/page citations.

If this works, the core of Noye works.

What remains before a person can use it: SQLite file metadata (so a citation
can show a file name instead of an id), an upload API, visible processing
states, and the UI. Those are Phase 2 onward.

------------------------------------------------------------------------

# 10. Phase 2 --- Library

Build the first major UI.

Route:

``` text
/library
```

## Features

-   [x] Drag-and-drop upload
-   [x] File picker
-   [x] PDF support
-   [x] Markdown support
-   [x] TXT support
-   [x] File list
-   [x] File type
-   [x] File size
-   [x] Processing status
-   [x] Delete file
-   [x] Failure state

Suggested processing UI:

``` text
Uploading
   ↓
Extracting
   ↓
Chunking
   ↓
Embedding
   ↓
Ready
```

Prefer these real stages over fake percentage progress bars.

## Upload API

Example:

``` text
POST /files
```

Backend flow:

``` text
receive file
   ↓
save original
   ↓
create File record
   ↓
extract
   ↓
chunk
   ↓
embed
   ↓
Qdrant
   ↓
READY
```

### Implemented pipeline

`ingest_file(connection, file_id)` in `backend/app/services/ingestion.py` owns
everything from `extract` to `READY`. The API layer's job is the first three
steps — save the upload and create the row — then hand the id over.

It runs in the background, so the status written at each stage is the only way
the user learns where a file is:

``` text
EXTRACTING -> CHUNKING -> EMBEDDING -> READY
                                    \-> FAILED (with a reason)
```

Guarantees that matter more than the happy path:

-   **A failure never leaves a partial index.** If embedding or indexing dies
    part-way, the file's vectors and chunk rows are deleted before it is marked
    FAILED. Otherwise a file the library shows as broken would still answer
    questions using half its content.
-   **Re-ingestion is safe and complete.** Vectors are cleared before new ones
    are written. Chunk rows are replaced wholesale, but vectors are keyed by
    chunk index, so a second, shorter run would otherwise leave the tail of the
    first run searchable — tested explicitly by re-ingesting a shrunk document.
-   **Ingestion failures do not raise.** The failure *is* the outcome, recorded
    on the file for the library to display. Only a bad `file_id` raises, since
    that is a caller error rather than a user-visible failure.
-   **A file always reaches a terminal state.** Even an unexpected exception is
    caught, its type preserved in the message; a row stuck in `EMBEDDING`
    forever would be worse than an ugly error string.

Two product decisions are settled here:

-   **A PDF with no extractable text FAILS rather than going READY**, with a
    message naming OCR. A scan indexed as zero chunks would look searchable in
    the library and silently never match anything.
-   **Non-PDF uploads fail with "not supported yet"** until Markdown and text
    ingestion lands, rather than being stored as unsearchable files.

### Test

`backend/app/tests/test_ingestion.py` (17 tests). Unit tests use an in-memory
database, an in-memory Qdrant, and a mocked Ollama, and assert the exact status
sequence, that chunk rows carry the vector id actually stored for them, and
every failure path. The integration test ingests a real three-page PDF and then
asks a question about it, checking the citation reads `<filename> — page 2` —
the first point at which citations show a filename instead of a UUID.

## Delete behavior

### Implemented API

`backend/app/api/files.py`, mounted in `app/main.py`:

  ------------------------------------------------------------------------
  Route                      Behavior
  -------------------------- ---------------------------------------------
  `POST /files`              Saves the upload, creates the row, schedules
                             background ingestion, returns 201 with the
                             file in `UPLOADING`

  `GET /files`               Every file, newest first

  `GET /files/{id}`          One file — the polling endpoint

  `POST /files/{id}/reingest` Retry or re-index the saved original; 202

  `POST /files/{id}/cancel`   Stop active or interrupted processing; 202

  `DELETE /files/{id}`       Vectors, original, and metadata; 204,
                             or 409 while processing
  ------------------------------------------------------------------------

Decisions taken here:

-   **Uploads are stored as `{file_id}__{filename}`.** Two uploads of the same
    name would otherwise overwrite each other. `File.name` keeps the original
    for display. Duplicate *detection* belongs to the Phase 8 reliability
    baseline; silently destroying the first upload is not an acceptable stand-in.
-   **The response never includes `path`.** A server filesystem path is of no
    use to a client and invites being treated as a URL.
-   **Delete removes vectors first, and aborts the whole delete if that
    fails** (503). A half-deleted source whose vectors survive would keep
    answering questions about a document the user believes is gone — worse than
    a failed delete they can retry. A missing original file is tolerated.
-   **An empty upload is rejected** (400) and nothing is kept: a zero-byte row
    could never reach `READY` and would sit in the library forever.
-   **Markdown and text are accepted at the API boundary** even though
    ingestion still fails them, because the MVP scope includes those formats
    and the API should not be the thing that rejects them.
-   **The background task opens its own database connection.** The request's
    connection is closed when the response is sent, and the task runs on
    another thread.

CORS allows only `FRONTEND_ORIGINS` (default `localhost:3000` and
`127.0.0.1:3000`), since the Next.js dev server is a different origin.

**There is no authentication, by design** (see MVP scope). Anyone who can reach
this port can read and delete the user's documents, so the server binds to
`127.0.0.1` and must not be exposed on a network interface until auth exists.

Deleting a source must clean up:

``` text
original file
SQLite metadata
associated chunks
Qdrant vectors
```

------------------------------------------------------------------------

## Implemented UI

Built in `feat/library-ui`. The visual system is recorded separately in
`DESIGN.md`; this section records what the library page does and why.

### Design tokens, not `dark:` variants

`frontend/src/styles/tokens.css` declares every colour once with CSS
`light-dark()`, and `globals.css` maps those onto Tailwind names with
`@theme inline`. A component writes `bg-card` and gets the right fill in either
mode, so there are no dark-mode colour variants anywhere in the components. If a
`dark:` variant ever seems necessary, the token set is missing a role.

Turbopack compiles this with Lightning CSS, which downlevels `light-dark()` into
a pair of guard variables plus the companion rules — verified in the served
stylesheet, including the `[data-theme]` overrides that a future theme toggle
needs. So the browser floor is not raised by using it.

### The API is reached directly from the browser

Not through a Next rewrite. Two reasons: it keeps the backend's CORS allow-list
exercised, which is the only real protection on a server with no
authentication; and in Phase 5 the desktop build talks straight to a local
backend, so a development-only proxy would be a fiction. `multipart/form-data`
is CORS-safelisted, so an upload makes no preflight request — confirmed against
the running backend.

### Status is never carried by colour alone

Measured on the Phase 2 palette, the failure oxblood and the brand green differ
by 1.01:1 in luminance, and red-against-green is the worst pair for the
commonest colour blindness. So every state carries an icon and a word, and
colour is reinforcement only. Ready deliberately carries no colour at all: it is
the resting state of nearly every file, and colouring it would drown the one
card that needs a decision.

### Polling, and only where it is needed

Files still being ingested are polled individually on `GET /files/{id}` every
two seconds; a settled library makes no requests. The list is re-fetched when
the tab regains focus, so ingestion started elsewhere becomes visible without a
reload. Only terminal transitions are announced to a screen reader — narrating
every stage would talk over someone reading the page.

### Retry, cancellation, and per-file serialization

The library can retry a failed file from its saved original and stop a queued
or running ingestion. The API reserves each file before scheduling background
work, so a second ingestion or deletion gets 409 while it is busy. Cancellation
is cooperative: the pipeline checks between stages and after embedding before
indexing, cleans up derived data, and settles the file as `FAILED` with a clear
reason. A processing row left behind by a server restart can also be stopped;
this clears its derived data and lets the user retry or remove it. The UI no
longer treats a 60-second stall as permission to delete a live ingestion.

### Verified

-   `tsc --noEmit`, `eslint`, and `next build` all pass.
-   A 24-page PDF uploaded **from a browser** reached `READY` with 24 chunks,
    and Qdrant reports 25 points across the two indexed files. This closes the
    multipart-over-a-real-socket gap left open in the API work, and exercises
    the CORS path at the same time.
-   The served HTML and stylesheet carry the tokens, `role="status"`,
    `aria-live`, `aria-current`, the focus ring, `sr-only`, and the
    reduced-motion rules.

### Not verified

-   Visual judgement. No screenshot was captured: the machine had too little
    free memory to launch a browser under automation.
-   `next dev` did not hydrate the page during this work while the production
    build did, with the HMR websocket failing in the browser but upgrading
    correctly from curl. The cause was not established; memory was critically
    low throughout. Re-check the dev server before assuming it is healthy.


# 11. Phase 3 --- Search

Before or alongside full chat UI, expose semantic search directly.

Route:

``` text
/search
```

Example:

``` text
Query:
"How does Dijkstra choose the next vertex?"

Results:

Algorithms.pdf
Page 34
"...selects the unvisited vertex with the smallest..."

Lecture 07.pdf
Page 12
"...priority queue..."
```

Features:

-   [x] Search input
-   [x] Relevant snippets
-   [x] File names
-   [x] Page numbers
-   [ ] Similarity scores if useful
-   [x] Open source reference

The score is returned by the API but deliberately not displayed, so that item
stays unchecked rather than being claimed. "If useful" has not been established:
similarity is model-dependent, and until a threshold is calibrated on real
documents a bare 0.37 invites the reader to interpret a number nobody can
explain. Revisit it with evidence, not by adding the field.

This is useful both as a user feature and as a debugging tool for RAG
quality.

## 11.1 Starting point and scope

`backend/app/services/retrieval.py` already embeds a query and returns ranked
chunks with content, file id, page number, chunk index, and similarity score.
SQLite owns the human-readable file name. There is currently no search API,
source-opening route, or `/search` page. Phase 3 connects those pieces; it
does not add chat, conversation storage, or a new retrieval algorithm.

The first usable result is a person entering a query, reading a relevant
passage with its source name and optional page, then opening that original
source. PDF pages must come from stored provenance. Markdown and text files
have no page number and must not be labelled as page 1.

## 11.2 Branch and PR sequence

Use three focused branches, each created from an updated `main` after the
previous PR merges. Keep implementation and tests together in meaningful
commits; do not collect all of Phase 3 into one branch.

1.  `feat/search-api` — expose the existing retrieval service through
    `GET /search`. Return a typed result with snippet content, file id, file
    name joined from SQLite, nullable page number, chunk index, and score.
    Search only `READY` files, so an in-progress or failed source cannot be
    presented as searchable. Validate an empty query and the result limit;
    bound the limit rather than permitting an unbounded Qdrant response.
    Return a clear service error when embedding or vector search is
    unavailable. Cover ranking, metadata joins, page-free formats, empty
    library/results, validation, and upstream failures in API tests.
2.  `feat/source-reference` — add a read-only route such as
    `GET /files/{id}/source` that serves the saved original identified by its
    database row. Open PDFs inline so the client can append `#page=N`; open
    Markdown and text as text without inventing a page. Return 404 for an
    unknown row or missing original. Never accept a filesystem path from the
    request. Test file type, content, missing files, and path safety.
3.  `feat/search-ui` — build `/search` with a labelled input, submit action,
    ranked snippet cards, file name, optional page, and an Open source link.
    Activate Search in the application shell. Keep the query in the URL so a
    result can be revisited with Back or a copied link. Show distinct states
    for no indexed files, no matches, a pending search, and an unavailable
    backend. Reuse the Phase 2 tokens and citation treatment; verify keyboard
    operation, responsive layout, and both colour schemes.

The API may return a score for diagnosis, but the first UI need not display
it: similarity is model-dependent and lacks a user-facing interpretation
until a threshold or label is calibrated on real documents. Do not impose a
hard relevance threshold without measuring representative queries. Keep the
first result count modest (default five, with a bounded maximum); pagination
and source filters can follow evidence of need.

## 11.3 Acceptance and validation

-   A known PDF query returns the relevant passage, its actual file name and
    page number; Open source displays that PDF at the cited page.
-   A Markdown or text hit displays its file name and passage, with no page
    number, and opens the saved original.
-   Searches never show sources that are not `READY`. Empty libraries, no
    matches, invalid input, and unavailable Ollama/Qdrant produce distinct,
    understandable outcomes rather than a blank results area.
-   Backend unit/API tests cover the contracts above using the existing
    in-memory Qdrant and mocked embedding approach. A live-service smoke
    check is recorded separately when Ollama and Qdrant are available.
-   Frontend lint, TypeScript, and production build pass. Browser checks cover
    desktop and 390px layouts in light and dark schemes, Enter-key search,
    loading/error states, Back navigation, and opening a source. Record any
    check that could not run under `Not validated` in the PR.

After each merge, update the roadmap checkboxes only for behavior that was
actually implemented and verified. Correct the older README phase labels
when the Search page lands: this plan's Phase 3 is Search, Phase 4 is Chat.

------------------------------------------------------------------------

## 11.4 Implemented

Built across three branches as planned: `feat/search-api`, then
`feat/source-reference`, then `feat/search-ui`.

### The API searches only finished sources

`GET /search?q=…&limit=…` is thin over the existing retrieval service, adding the
two things retrieval leaves out on purpose: the human-readable file name, joined
from SQLite, and a restriction to `READY` files.

The restriction is the substantive behaviour. A file mid-ingestion has some of its
passages in the index and not others, and a `FAILED` one may have none; presenting
either as a result would show a partial document without saying so.

`searched_files` is on the response because "nothing is indexed yet" and "your
query matched nothing" need different words on screen, and an empty array cannot
tell them apart. An empty library returns before embedding anything. The limit is
bounded at 20 because it is passed straight to Qdrant.

### The source route takes an id, never a path

`GET /files/{id}/source` serves the saved original. The path comes from the
database row, and the resolved path is re-checked against the sources directory
anyway — a row pointing elsewhere would mean a tampered database, and serving
whatever it pointed at would turn an id into an arbitrary file read.

PDFs go out inline with their own media type so the browser's viewer renders them
and the client can append `#page=N`. Markdown and text are served as `text/plain`,
not `text/markdown`, which browsers download instead of displaying — a source you
cannot look at is not a source reference.

### The page keeps the query in the URL

Submitting navigates rather than fetching, so Back returns to the previous search,
a link can be copied, and a reload reproduces the results.

Four outcomes are kept distinct: nothing indexed yet (with a route to the
library), no matches (reporting how many files were searched), searching, and
backend unreachable. One blank results area would have conflated them.

Two React 19 constraints shaped the structure by rejecting the obvious code.
Syncing URL to state in an effect is refused by `set-state-in-effect`, so the
query is derived at render time; the form's field follows the URL by being
remounted on a `key` instead. Separately, `useSearchParams` fails the BUILD
without a Suspense boundary, so the part reading the URL is its own component —
which means the prerendered HTML is only a fallback, and a hydration failure
leaves this page blank rather than partly useful.

### Verified

-   Backend: 300+ tests. Live search returned page 18 at 0.652 for "how do I
    limit and skip rows" against an indexed 24-page PDF, versus 0.370 for an
    unrelated query — so ranking is meaningful, not merely responsive.
-   The source route returned the PDF byte-identical to the file on disk, inline,
    named as the user knows it rather than the `{id}__{name}` form on disk.
-   Frontend: 61 tests, plus `tsc`, `eslint` and a production build.
-   The project owner confirmed the page in a browser against a running backend.

### Not verified

-   No screenshot or automated browser check. That a PDF lands on the cited page
    from `#page=N`, the 390px layout, both colour schemes, and Back/Forward
    navigation were confirmed by a person, not by a test.
-   No relevance threshold is calibrated; see the note on similarity scores above.
-   Range requests are not handled on the source route, so a viewer seeking
    within a large PDF fetches the whole file. Largest tested: 2.1 MB.


# 12. Phase 4 --- Chat

Route:

``` text
/chat
```

Flow:

``` text
User question
      ↓
FastAPI
      ↓
Embedding
      ↓
Qdrant
      ↓
Relevant chunks
      ↓
Ollama
      ↓
Answer
      ↓
Citations
```

Features:

-   [x] New conversation
-   [x] User messages
-   [x] AI messages
-   [x] Citations below AI answer
-   [x] Persistent conversation history — stored and re-readable. **The model is
    not aware of earlier turns**; see §12.6.
-   [x] Conversation titles
-   [x] Loading state
-   [x] Retrieval/generation errors

Store conversations and messages in SQLite.

A key UI requirement:

**Sources should be easy to inspect rather than hidden.**

------------------------------------------------------------------------

## 12.1 Starting point and scope

The answering machinery already exists. `app.services.generation.answer_question`
retrieves passages and produces grounded prose; `app.services.citations` turns the
retrieval metadata into citations. Neither is reachable over HTTP, and nothing is
stored: every question would vanish with the page.

Phase 4 adds the two missing things — persistence for conversations and messages,
and a chat surface — and changes nothing about how an answer is produced. In
particular the model still never writes its own citations.

## 12.2 What persistence has to get right

Three decisions belong here rather than in the UI.

**A message's citations are stored, not recomputed.** Re-running retrieval to
re-display an old answer would show sources that were never the ones behind it —
the index changes as files are added, re-ingested and removed. A conversation is a
record of what was said, so the citations are written down with the answer.

**A citation survives its source file being deleted.** Storing only a `file_id`
would make an old answer silently lose its provenance the moment the user cleans
up their library. The file name is copied onto the stored citation so a past
answer keeps naming what it was based on, and the `file_id` is kept as well so the
source can still be opened when it does still exist.

**A failed answer is a message, not a lost turn.** If Ollama is down, the user's
question stays in the conversation with the failure recorded against it. Anything
else loses what they typed.

## 12.3 Branch and PR sequence

Three branches, each cut from an updated `main` after the previous merges.

1.  `feat/chat-persistence` — schema, models, and the SQLite layer for
    conversations, messages and message citations. Cascade deletes so removing a
    conversation removes its messages and their citations. A conversation's title
    is derived from its first question rather than asked for. Ordering is by
    creation, and the conversation list is by most recent activity. No API.
2.  `feat/chat-api` — `POST /chat` to ask inside a conversation (creating one if
    none is given), plus routes to list conversations, read one's messages, and
    delete one. The answer comes from the existing generation service; citations
    from the existing citation service. Unreachable Ollama, unsearchable index and
    an empty question each produce their own outcome. A question that retrieves
    nothing is answered honestly without calling the model, as generation already
    does.
3.  `feat/chat-ui` — `/chat` with a message list, a composer, per-message
    citations, and a conversation sidebar. Citations are **inspectable rather than
    hidden**: the plan's own UI requirement for this phase. Reuse the Phase 3
    result-card treatment and the Open-source link so a citation behaves the same
    way in both surfaces.

## 12.4 An open question the UI has to answer

Measured on a live run: asking about something the indexed document does not
cover produced an answer that correctly said the excerpts did not contain it —
with five citations attached. Vector search always returns its nearest
neighbours, so passages are retrieved regardless, and `Answer.is_grounded` only
tells us retrieval returned something, not that the model used it.

So a stored citation is precisely "a passage given to the model as context", not
"a source supporting this answer". Three ways to close the gap, none free:

1.  **A calibrated relevance threshold.** Evidence so far is 0.675 for a covered
    question and 0.52 for an uncovered one against the same document — two
    points, not a boundary. Needs measurement across several documents first.
2.  **A signal from the model**, e.g. asking it to state whether the excerpts
    answered the question. Adds a parsing step and a way for the model to be
    wrong about itself.
3.  **Honest framing in the UI**: label them as the passages consulted, and show
    the answer's own words about whether they sufficed.

Option 3 costs nothing and is not exclusive with the others, so the chat UI
should do it regardless. Do not add a threshold without the measurement.

## 12.5 Acceptance and validation

-   Asking a question about an indexed document returns a grounded answer whose
    citations name the real file and page, and those citations are still correct
    after a reload.
-   Deleting a cited file leaves the old answer's citation readable, with the
    file name intact, and the Open-source link absent or clearly unavailable.
-   A conversation survives a restart. Its title reflects its first question.
-   Ollama being down produces a recorded failure against the user's question,
    not a lost message.
-   Backend tests cover the persistence contracts and the API's outcomes using the
    existing in-memory Qdrant and mocked-Ollama approach. Frontend lint,
    TypeScript, tests and production build pass. Record any browser check that
    could not run under `Not validated`.


## 12.6 What "conversation history" does and does not mean

Conversations are stored, titled, listed by recent activity, re-readable with
their citations intact, renameable and deletable. That is the roadmap item, and
it is done.

**The model does not receive earlier turns.** Each question is answered from
retrieval alone, so asking "and what about the second one?" will not resolve
against the previous answer — the retrieval step sees only those words.

This is unresolved rather than decided. The cost of fixing it is real: history
competes with retrieved passages for a local model's context, and `qwen3.5` on
this hardware is already the slow step. Options, in rising cost:

1.  **Rewrite the follow-up question** using the last turn or two before
    retrieval, and keep the prompt as it is. Cheap, and it fixes the common case
    of a pronoun referring to the previous answer.
2.  **Include the last N turns in the prompt** alongside the excerpts. Simple,
    but it spends the context the passages need, and the trade gets worse as a
    conversation grows.
3.  **Summarise the conversation** and carry the summary. Most capable, and the
    most machinery, including a second model call per turn.

Do not pick one without measuring what it costs in answer quality and latency on
this hardware. Option 1 is the one to try first.

## 12.7 Implemented

Built across three branches: `feat/chat-persistence`, `feat/chat-api`,
`feat/chat-ui`.

### Citations are written down, not recomputed

Re-running retrieval to re-render an old answer would show sources that were
never the ones behind it, because the index changes as files are added,
re-ingested and removed. The file name is copied onto each stored citation, so an
answer keeps naming what it was based on after that file is deleted; the file id
is kept too, so the original can still be opened while it exists.

### A failed answer is a turn, not a lost question

The user's question is written before the model is called, and a failure —
unreachable Ollama, unsearchable index, an embedding that could not be made — is
recorded against the assistant's turn. The UI renders that as a notice carrying
the reason rather than an empty bubble, so someone returning to a conversation can
see what went unanswered and why.

### They are "passages consulted", not "sources"

The plan's §12.4 question was answered by framing, and the framing is load-bearing
rather than cosmetic. Vector search always returns its nearest neighbours, so a
question the documents do not cover still retrieves passages while the model
correctly declines. "Passages consulted" is true either way; "Sources" would claim
support nobody has verified. A test asserts the word does not ship.

They are collapsed by default so an answer reads as prose, and expandable because
this phase's own requirement is that sources be easy to inspect rather than
hidden. Each names its file and page and opens the original at that page, reusing
Phase 3's `sourceUrl`.

### Verified

-   Backend: 352 tests, 0 skipped, including an end-to-end run against the real
    local model. Frontend: 96 tests, plus `tsc`, `eslint` and a production build.
-   A real answer over a real socket: "What does OFFSET do in a SQL query?"
    returned "OFFSET skips rows (k rows) before returning rows when used with
    LIMIT" citing page 18 of the indexed PDF.
-   The shipped client bundle carries every state string, and `"Sources"` appears
    zero times in it.

### Not verified

-   No screenshot or automated browser check: this machine could not launch a
    browser. The responsive layout and both colour schemes are unconfirmed.
-   Long conversations render every message with no virtualisation, and a
    conversation is read whole in two queries. Both are right for a local
    single-user app and unmeasured past a handful of turns.
-   Concurrent asking in two tabs of one conversation is not handled.


# 13. Phase 5 --- Document Workspace

This is one of Noye's strongest differentiators.

From an AI answer:

``` text
Create Document
```

Then:

``` text
Answer
+ retrieved sources
+ user instruction
       ↓
     Ollama
       ↓
    Markdown
       ↓
Document Workspace
```

Route:

``` text
/documents
```

Features:

-   [x] Create document
-   [x] Generate from chat answer
-   [x] Markdown editor
-   [x] Markdown preview
-   [x] Save — manual, with an explicit state, `Cmd/Ctrl-S`, and an unload
    warning while edits are unsaved. Autosave was rejected; see §13.6
-   [x] Rename — the title field, saved with the body
-   [x] Delete
-   [x] Export `.md`
-   [x] Export PDF — native synthetic output inspected (§16.8); broader acceptance remains Phase 8

Example use:

``` text
User:
"Turn this explanation into exam revision notes."

Noye:
retrieves sources
      ↓
creates structured Markdown
      ↓
user edits it
      ↓
exports PDF
```

AI-generated text should always remain editable.

------------------------------------------------------------------------

## 13.1 Starting point and scope

Chat produces grounded answers with the passages behind them. Nothing can be kept
from one: an answer lives in a conversation and is read-only. Phase 5 adds
documents — generated from an answer, then **edited by the person**, saved, and
exported.

The principle the plan states for this phase is the constraint: AI-generated text
must always remain editable. So a document is not a rendering of an answer that
re-derives itself. It is a copy the user owns from the moment it exists, and
nothing regenerates it behind their back.

## 13.2 Two dependency decisions

Both are made here rather than discovered mid-branch, because both add something
to a local-first app the user installs themselves.

### PDF export uses the browser's own print path

Not a server-side renderer. `weasyprint` and its relatives need system libraries
(cairo, pango) that a user would have to install with a package manager before
Noye worked — for a product whose claim is that it runs on your machine without
setup, that is a real cost. The browser already has a PDF engine, it is offline,
and it needs no dependency at all.

The cost is honest: less control over the output, and the user passes through a
print dialog. Mitigated with a print stylesheet so the exported page is the
document rather than the application around it. Revisit only if the output proves
unusable, and say so in the PR if it does.

### Markdown preview uses `react-markdown`, not a string-to-HTML renderer

The content is model-generated and then user-edited, and it is derived from the
user's own files — so an ingested PDF containing something that looks like a script
tag could reach the preview through the model. A `marked`-style renderer produces
an HTML string that has to go through `dangerouslySetInnerHTML`, which makes
sanitisation a thing we must not forget. `react-markdown` builds a React element
tree instead and does not render raw HTML by default, so the safe behaviour is the
default rather than a discipline.

## 13.3 What persistence has to get right

**A document keeps the citations it was generated from.** Same reason as chat: the
index changes, so re-deriving them later would attribute a document to sources that
were never behind it. They are copied in, file name included, and survive the file
being deleted.

**A document records where it came from, loosely.** The conversation and message it
was generated from are stored, but as plain columns without a foreign key — deleting
a conversation must not delete the documents made from it. The document is the
user's work; the conversation was scaffolding.

**Edits are the document.** There is no "regenerate" that silently replaces what
someone wrote. Generating again creates a new document.

## 13.4 Branch and PR sequence

1.  `feat/document-persistence` — schema, models, SQLite layer. Documents carry
    title, Markdown body, optional provenance, and copied citations. No API.
2.  `feat/document-api` — CRUD plus `POST /documents/generate`, which turns a
    stored answer plus a user instruction into Markdown through a prompt built for
    that task rather than the QA prompt. Generation failures do not create a
    half-written document.
3.  `feat/document-ui` — `/documents` with a list, a Markdown editor, a preview,
    and both exports. Activate Documents in the shell.

## 13.5 Acceptance and validation

-   Generating from a chat answer with an instruction ("turn this into revision
    notes") produces structured Markdown that is immediately editable, and the
    edit is what persists.
-   A document's citations still name the right file and page after a reload, and
    after the cited file is deleted.
-   Deleting the conversation a document came from leaves the document intact.
-   `.md` export round-trips: what is exported is what is in the editor.
-   PDF export produces the document, not the application chrome around it.
-   Backend tests cover the persistence contracts and the API's outcomes with the
    existing mocked-Ollama approach. Frontend lint, TypeScript, tests and
    production build pass. Record any browser check that could not run under
    `Not validated`.


## 13.6 What was built, and the decisions taken along the way

This is the historical Phase 5 checkpoint. §16.8 records the later native export
inspection and fixes, including a long cited PDF without application chrome.

Three branches, merged as #24 (persistence), #25 (API) and #26 (UI). Frontend
tests went from 96 to 115; the backend suite collects 420, the documents tests
among them.

**One acceptance criterion in §13.5 is not met.** "PDF export produces the
document, not the application chrome around it" is unverified: the print
stylesheet exists and a test asserts the preview carries the `data-print`
attribute it depends on, but no printed page has been inspected, because Chromium
cannot launch at this machine's available memory. The checkboxes above say so
rather than claiming it. This is the cost §13.2 accepted when it chose the
browser's print path — weak control over output — and it should be confirmed by
eye during Phase 8's native export acceptance pass.

**The print stylesheet is a whitelist.** Only `data-print="document"` and its
ancestors survive printing. A blacklist would need every future control
remembering, and its failure mode is a stray sidebar inside someone's PDF; a
whitelist fails as a missing element instead, which is noticed at once.

**Autosave was rejected.** A local model's output is long and edits to it are
wholesale rather than incremental, so an autosave firing mid-thought would make
undo the user's problem. What autosave usually protects against — losing work by
navigating away — is handled by a `beforeunload` warning, which costs nothing.

**PDF export is disabled outside the Preview tab.** Printing the Write tab would
put raw Markdown into the PDF. The control explains why rather than silently
producing a bad export.

**The `react-markdown` decision from §13.2 held, and is now tested rather than
asserted.** A test feeds `<script>` and `<img onerror>` into the preview and
checks that neither element reaches the DOM, and a second checks raw HTML appears
as text rather than vanishing — silently dropping a line would leave someone
hunting for it.

**A test-infrastructure change came out of the UI work.** Adding `useRouter` to
the message bubble broke three unrelated chat tests with "invariant expected app
router to be mounted". `next/navigation` is now mocked in the test setup rather
than per file, so the next component that navigates does not repeat it.

**Three defects were caught by checking rather than by a test failing**, which is
worth noting because none of them would have failed a test. A string replacement
inserting the print stylesheet orphaned the `prefers-reduced-motion` block's body.
Seven `data-print-hide` attributes were dead code, naming a mechanism the
stylesheet does not use. And one existing chat test asserted "no button at all" as
a proxy for "no passages panel", which the new action quietly made false — a
proxy assertion outlives the assumption it was standing in for.

**§12.6 is now more visible, not less.** Phase 5 makes chat the route into
documents, so the fact that the model does not receive earlier conversation turns
is easier to run into. Its cheapest option — rewriting a follow-up question
before retrieval — belongs to Phase 7 item 11 after desktop implementation;
Phase 8 rechecks the resulting quality and latency.


# 14. Phase 6 --- Desktop Application

**Sequence update, 2026-10-03:** implement Tauri in Phase 6, then the twelve approved
core workflow improvements in Phase 7 (§16). Stability/quality refinement and final
packaged-app acceptance follow in Phase 8 (§17.10). Proceed with desktop milestones
once their relevant unit/API/UI tests, lint, types and builds pass; these checks continue throughout
implementation. Completing this phase does not declare the desktop MVP accepted.
Native PDF export, live RAG quality and local/cloud latency remain unresolved until
observed in Phase 8's packaged-app acceptance pass.

Use Tauri to package the application.

Initial target:

``` text
macOS
```

Then:

``` text
Windows
```

Desktop work includes:

-   [x] Tauri setup
-   [x] Start/manage the app's own backend
-   [x] Manage local data directory and explicit copy-only web-data import
-   [x] Opt-in Qdrant preparation, verified ownership, persistent storage and shutdown
-   [x] Ollama availability, explicit installed-service start and model management
-   [x] Application packaging (local unsigned preview)
-   [x] macOS build (Apple Silicon; other machines not validated)
-   [ ] Windows build

## 14.1 Desktop implementation order

1. **Tauri foundation and lifecycle:** macOS application shell, persistent app-data
   location, managed backend startup/shutdown, readiness checks, and clear Ollama/
   Qdrant availability. Package a built UI rather than relying on a development
   server. Preserve existing user files, conversations and documents on migration.
2. **Chat-focused interface:** familiar AI-assistant layout with conversation
   navigation on the left, a readable central conversation and composer, model/
   provider selection, and an inspectable source panel. Library and Documents
   remain accessible. Reuse the existing palette and accessibility rules; the
   requested interaction direction supersedes the older library-first framing.
3. **First-run setup:** detect OS, architecture, total/available RAM, available
   disk, and known inference acceleration. Detect Ollama and installed models.
   Explain a conservative recommendation and its download size; the user chooses
   local setup or a cloud key. Hardware estimates are guidance, not a guarantee
   of measured speed. Optional short benchmarking can refine a recommendation.
4. **Model installation:** offer recommended generation and embedding models with
   explicit download confirmation, progress, cancel/retry, disk checks and usable
   errors. Never silently download a model or enable cloud billing. Start with
   Ollama's supported model-management API rather than arbitrary shell commands.
5. **Persistent AI settings:** let the user change installed generation models and
   providers later. Store cloud credentials using OS-protected credential storage;
   return only availability to the UI. Changing a generation model needs no index
   rebuild. Changing an embedding model does, and requires the existing explicit
   rebuild workflow.
6. **Handoff to Phase 7:** finish desktop implementation, record its validation
   and outstanding defects, then implement the twelve improvements in §16.
   Phase 8 (§17.10) performs subsequent stability/quality refinement and final
   packaged-app acceptance; keep the MVP checklist open until then.

## 14.2 Desktop implementation acceptance

- First launch presents a usable local recommendation or a cloud setup path.
- Installation can finish, fail, be cancelled and retried with clear feedback.
- Installed generation models, Gemini, OpenAI and Claude can be selected and changed later.
- A provider/model switch does not discard saved conversations or documents.
- Cloud payload disclosure appears before use; local mode sends no content to Google.
- The packaged app launches and stops its own backend cleanly without stopping
  unrelated user services.
- Relevant unit/API/UI checks, lint, types and packaged builds pass for each
  milestone; retain outstanding checks explicitly for Phase 8 (§17.10).
- Full workflow acceptance, native export inspection and live quality/latency
  measurement belong to Phase 8 and remain required before the MVP release.

## 14.3 macOS foundation implementation

Implemented on `feat/tauri-macos`, based on the unmerged
`feat/optional-gemini` work. Branch names now follow the user's requested `feat/`
prefix without `codex/`. No published history was rewritten.

The Tauri 2 application packages a Next.js static export and a native PyInstaller
sidecar. The backend binds a reserved loopback socket on an OS-selected port and
announces readiness only after SQLite schema initialization. The frontend waits
for that announcement before mounting API consumers; source and Markdown export
links use the same runtime address. A lost native command or failed startup has
bounded waiting and a visible error rather than indefinite loading.

The app owns only its sidecar. Closing the window or quitting requests graceful
shutdown, with a bounded fallback for that child alone. Closed parent stdin also
stops the backend if the parent disappears. A single-instance guard prevents
accidental duplicate app launches. Ollama and Qdrant are inspected with bounded
GET requests, never started, stopped or downloaded by this milestone.

Desktop storage lives in macOS Application Support, not the app bundle or the
frozen backend's extraction directory. The default desktop Qdrant collection is
`noye_desktop`, separate from the web workspace's `noye`, so a desktop rebuild
cannot silently discard the web index. Explicit workspace import copies sources,
documents and a SQLite backup, rewrites copied source paths, rejects existing
destinations and symbolic links, and leaves originals and credentials untouched.
The copied library requires an explicit desktop-index rebuild. No existing user
workspace was imported during implementation.

Build/data instructions and exact validation evidence are in `docs/DESKTOP.md`.
This completes §14.1 step 1's local macOS foundation, not the desktop MVP release.
The chat-focused layout is implemented under §14.4, with a read-only first-run
recommendation guide under §14.5. Next: opt-in installation and secure persistent
AI settings. Live RAG, citations, exports, inference latency,
Windows, other Macs and signed/notarized distribution remain unvalidated; final
macOS workflow acceptance and quality/latency measurement belong to Phase 8.

## 14.4 Chat-focused workspace implementation

Implemented on the same `feat/tauri-macos` branch at the user's request. Web and
desktop launch into Chat, with conversation navigation on the left, a bounded
scrolling message column and bottom composer. Library, Search and Documents remain
reachable. Provider selection shows the configured model; changing installed
generation models belongs to §14.1 steps 4–5, not this milestone.

Each answer can open its own consulted-passage metadata in a right-hand panel on
wide screens or an inline panel at smaller widths. It retains file/page links and
the warning that retrieved context is not verified support. Markdown answers use
the existing safe renderer, without automatic images or document print marking.
The UI continues to disclose cloud payloads and the lack of previous-turn context.
The waiting state names the selected provider without pretending to know which
retrieval/generation stage is active.

URL-keyed controllers abort stale reads and ignore late generation results after
navigation; generation itself continues on the backend. Delete completion cannot
reset a different open conversation. Failed questions return to the composer,
IME composition does not submit Enter, and scrolling respects reduced motion.

Frontend tests: **160 passed**; ESLint and TypeScript passed. The macOS/static UI
build passed. Browser UI checks used synthetic in-memory conversations, not live
AI or personal files. Native launch/navigation and cleanup were observed. Exact
evidence and limitations are recorded in `docs/DESKTOP.md`.

This completes §14.1 step 2. The first-run hardware prerequisite and read-only
guide are described below. This does not complete final live RAG/PDF acceptance
or fix inference latency.

### First-run hardware foundation (2026-10-04)

`GET /runtime/hardware` now reports OS, architecture, logical CPUs, workspace-volume
free disk, and macOS total/free-plus-inactive memory. Missing or restricted probes
return null, not zero. Apple Silicon architecture is an acceleration candidate,
not a verified Metal device or speed benchmark. Queries are read-only and bounded;
no credentials, user paths, model downloads or cloud calls are included.

Hardware/API and existing desktop lifecycle tests: **22 passed**; backend Ruff
passed. This is only the measurement prerequisite for §14.1 step 3. Recommendation
rules and first-run UI were pending at this checkpoint; §14.5 adds the read-only
guide. Installation and secure persistent settings remain pending.
The user requested stopping at ordinary usage limits, so the milestone is not
marked complete. See `docs/DESKTOP.md` for validation boundaries.

## 14.5 Conservative recommendations and read-only setup guide

Implemented 2026-10-05 on the same `feat/tauri-macos` branch. `GET /runtime/setup`
combines measured hardware, GET-only local service/model inventory checks and a
small versioned Ollama catalog. Recommendations use total RAM and current available
memory, reserving headroom for the OS, app, local embeddings and short questions.
Unknown acceleration considers only the smallest candidate. Busy/unknown memory
does not claim the model fits; workspace disk is not claimed to be Ollama's actual
model-storage volume. Download sizes come from official Ollama pages; memory budgets
are Noye heuristics, not vendor requirements or measured speed/quality.

After the owned backend is ready, a desktop-only guide shows the candidate, current
model, approximate download sizes and missing prerequisites. Local/Gemini views
explain their data paths without changing providers, downloading models, making
inference calls or exposing keys. Only guide dismissal is remembered locally;
AI setup reopens it with fresh readings. Skip/Continue and failed-check retry remain
available, while saved-work UI stays mounted. A configured key is not live validation.

Executed backend checks: **588 passed, 19 skipped**; frozen-backend lifecycle/setup
checks: **10 passed**. Frontend: **175 passed**; Ruff, ESLint, TypeScript and the
unsigned macOS build passed. Browser checks used synthetic fixtures; native launch
showed actual hardware and offline services. Exact evidence, interaction repairs
and limitations are in `docs/DESKTOP.md`.

This implements the recommendation/guide portion of §14.1 step 3, not complete
first-run AI setup. Next are explicit model downloads with progress/cancel/retry
and actual model-volume disk checks (§14.1 step 4), persistent generation-model
settings and OS-secure API-key entry (§14.1 step 5), then remaining service setup
(§14.1 step 6). No automatic cloud fallback is permitted. Embedding changes still
require an explicit rebuild. Final live RAG, latency and native PDF acceptance
remain deferred to Phase 8 as requested.

Avoid making desktop packaging block development of the knowledge engine.

### AI management update — 2026-10-05

Implemented explicit recommended-model downloads with user-confirmed model-volume
disk checks, layer progress, cancel/retry and sanitized errors. Exact-name
deletion protects configured generation, fixed embeddings and Noye's active
inference. Model writes require a per-process desktop capability and loopback
Ollama. No arbitrary shell command, remote mutation or partial-blob cleanup.

Implemented native model/default-provider preferences and macOS Keychain
entry/removal for three cloud APIs. Private stdin passes credentials to the owned
backend with a non-secret acknowledgement; whole settings snapshots preserve
running jobs. The settings overlay preserves workspace children. Frontend design
skills guided three calm sections, compact service messaging, palette-matched
progress and fixed dialog controls with responsive scrolling.

Validated: backend **632 passed, 19 skipped**; frontend **182 passed**; native Rust
**3 passed**; frozen-backend lifecycle/configuration **10 passed**. Ruff, ESLint,
TypeScript and unsigned macOS packaging passed. Browser fixtures exercised fake
key save, downloads, cancel and draft/focus preservation. Native non-secret save
and secure input rendering were observed. Exact evidence is in `docs/DESKTOP.md`.

At this checkpoint, Ollama/Qdrant service preparation/recovery was still pending.
The owner clarified that native credential lifecycle, live model management and
other real-service acceptance belong to Phase 8, not a live-test gate for Phase 6.
The implementation update below supersedes the service limitation. Actual cloud
authorization, RAG/quality/latency, PDF export and packaged-app E2E remain unvalidated.

### Service preparation and implementation handoff — 2026-10-05

Settings now explicitly starts an installed local-only Ollama and prepares pinned
Qdrant through local Docker Desktop. It opens Docker or fixed official prerequisite
guides on request; no package installer, automatic model download or cloud fallback.
Custom service URLs remain externally managed. Existing healthy services are reused,
never adopted. Occupied/unhealthy external ports or previous-session containers are
left untouched. Retry only restarts an unhealthy child/container owned by this session.

Qdrant persists in app-data `qdrant/storage`, with a stable workspace UUID, exact
container ID, owner label, pinned image, verified mount and localhost-only REST port.
No gRPC publishing, container/volume deletion, index reset or remote Docker context.
Shutdown cancels app-owned preparation/model jobs and stops only owned handles;
the native backend fallback allows 16 seconds for drain and bounded cleanup.
New Qdrant storage does not import old vectors; Library check/rebuild stays explicit.

The requested dark palette is neutral charcoal, off-white and muted blue; light
mode is unchanged. Design skills guided semantic tokens, ownership-labelled rows,
44px actions, quiet separators and clear confirmation/retry states.

Relevant unit/API/UI checks, lint, types and macOS packaging are recorded in
`docs/DESKTOP.md`. This finishes the requested Phase 6 macOS implementation scope
and unblocks focused Phase 7 work, beginning with §16.3's Compose exposure fix.
It is not MVP acceptance: real Docker/Ollama preparation and shutdown, model/key
lifecycle, browser/native visual inspection, RAG, latency and actual exported PDFs
remain Phase 8 checks. Windows and signed/notarized distribution are not delivered.

------------------------------------------------------------------------

# 15. Testing Strategy

Testing should focus heavily on the knowledge pipeline.

## Unit tests

### Extraction

-   [ ] PDF text extraction
-   [ ] Page preservation
-   [ ] Invalid PDF

### Chunking

-   [ ] Chunk size
-   [ ] Chunk overlap
-   [ ] Ordering
-   [ ] Page metadata

### Citations

-   [ ] Correct file mapping
-   [ ] Correct page mapping
-   [ ] Multiple source mapping

### Retrieval

-   [ ] Known query retrieves expected chunk
-   [ ] Top-K behavior

### File deletion

-   [ ] Metadata removed
-   [ ] Vectors removed
-   [ ] Original source removed

## API tests

-   [ ] `/health`
-   [ ] upload file
-   [ ] list files
-   [ ] delete file
-   [ ] semantic search
-   [ ] chat
-   [ ] document creation

## End-to-end test

Eventually test:

``` text
Upload PDF
   ↓
Wait for Ready
   ↓
Ask known question
   ↓
Receive correct answer
   ↓
Verify citation
   ↓
Create document
   ↓
Edit
   ↓
Export
```

------------------------------------------------------------------------

# 16. Phase 7 --- Core Workflow Improvements

Implement the twelve improvements approved on 2026-10-03 after the Phase 6 Tauri
milestones. This is an implementation phase: relevant unit/API/UI tests, lint,
types and builds run with each change. Phase 7.5 then adds the approved folder/wiki
and prompt-driven document workflow; Phase 8 performs broader stability/quality
refinement and final packaged-app acceptance.

All twelve items have their implementations and measured limits recorded
(see §§16.5–16.8). This includes actual local answer/abstention evaluation and
native cited exports; larger quality studies and the full packaged acceptance
flow remain Phase 8 work. Reassess current code before further changes and
preserve all saved work.

## 16.1 Approved scope and expected benefit

| ID | Priority | Improvement | Expected benefit |
| --- | --- | --- | --- |
| 1 | High | Store retrieved excerpts and pass them to document drafting | Draft detailed documents using source examples and numbers omitted from a short answer |
| 2 | High | Preserve the source version and excerpt behind each citation | Inspect the evidence behind old answers after originals change or disappear |
| 3 | High | Prevent rebuilds from conflicting with active work | Avoid collection resets colliding with uploads or ingestion |
| 4 | High | Version indexes by model, chunking and input format | Detect incompatible old vectors when processing or embedding behavior changes |
| 5 | High | Back up and restore SQLite together with original files | Preserve conversations and user-edited documents independently of the derived index |
| 6 | High | Persist jobs, recover after restart and cancel between batches | Make interrupted work understandable and safely resumable |
| 7 | High | Complete desktop data/service/model integration | Make installation usable and service/model failures diagnosable |
| 8 | High | Restrict published Qdrant ports to localhost | Keep local knowledge storage within the intended network boundary |
| 9 | Medium | Separate query/document embedding formats and validate input length | Use task-appropriate inputs and detect truncation instead of silently losing text |
| 10 | Medium | Establish retrieval evaluation and assess hybrid search/reranking | Measure and improve bilingual, exact-term and multi-document retrieval |
| 11 | Medium | Support bounded conversation context and selected sources | Resolve follow-up questions and restrict answers to the user's chosen material |
| 12 | Medium | Improve evidence inspection, cited exports and PDF extraction status | Inspect/share document provenance and identify pages with no extracted text |

Hybrid retrieval and reranking are evaluation-gated options in item 10. A measured
finding that an option does not improve the baseline is a valid documented result;
adding an extra model or service is not required to mark the evaluation complete.
Item 12 includes PDF extraction coverage reporting, not mandatory OCR, layout
models or a new document parser. Folder/topic wiki organization and prompt-driven
source documents are now planned in Phase 7.5 (§16A); item 11 supplies source
selection within the existing Phase 7 workflow.

## 16.2 Implementation milestones

### 1. Retrieved excerpts in document generation

-   [x] Persist the actual excerpts used for an answer and pass that saved material
    with the answer and instruction to `services/documents.py`. Reuse item 2's
    evidence storage; do not re-retrieve current chunks to reconstruct old evidence.
- Expanded historical excerpts remain local-only: require loopback Ollama for
  their use. Gemini/OpenAI/Anthropic drafts retain the instruction, saved answer
  and source-name payload, with explicit UI disclosure; stored snapshots stay
  intact. No expanded cloud payload or automatic provider fallback is added.
- Validate captured generation requests contain source detail absent from the
  answer, while legacy messages without snapshots are clearly identified and do
  not acquire invented historical evidence.

### 2. Citation evidence and source versions

-   [x] Add immutable excerpt snapshots and original source identity/version to
    stored message/document evidence using additive SQLite migrations. Preserve
    file/page/chunk metadata and any available index identity from item 4.
- Keep historical evidence after source re-ingestion/deletion; show changed,
  missing and legacy-unknown originals clearly. Existing citation metadata remains
  readable, but cannot be labelled as an exact text snapshot it never stored.
- Validate old evidence remains identical after source edits/re-indexing/deletion
  and conversation/document reload. Never treat the presence of citations as
  proof that every generated or subsequently edited sentence is supported.

### 3. Rebuild and ingestion coordination

-   [x] Coordinate library-wide maintenance with ingestion/deletion before any
    collection reset. Refuse or safely drain conflicting work; reserve eligible
    work before destructive operations. Keep the ordinary non-reset rebuild path.
- Start with the existing single-process architecture and a shared maintenance
  guard; use versioned collections only if a concrete need justifies the change.
- Validate a dimension-changing rebuild with a busy file cannot reset the live
  collection before reporting the conflict. Cover upload, cancel, deletion and
  duplicate rebuild requests, including failure cleanup.

### 4. Index identity and compatibility

-   [x] Persist an index fingerprint covering embedding model identity/digest,
    vector dimension, input-format version, and extraction/chunking configuration.
    Store source revisions separately and expose when an explicit rebuild is needed.
- Reuse existing migrations and integrity checks. Mark legacy identity as unknown;
  do not invent compatibility from the model name alone. Generation-model changes
  do not invalidate embeddings; embedding-format/model changes may require rebuild.
- Validate changes under the same model tag and changes to prefix/chunk settings
  are detected, incompatible spaces never share rankings, and saved writing survives.

### 5. Complete workspace backup and restore

-   [x] Build a user-visible backup/restore workflow covering originals, SQLite
    conversations, edited documents and evidence snapshots. Reuse SQLite's backup
    API and the desktop import's copy-first/no-overwrite behavior, including WAL data.
- Define a consistent snapshot boundary with active writes/jobs. Include versioned
  metadata, exclude credentials/model weights and rebuildable vectors, and restore
  into a new destination before an explicit switch. Correct stale "SQLite is
  entirely rebuildable" documentation in `db/database.py` and storage helpers.
- Validate round-trip preservation, invalid/partial backup rejection, migration,
  missing-source reporting and no overwrites. Rebuild the restored derived index
  without claiming original files alone can recover conversations or edited text.

### 6. Durable jobs and responsive cancellation

-   [x] Persist job identity, status/progress and interruption reason in SQLite;
    recover interrupted work on startup and expose safe resume/retry. Use bounded
    local workers rather than introducing Redis/Celery by default.
- Check cancellation between embedding batches, bound simultaneous local inference,
  and keep only fully committed files searchable. Resume idempotently and reconcile
  SQLite/Qdrant after partial writes. Never automatically repeat cloud generation
  or activate billing because an app restarted.
- Validate restart/closed-parent behavior during queued, embedding and indexing
  stages, batch cancellation, retry and repeated resume without duplicate vectors.

### 7. Desktop data, service and model integration

-   [x] Reuse Phase 6 app-data paths, owned backend lifecycle, service/model checks,
    onboarding and persistent AI settings; complete remaining integration gaps.
- Distinguish configuration, service availability, installed model and readiness.
  Preserve work across app replacement, imports and provider/model changes. Bound
  generation context/output budgets and make long-running progress/cancel states
  understandable; model installation remains explicit and credentials OS-protected.
- Validate missing/recovered services and models, installation failure/cancel/retry,
  bounded startup/shutdown and data persistence. Already validated foundation work
  stays complete; this item is not a second Tauri build.

### 8. Local-only Qdrant exposure

-   [x] Bind Docker-published Qdrant ports to `127.0.0.1`; remove the gRPC mapping
    unless used. Keep app-owned backend binds local and remove documentation that
    treats CORS as authentication or a substitute for network access control.
- Validate Compose configuration and effective listener bindings when Docker is
  available, and confirm local ingestion/search still connect. Do not claim a
  network verification from static YAML inspection alone.

### 9. Task-specific embedding inputs and length limits

-   [x] Separate query and document embedding functions with explicit model-aware
    input formats. For EmbeddingGemma, verify runner behavior and compare retrieval
    task prefixes against the current baseline; record the format in item 4.
- Detect oversized inputs, including prefixes, and request non-silent truncation
  behavior where supported. Return usable length errors or split documents before
  embedding; keep original excerpt text separate from model input formatting.
- Validate captured query/document payloads, boundary/oversized inputs and bilingual
  retrieval. Re-index explicitly when a chosen input format changes the embedding
  space; do not compare new-format queries with an old-format document index.

### 10. Retrieval evaluation and measured improvements

-   [x] Create a reproducible, non-personal evaluation set with Korean/English and
    cross-language questions, exact identifiers, negatives and multi-document cases.
    Record the current baseline before selecting an algorithm or another model.
- Measure Recall@K/ranking, evidence relevance, answer accuracy/abstention and
  cold/warm latency. Compare deduplication/diversity, lexical+dense retrieval and
  conditional local reranking only where justified; measure Korean tokenization.
- Record adopted/declined options and reasons. Retain the current stack and avoid
  unmeasured thresholds or always-on extra model calls. Phase 8 expands and tunes
  this evaluation instead of rebuilding it.

### 11. Conversation context and source selection

-   [x] Resolve follow-ups with bounded recent context or measured question
    rewriting; pass selected source IDs through chat/retrieval and persist the
    conversation's scope. Only recent user questions are included; historical
    generated answers are excluded.
- Define unrestricted, explicitly empty and chosen-source scopes distinctly;
  deleted/unready/incompatible files must not silently broaden a selected scope.
  Keep history within the local model's budget and compare answer quality/latency.
- Validate pronouns/comparisons, scope persistence/reload, empty selections and
  deleted sources. Keep full notebook organization and long-term memory out of
  this item unless separately requested.

### 12. Evidence inspection, cited exports and PDF coverage

-   [x] Show item 2's saved excerpts and original status in the source panel;
    offer body-only and provenance-inclusive Markdown/PDF exports; report PDF pages
    with no extracted text and the actual extraction coverage.
- Keep exports consistent with saved/unsaved editing state and the user's chosen
  export mode. Include portable source labels/versions rather than temporary
  localhost links. Describe evidence as supporting the first draft, not validating
  subsequent user edits. No-text pages are not automatically classified as scans.
- Validate changed/missing sources, mixed text/image PDFs, pageless formats, and
  actual native-webview export files. Evidence is retained independently of the
  original; any future OCR or bounding-box viewer work needs separate justification.

## 16.3 Dependency order and focused changes

Keep the twelve IDs above stable while following actual dependencies. Begin with
item 8's small local-exposure fix; items 3/4 protect maintenance and index identity.
Item 2 establishes evidence storage before item 1's drafting and item 12's exports.
Item 5 uses the resulting schema; item 6 reuses maintenance coordination. Item 7
builds on Phase 6 rather than restarting it. Evaluate item 9 with item 10's baseline,
then implement measured input/retrieval changes and item 11's bounded context/scope.

Use focused Conventional Commits and reviewable PRs for meaningful units. Combined
items may share schema prerequisites, but do not put all twelve into one large
feature commit. Preserve existing user data and keep unrelated in-progress work
out of each change. No database/framework replacement is required by this phase.

## 16.4 Completion and handoff to Phase 7.5

- Items 1–9, 11 and 12 are implemented and have their relevant regression/API/UI
  checks and remaining limits recorded. Reused Phase 6 behavior counts when the
  complete milestone is verified; incomplete required work remains open.
- Item 10 has a working evaluation set/harness and recorded baseline/comparison
  results. Only hybrid/reranking adoption may be declined with measured reasons;
  that decision does not waive the evaluation implementation.
- Changes to SQLite preserve existing work; old evidence remains honest about
  missing snapshots. No personal data, credentials or models enter Git/test fixtures.
- Local/cloud payload disclosure matches actual behavior; no automatic cloud
  fallback/retry or implicit model download is introduced.
- Relevant suites, lint, types and web/desktop builds pass for affected surfaces.
  Record unavailable live checks rather than marking them complete.
- Phase 7.5 builds on these integrated foundations. Phase 8 then expands
  stability/quality evaluation and runs the full packaged workflow, including the
  new folder/wiki and prompt-driven document path. Phase 7 completion alone does
  not close the final MVP acceptance checklist.

------------------------------------------------------------------------

## 16.5 First ordered integration — 2026-10-05

The owner authorized merging Phase 6 followed by the work from #37, #38, #39
and #40. Those four drafts were closed after their `codex/` remote heads were
replaced by identical `feat/` heads. Their original feature commits are preserved;
normal main refreshes and merge commits avoid rewriting published history.

Phase 6 is #43, local Qdrant exposure is #44 (replaces #37), rebuild coordination
is #45 (replaces #38), and index identity is #46 (replaces #39). Retrieval evaluation
is #47 on `feat/retrieval-evaluation` (replaces #40), refreshed after those merges.
The merge guide in `docs/phase7/parallel-merge-guide.md` retains historical preview
evidence and records fresh final-source checks and the four actual resolutions.

Final combined implementation `f1cdc8b`: backend **734 passed, 19 skipped, 8 warnings**;
frontend **199 passed across 27 files**; native Rust **3 passed** at the unchanged
native source; final frozen-backend checks **10 passed**. Ruff, ESLint, TypeScript,
route type generation, web build, desktop UI export, Rust format/Clippy and unsigned
Apple Silicon packaging passed. The app is **67.53 MiB**. The model-free lexical
pilot reproduced Recall@5 **0.7143** and nDCG@5 **0.7656**. No personal workspace,
model lifecycle, real cloud call or native GUI acceptance was used for these checks.

Items 3/4/8's implementations and relevant regressions are complete. Item 10 still
needs generated-answer/abstention review, representative data, embedding/chunking
comparisons and a measured reranking decision; its foundation is not completion.
Other Phase 7 milestones and all final Phase 8 acceptance remain open. No final
listener recreation, live dimension reset, latency or actual PDF output is claimed.

## 16.6 Historical evidence and document integration — 2026-10-05

The owner authorized the work from closed #41 and #42 in the same ordered,
history-preserving workflow. The identical feature heads remain on
`feat/evidence-snapshots` and `feat/document-evidence`; replacement PRs target main.
Item 2 lands before item 1. The separate active working tree is left untouched.

The evidence snapshot merge retains all four generation providers, saved identity
failures and coordinated ingestion. Its only textual conflict was the shared
chat passage panel: keep the desktop layout and put saved evidence across both
grid columns. An added UI regression exercises that actual shared panel.

Fresh checks: backend **743 passed, 19 skipped, 8 warnings**; frontend **207 passed
across 28 files**; Ruff, ESLint, route type generation, TypeScript and the web build
passed. Initial parallel UI/desktop checks timed out during environment delays;
the unchanged desktop startup suite then passed **10 tests**, and the entire
backend rerun passed. Frontend passed with a single thread worker and the default
test timeouts. No timeout or production configuration change was committed.

Item 2 lands as PR #48 with main merge `5ea0e57`. Item 1 is PR #49, replacing
closed #42 and building on that merge. Normal refresh `bba3864` keeps one typed provider
argument, local-only excerpt guards, API/service provider forwarding and both
the provider selector and evidence disclosure in the creation form. Four real
adapters are exercised through mock transports, and four UI regressions verify
the selected provider/disclosure. The pending text now names OpenAI and Claude
instead of incorrectly calling their generation local.

Final implementation `5943ba7`: backend **755 passed, 19 skipped, 8 warnings**;
frontend **211 passed across 28 files**; Ruff, ESLint, TypeScript, route type
generation, web build and desktop static export passed. Unsigned Apple Silicon
packaging succeeded at **67.54 MiB**; its actual frozen backend passed **10
checks** with temporary data for readiness, private configuration, control/CORS
boundaries and line/EOF shutdown. Native Rust source is unchanged; no new
Rust test result is claimed for this batch. These checks do not run a native GUI,
use real cloud credentials or validate live generation quality/context capacity.

Items 1/2's implementations are complete, not the whole Phase 7 roadmap. Item
12's cited exports/PDF coverage and all real-service/native-GUI acceptance remain
separate work in their planned phases.

------------------------------------------------------------------------

## 16.7 Workspace recovery and desktop integration — 2026-10-05

Items 5, 6 and 7 use the ordered integration sequence
[workspace backup #53](https://github.com/Kouen-Park/Noye/pull/53) →
[durable jobs #54](https://github.com/Kouen-Park/Noye/pull/54) →
[desktop integration #55](https://github.com/Kouen-Park/Noye/pull/55).
These replace closed draft PRs #50, #51 and #52, respectively, using matching
feat branches. Each successor integrates main after its predecessor. Ordinary
merges preserve the published feature history without rebase or force push.

Backups preserve SQLite/WAL, originals, edited documents and historical evidence,
validate checksums/schema/inventory, and restore into new folders. Native
selection explicitly restarts into a verified restore and preserves the original
and previous workspace. UUID-derived restored collections prevent vector reuse
between workspaces. Preferences and Keychain credentials remain outside backups.

Jobs persist attempts/progress/cancellation, settle unfinished work on startup,
and offer an explicit retry from the original. One ingestion pipeline and one
local inference request run at a time; cancellation is checked between embedding
batches. Partial files stay excluded from search. There is no cloud replay.

Readiness distinguishes configured/installed models and running services; saved
keys do not prove cloud API access. Local generation has context/output bounds
and a conservative UTF-8 input check, without silently trimming saved evidence.
The user's local-only document-excerpt policy remains in force.

Fresh integrated implementation bfc1d6d: backend 793 passed, 19 skipped,
8 warnings; frontend 221 passed in 31 files; Ruff, ESLint, route types,
TypeScript, explicit Webpack web build and desktop static export passed.
Rust tests: 5 passed; fmt/Clippy passed. The newly packaged app's frozen sidecar:
10 desktop checks passed with 7 warnings using temporary data. Unsigned macOS
packaging: 67.65 MiB. Subsequent checkpoint changes are documentation-only.
Integration inspection fixed previous-workspace recovery after returning to the
original location, with a failing-then-passing UI regression. A reproducible
backup/job test preserves unfinished 16/40 progress and saved writing/evidence
without replaying work or changing the original workspace.
See docs/phase7/desktop-integration.md for decisions and exact acceptance limits.
Native GUI restart/download/export, real inference interruption/latency, large
backups and live provider access remain Phase 8. No real user data or Keychain
entry was changed. Items 9–12 were separate at this checkpoint; §16.8 records
their implementation and export validation.

------------------------------------------------------------------------

## 16.8 Embedding, evaluation and selected-source workflows — 2026-10-05

`feat/knowledge-workflow-completion` implements items 9–11 and item 12's cited
exports/extraction coverage. During implementation main merged #48/#49 as
`ce01d3f`; normal merge `5aa5416` reuses their versioned evidence serialization,
local excerpt drafting, private cloud payload policy, byte-copy extraction and
shared evidence panel. Normal merges `a94d6a6` and `f29aca4` retain main's #53/#54
workspace backup/durable jobs and #55 desktop readiness/workspace integration.
Released migrations 3/4 remain unchanged; migration 5 adds scope/coverage
and has version-3/version-4 upgrade regressions. No published history was
rewritten and no personal workspace was re-indexed.

Item 9 separates query/document formatting, keeps raw excerpts, checks the entire
formatted batch and uses `truncate=false`. Actual Ollama 0.34.2 runner checks
confirmed 768 dimensions and an oversized Korean token-limit rejection. Prefixes
remain optional and index-versioned: Lumen Recall@5 declines from 0.9762 to 0.9524,
while Atlas ranking improves with unchanged Recall@5 of 1.0. Raw remains default.

Item 10 now retains two invented bilingual corpora, actual answers, exact-answer
rubric reviews and a bounded-follow-up comparison. Codex inspected 24 local
answers: core correctness 22/24, faithfulness 21/24 and negative abstention 3/3.
This is explicit agent review, not independent human review. The retained inference
runs precede #55's generation context/output limits; they are historical measured
baselines, not a fresh quality pass of the final package. Simple hybrid and
unconditional diversity reduced recall. Conditional reranking was declined for
this baseline because the measured factual failures already had the needed
excerpts; no cross-encoder comparison is claimed. Real PDFs, chunking parameters,
larger samples and independent review remain Phase 8 work.

Item 11 distinguishes all/empty/chosen source scopes, saves checkbox changes and
uses bounded recent user questions. Deleted/incompatible selections cannot broaden
to all files. Prior generated prose was removed after an observed contamination
failure. English comparison retrieval improves, but a Korean answer still treats
an unrecorded count as zero; that numerical-faithfulness failure is retained.
Historical §12.6 is superseded by this implementation, not a general quality pass.

Integrated checks after `f29aca4`: backend **808 passed, 19 skipped, 8 warnings**;
frontend **227 passed across 32 files**; Ruff, ESLint and TypeScript passed.
Rust format, **5 tests** and Clippy passed. Native export inspection used a distinct
**67.57-MiB** unsigned Apple Silicon QA app and synthetic workspace before #55's
integration; the export code did not change in that merge. The packaged frozen
backend passed **10 checks, 7 warnings** with temporary data on a standalone
retry. An initial run alongside the web build hit the 20-second first-start limit
(9 passed, 1 failed); no test timeout was changed. Final web/static builds and
**67.66-MiB** unsigned integrated macOS packaging passed.

Native observations verified scope reload, saved English/Korean excerpts and
changed/missing originals. PDF exports retained all 96 repeated body sentences,
the last section and unsaved Korean text: body-only **3 pages / 25,792 bytes**,
provenance-inclusive **4 pages / 35,988 bytes** with both complete saved excerpts
and no application chrome. The final appendix was also visually inspected.
Separate provenance pagination fixed a reproduced long-export truncation.
Current Markdown exports passed both modes (**6611 / 7377 bytes**), including
unsaved edits; the stored document was unchanged after quitting.

An earlier repeat of the same Markdown filename blocked inside WebKit's
sandbox-extension call. The final unique-name exports passed, but repeat-name
reliability is not established. The full packaged RAG, backup/recovery, real cloud
and other-platform acceptance remains Phase 8 work. Final packaging results and
commands are recorded in docs/phase7/knowledge-workflow.md.

------------------------------------------------------------------------

# 16A. Phase 7.5 --- Knowledge Wiki and Source-Driven Documents

**Approved planning scope, 2026-10-05; not implemented.** The owner requested a
folder-based knowledge workspace that maintains summaries and links, and creates
documents directly from relevant local files through a general chat prompt.
Implement this phase after the outstanding Phase 7 work is integrated and validated, before Phase 8's
broader stability/quality refinement and final desktop acceptance. Keep Phase 7's
twelve IDs, completed work and recorded limits intact.

## 16A.1 Intended experience

The primary desktop workflow becomes:

``` text
Choose a local knowledge folder or connect an existing source folder
        ↓
Add or edit supported files using Finder or the app
        ↓
Detect changes / catch up when the app next opens
        ↓
Extract and preserve source locations
        ↓
Classify + write source summaries + maintain related topic pages
        ↓
Describe a task in chat → discover and inspect relevant files → draft a document
        ↓
Edit and save the document → export Markdown or PDF
```

Originals remain on the user's computer. Folder-based intake becomes the primary
Tauri workflow; existing upload and answer-to-document flows remain compatible.
The initial supported formats remain PDF, Markdown and TXT. Folder access initially
targets the macOS desktop app, not arbitrary client paths submitted to the web API.

Example request in chat:

> 지금까지의 COMPSCI 210 렉쳐노트를 기반으로 요약 정리 노트 생성해줘.

The course is an example, not a required input or a special-purpose feature.
A general request such as “compare the design decisions across my projects” or
“create a report on this topic from my files” should cause the AI to interpret the
purpose, discover relevant files in the user's enabled knowledge folders, inspect
supporting sources and produce the requested document. The user need not select
every file or first obtain an assistant answer. Explicit source/folder selections
remain authoritative; discovery never expands an empty or restricted scope.

The chat shows progress and a link to an independently saved, editable artifact;
the document workspace supplies editing and Markdown/PDF export. Conversation
history may clarify the task, but the transcript is not the document's evidence.

## 16A.2 Storage, ownership and existing foundations

A new managed knowledge folder may use this layout; exact names are configurable
implementation details, not a migration already performed:

``` text
<user-selected knowledge folder>/
├── sources/
│   ├── inbox/
│   ├── Learning/COMPSCI 210/
│   ├── Projects/
│   └── Unclassified/
├── wiki/
│   ├── sources/
│   ├── concepts/
│   ├── projects/
│   └── analyses/
└── documents/                 # authored outputs or portable exports
```

- A **managed folder** permits organization inside the area the user enabled for
  automatic filing. A **connected existing folder** retains its originals and
  directory structure by default; enable file organization separately per folder.
  Removing a connection does not delete the user's external files.
- Preserve source bytes, stable file IDs, relative paths and version hashes. A path
  change must update the registry without breaking historical citations. Resolve
  ambiguous rename/copy events explicitly instead of guessing from equal hashes.
- Use Markdown for readable wiki content and SQLite for source registrations,
  links, versions, processing and provenance. Current document bodies are stored
  in SQLite; this proposed layout does not relocate them or `app.db` automatically.
  Define database/workspace locations and migrate existing sources non-destructively
  before implementing a new layout. Keep credentials and model preferences separate.
- Reuse Next.js, Tauri, FastAPI, SQLite, Qdrant and Ollama. Qdrant may index wiki
  content as well as original passages. A new graph database or agent framework is
  not required. Wiki summaries are interpretations, not replacement primary evidence.
- Retain page-aware extraction, original passage retrieval and saved evidence.
  Long inputs still need bounded sections/batches; a wiki-first workflow does not
  remove model context limits or the need to verify numbers and exceptions.
- Reuse Phase 7 evidence/versioning, library coordination, durable jobs, local
  inference limits, source scopes and evaluation. Extend backups to cover new
  authored wiki content and connections. User edits and saved documents cannot be
  reconstructed by rebuilding vectors.
- Classification, wiki maintenance and source-driven document synthesis use local
  Ollama. Preserve the owner's local-only excerpt drafting policy and existing
  explicit cloud payload boundaries; this phase must not silently send originals,
  saved excerpts or expanded wiki/document context to a cloud provider. Display the
  local provider for these jobs; do not silently switch a user-selected provider.

## 16A.3 Ordered implementation milestones

### 7.5-1. User-selected folders and reliable change detection

- [ ] Add native folder selection and persistent registration for a managed root
  and connected source folders. Keep this separate from Phase 7's backup
  workspace switching. Limit file access to registered roots using canonical path
  checks and native authorization; prevent traversal or links escaping those roots.
- [ ] Scan existing supported files, observe stable additions/edits/moves and run a
  startup reconciliation scan for changes while the app was closed. Coalesce events
  and avoid reading a half-written file or queuing the same work repeatedly.
- [ ] Exclude generated wiki/output, temporary and application data from source
  intake. Handle permissions, disconnected drives and missing folders as visible
  unavailable states; do not infer deletion from an inaccessible root.
- [ ] Show the real folder tree, connection and processing states, per-folder
  processing controls and Open in Finder. Reuse durable jobs for cancellation,
  explicit retry and interrupted work; no closed-app background daemon is assumed.

### 7.5-2. Automatic filing and source-summary pages

- [ ] Generate structured classification and a faithful summary with local Ollama.
  Prefer existing categories, allow new categories when justified, use one primary
  folder plus multiple tags, and keep uncertain classifications in Unclassified.
- [ ] Create `wiki/sources` pages with stable IDs, source/version references,
  original page or passage locators, summary, key points and uncertainties. Record
  model/prompt version and processing time; never invent a page or citation.
- [ ] Validate AI-proposed destinations in application code before creating folders
  or moving a file. Preserve bytes, prevent name collisions and journal path/registry
  changes for recovery. Respect manually fixed categories and user folder names.
- [ ] Make a path-only organization change independent of re-embedding unchanged
  content. Extend exclusion/loop detection so the app's own moves do not reprocess
  indefinitely. Keep source indexing and summary-generation failures distinguishable.

### 7.5-3. Related sources and maintained topic knowledge

- [ ] Find candidate related sources and wiki pages; store validated target IDs,
  backlinks, relation type and an explanation. Distinguish shared subject,
  supporting evidence, alternative approaches and contradictions.
- [ ] Maintain concept/project pages across sources, record tensions and update
  history, and offer to file reusable analyses. Bound link traversal and avoid
  duplicate concepts or a growing set of links based only on shared vocabulary.
- [ ] Refresh affected generated content when source versions change. Preserve
  user-authored edits with revision/conflict handling; do not overwrite edited pages
  during regeneration. Missing or superseded sources leave explicit provenance.

### 7.5-4. Wiki-first questions with original evidence

- [ ] Resolve the selected folder/course/source scope, find relevant summaries and
  topics, follow useful links within that scope, and consult original passages for
  supporting detail. Compare this route with the existing retrieval baseline.
- [ ] Keep all/empty/chosen scopes distinct. Connected documents and wiki links
  cannot broaden a selected scope. Distinguish source facts from wiki interpretation,
  reject stale evidence for current claims and retain historical snapshots honestly.
- [ ] Present wiki links and underlying original references together. Exact-detail
  questions must be able to reach material omitted from a short summary. Do not turn
  prior assistant answers into evidence or claim that the model has been trained.

### 7.5-5. Prompt-driven document creation with automatic source discovery

- [ ] Add an explicit document-generation intent to chat and a source-driven
  generation service/API that does not require a previous assistant message ID.
  Show an artifact card with progress, Open document and export actions; preserve
  the existing answer-to-document option.
- [ ] Interpret the user's goal, topic, output type and language, then discover
  candidate files through the catalog, source summaries, search and related links
  within enabled roots and the conversation's allowed scope. Read relevant original
  sections when summaries are insufficient. Course labels and named collections are
  optional filters, not mandatory input; discovery is application-controlled rather
  than arbitrary model filesystem commands.
- [ ] Show the selected sources and actual coverage; clarify only unresolved task
  or scope ambiguity. A request for “all COMPSCI 210 lecture notes so far” must
  enumerate that collection; a general report must find material relevant to the
  prompt without claiming that every local file was read. Freeze source versions
  when consumed and record the final source manifest. An all-source request freezes
  its inventory at job start; later discoveries remain within that initial scope.
- [ ] Plan an outline and aggregate material across that set with bounded local
  per-source/section processing and synthesis. A normal chat's top-five passages
  cannot establish collection-wide coverage. Long documents need staged generation and
  progress, not silent input truncation or a single over-budget prompt.
- [ ] Generate an editable document shaped by the prompt: study notes, a project
  analysis, a comparison or a report. Use supported definitions/examples and a
  source/coverage report. List unprocessed, missing or no-text requested material,
  label partial results, and explain insufficient evidence instead of inventing
  conclusions. Study notes may organize by lecture/topic, but that is one output
  form, not a restriction on document generation.
- [ ] Attach validated source locators and saved excerpt/version snapshots from the
  actual inputs. Save the artifact independently of the chat, preserve user edits,
  and expose cancellation/retry without duplicating or replacing saved notes.
- [ ] Export the current chosen document revision to Markdown and PDF with optional
  provenance. Existing PDF output uses the print path; a new PDF renderer is not
  assumed. Validate actual native output, Unicode and long-document pagination.
  A chat request alone is not evidence that a PDF has been exported successfully.

### 7.5-6. Recovery, portability and acceptance evidence

- [ ] Extend backup/restore for wiki files, user edits, link/version metadata and
  document jobs. Make external-original inclusion explicit; never describe an
  index-only/connection-only backup as containing those original files. Restore into
  a new destination, report unavailable roots and require explicit reconnection.
- [ ] Coordinate scans, filing, wiki refresh, deletion and rebuilds with ongoing
  reads/jobs. Separate disconnecting, removing derived records and deleting a
  physical original. Capture source versions consistently during synthesis.
- [ ] Validate each milestone using synthetic material, then record a real native
  folder → detected files → summaries/links → prompt-driven document → edit/save →
  Markdown/PDF workflow. Verify restart catch-up, cancellation, moves, changed or
  missing sources, unchanged user edits and portable backup/restore.
- [ ] Extend the existing evaluation with whole-collection coverage, summary
  faithfulness, link usefulness, cross-source reasoning, exact details, partial
  extraction, Korean/English output and ingestion/generation latency. Record actual
  model/hardware and limits; do not assume local-model parity with the current
  SecondBrain agent or claim independent review without it.

## 16A.4 Delivery order and handoff

Keep folder registration, filing/summaries, topic maintenance, query orchestration
and prompt-driven document generation in focused Conventional Commits and reviewable
branches/PRs. Begin implementation from integrated Phase 7, not an unrelated live
feature branch. Preserve published history and existing workspaces; use additive
schema migrations and version new wiki indexes separately from original passages.
Recovery and backup changes accompany the features that need them rather than
waiting until milestone 7.5-6 to protect data.

Phase 7.5 is complete only when the intended source-driven workflow exists and
its relevant checks pass. Keep every checklist open until implementation and
validation are recorded. Phase 8 then broadens real-data quality/latency evaluation
and performs the final packaged-app acceptance for both the new folder/wiki workflow
and compatible upload/answer-based document flows.

------------------------------------------------------------------------

# 17. Phase 8 --- Reliability and Quality

Phase 8 follows Phase 6 desktop implementation, the twelve Phase 7 core workflow
improvements and Phase 7.5's folder/wiki and prompt-driven source documents. Refine
stability and quality using the completed features, then perform final packaged-app
end-to-end acceptance before the desktop MVP release.

**Sequence update, 2026-10-03:** the user assigned the twelve comparison-review
improvements to Phase 7 and moved the previous reliability/quality phase to Phase 8.
Keep already implemented migrations, logging, upload safeguards and index-integrity
work complete. Phase 7 features are not implemented a second time here. The
implementation notes in §§17.1–17.9 retain the original design context and measured
results; statements about missing functionality there describe that earlier
starting point. They are not instructions to rebuild delivered features. Remaining
work and final acceptance are listed in §17.10.

## 17.1 What the original checklist got wrong

The lists below were written before Phases 2--5 existed, and several of their items
were delivered on the way. They should be **verified and ticked, not built**:

-   *Delete vectors when source is deleted* --- Phase 2. Deletion removes the
    original, the metadata and the vectors.
-   *File type validation* --- `FileType.from_filename` rejects an unknown
    extension at upload with a 400, server-side. The frontend's `rejectionFor`
    is a courtesy on top, not the enforcement.
-   *Empty-document handling* --- upload deletes and rejects a zero-byte file
    rather than leaving a row that can never become READY.
-   *The whole UX group* --- empty, loading, error and processing states, source
    display and keyboard usability were built across Phases 2--5 against
    `DESIGN.md`'s floor, on all four surfaces.

At the original baseline stage, the remaining work was narrower than the list: **size
limits, duplicate detection, corrupt-file handling, the three kinds of index
staleness, rebuilding on demand, and the whole of logging.**

Two items carry over from earlier phases and belong here:

-   **§12.6** --- the model still does not receive earlier conversation turns.
    Phase 5 made chat the route into documents, so this is now easier to run into.
    Phase 7 item 11 implements bounded follow-up context; Phase 8 verifies its
    answer quality and latency across the complete conversation workflow.
-   **§13.6** --- native body-only/cited synthetic PDF output is inspected in §16.8.
    Phase 8 still tests broader document shapes and the full packaged workflow.

## 17.2 Implemented schema migration design

Before the reliability baseline, earlier phases had only **added tables**, for
which `CREATE TABLE IF NOT EXISTS` was enough. The baseline required **adding
columns to an existing table**: `files` needed the embedding model that produced
its vectors and a content hash.

At that starting point there was no migration mechanism: `app/db/` contained no
`ALTER`, `user_version`, or migration runner. The failure mode was silent.
Re-running a `CREATE TABLE IF NOT
EXISTS` that now names a new column against a database where the table already
exists is a **no-op**; the column does not appear. Confirmed empirically rather
than assumed. A user with an existing `data/app.db` would therefore get code
expecting a column that is not there, and the first query would fail at runtime
rather than at startup.

The migration runner was therefore the first reliability branch. It is now
implemented; future Phase 8 schema changes must reuse it and preserve existing data.

**Decision: `PRAGMA user_version` plus a list of numbered, idempotent steps applied
in order at startup.** Not Alembic --- that is a second dependency, a config file
and a migrations directory for what will be a handful of `ALTER TABLE` statements
on a single-user local SQLite database, and Noye's claim is that it works without
setup. Reconsider if the schema ever starts changing *shape* rather than growing.

**The requirement that matters: a migration must never lose the user's data.**
Original files are the source of truth and the vector index is rebuildable, but
SQLite holds the things that are *not* derived --- conversations and documents,
which are the user's own questions and writing. So migrations are additive only,
and any step that would drop or rewrite a column takes a file copy of the database
first.

## 17.3 Four decisions to take up front

**What "duplicate" means.** Not the filename: the same name in two folders is
legitimately two files, and a renamed copy is still a duplicate. So a **sha256 of
the bytes**, computed while the upload is being written, stored on the row.

The choice to make is what a duplicate *does*. Accepting it and pointing two rows
at one blob saves disk but makes deletion ambiguous --- deleting one file would
have to know the other still needs the bytes. **Refuse it, with a 409 naming the
existing file**, because the user's actual question is "do I already have this?"
and the answer should be a name they recognise. The hash earns its place twice
over: it also detects a source file that changed since it was indexed.

**What "stale" means.** Before the integrity work, three failures were indistinguishable,
and each needs a different remedy, so each has to be detected separately rather
than collapsed into one flag:

1.  The **source changed on disk** since it was indexed --- the stored hash no
    longer matches the file. Remedy: re-ingest that one file.
2.  The **embedding model changed** --- the vectors are from a different space.
    Detectable cheaply by comparing the stored model name against the
    configuration; no Qdrant call needed.
3.  The **index lost points SQLite says exist** --- a dropped collection, a
    deleted Docker volume. Needs an actual count comparison against Qdrant, so it
    is the expensive check and should not run on every request.

**What a model change should do.** Not silently re-embed: on this machine a
re-index of a real library is minutes to hours of local inference, and the user
should choose when to pay that. Detect it, say so plainly, and offer the rebuild.

The rule that makes this a correctness issue rather than a tidiness one:
**search and chat must never mix vectors from two embedding spaces.** A cosine
score between them is meaningless, so the ranking would be confidently wrong ---
which is worse than returning nothing, because nothing is visible and a bad
ranking is not. A file whose vectors are from a superseded model therefore leaves
the searchable set, with a stated reason, exactly as a file mid-ingestion already
does.

**What logging may and may not record.** Before the logging branch there was no
backend logging. Its implemented design follows two rules:

-   **Never log file contents, a chunk, or a question's text.** This is a private
    knowledge base whose whole claim is that it stays on the user's machine, and a
    log file is the one place its contents would leak *outside* the files the user
    chose to put there. A test should assert this rather than a comment asking for
    it.
-   **Log the pipeline's decisions and every failure's cause.** The ingestion
    error already reaches SQLite for the UI; the log is for whoever is debugging,
    so it carries what the UI deliberately withholds --- timings, stack traces,
    which model answered, how many chunks, which Qdrant call failed.

Stdlib `logging` with a plain formatter, to stderr and a file under `data/logs/`.
No new dependency, and structured enough to grep.

## 17.4 Original branch and PR sequence (implemented)

```text
1. feat/schema-migrations      user_version runner; unblocks everything
2. feat/backend-logging        independent, and makes 3-7 debuggable
3. feat/upload-limits          size cap, content hash, corrupt files      (needs 1)
4. feat/duplicate-detection    the 409 path and its wording               (needs 3)
5. feat/index-integrity        the three staleness checks, /index/status   (needs 1)
6. feat/rebuild-index          rebuild endpoint and action                (needs 5)
7. feat/library-integrity-ui   the surface for all of it                  (needs 4,6)
```

Logging is second rather than last on purpose: every branch after it is easier to
diagnose with it in place, and it is the one item with no dependency on the schema.

`feat/rebuild-index` should reuse what already exists rather than adding a path ---
`indexing.py` already carries a collection reset whose docstring names the
rebuild-index command as its intended caller, and `embeddings.py` already refuses
a vector whose dimension disagrees with the configuration.

Not a branch, but Phase 8 work all the same: **threshold calibration and chunking
parameters** need several real documents to measure against, which only now exists.
Both were deferred from Phase 1 for exactly that reason.

## 17.5 Acceptance and validation

-   An existing `data/app.db` from before the schema migrations opens, gains its new columns, and
    keeps every conversation, message and document. Tested against a real copied
    database, not only a fresh one.
-   Uploading the same file twice is refused the second time, naming the first ---
    including when it has been renamed.
-   A file edited on disk after indexing is reported as out of date, and
    re-ingesting it makes the report go away.
-   Changing `ollama_embedding_model` takes the affected files out of search and
    chat with a stated reason, and never mixes their vectors with new ones.
-   Deleting the Qdrant collection is detected and distinguished from the other two
    staleness causes.
-   A rebuild restores search to what it was, from `data/sources/` alone.
-   A truncated or non-PDF-masquerading-as-PDF file fails with a reason the UI can
    show, and leaves nothing behind.
-   A test asserts no chunk text, file content or question reaches the log.
-   Backend and frontend suites, lint, types and the production build pass. Record
    any browser check that could not run under `Not validated`.

## 17.6 Checklists

### File handling

-   [x] File type validation --- `FileType.from_filename`, server-side, Phase 2
-   [x] Empty-document handling --- zero-byte upload rejected, Phase 2
-   [x] File size validation
-   [x] Duplicate detection
-   [x] Corrupt file handling

### Index integrity

-   [x] Delete vectors when source is deleted --- Phase 2
-   [x] Schema migration runner *(prerequisite; see §17.2)*
-   [x] Detect a changed source file
-   [x] Detect an embedding model change
-   [x] Detect an index that lost points
-   [x] Rebuild index on demand

### UX

-   [x] Empty states --- all four surfaces, Phases 2--5
-   [x] Loading states --- all four surfaces, Phases 2--5
-   [x] Error states --- all four surfaces, Phases 2--5
-   [x] Processing states --- Phase 2
-   [x] Clear source display --- Phases 3--4
-   [x] Keyboard usability --- `DESIGN.md`'s floor, Phases 2--5
-   [x] Surface index integrity in the library

### Logging

-   [x] Backend structured logging
-   [x] Processing errors
-   [x] Ollama errors
-   [x] Qdrant errors
-   [x] A test proving no user content is logged

### Carried over

-   [ ] Recheck Phase 7 follow-up handling (§12.6, item 11) against quality/latency targets
-   [x] Inspect body-only and cited synthetic PDFs from a packaged QA app (§16.8)
-   [ ] Calibrate the similarity threshold (deferred from Phase 1)
-   [ ] Measure chunking parameters (deferred from Phase 1)

------------------------------------------------------------------------

## 17.7 Live Qdrant verification (what branches 5–6 could only stub)

Performed after #33 merged, with Qdrant deliberately up. One file in the real library:
`cs235_lab_07.pdf`, READY, 24 chunks, `content_hash` empty (indexed before #27),
`embedding_model` empty before the run.

**Deep point comparison confirmed.** The first time the branch-5 deep check actually
read Qdrant: 24/24 match, no problems.

**POINTS_MISSING confirmed.** Ten points deleted directly via Qdrant's API.
- Shallow: `problems: none` (the cheap checks cannot see it — as designed).
- Deep: `POINTS_MISSING searchable=True points=14/24`.
- `searchable=True` confirmed: an incomplete index is *out of date*, not *wrong*.

**Rebuild success path confirmed.** First real run of `POST /index/rebuild`
against a live Qdrant:
- Response: `202 queued=1 collection_recreated=false` — the collection was NOT
  dropped, which is the decision the branch exists to make.
- 12 seconds later: `READY chunks=24 qdrant=24`.
- `embedding_model=embeddinggemma` written by ingestion.

**Finding fixed in `fix/hash-on-reingest`.** The first live rebuild left
`content_hash` NULL because re-ingest reads a file already on disk and does not pass
through `_save_upload`. The common ingestion path now hashes the stored original
after extraction proves it readable, so both a single-file retry and a whole-library
rebuild fill the missing identity. Re-ingesting a deliberately changed source also
records the new bytes as the integrity baseline. Unit tests cover both cases and keep
an old file's hash unknown when extraction fails before the new step runs.

## 17.8 Library integrity UI

The library now makes the backend's integrity decisions visible without turning an
expensive Qdrant scan into background traffic. Opening or refocusing the page runs
the cheap source-hash and embedding-model check. **Check stored index** is the
explicit deep action that also compares stored point counts with Qdrant.

The status response carries `point_check_complete` separately from `deep`. This is
important when Qdrant is unavailable: the page says that the stored index could not
be checked and does not misreport an empty `problems` list as a healthy deep check.

Remediation follows the cause rather than offering one ambiguous repair:

-   a changed source offers a one-file re-index;
-   an embedding-model mismatch or missing points offers a confirmed library rebuild;
-   a missing source asks the user to restore or remove the file;
-   rebuild responses show queued, skipped, and recreated-collection results, while
    the existing ingestion polling continues to report progress.

Validation for the branch covered the backend contract, API client, hook request
sequencing, each problem presentation, rebuild confirmation and results, the full
backend and frontend suites, Ruff, ESLint, TypeScript, and a production Webpack
build. A browser pass against the real library confirmed the cheap healthy summary,
the explicit deep-check action, the Qdrant-unavailable state, visible keyboard focus,
and no console warnings or errors. No rebuild or file mutation was performed during
that browser pass.

## 17.9 Optional Gemini generation

Implemented on `feat/optional-gemini`: local Ollama remains the default and
`provider: "gemini"` selects Google generation for `/chat` or
`/documents/generate`. `/ai/providers` returns model names and configuration
availability only. The shared selector explains the cloud payload and free-tier
data policy. Gemini keys stay in the backend environment; errors omit raw provider
bodies and credentials. Quota errors never trigger automatic fallback or retries.
The existing citation mapping and local embedding/index pipeline are unchanged.

Validation (2026-10-03): backend suite **534 passed, 19 skipped**; Gemini transport
and routing tests **28 passed** using mocked responses; frontend **137 passed**;
Ruff, ESLint, TypeScript and the production Webpack build passed. No live Gemini
request or cloud latency measurement was performed. Remaining live end-to-end and
PDF checks are deferred to Phase 8 at the user's request.

## 17.10 Stability/quality refinement and final acceptance

Start after Phase 6 desktop milestones, all twelve Phase 7 items and Phase 7.5's
milestones are completed with their relevant validation. Reassess remaining defects
rather than repeating the completed reliability branches or Phase 7 implementations. Prioritize data
preservation, index/rebuild correctness and source provenance, then measure
retrieval, answer quality and inference latency.

-   [ ] Resolve remaining reliability and quality defects found in the packaged app.
-   [ ] Recheck Phase 7 follow-up handling (§12.6) against quality and latency targets.
-   [ ] Expand the Phase 7 retrieval evaluation and refine thresholds/chunking on
    representative documents; do not rebuild its evaluation harness.
-   [ ] Verify first-run setup, model download failure/cancel/retry and persistent
    provider/model settings, including OS-protected cloud credentials.
-   [ ] Verify provider/model changes preserve saved conversations and documents;
    cloud payload disclosure precedes use and local mode sends no content to Google.
-   [ ] Verify the packaged app owns its backend lifecycle without stopping
    unrelated services, and preserves data across shutdown/relaunch.
-   [ ] Run upload → READY → search → chat → source/citation inspection → conversation
    reload → document generation → edit/save → Markdown/PDF export → clean deletion
    in the packaged macOS app. Inspect actual exported files from the native webview.
-   [ ] Run the Phase 7.5 native folder/wiki workflow, including changes made while
    closed, unavailable roots, automatic filing, preserved user edits, link updates,
    disconnect versus deletion and backup/restore of authored knowledge.
-   [ ] Verify general chat prompts discover relevant files and create independently
    saved documents without a previous assistant answer. Measure requested-source
    coverage and faithfulness; inspect long Korean/English Markdown/PDF outputs.
-   [ ] Compare original retrieval and wiki-assisted discovery on exact details and
    cross-source questions. Record summary omissions, wrong links and stale claims.
-   [ ] Measure local and cloud latency separately. Mocked responses do not establish
    live speed or answer quality; record checks that require unavailable services/keys.
-   [ ] Record final acceptance evidence and close the MVP checklist only for
    behavior actually verified. Folder/topic grouping and prompt-driven documents
    are Phase 7.5 scope; advanced notebook organization and reusable template systems
    beyond those milestones follow the completed MVP.

------------------------------------------------------------------------

# 18. Folder Watch --- Promoted to Phase 7.5

The earlier post-MVP folder-watch proposal is now approved Phase 7.5 work (§16A).
Native folder selection, change detection, startup reconciliation and folder-based
knowledge maintenance precede Phase 8. They remain planned, not implemented.
Do not schedule or build a second folder-watch pipeline after MVP acceptance.

------------------------------------------------------------------------

# 19. Future Ideas --- Not MVP

Possible later features. Phase 6 desktop/model management, Phase 7 source selection
and evaluation, and Phase 7.5 folder intake, tags, source links, maintained wiki and
prompt-driven documents are explicitly in scope. Do not defer those approved
milestones to this list; advanced versions beyond them remain future work.

-   Advanced notebook/collection management beyond Phase 7.5 folders and topics
-   OCR for scanned PDFs
-   DOCX support
-   PPTX support
-   Better semantic chunking
-   Knowledge graph experiments
-   Multiple embedding models
-   Reusable document template systems beyond prompt-directed output
-   Flashcard generation
-   Additional cloud model providers beyond the requested optional providers
-   Optional sync

Do not build these until the basic workflow is reliable.

------------------------------------------------------------------------

# 20. What Noye Should Avoid Becoming

Avoid feature creep toward:

``` text
generic chatbot
AI agent framework
Notion clone
general productivity suite
cloud SaaS platform
```

The core identity should remain:

> **A local-first workspace for turning personal files into searchable,
> cited, reusable knowledge.**

------------------------------------------------------------------------

# 21. Memex Inspiration --- Without Becoming a Fork

Memex was reviewed as a useful architectural/product reference.

Useful ideas to learn from:

-   Local filesystem storage
-   SQLite persistence
-   Clear service/data separation
-   Markdown export
-   Background processing states
-   Local-first philosophy
-   LLM abstraction

However, Noye should remain independently implemented.

The distinction should stay clear:

``` text
Memex
→ life logging
→ journal
→ photos / voice
→ timeline
→ agents
→ companion

Noye
→ files / PDFs
→ knowledge retrieval
→ semantic search
→ source citations
→ research chat
→ reusable documents
→ Markdown / PDF generation
```

This distinction is important both for product identity and for the
project being strong portfolio evidence.

------------------------------------------------------------------------

# Git Branch Strategy

Noye uses a lightweight **GitHub Flow** approach suitable for a solo
project while still demonstrating professional software-engineering
practice.

Do not add a permanent `develop` branch at this stage.

The normal flow is:

``` text
main
  │
  ├── focused branch
  │       ↓
  │    commits
  │       ↓
  │   validation
  │       ↓
  │ Pull Request
  │       ↓
  └──── merge → main
```

## Protected role of `main`

`main` should represent the latest stable, usable state of Noye.

New feature development and non-trivial fixes should normally not begin
directly on `main`.

Before creating a branch:

``` bash
git switch main
git pull
git status
```

The working tree should be understood before starting new work.

## Branch naming

Use lowercase kebab-case.

### New functionality

``` text
feat/pdf-extraction
feat/chunking
feat/ollama-embeddings
feat/qdrant-indexing
feat/semantic-search
feat/rag-generation
feat/citations
feat/file-upload
feat/chat
feat/document-editor
```

### Bugs

``` text
fix/pdf-page-number
fix/vector-cleanup
fix/ollama-timeout
```

### Refactoring

``` text
refactor/retrieval-service
refactor/citation-mapping
```

### Tests

``` text
test/chunking
test/retrieval
```

### Documentation

``` text
docs/architecture
docs/development-plan
```

### Project/configuration work

``` text
chore/backend-setup
chore/docker-setup
chore/dependency-update
```

## Branch size

Prefer small branches with one clear responsibility.

Avoid:

``` text
feat/rag-system
```

if it contains extraction, chunking, embeddings, Qdrant, retrieval,
generation, and citations all at once.

Prefer:

``` text
feat/pdf-extraction
        ↓ merge

feat/chunking
        ↓ merge

feat/ollama-embeddings
        ↓ merge

feat/qdrant-indexing
        ↓ merge

feat/semantic-search
        ↓ merge

feat/rag-generation
        ↓ merge

feat/citations
        ↓ merge
```

A branch should ideally produce a PR that is understandable without
reviewing the entire project.

## Commit convention

Use Conventional Commits.

Examples:

``` text
feat: add PDF text extraction
feat: preserve page metadata during chunking
fix: handle empty PDF pages
test: add extraction regression tests
refactor: separate citation mapping
docs: update architecture notes
chore: add PyMuPDF dependency
```

Common prefixes:

  -----------------------------------------------------------------------
  Prefix                              Purpose
  ----------------------------------- -----------------------------------
  `feat:`                             New user-facing or application
                                      capability

  `fix:`                              Bug fix

  `test:`                             Tests

  `refactor:`                         Internal restructuring without
                                      intended behavior change

  `docs:`                             Documentation

  `chore:`                            Tooling, dependencies,
                                      configuration, repository
                                      maintenance
  -----------------------------------------------------------------------

Commits should describe a meaningful change rather than the act of
editing a file.

Prefer:

``` text
feat: preserve page metadata during extraction
```

over:

``` text
update extraction.py
```

## Pull Requests

Even though Noye is currently a solo project, use Pull Requests for
meaningful branches.

A PR should explain:

``` text
What changed?
Why?
How was it tested?
Any limitations or follow-up work?
```

### PR title style

Use the same Conventional Commit prefix as the branch's work, in the
imperative, lowercase after the prefix, no trailing period, and under
70 characters:

``` text
chore: set up local backend environment
feat: extract PDF text with page provenance
fix: clean up Qdrant vectors when a source is deleted
```

Do not use a bare branch name or a vague title such as
`update files` or `backend work`.

### PR description style

Use the following sections, in this order. The Phase 2 library PR is the
reference for their level of specificity: it explains what changed, why the
choice was made, what was actually observed, and what remains uncertain.
Scale the length to the work; a small PR does not need a long essay. Omit a
section only when it genuinely does not apply. Include `Review` when a
separate design, usability, documentation, or code review pass took place.
PR #14 (`feat: build the library UI with a measured design system`) is the
worked example: it ties specific files to behavior, reports measured contrast
and a real browser upload, records that visual judgement and dev hydration
were unresolved, and explains which review findings changed the UI.

``` text
## Summary
## Changes
## Validated
## Not validated
## Notes
## Review
## Roadmap
```

  ------------------------------------------------------------------------
  Section           Content
  ----------------- ------------------------------------------------------
  `## Summary`      What the PR accomplishes and why it exists. Give the
                    reader the product or engineering context before the
                    implementation details.

  `## Changes`      Name the meaningful files or groups and say what each
                    contributes. Use short paragraphs or a list according
                    to the size of the change; do not merely repeat names.

  `## Validated`    Exactly what was actually run or observed, with real
                    results -- commands, endpoints, measured numbers.
                    Never list something that was not executed.

  `## Not           Anything intentionally unverified, blocked, or left to
  validated`        the user, and why. This section is mandatory whenever
                    such items exist; an empty claim of full verification
                    is not acceptable.

  `## Notes`        Explain decisions a reviewer might question and the
                    tradeoffs behind them. Include limits that affect later
                    phases or clients.

  `## Review`       Name the review passes actually performed, their most
                    useful findings, what changed because of them, and any
                    suggestion deliberately declined with a reason. Do not
                    imply independent review when none happened.

  `## Roadmap`      Which phase and milestone this PR belongs to, and what
                    it unblocks next.
  ------------------------------------------------------------------------

Rules for the description:

-   State facts, not intentions. Describe what the branch does, not what
    someone should do later, except in `## Notes` and `## Roadmap`.
-   Put measured numbers in `## Validated` rather than adjectives
    ("fast", "works well").
-   Never claim a test or command was run when it was not.
-   Distinguish a browser observation, an automated test, a code inspection,
    and an inference. Record failed or blocked validation under
    `## Not validated` with its cause, if known.
-   Keep it scannable with concrete paragraphs or short bullets. Preserve
    the reasoning when a decision or review finding needs more than one line.
-   Write the description in English so the repository history stays
    consistent for a portfolio reader.

Before merge:

-   [ ] Requested scope is complete
-   [ ] Relevant tests pass
-   [ ] No secrets or personal files are included
-   [ ] Diff has been reviewed
-   [ ] Documentation is updated if necessary
-   [ ] Roadmap status is accurate

After merge, delete the feature branch unless there is a concrete reason
to keep it.

## Merge strategy

For focused feature branches, prefer **Squash and Merge** when many
small work-in-progress commits do not add historical value.

If the branch already contains a clean series of meaningful commits, a
normal merge/rebase workflow may also be used.

The important goal is a readable `main` history.

Do not force-push `main`.

## Recommended near-term branch sequence

From the current stage, the expected sequence is approximately:

``` text
chore/backend-setup
        ↓
feat/pdf-extraction
        ↓
feat/chunking
        ↓
feat/ollama-embeddings
        ↓
feat/qdrant-indexing
        ↓
feat/semantic-search
        ↓
feat/rag-generation
        ↓
feat/citations
        ↓
feat/file-upload
        ↓
feat/chat
        ↓
feat/document-workspace
```

This sequence may change when implementation reveals a better dependency
order, but changes should remain deliberate.

------------------------------------------------------------------------

# 22. Recommended Development Order

Do not jump randomly between frontend and AI features.

Follow this order:

``` text
1. FastAPI health check
        ↓
2. Qdrant + Ollama environment
        ↓
3. PDF extraction
        ↓
4. Chunking
        ↓
5. Embeddings
        ↓
6. Qdrant indexing
        ↓
7. Semantic search
        ↓
8. RAG generation
        ↓
9. Citation mapping
        ↓
10. Library UI
        ↓
11. Search UI
        ↓
12. Chat UI
        ↓
13. Conversation persistence
        ↓
14. Document workspace
        ↓
15. Markdown/PDF export
        ↓
16. Tauri desktop implementation (Phase 6)
        ↓
17. Twelve core workflow improvements (Phase 7)
        ↓
18. Folder intake + knowledge wiki + prompt-driven documents (Phase 7.5)
        ↓
19. Reliability + quality + final desktop acceptance (Phase 8)
```

------------------------------------------------------------------------

# 23. Suggested Timeline

## Week 1 --- Core Setup

-   FastAPI environment
-   Qdrant
-   Ollama
-   PyMuPDF
-   extraction
-   chunking
-   tests

## Week 2 --- Retrieval Engine

-   embeddings
-   Qdrant indexing
-   semantic search
-   retrieval tests
-   initial RAG

## Week 3 --- Library

-   Next.js setup
-   upload UI
-   file API
-   processing states
-   file management

## Week 4 --- Chat

-   chat API
-   citations
-   conversation persistence
-   chat interface

## Week 5 --- Documents

-   Create Document workflow
-   Markdown editor
-   preview
-   Markdown export
-   PDF export

**Target: usable MVP by the end of Week 5.**

## Week 6 --- Desktop (Phase 6)

-   Tauri and macOS packaging
-   local application lifecycle and persistent storage
-   chat-focused layout
-   first-run setup, model installation and persistent AI settings
-   relevant automated checks for each implementation milestone

## Week 7 --- Core Workflow Improvements (Phase 7)

-   implement the twelve approved milestones in §16
-   evidence/document generation, index safety and backup/job recovery
-   desktop/service integration and local exposure
-   embedding/retrieval evaluation, follow-up context and source selection
-   evidence inspection, cited exports and PDF coverage
-   validate each focused change before moving on

## After Week 7 --- Knowledge Wiki and Source Documents (Phase 7.5)

-   user-selected folders, change detection and restart catch-up
-   automatic filing, source summaries, related links and maintained topic pages
-   wiki-first questions with original evidence and preserved source scopes
-   general chat prompts that discover sources and create editable documents
-   compatible migrations, recovery, backups and Markdown/PDF output
-   validate each focused milestone in §16A; no fixed one-week estimate

## Week 8 --- Reliability and Quality (Phase 8)

-   remaining error handling and data/index safety fixes
-   retrieval and answer-quality measurement
-   inference latency and chunking/threshold calibration
-   final packaged-app acceptance, including folder/wiki and source-document exports
-   README/demo evidence and initial desktop release

The timeline is directional, not a deadline. Phase 7 contains twelve milestones;
Phase 7.5 adds the planned knowledge workflow. Both may span multiple weeks, and
Phase 8 starts after them; week labels describe order, not effort estimates.

------------------------------------------------------------------------

# 24. Portfolio Goals

Noye should demonstrate skills beyond a standard CRUD web application.

The finished project should visibly demonstrate:

-   TypeScript
-   Next.js
-   React
-   Python
-   FastAPI
-   API design
-   SQLite
-   vector databases
-   Qdrant
-   embeddings
-   semantic search
-   RAG
-   local LLM inference
-   Ollama
-   document processing
-   source provenance
-   Docker
-   automated testing
-   desktop packaging with Tauri

A recruiter should be able to understand the project quickly:

> **Noye is a local-first AI knowledge workspace that lets users ingest
> personal documents, semantically search them, ask source-grounded
> questions with page-level citations, and turn retrieved knowledge into
> editable Markdown/PDF documents.**

------------------------------------------------------------------------

# 25. Demo Goal

The eventual portfolio demo should show Phase 7.5's primary desktop workflow.
Keep the existing upload and answer-to-document route as a compatibility demo.
The new flow is planned, not verified:

``` text
Choose a local knowledge folder
       ↓
Add supported files in Finder
       ↓
Noye detects, classifies, summarizes and links them
       ↓
Ask chat to create notes, a comparison or a report
       ↓
AI discovers and reads relevant permitted sources
       ↓
A saved editable document appears with source coverage and provenance
       ↓
Open and edit the document
       ↓
Export Markdown or PDF
```

This should become the main demo video/GIF on the GitHub README and
portfolio.

------------------------------------------------------------------------

# 26. Current Immediate Tasks

The repository foundation now exists.

Work next in this exact order:

-   [x] Start backend virtual environment
-   [x] Install backend requirements
-   [x] Run FastAPI
-   [x] Confirm `/health`
-   [x] Run Qdrant with Docker
-   [x] Confirm Qdrant is reachable
-   [x] Install/configure Ollama
-   [x] Choose embedding model
-   [x] Add PyMuPDF dependency
-   [x] Implement `extraction.py`
-   [x] Write extraction tests
-   [x] Implement `chunking.py`
-   [x] Write chunking tests
-   [x] Commit the first real knowledge-engine feature

### First meaningful milestone

> **Given a PDF, Noye can extract every page and produce chunks that
> retain their original file and page metadata.**

Do not move to UI work until this milestone is reliable.

------------------------------------------------------------------------

# 27. Definition of MVP Complete

The MVP is complete when a user can:

-   [ ] Run Noye locally
-   [ ] Upload a supported document
-   [ ] See processing status
-   [ ] Search the document semantically
-   [ ] Ask a question about stored knowledge
-   [ ] Receive a useful answer
-   [ ] See the source file and page
-   [ ] Start a new conversation
-   [ ] Return to previous conversations
-   [ ] Turn an answer into a Markdown document
-   [ ] Choose/connect a local knowledge folder and detect files added while closed
-   [ ] Inspect maintained source summaries, topic pages and related-document links
-   [ ] Preserve original bytes and user edits during automatic filing/wiki updates
-   [ ] Ask chat to discover relevant files and create a document without a prior answer
-   [ ] Inspect actual source coverage and evidence behind a synthesized document
-   [ ] Back up and recover connected-folder metadata, authored wiki and documents
-   [ ] Edit the document
-   [ ] Save it
-   [ ] Export Markdown
-   [ ] Export PDF
-   [ ] Delete a source cleanly
-   [ ] Use the core workflow without an external AI API

------------------------------------------------------------------------

## Guiding Rule

When deciding what to build next, ask:

> **Does this make it easier to turn the user's own files into
> searchable, trustworthy, reusable knowledge?**

If the answer is no, it probably does not belong in the MVP.
