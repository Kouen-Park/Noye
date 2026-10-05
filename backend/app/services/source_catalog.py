"""Scoped source inventory and versioned original extraction for Wiki consumers."""

from pathlib import Path

from app.db import jobs
from app.services.folders import SourceError, read_original, root_record
from app.services.integrity import hash_file


def validate_scope(scope):
    scope = {"mode": "all"} if scope is None else scope
    if not isinstance(scope, dict) or scope.get("mode") not in {"all", "empty", "chosen"}:
        raise SourceError("out_of_scope", "Choose an explicit all, empty or chosen source scope.")
    for key in ("source_ids", "root_ids"):
        if not isinstance(scope.get(key, []), list) or not all(
            isinstance(value, str) for value in scope.get(key, [])
        ):
            raise SourceError("out_of_scope", "Invalid source scope identifiers.")
    return scope


class SourceCatalog:
    def __init__(self, connection):
        self.connection = connection

    def list_sources(self, scope=None):
        scope = validate_scope(scope)
        if scope["mode"] == "empty":
            return []
        rows = self.connection.execute(
            "SELECT f.*,s.root_id,s.relative_path,s.version,s.availability,s.manual_category,"
            "r.connected,r.processing,r.availability AS root_availability "
            "FROM files f LEFT JOIN sources s ON s.file_id=f.id "
            "LEFT JOIN source_roots r ON r.id=s.root_id ORDER BY f.created_at,f.id"
        ).fetchall()
        result = []
        for row in rows:
            if scope["mode"] == "chosen":
                if row["id"] not in scope.get("source_ids", []) and row["root_id"] not in scope.get(
                    "root_ids", []
                ):
                    continue
            elif row["root_id"] and (
                not row["connected"]
                or not row["processing"]
                or row["root_availability"] != "available"
            ):
                continue
            availability = row["availability"] or (
                "available" if Path(row["path"]).is_file() else "missing"
            )
            if row["root_id"] and row["root_availability"] != "available":
                availability = row["root_availability"]
            result.append(
                {
                    "source_id": row["id"],
                    "file_id": row["id"],
                    "root_id": row["root_id"],
                    "relative_path": row["relative_path"] or row["name"],
                    "name": row["name"],
                    "file_type": row["file_type"],
                    "content_hash": row["version"] or row["content_hash"],
                    "version": row["version"] or row["content_hash"],
                    "availability": availability,
                    "processing_state": row["status"],
                    "error": row["error"],
                    "manual_category": row["manual_category"],
                    "job": jobs.latest(self.connection, row["id"]),
                }
            )
        return result

    def get(self, source_id):
        """Administrative descriptor, including disconnected/missing provenance; no read grant."""
        values = self.list_sources({"mode": "chosen", "source_ids": [source_id]})
        if not values:
            raise SourceError("unavailable", "This source no longer exists.")
        return values[0]

    def freeze(self, scope=None):
        return [
            {
                key: item[key]
                for key in (
                    "source_id",
                    "root_id",
                    "relative_path",
                    "version",
                    "availability",
                    "processing_state",
                )
            }
            for item in self.list_sources(scope)
        ]

    def assert_allowed(self, source_id, scope=None, manifest=None):
        descriptor = next(
            (value for value in self.list_sources(scope) if value["source_id"] == source_id), None
        )
        if descriptor is None or (
            manifest is not None and not any(value["source_id"] == source_id for value in manifest)
        ):
            raise SourceError("out_of_scope", "This source is outside the allowed inventory.")
        return descriptor

    def changes(self, after=0, limit=100):
        if not 1 <= limit <= 1000 or after < 0:
            raise ValueError("Invalid change cursor or limit.")
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM source_events WHERE sequence>? ORDER BY sequence LIMIT ?",
                (after, limit),
            )
        ]


class EvidenceReader:
    def __init__(self, connection):
        self.connection = connection

    def read(
        self,
        source_id,
        version,
        scope=None,
        manifest=None,
        chunk_indexes=None,
        limit=100,
        offset=0,
        historical=False,
    ):
        descriptor = SourceCatalog(self.connection).assert_allowed(source_id, scope, manifest)
        if not version or not 1 <= limit <= 100 or offset < 0:
            raise SourceError(
                "stale_version", "A source version and bounded passage range are required."
            )
        if manifest is not None and not any(
            value["source_id"] == source_id and value["version"] == version for value in manifest
        ):
            raise SourceError("stale_version", "This version was not frozen in the job inventory.")
        if not historical:
            if descriptor["availability"] != "available":
                raise SourceError("unavailable", "The original source is unavailable.")
            if descriptor["version"] != version:
                raise SourceError(
                    "stale_version", "The source changed after the job inventory was frozen."
                )
            if descriptor["processing_state"] != "READY":
                raise SourceError("not_ready", "Wait for source ingestion or retry its failed job.")
            row = self.connection.execute("SELECT * FROM files WHERE id=?", (source_id,)).fetchone()
            if descriptor["root_id"]:
                root = root_record(self.connection, descriptor["root_id"])
                if not root["connected"] or not root["processing"]:
                    raise SourceError("unavailable", "This folder is disconnected or paused.")
                _, actual, _ = read_original(root, descriptor["relative_path"])
            else:
                actual = hash_file(row["path"])
            if actual != version or row["content_hash"] != version:
                raise SourceError(
                    "stale_version", "Original bytes no longer match the extracted version."
                )
        if descriptor["root_id"]:
            passages = self.connection.execute(
                "SELECT chunk_index,page_number,content FROM source_passages "
                "WHERE file_id=? AND version=? ORDER BY chunk_index",
                (source_id, version),
            ).fetchall()
        else:
            if historical and descriptor["version"] != version:
                raise SourceError(
                    "stale_version", "No historical extraction was saved for this upload."
                )
            passages = self.connection.execute(
                "SELECT chunk_index,page_number,content FROM chunks "
                "WHERE file_id=? ORDER BY chunk_index",
                (source_id,),
            ).fetchall()
        if not passages:
            raise SourceError("not_ready", "No extraction is saved for this version.")
        if chunk_indexes is not None:
            requested = set(chunk_indexes)
            known = {row["chunk_index"] for row in passages}
            if not requested <= known:
                raise SourceError(
                    "invalid_path", "Requested passage does not exist in this extraction."
                )
            passages = [row for row in passages if row["chunk_index"] in requested]
        return [
            {
                "source_id": source_id,
                "file_id": source_id,
                "root_id": descriptor["root_id"],
                "relative_path": descriptor["relative_path"],
                "version": version,
                "content_hash": version,
                "historical": historical,
                **dict(row),
            }
            for row in passages[offset : offset + limit]
        ]


def save_extraction(connection, file_id):
    """Persist immutable passages before later ingestion can replace current chunks."""
    source = connection.execute("SELECT * FROM sources WHERE file_id=?", (file_id,)).fetchone()
    if source is None:
        return
    file = connection.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
    if file["content_hash"] != source["version"]:
        raise SourceError(
            "stale_version", "Ingestion did not process the registered byte snapshot."
        )
    with connection:
        connection.execute(
            "INSERT OR IGNORE INTO source_passages(file_id,version,chunk_index,"
            "page_number,content) "
            "SELECT file_id,?,chunk_index,page_number,content FROM chunks WHERE file_id=?",
            (source["version"], file_id),
        )


def folder_source_enabled(connection, file_id):
    row = connection.execute(
        "SELECT s.availability,r.connected,r.processing,r.availability AS root_availability,"
        "s.version,f.content_hash FROM sources s JOIN source_roots r ON r.id=s.root_id "
        "JOIN files f ON f.id=s.file_id WHERE s.file_id=?",
        (file_id,),
    ).fetchone()
    return row is None or (
        row["availability"] == "available"
        and row["connected"]
        and row["processing"]
        and row["root_availability"] == "available"
        and row["version"] == row["content_hash"]
    )
