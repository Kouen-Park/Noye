# Phase 7 item 4: index identity and compatibility

Started from `main` in a separate checkout on 2026-10-05. Phase 6 continues
independently. Merge Phase 6 first, then item 3's maintenance guard, then refresh
this branch and resolve the shared ingestion/rebuild/API changes before merging.

Migration 2 adds nullable `files.index_fingerprint` and `files.index_metadata`.
Existing rows remain unknown; no identity is backfilled from the model name.
Conversations, messages, documents, original hashes and source files are preserved.

The SHA-256 fingerprint covers the installed embedding model tag/digest, vector
dimension, input-format version, chunk size/overlap, chunker/extractor versions and
PyMuPDF version. Source revisions stay separate in `content_hash`. Generation-model
changes do not invalidate embeddings. `CHUNK_SIZE` and `CHUNK_OVERLAP` are validated
settings with the existing defaults of 1000 and 150 characters.

Ingestion captures identity before chunking and checks it before/after embedding
and after indexing. It writes the observed identity to SQLite and each Qdrant
point only for that processing run. Failure clears identity with the partial data.
Retrieval verifies the query identity before/after embedding and filters points by
fingerprint and file scope. Unknown/incompatible points cannot join a ranking.

The library/API distinguish `INDEX_UNKNOWN`, `INDEX_CHANGED` and
`IDENTITY_UNAVAILABLE`: the first two require an explicit rebuild; the last needs
service/model recovery. `/index/status` exposes stored/expected fingerprints and
`rebuild_required`. Search reports unavailable identity as 503; chat preserves the
question and a failed assistant turn. A rebuild verifies model installation before
any collection reset. There is no automatic reindex or model download.

Model digests come from Ollama's local
[list-models endpoint](https://docs.ollama.com/api/tags); they are not inferred.
This adds bounded local metadata requests; it does not introduce generation calls.

Validated on 2026-10-05:

- Backend: **536 passed, 19 skipped** with
  `python -m pytest app/tests -q -p no:cacheprovider`; Ruff passed.
- Frontend: **130 passed**; ESLint, Next type generation, TypeScript and the
  production Webpack build passed using the `main` lockfile (Next.js 16.3.5).
- Tests cover same-tag digest replacement, dimension/input/chunk/extractor changes,
  generation-model independence, unknown indexes, incompatible/legacy point
  exclusion, empty scopes, model unavailability, pre-reset rejection, preserved
  writing through migration, and changes during query/chunking/ingestion.
- Real local Ollama 0.34.2 on an owned temporary loopback port: EmbeddingGemma digest
  `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1` was resolved,
  a synthetic file reached READY with `raw-v1` identity, and its expected passage
  was retrieved through the fingerprint filter using in-memory Qdrant.

Code inspection found that resolving identity only after chunking could label old
chunks with changed settings. Identity is now captured before chunking and a
regression test rejects this case.

Not validated: packaged Tauri/browser interaction, live tag replacement, a real
dimension-changing rebuild, or integration with unfinished Phase 6 changes.
The 19 default live-service tests skipped; the separate local embedding check above
was performed with synthetic data. `npm ci --ignore-scripts` reported six audit
findings in the existing main lockfile (five high, one critical); this focused change
does not update dependencies. Phase 6's dependency changes must be retained at merge.

## Final integration — 2026-10-05

The identical closed #39 head `a46a012` is retained on `feat/index-identity`.
Main `f46b8c1` includes Phase 6 and the local exposure/maintenance replacements.
Normal merge `9fe73f4` resolves the four documented conflicts: README retains
compatibility and cloud setup; configuration combines SecretStr/desktop settings
with chunk validation; chat keeps readiness inside its saved-failure handler and
forwards the explicit provider; index rebuild retains both maintenance 409 and
embedding preflight 503. Automatic ingestion/rebuild/type merges were inspected.
Desktop startup/shutdown files and Next.js 16.3.8 manifests remain identical to main.

Eight regression cases in `38b9d05` cover all four providers through real
compatibility lookup and preserve failed turns without generation when identity
resolution fails. Fresh backend: **720 passed, 19 skipped, 8 warnings**. Frontend:
**199 passed across 27 files**. Ruff, ESLint, Next route types, TypeScript, web
Webpack build, desktop UI export and diff checks passed. No new live service,
credential, model replacement, dimension reset or native GUI check was performed.
Earlier live embedding evidence above remains historical rather than a rerun.
