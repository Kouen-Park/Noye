"""Rebuilding the index from the files it was derived from.

The index is derived data: `data/sources/` is the source of truth, so anything Qdrant
holds can be produced again. This is the path that does it when the per-file retry in
`/files/{id}/reingest` is not the right granularity — after an embedding model change,
or after the collection or its volume was lost.

The decision this module exists to make
---------------------------------------
**Do not drop the collection unless the dimension actually requires it.**

Dropping first is the obvious implementation and the wrong default. Re-embedding a
real library takes minutes to hours of local inference, and it can fail part-way —
Ollama stops, the machine sleeps. If the collection was dropped first, the user is
left with **no index at all**, where before they had a stale one that still answered
questions. A stale index is a worse answer; an absent index is no answer.

Per-file re-ingestion already replaces a file's vectors atomically enough for this:
`_embed_and_index` deletes that file's points before writing the new ones. So the
normal rebuild is just every file through the ordinary pipeline, and the index
degrades file by file instead of all at once.

The exception is a **dimension change**. A collection created for 768-wide vectors
cannot accept 1024-wide ones, so there is nothing to preserve — the old points are
unusable by definition and the collection has to be recreated before anything can be
written. That is detected rather than asked for.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from qdrant_client import QdrantClient

from app.config import get_settings
from app.db import files as file_store
from app.logging_config import get_logger
from app.services.indexing import collection_vector_size, recreate_collection
from app.services.ingestion import AlreadyIngesting, reserve_ingestion

logger = get_logger("rebuild")


@dataclass(frozen=True)
class Skipped:
    """A file the rebuild did not queue, and why."""

    file_id: str
    file_name: str
    reason: str


@dataclass(frozen=True)
class RebuildPlan:
    """What a rebuild will do. Returned before the work starts."""

    file_ids: tuple[str, ...]
    skipped: tuple[Skipped, ...]
    collection_recreated: bool
    embedding_model: str

    @property
    def queued(self) -> int:
        return len(self.file_ids)


def needs_recreation(client: QdrantClient | None = None) -> bool:
    """Whether the collection's width disagrees with the configuration.

    True only for a real disagreement. A collection that does not exist yet needs
    creating, not recreating, and ingestion does that on its own.
    """
    configured = get_settings().qdrant_vector_size
    live = collection_vector_size(client)
    return live is not None and live != configured


def plan_rebuild(
    connection: sqlite3.Connection, *, client: QdrantClient | None = None
) -> RebuildPlan:
    """Decide what to re-ingest, and reserve each file before returning.

    Reserving here rather than in the background task is deliberate: the caller gets a
    truthful count, and a file that something else is already ingesting is reported as
    skipped instead of silently colliding.

    A file whose source is gone cannot be rebuilt from anything. It is skipped with
    that reason rather than failed, because its existing vectors — if any — are still
    the best record of a document the user no longer has on disk.
    """
    settings = get_settings()
    recreated = False

    if needs_recreation(client):
        live = collection_vector_size(client)
        logger.warning(
            "Recreating collection: configured dimension %d, collection has %s",
            settings.qdrant_vector_size,
            live,
        )
        recreate_collection(client)
        recreated = True

    queued: list[str] = []
    skipped: list[Skipped] = []

    for record in file_store.list_files(connection):
        if not Path(record.path).exists():
            skipped.append(
                Skipped(record.id, record.name, "The original file is missing from disk.")
            )
            continue
        try:
            reserve_ingestion(record.id)
        except AlreadyIngesting:
            skipped.append(
                Skipped(record.id, record.name, "Already being processed.")
            )
            continue
        queued.append(record.id)

    logger.info(
        "Rebuild planned queued=%d skipped=%d recreated=%s model=%s",
        len(queued),
        len(skipped),
        recreated,
        settings.ollama_embedding_model,
    )

    return RebuildPlan(
        file_ids=tuple(queued),
        skipped=tuple(skipped),
        collection_recreated=recreated,
        embedding_model=settings.ollama_embedding_model,
    )
