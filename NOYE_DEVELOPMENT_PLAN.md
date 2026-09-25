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
-   Do not begin Tauri packaging before the local web MVP is
    sufficiently stable.
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

## 0.6 Data safety rules

Agents must be conservative with user data.

-   Never mutate original source files unless explicitly requested.
-   Generated/editable documents belong separately from original
    sources.
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
Stable MVP
        ↓
Tauri Desktop Application
```

Do **not** start by solving desktop packaging.

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

Suggested structure:

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
    for display. Duplicate *detection* is Phase 6; silently destroying the
    first upload is not an acceptable stand-in for it.
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
-   [x] Export PDF — implemented, output not yet inspected (§13.6)

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
eye before Phase 6.

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
before retrieval — is worth taking before or alongside Phase 6.


# 14. Phase 6 --- Reliability and Quality

The workflow is complete: a file becomes searchable knowledge, an answer cites its
sources, and a document outlives both. Phase 6 is about what happens when that
workflow meets a library that has been used for a while --- a file that changed on
disk, the same PDF uploaded twice, an embedding model swapped out, a Qdrant volume
that was deleted. None of those are hypothetical; all of them are silent today.

## 14.1 What the original checklist got wrong

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

What genuinely remains is narrower and sharper than the list suggests: **size
limits, duplicate detection, corrupt-file handling, the three kinds of index
staleness, rebuilding on demand, and the whole of logging.**

Two items carry over from earlier phases and belong here:

-   **§12.6** --- the model still does not receive earlier conversation turns.
    Phase 5 made chat the route into documents, so this is now easier to run into.
    Its cheapest option (rewrite a follow-up question before retrieval) is one
    prompt and one model call.
-   **§13.6** --- nobody has inspected a printed PDF. That check is two minutes
    and could invalidate a claim already shipped in the README, so it should
    happen **before** Phase 6 work starts rather than after.

## 14.2 The schema problem that comes first

Every phase so far only ever **added tables**, and `CREATE TABLE IF NOT EXISTS` is
enough for that. Phase 6 is the first phase that must **add columns to an existing
table**: `files` needs at least the embedding model that produced its vectors, and
a content hash.

There is no migration mechanism --- verified: nothing in `app/db/` contains
`ALTER`, `user_version`, or anything resembling a migration. And the failure mode
is silent, which is what makes it dangerous. Re-running a `CREATE TABLE IF NOT
EXISTS` that now names a new column against a database where the table already
exists is a **no-op**; the column does not appear. Confirmed empirically rather
than assumed. A user with an existing `data/app.db` would therefore get code
expecting a column that is not there, and the first query would fail at runtime
rather than at startup.

So the migration runner is branch one, and nothing else in Phase 6 can land before
it.

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

## 14.3 Four decisions to take up front

**What "duplicate" means.** Not the filename: the same name in two folders is
legitimately two files, and a renamed copy is still a duplicate. So a **sha256 of
the bytes**, computed while the upload is being written, stored on the row.

The choice to make is what a duplicate *does*. Accepting it and pointing two rows
at one blob saves disk but makes deletion ambiguous --- deleting one file would
have to know the other still needs the bytes. **Refuse it, with a 409 naming the
existing file**, because the user's actual question is "do I already have this?"
and the answer should be a name they recognise. The hash earns its place twice
over: it also detects a source file that changed since it was indexed.

**What "stale" means.** Three distinct failures are currently indistinguishable,
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

**What logging may and may not record.** There is none today --- zero
`import logging` in the backend, verified. Two rules before any is added:

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

## 14.4 Branch and PR sequence

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

Not a branch, but Phase 6 work all the same: **threshold calibration and chunking
parameters** need several real documents to measure against, which only now exists.
Both were deferred from Phase 1 for exactly that reason.

## 14.5 Acceptance and validation

-   An existing `data/app.db` from before Phase 6 opens, gains its new columns, and
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

## 14.6 Checklists

### File handling

-   [x] File type validation --- `FileType.from_filename`, server-side, Phase 2
-   [x] Empty-document handling --- zero-byte upload rejected, Phase 2
-   [ ] File size validation
-   [ ] Duplicate detection
-   [ ] Corrupt file handling

### Index integrity

-   [x] Delete vectors when source is deleted --- Phase 2
-   [ ] Schema migration runner *(prerequisite; see §14.2)*
-   [ ] Detect a changed source file
-   [ ] Detect an embedding model change
-   [ ] Detect an index that lost points
-   [ ] Rebuild index on demand

### UX

-   [x] Empty states --- all four surfaces, Phases 2--5
-   [x] Loading states --- all four surfaces, Phases 2--5
-   [x] Error states --- all four surfaces, Phases 2--5
-   [x] Processing states --- Phase 2
-   [x] Clear source display --- Phases 3--4
-   [x] Keyboard usability --- `DESIGN.md`'s floor, Phases 2--5
-   [ ] Surface index integrity in the library

### Logging

-   [ ] Backend structured logging
-   [ ] Processing errors
-   [ ] Ollama errors
-   [ ] Qdrant errors
-   [ ] A test proving no user content is logged

### Carried over

-   [ ] Rewrite a follow-up question before retrieval (§12.6)
-   [ ] Inspect a printed PDF (§13.6) --- do this first; it is two minutes
-   [ ] Calibrate the similarity threshold (deferred from Phase 1)
-   [ ] Measure chunking parameters (deferred from Phase 1)

------------------------------------------------------------------------

## 14.7 Live Qdrant verification (what branches 5–6 could only stub)

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

# 16. Phase 7 --- Desktop Application

Only start this once the local web version is stable.

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

-   [ ] Tauri setup
-   [ ] Start/manage backend
-   [ ] Manage local data directory
-   [ ] Manage Qdrant
-   [ ] Manage Ollama detection
-   [ ] Application packaging
-   [ ] macOS build
-   [ ] Windows build

Avoid making desktop packaging block development of the knowledge
engine.

------------------------------------------------------------------------

# 17. V2 --- Folder Watch

One of the first post-MVP features should be folder watching.

Example:

``` text
~/Noye/
├── University/
│   └── CS220/
│       └── lecture.pdf
├── Projects/
│   └── BirdieBuddy/
│       └── architecture.md
└── Research/
    └── paper.pdf
```

Noye watches this folder.

When a new supported file appears:

``` text
Detected
   ↓
Extract
   ↓
Chunk
   ↓
Embed
   ↓
Ready
```

This makes Noye feel less like an upload website and more like a
persistent personal knowledge system.

------------------------------------------------------------------------

# 18. Future Ideas --- Not MVP

Possible later features:

-   Folder watch
-   Automatic re-index when source changes
-   Knowledge collections/workspaces
-   Tags
-   Source linking
-   OCR for scanned PDFs
-   DOCX support
-   PPTX support
-   Better semantic chunking
-   Hybrid keyword + vector search
-   Reranking
-   Knowledge graph experiments
-   Local model management UI
-   Multiple embedding models
-   Source filters
-   Conversation-to-document workflows
-   Document templates
-   Automatic study guides
-   Flashcard generation
-   Offline-first desktop packaging
-   Optional cloud model providers
-   Optional sync

Do not build these until the basic workflow is reliable.

------------------------------------------------------------------------

# 19. What Noye Should Avoid Becoming

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

# 20. Memex Inspiration --- Without Becoming a Fork

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

# 21. Recommended Development Order

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
16. Tests + reliability
        ↓
17. Tauri desktop packaging
        ↓
18. Folder Watch
```

------------------------------------------------------------------------

# 22. Suggested Timeline

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

## Week 6 --- Quality

-   tests
-   error handling
-   duplicate detection
-   deletion cleanup
-   UX polish
-   README/demo improvements

## Week 7 --- Desktop

-   Tauri
-   macOS packaging
-   local application lifecycle
-   initial desktop release

The timeline is directional, not a deadline.

------------------------------------------------------------------------

# 23. Portfolio Goals

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

# 24. Demo Goal

The eventual portfolio demo should show one continuous workflow:

``` text
Drag PDF into Noye
       ↓
Processing stages appear
       ↓
File becomes Ready
       ↓
Ask a question
       ↓
Noye answers
       ↓
Exact source + page citation appears
       ↓
Click "Create Document"
       ↓
Noye creates Markdown
       ↓
Edit document
       ↓
Export PDF
```

This should become the main demo video/GIF on the GitHub README and
portfolio.

------------------------------------------------------------------------

# 25. Current Immediate Tasks

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

# 26. Definition of MVP Complete

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
