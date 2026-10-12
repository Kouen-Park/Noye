"""Read/cancel/retry durable local knowledge work; feature routers enqueue it."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.services import knowledge_jobs

router = APIRouter(prefix="/knowledge-jobs", tags=["knowledge jobs"])


@router.get("")
def list_jobs(db: sqlite3.Connection = Depends(get_db)):
    return [
        knowledge_jobs.get(db, row["id"])
        for row in db.execute("SELECT id FROM knowledge_jobs ORDER BY updated_at DESC LIMIT 100")
    ]


@router.post("/{job_id}/{action}")
def action(job_id: str, action: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        if action == "cancel":
            return knowledge_jobs.cancel(db, job_id)
        if action == "resume":
            return knowledge_jobs.resume(db, job_id)
        raise HTTPException(404, "Unknown task action.")
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
