# Noye

> **Your knowledge, at your command.**

Noye is a **local-first AI knowledge workspace** that turns your files into searchable, reusable knowledge.

Upload PDFs, Markdown files, and notes. Noye is designed to process them locally, let you search and ask questions across your knowledge base, preserve source citations, and turn useful results into editable documents.

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
| Desktop | Tauri *(planned)* |

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
- [ ] Frontend bootstrap
- [ ] Docker development environment

### Phase 1 — Knowledge Engine

- [ ] PDF text extraction
- [ ] Page-aware chunking
- [ ] Local embeddings
- [ ] Qdrant indexing
- [ ] Semantic retrieval
- [ ] Local LLM generation
- [ ] Citation mapping

### Phase 2 — Library

- [ ] Drag-and-drop upload
- [ ] Processing states
- [ ] File management
- [ ] Duplicate detection
- [ ] Vector cleanup on deletion

### Phase 3 — Chat

- [ ] Knowledge-base chat
- [ ] Source citations
- [ ] Conversation history
- [ ] Persistent messages

### Phase 4 — Documents

- [ ] Generate documents from retrieved knowledge
- [ ] Markdown editor and preview
- [ ] Markdown export
- [ ] PDF export

### Phase 5 — Desktop

- [ ] Tauri integration
- [ ] macOS packaging
- [ ] Folder watching
- [ ] Rebuild vector index
- [ ] Windows support

## Privacy Philosophy

**Local by default.** Personal knowledge should not require cloud storage.

**Sources over hallucinations.** Generated answers should remain connected to the information they came from.

**Your data remains yours.** Original files are the source of truth, and derived indexes should be rebuildable.

## Development

The backend currently provides a minimal FastAPI health endpoint.

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

## License

A license has not been selected yet.
