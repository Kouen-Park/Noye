"""Remove rebuildable indexes, preserving original identity/bytes and authored history."""

import json

from app.db import files
from app.models.files import FileStatus
from app.services import ingestion
from app.services.folder_scanner import folder_lock
from app.services.folders import SourceError, root_record
from app.services.indexing import delete_file_chunks


def remove_source_index(connection, source_id):
    with folder_lock:
        source = connection.execute(
            "SELECT * FROM sources WHERE file_id=?", (source_id,)
        ).fetchone()
        if source is None:
            raise SourceError("unavailable", "This connected-folder source no longer exists.")
        root = root_record(connection, source["root_id"])
        if root["connected"] and root["processing"]:
            raise SourceError("busy", "Pause this folder before removing derived data.")
        active = connection.execute(
            "SELECT manifest_json FROM knowledge_jobs "
            "WHERE state IN ('queued','running','cancelling')"
        ).fetchall()

        if any(
            any(item["source_id"] == source_id for item in json.loads(row[0])) for row in active
        ):
            raise SourceError("busy", "Wait for active knowledge/document jobs to stop first.")
        ingestion.reserve_delete(source_id)
        try:
            # Do not mark the DB cleared if the remote derived index could not be removed.
            delete_file_chunks(source_id)
            with connection:
                connection.execute("DELETE FROM chunks WHERE file_id=?", (source_id,))
                connection.execute(
                    "DELETE FROM wiki_index WHERE wiki_id IN "
                    "(SELECT r.wiki_id FROM wiki_revisions r JOIN wiki_evidence e "
                    "ON e.revision_id=r.id WHERE e.source_id=?)",
                    (source_id,),
                )
                connection.execute(
                    "UPDATE files SET chunk_count=0,index_fingerprint=NULL,index_metadata=NULL,"
                    "embedding_model=NULL WHERE id=?",
                    (source_id,),
                )
                files.set_status(
                    connection,
                    source_id,
                    FileStatus.FAILED,
                    error="Derived indexes removed. Resume and rebuild from original.",
                )
            return {
                "source_id": source_id,
                "original_preserved": True,
                "history_preserved": True,
                "rebuild_required": True,
            }
        finally:
            ingestion.release_file(source_id)
