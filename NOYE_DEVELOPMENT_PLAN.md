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

# 

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

-   [ ] Upload PDF files
-   [ ] Upload Markdown files
-   [ ] Upload TXT files
-   [ ] Extract text
-   [ ] Preserve PDF page numbers
-   [ ] Chunk extracted content
-   [ ] Generate embeddings locally
-   [ ] Store vectors in Qdrant
-   [ ] Semantic search
-   [ ] Ask questions over indexed knowledge
-   [ ] Local LLM generation through Ollama
-   [ ] File citations
-   [ ] Page citations
-   [ ] Conversation history
-   [ ] Generate Markdown documents from answers/retrieved knowledge
-   [ ] Edit generated Markdown
-   [ ] Preview Markdown
-   [ ] Export Markdown
-   [ ] Export PDF
-   [ ] Visible processing states
-   [ ] Delete files and associated vectors
-   [ ] Basic error handling

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
-   [ ] Install/start Docker
-   [ ] Start Qdrant
-   [x] Install/configure Ollama
-   [x] Select embedding model
-   [x] Select initial local generation model
-   [ ] Bootstrap Next.js frontend

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

Requirements:

-   [ ] Accept PDF path
-   [ ] Open PDF
-   [ ] Iterate through pages
-   [ ] Extract page text
-   [ ] Preserve page number
-   [ ] Handle empty pages
-   [ ] Handle invalid/corrupt PDF
-   [ ] Return structured extraction result

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

-   [ ] Known PDF produces expected page count
-   [ ] Page numbers are correct
-   [ ] Extracted text is non-empty where expected
-   [ ] Invalid PDF produces controlled error

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

-   [ ] Define chunk size
-   [ ] Define overlap
-   [ ] Avoid losing page provenance
-   [ ] Produce deterministic chunk ordering

Do not over-engineer sophisticated semantic chunking initially.

Start simple, measure retrieval quality, then improve.

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

-   [ ] Connect FastAPI backend to Ollama
-   [ ] Embed a single text string
-   [ ] Embed document chunks
-   [ ] Handle Ollama connection errors
-   [ ] Configure model using environment variables

Avoid hardcoding model names throughout the application.

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

-   [ ] Create Noye collection
-   [ ] Insert vectors
-   [ ] Retrieve vectors
-   [ ] Delete vectors belonging to a file
-   [ ] Recreate/rebuild collection

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

### Phase 1 exit condition

From the backend alone:

1.  Give Noye a PDF.
2.  Extract it.
3.  Chunk it.
4.  Embed it.
5.  Index it.
6.  Ask a question.
7.  Retrieve relevant chunks.
8.  Generate an answer.
9.  Return correct source/page citations.

If this works, the core of Noye works.

------------------------------------------------------------------------

# 10. Phase 2 --- Library

Build the first major UI.

Route:

``` text
/library
```

## Features

-   [ ] Drag-and-drop upload
-   [ ] File picker
-   [ ] PDF support
-   [ ] Markdown support
-   [ ] TXT support
-   [ ] File list
-   [ ] File type
-   [ ] File size
-   [ ] Processing status
-   [ ] Delete file
-   [ ] Failure state

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

## Delete behavior

Deleting a source must clean up:

``` text
original file
SQLite metadata
associated chunks
Qdrant vectors
```

------------------------------------------------------------------------

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

-   [ ] Search input
-   [ ] Relevant snippets
-   [ ] File names
-   [ ] Page numbers
-   [ ] Similarity scores if useful
-   [ ] Open source reference

This is useful both as a user feature and as a debugging tool for RAG
quality.

------------------------------------------------------------------------

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

-   [ ] New conversation
-   [ ] User messages
-   [ ] AI messages
-   [ ] Citations below AI answer
-   [ ] Persistent conversation history
-   [ ] Conversation titles
-   [ ] Loading state
-   [ ] Retrieval/generation errors

Store conversations and messages in SQLite.

A key UI requirement:

**Sources should be easy to inspect rather than hidden.**

------------------------------------------------------------------------

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

-   [ ] Create document
-   [ ] Generate from chat answer
-   [ ] Markdown editor
-   [ ] Markdown preview
-   [ ] Save
-   [ ] Rename
-   [ ] Delete
-   [ ] Export `.md`
-   [ ] Export PDF

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

# 14. Phase 6 --- Reliability and Quality

Once the complete workflow works, improve reliability.

## File handling

-   [ ] File size validation
-   [ ] File type validation
-   [ ] Duplicate detection
-   [ ] Corrupt file handling
-   [ ] Empty-document handling

## Index integrity

-   [ ] Delete vectors when source is deleted
-   [ ] Detect stale vectors
-   [ ] Rebuild index command
-   [ ] Handle embedding model changes

## UX

-   [ ] Empty states
-   [ ] Loading states
-   [ ] Error states
-   [ ] Processing states
-   [ ] Clear source display
-   [ ] Keyboard usability

## Logging

-   [ ] Backend structured logging
-   [ ] Processing errors
-   [ ] Ollama errors
-   [ ] Qdrant errors

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
-   [ ] Run Qdrant with Docker
-   [ ] Confirm Qdrant is reachable
-   [ ] Install/configure Ollama
-   [ ] Choose embedding model
-   [ ] Add PyMuPDF dependency
-   [ ] Implement `extraction.py`
-   [ ] Write extraction tests
-   [ ] Implement `chunking.py`
-   [ ] Write chunking tests
-   [ ] Commit the first real knowledge-engine feature

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
