# Phase 7 item 8: local Qdrant exposure

This independent change starts from `main` while Phase 6 desktop work continues
in a separate checkout, as requested on 2026-10-05. Merge Phase 6 first, then
refresh this branch against `main` before merging it.

Compose publishes only REST at `127.0.0.1:6333`; gRPC is not published because
the backend uses REST. Recreate an existing container with
`docker compose up -d qdrant` for the mapping to take effect; preserve the volume.
CORS is a browser policy, not authentication or a firewall.

Validated on 2026-10-05:

- `docker compose config --format json`: one published port, target/published
  6333 and host IP `127.0.0.1`.
- Docker Desktop 29.8.0, Qdrant v1.19.1: a separate temporary Compose project
  published REST at `127.0.0.1:59352` and did not publish gRPC. An ephemeral host
  port avoided interference with the existing local service.
- Application ingestion reached READY for a synthetic Markdown file; retrieval
  returned its expected chunk over real Qdrant REST. Embeddings were mocked;
  this was a connectivity check, not a relevance test.
- The temporary container and network were removed. No personal library or
  existing Qdrant volume was changed.

Not validated: live Ollama embeddings, access from another physical machine,
or the final packaged Tauri workflow.

## Final integration — 2026-10-05

The original draft #37 was closed when its `codex/` remote branch was replaced.
`feat/qdrant-localhost` retains the identical feature commit `bc21669` and now
includes Phase 6 main `141fa47` through a normal merge, without rewriting history.
README's desktop/cloud instructions and this network boundary both remain intact.
`docker compose config --format json` was repeated: exactly one TCP publication,
`127.0.0.1:6333:6333`, pinned image and unchanged named storage volume.
The earlier isolated listener/REST smoke check above is historical evidence; no
running personal container was recreated during this final integration.
