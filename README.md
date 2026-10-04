# Noye

> **Your knowledge, at your command.**

Noye is a **local-first AI knowledge workspace** that turns your files into searchable, reusable knowledge.

Upload PDFs, Markdown files, and notes. Noye processes and searches them locally,
preserves source citations, and turns useful results into editable documents.
Generation defaults to local Ollama; you can explicitly select Gemini, OpenAI or Claude with your
own API key for chat or document drafting.

> 🚧 **Noye is currently under active development.** The features below describe the planned MVP unless marked complete.

## Why Noye?

Knowledge is often scattered across lecture notes, PDFs, project documentation, research papers, and personal files.

Noye aims to provide one local workspace where you can:

- search your files by meaning rather than exact keywords;
- ask questions across your personal knowledge base;
- trace answers back to their original file and page;
- turn retrieved knowledge into reusable documents;
- keep the core workflow local and under your control.

## Planned MVP

- PDF, Markdown, and TXT ingestion
- Page-aware text extraction and chunking
- Local embeddings and semantic search
- Retrieval-Augmented Generation (RAG)
- File and page citations
- Local LLM inference with Ollama
- Persistent conversations
- Editable Markdown documents
- Markdown and PDF export
- Visible file-processing states

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js, React, TypeScript |
| Backend | FastAPI, Python |
| Extraction | PyMuPDF |
| Metadata | SQLite |
| Vector Search | Qdrant |
| Local AI | Ollama |
| Infrastructure | Docker |
| Desktop | Tauri 2 *(macOS foundation implemented; final acceptance pending)* |

## Architecture

```text
                Next.js / React
                       |
                       v
                    FastAPI
                       |
          +------------+------------+
          |            |            |
          v            v            v
       SQLite        Qdrant       Ollama
      Metadata       Vectors      Local AI
          |
          v
    Local Filesystem
```

Original source files remain the **source of truth**. SQLite stores application metadata and relationships, while Qdrant contains a derived vector index that can be rebuilt from the original files.

## Data Flow

### File ingestion

```text
Upload -> Text Extraction -> Chunking -> Embeddings -> Qdrant
```

Each chunk keeps provenance metadata such as its file, page, and chunk index.

### Question answering

```text
Question -> Query Embedding -> Vector Search -> Relevant Chunks
         -> Local LLM -> Grounded Answer + Citations
```

### Document generation

```text
Retrieved Knowledge + User Instruction
                 |
                 v
              Ollama
                 |
                 v
              Markdown
                 |
                 v
          Edit -> Save -> Export
```

## Project Structure

```text
noye/
├── frontend/
├── backend/
│   └── app/
│       ├── api/
│       ├── services/
│       ├── models/
│       ├── db/
│       └── tests/
├── data/
│   ├── sources/
│   └── documents/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Roadmap

### Phase 0 — Foundation

- [x] Repository created
- [x] Initial project structure
- [x] Backend health endpoint
- [x] Frontend bootstrap
- [x] Docker development environment

### Phase 1 — Knowledge Engine

- [x] PDF text extraction
- [x] Page-aware chunking
- [x] Local embeddings
- [x] Qdrant indexing
- [x] Semantic retrieval
- [x] Local LLM generation
- [x] Citation mapping

### Phase 2 — Library

- [x] Drag-and-drop upload
- [x] Processing states
- [x] File management
- [x] Retry a failed file
- [x] Stop a file that is processing
- [x] Vector cleanup on deletion

### Phase 3 — Search

- [x] Search input
- [x] Ranked passage snippets
- [x] Source file names
- [x] Page numbers where the format has them
- [x] Open the original source

### Phase 4 — Chat

- [x] Knowledge-base chat
- [x] Inspectable passages behind every answer
- [x] Conversation history
- [x] Persistent messages

### Phase 5 — Document Workspace

- [x] Generate documents from retrieved knowledge
- [x] Markdown editor and preview
- [x] Markdown export
- [x] PDF export *(via your browser's print dialog)*

### Phase 6 — Desktop Application

- [x] Tauri integration with a bundled static UI
- [x] Start and stop the app's own backend
- [x] Persistent app-data directory and explicit workspace import
- [x] Local macOS application bundle
- [x] Chat-focused layout with conversation navigation and passage inspection
- [ ] Hardware recommendations and model installation
- [ ] Persistent model/provider settings and OS-protected API keys
- [ ] Signed/notarized distribution
- [ ] Windows support

### Phase 7 — Core Workflow Improvements

- [ ] Store retrieved excerpts and pass them to document generation
- [ ] Preserve citation excerpts and original source versions
- [ ] Coordinate rebuilds with active ingestion/deletion
- [ ] Version indexes by embedding model, chunking and input format
- [ ] Back up and restore SQLite together with source files
- [ ] Persist jobs, recover after restart and cancel between batches
- [ ] Complete desktop data/service/model integration using Phase 6 foundations
- [ ] Restrict Qdrant port publishing to localhost
- [ ] Separate query/document embedding formats and validate input length
- [ ] Establish retrieval evaluation and assess hybrid search/reranking
- [ ] Support bounded conversation context and selected sources
- [ ] Improve evidence inspection, cited exports and PDF extraction coverage

These twelve milestones are planned work; existing partial foundations remain
implemented. Hybrid search/reranking adoption depends on measured benefit.

### Phase 8 — Reliability and Quality

- [x] Upload size limits
- [x] Duplicate detection
- [x] Stale vector detection
- [x] Rebuild the index on demand
- [x] Handle a change of embedding model
- [x] Surface index integrity in the library

- [ ] Stability and quality refinement after the twelve Phase 7 improvements
- [ ] Expanded retrieval/answer quality and local/cloud latency validation
- [ ] Final desktop end-to-end verification, including native Markdown/PDF export

Completed safeguards above retain their status from earlier work. Phase 6 builds
out the desktop app; Phase 7 implements the twelve improvements; Phase 8 refines
stability/quality and validates the packaged workflow before MVP release. Relevant
tests, lint, types and builds run throughout implementation.

## Privacy Philosophy

**Local by default.** Personal knowledge should not require cloud storage.
Selecting Gemini sends the question and retrieved excerpts to Google; document
drafting sends the instruction, stored answer and cited file names. Original files,
embeddings, search and saved work remain local.

**Sources over hallucinations.** Generated answers should remain connected to the information they came from.

**Your data remains yours.** Original files are the source of truth, and derived indexes should be rebuildable.

## Development

### Backend

The backend serves ingestion, search, chat and documents over the routes listed
below. Ingestion and search need local Qdrant and Ollama embeddings, including
when Gemini handles generation. Generation uses the provider explicitly selected
for each request, defaulting to Ollama.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/health`.

Expected response:

```json
{"status":"ok"}
```

Run the tests:

```bash
pip install -r requirements-dev.txt
pytest app/tests/
```

Lint:

```bash
ruff check app/          # report
ruff check app/ --fix    # apply the safe fixes
```

The rule selection is in `backend/pyproject.toml`, with a note on each group
saying why it is on or off. It is chosen to catch bugs rather than to enforce
taste — `F821` (undefined name) is the reason it exists, since that class of
mistake hides on error paths that only run when something else has already gone
wrong.

Available endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `GET` | `/ai/providers` | Generation model names and cloud-key availability; never returns credentials |
| `GET` | `/runtime/services` | Bounded Ollama/Qdrant and installed-model checks; never generates or downloads |
| `POST` | `/files` | Upload a file; ingestion runs in the background. Refuses one that is too large, empty, mislabelled, or one you already have |
| `GET` | `/files` | List files, newest first |
| `GET` | `/files/{id}` | Poll one file's processing status |
| `POST` | `/files/{id}/reingest` | Retry or re-index the saved original; returns 202 |
| `POST` | `/files/{id}/cancel` | Stop processing; returns 202 |
| `DELETE` | `/files/{id}` | Delete the original, metadata and vectors; returns 409 while processing |
| `GET` | `/files/{id}/source` | Serve the saved original, inline, for opening a citation |
| `GET` | `/search` | Search finished sources by meaning; `?q=` and optional `?limit=` |
| `POST` | `/chat` | Ask a question; creates a conversation when none is given |
| `GET` | `/chat/conversations` | List conversations, most recently active first |
| `GET` | `/chat/conversations/{id}` | Read one conversation with its messages |
| `PATCH` | `/chat/conversations/{id}` | Rename a conversation |
| `DELETE` | `/chat/conversations/{id}` | Delete a conversation; documents are untouched |
| `GET` | `/documents` | List documents, most recently edited first |
| `POST` | `/documents` | Create an empty document, or one from text you have |
| `POST` | `/documents/generate` | Draft a document from a stored answer and an instruction |
| `GET` | `/documents/{id}` | Read one document with its citations |
| `PATCH` | `/documents/{id}` | Save a title or body edit |
| `DELETE` | `/documents/{id}` | Delete a document |
| `GET` | `/documents/{id}/export.md` | Download the stored Markdown |
| `GET` | `/index/status` | Whether the index still matches the files; `?deep=true` also compares point counts |
| `POST` | `/index/rebuild` | Re-index every file from the originals on disk; returns 202 |

Interactive docs are at `http://127.0.0.1:8000/docs`.

### Optional cloud generation

Desktop: open **Settings → Cloud APIs** for OpenAI, Claude and Gemini key
entry/removal using macOS Keychain. Saved keys are never returned to the UI.
An explicit default-provider preference applies to new work, not existing selections.
Saving keys never sends a validation request or activates billing.

**Settings → Local models** downloads supported recommendations, reports layer
progress, cancels/retries downloads, switches installed generation models and
deletes unused models after exact-name confirmation. Confirm a folder on Ollama's
actual model-storage volume first. Ollama must already be running. Current
generation, fixed embeddings and models used by Noye inference are protected.
See [desktop setup and validation](docs/DESKTOP.md) for remaining limits.

Web: configure OpenAI using `OPENAI_API_KEY`/`OPENAI_MODEL` and Claude using
`ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` in the repository-root `.env`, never frontend
environment variables. Gemini web configuration follows:

Set these values in the repository-root `.env` (not `frontend/.env.local`), then
restart the backend:

```dotenv
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.8-flash
```

Obtain a key from [Google AI Studio](https://aistudio.google.com/apikey).
The model is configurable; choose one available to your project using the
[official model list](https://ai.google.dev/gemini-api/docs/models).
The chat screen and Create document form each have a provider selector. They
start in local mode even when a Gemini key exists; no key enables cloud mode
automatically. Without a key, Gemini is disabled and setup guidance is shown.

Only FastAPI reads the key and sends it to Google in a header. Do not commit it,
put it in a `NEXT_PUBLIC_*` variable, or paste it into a conversation. Provider
errors never include Gemini's raw response body, which could echo private input.
Noye makes one request and does not retry or switch providers on failure.

Your API project's billing determines charges. Noye cannot turn a paid project
into a free one or enforce Google's free quota; use a project without activated
billing for free-only testing. A quota/rate-limit failure is shown as an error.
Free-tier inputs and outputs may be used to improve Google products, so avoid
confidential material and review the
[data terms](https://ai.google.dev/gemini-api/terms) before selecting cloud mode.

This does not change the embedding model or invalidate the local vector index.
Gemini requires internet access; local mode continues to work without a Gemini key.

The API has **no authentication** — Noye is local and single-user, so the server
binds to `127.0.0.1`. Do not expose it on a network interface.

### Frontend

Next.js 16 with TypeScript, Tailwind CSS 4, and the App Router.

```bash
cd frontend
npm install
cp .env.example .env.local   # optional; the default already points at :8000
npm run dev
```

Then open `http://localhost:3000`, which redirects to `/library`.

Run the frontend tests:

```bash
npm test          # once
npm run test:watch
```

Vitest with Testing Library, in jsdom. The tests cover the presentation layer
and the components' accessible surface — the label/input association on the drop
zone, the status word on every pill, and the stage exposed as a real
progressbar — because those are the parts that fail silently when they break.

Four surfaces are built. The **library** takes files — drag them in or pick them,
watch each move through the four ingestion stages, retry one that failed, stop one
mid-flight, and remove what you no longer want indexed. **Search** takes a
question in plain language and returns the passages that match it by meaning, each
naming its file and page, with a link that opens the original at that page.
**Chat** answers a question from those files and keeps the conversation.
**Documents** is where an answer becomes yours: press *Create document* on an
answer, say what it should become, and edit the draft as Markdown with a rendered
preview beside it.

A document is stored text, not a cached generation — nothing regenerates behind
you, and the citations shown describe the first draft rather than what you have
written since. Saving is deliberate: there is a Save button and `Cmd/Ctrl-S`, and
the browser warns before you navigate away with unsaved edits. Autosave is
deliberately absent, because edits to a generated draft tend to be wholesale
rather than incremental and one firing mid-thought would make undo your problem.

Markdown export downloads exactly what is stored. PDF export uses your browser's
own print dialog — choose *Save as PDF* — so Noye needs no extra system libraries
to produce one. A print stylesheet hides the application so the page that reaches
the PDF is the document; it is available from the Preview tab, since printing the
raw Markdown you are editing is not what anyone wants on paper.

Search and chat cover files that have finished indexing, so a half-processed
document is never presented as a whole one. The query or open conversation is kept
in the URL, so Back works and a result can be shared as a link.

An answer shows the **passages consulted** rather than a list called "Sources".
That wording is deliberate: a vector search always returns its nearest
neighbours, so a question your documents do not cover still retrieves passages
while the model correctly says it cannot answer. "Passages consulted" is true
either way, and each one opens the original at its page so you can judge it
yourself. The model never writes its own citations — they are built from the
index.

Both talk to the backend directly, so it has to be running and its
`FRONTEND_ORIGINS` has to include the address you loaded the page from.

`NEXT_PUBLIC_API_BASE_URL` is baked into the browser bundle at build time, so
changing it needs a rebuild rather than just a restart.

The visual system — palette, measured contrast, the status rules, and the two
things that are easy to get wrong — is documented in
[`DESIGN.md`](DESIGN.md). Colours live in `frontend/src/styles/tokens.css` as
plain custom properties with no framework dependency; components never hardcode
a colour, and never need a `dark:` variant, because each token resolves itself
per colour scheme.

### macOS desktop preview

The macOS shell bundles the static frontend and a frozen Python backend; it does
not need Next.js or Python servers running separately. It starts its own loopback
backend on an available port and stops only that process when you quit or close
the window. Qdrant and Ollama still run separately; a banner reports missing
services or models rather than starting Docker or downloading anything silently.

See [the desktop build and data guide](docs/DESKTOP.md) for prerequisites,
packaging, validation and a non-destructive import of existing web data. The
chat-focused interface is included: conversations on the left, a bottom composer,
local/cloud provider selection and an answer-specific passage panel. First-run
recommendations, model installation, changing installed models and secure in-app
API-key settings are the next milestones, not included in this preview.
The final full workflow and native PDF export remain unverified.

### Supporting services

Qdrant runs in Docker; Ollama runs on the host.

```bash
docker compose up -d          # Qdrant on :6333
brew services start ollama    # Ollama on :11434
ollama pull embeddinggemma    # embeddings, 768 dimensions
ollama pull qwen3.5:4b        # generation
```

Copy `.env.example` to `.env` before running the backend against these services.

## License

A license has not been selected yet.
