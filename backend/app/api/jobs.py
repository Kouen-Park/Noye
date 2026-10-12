"""Latest durable ingestion attempts, including those left by an earlier process."""

import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_db
from app.api.files import cancel_file, reingest_file
from app.db import jobs as store

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(db: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    roots = {
        row["file_id"]: row["root_id"] for row in db.execute("SELECT file_id,root_id FROM sources")
    }
    return [{**job, "folder_root_id": roots.get(job["file_id"])} for job in store.list_latest(db)]


def _latest(db, job_id):
    try:
        job = store.get(db, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if store.latest(db, job["file_id"])["id"] != job_id:
        raise HTTPException(status_code=409, detail="A newer attempt exists. Refresh the jobs.")
    return job


@router.post("/{job_id}/cancel", status_code=202)
def cancel_job(job_id: str, db: sqlite3.Connection = Depends(get_db)) -> dict:
    job = _latest(db, job_id)
    if job["state"] not in store.OPEN_STATES:
        raise HTTPException(status_code=409, detail="This job is no longer processing.")
    cancel_file(job["file_id"], db)
    return store.get(db, job_id)


@router.post("/{job_id}/resume", status_code=202)
def resume_job(
    job_id: str, background: BackgroundTasks, db: sqlite3.Connection = Depends(get_db)
) -> dict:
    job = _latest(db, job_id)
    if job["state"] not in ("failed", "cancelled", "interrupted"):
        raise HTTPException(status_code=409, detail="Only an unfinished job can be retried.")
    reingest_file(job["file_id"], background, db)
    return store.latest(db, job["file_id"])
