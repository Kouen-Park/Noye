"""Folder controls take registered IDs; selection is native/private stdin only."""

import sqlite3
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_db
from app.api.models import desktop_control
from app.db.sources import clear_issue, issues
from app.services import ingestion, knowledge_jobs
from app.services.filing import file_source, recover_filing
from app.services.folder_scanner import collect, folder_lock
from app.services.folders import SourceError, root_record, update_root
from app.services.source_catalog import SourceCatalog

router = APIRouter(prefix="/folders", tags=["folders"], dependencies=[Depends(desktop_control)])


def public_root(root, db):
    result = {
        key: value for key, value in dict(root).items() if key not in {"path", "device", "inode"}
    }
    result["recovery_conflicts"] = issues(db, root["id"], "recovery")
    return result


def fail(exc):
    raise HTTPException(
        409 if getattr(exc, "code", None) == "busy" else 400,
        {"code": getattr(exc, "code", "busy"), "message": str(exc)},
    ) from exc


@router.get("")
def roots(db: sqlite3.Connection = Depends(get_db)):
    return [
        public_root(row, db) for row in db.execute("SELECT * FROM source_roots ORDER BY created_at")
    ]


class RootPatch(BaseModel):
    processing: bool | None = None
    organization_prefix: str | None = None
    disconnect: bool = False
    acknowledge_recovery_conflicts: bool = False


@router.patch("/{root_id}")
def control(root_id: str, body: RootPatch, db: sqlite3.Connection = Depends(get_db)):
    try:
        with folder_lock:
            root = update_root(
                db,
                root_id,
                processing=body.processing,
                organization_prefix=body.organization_prefix,
                set_organization="organization_prefix" in body.model_fields_set,
                disconnect=body.disconnect,
            )
            if body.disconnect or body.processing is False:
                for row in db.execute("SELECT file_id FROM sources WHERE root_id=?", (root_id,)):
                    ingestion.cancel_ingestion(row["file_id"], db)
                for row in db.execute(
                    "SELECT id FROM knowledge_jobs WHERE state IN ('queued','running','cancelling')"
                ).fetchall():
                    job = knowledge_jobs.get(db, row["id"])
                    if any(item["root_id"] == root_id for item in job["manifest"]):
                        knowledge_jobs.cancel(db, row["id"])
            if body.acknowledge_recovery_conflicts:
                clear_issue(db, root_id, "recovery")
            return public_root(root, db)
    except (SourceError, ingestion.AlreadyIngesting) as exc:
        fail(exc)


@router.get("/{root_id}/tree")
def tree(root_id: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        root = root_record(db, root_id)
    except SourceError as exc:
        fail(exc)
    sources = SourceCatalog(db).list_sources({"mode": "chosen", "root_ids": [root_id]})
    try:
        _, entries = collect(root, show_excluded=True)
    except (SourceError, OSError):
        entries = []
    by_path = {source["relative_path"]: source for source in sources}
    intake_errors = {
        item["relative_path"]: item["message"] for item in issues(db, root_id, "intake")
    }
    for source in sources:
        latest = db.execute(
            "SELECT id FROM knowledge_jobs WHERE kind='wiki' AND subject_id=? "
            "ORDER BY rowid DESC LIMIT 1",
            (source["source_id"],),
        ).fetchone()
        source["knowledge_job"] = knowledge_jobs.get(db, latest["id"]) if latest else None
    for entry in entries:
        entry["source"] = by_path.pop(entry["relative_path"], None)
        entry["intake_error"] = intake_errors.pop(entry["relative_path"], None)
    entries.extend(
        {"relative_path": path, "kind": "file", "source": source}
        for path, source in by_path.items()
    )
    entries.extend(
        {"relative_path": path, "kind": "file", "intake_error": message}
        for path, message in intake_errors.items()
        if not any(entry["relative_path"] == path for entry in entries)
    )
    known = {entry["relative_path"] for entry in entries}
    for entry in list(entries):
        for parent in PurePosixPath(entry["relative_path"]).parents:
            relative = parent.as_posix()
            if relative != "." and relative not in known:
                entries.append({"relative_path": relative, "kind": "directory", "remembered": True})
                known.add(relative)
    return {
        "root": public_root(root, db),
        "entries": sorted(entries, key=lambda row: row["relative_path"]),
    }


@router.post("/{root_id}/reconcile")
def reconcile(root_id: str, db: sqlite3.Connection = Depends(get_db)):
    from app.services.folder_scanner import watcher

    root_record(db, root_id)
    try:
        with folder_lock:
            recover_filing(db)
            queued = watcher.scanner.scan_root(db, root_id) if watcher.scanner else []
        return {"queued": queued, "stability_wait_seconds": 2}
    except (SourceError, ingestion.AlreadyIngesting) as exc:
        fail(exc)


class FilingIn(BaseModel):
    source_id: str
    destination: str
    expected_version: str
    manual: bool = False


@router.post("/{root_id}/file")
def file(root_id: str, body: FilingIn, db: sqlite3.Connection = Depends(get_db)):
    source = db.execute("SELECT root_id FROM sources WHERE file_id=?", (body.source_id,)).fetchone()
    if source is None or source["root_id"] != root_id:
        raise HTTPException(400, "This source does not belong to this folder.")
    try:
        return file_source(db, body.source_id, body.destination, body.expected_version, body.manual)
    except (SourceError, ingestion.AlreadyIngesting) as exc:
        fail(exc)


@router.get("/{root_id}/filing")
def filing(root_id: str, db: sqlite3.Connection = Depends(get_db)):
    return [
        dict(row)
        for row in db.execute(
            "SELECT * FROM filing_journal WHERE root_id=? ORDER BY created_at DESC", (root_id,)
        )
    ]


@router.post("/{root_id}/sources/{source_id}/remove-derived")
def remove_derived(root_id: str, source_id: str, db: sqlite3.Connection = Depends(get_db)):
    from app.services.derived_data import remove_source_index
    from app.services.indexing import IndexingError

    source = db.execute("SELECT root_id FROM sources WHERE file_id=?", (source_id,)).fetchone()
    if source is None or source["root_id"] != root_id:
        raise HTTPException(400, "This source does not belong to this folder.")
    try:
        return remove_source_index(db, source_id)
    except (SourceError, ingestion.AlreadyIngesting, ingestion.MaintenanceBusy) as exc:
        fail(exc)
    except IndexingError as exc:
        raise HTTPException(
            503, "Derived index removal failed. Original and history preserved."
        ) from exc
