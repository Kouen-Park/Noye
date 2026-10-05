# Durable ingestion attempts

Phase 7 item 6 stores a job before upload/retry/rebuild is scheduled. SQLite
records the attempt ID, file ID/name, stage, embedding passage counts, timestamps,
cancel request and terminal/interruption reason. Historical attempts remain;
the library shows the latest 100 attempts, one per file.

One ingestion pipeline and one local model request run at a time. The shared
inference gate also covers local chat, document generation and query embeddings.
Waiting for inference is bounded at 30 seconds; a busy request produces a retryable
error. No extra worker service or dependency is required.

Embedding progress commits after each batch of at most 16 passages. Cancellation
is checked before/after each batch and before/after indexing. An already running
HTTP request cannot be interrupted instantly; embedding transport has a 120-second
timeout. Desktop parent EOF/shutdown signals cancellation before ASGI drains;
the native parent retains its existing bounded 16-second owned-child shutdown.

On startup, unfinished attempts and legacy processing files become interrupted,
with original progress retained. Partial SQLite chunks and index identity are
cleared. Search excludes these files even if unreachable Qdrant retains stale
points. Retry is explicit, starts from the saved original, and replaces the file's
deterministically keyed vectors before making it READY. This does not cache or
resume embeddings from a partially completed batch. It never replays cloud
generation or switches provider.

GET /jobs lists latest attempts; POST /jobs/{id}/cancel and /resume require the
latest attempt and reject stale/invalid transitions. Restored workspace backups
also settle open jobs as interrupted. Missing originals prevent retry.

Automated coverage uses synthetic sources, real temporary SQLite, an in-memory
Qdrant and captured Ollama requests: restart in queued/embedding/indexing stages,
progress retention, between-batch cancellation, queued cancellation, repeated
retry without duplicate vectors, stale attempt rejection, and shared inference
serialization/timeout cleanup. Packaged-app sleep/kill and real model latency are
Phase 8 acceptance checks.
