"""Source-driven generation and immutable revision export, alongside legacy APIs."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import get_db
from app.api.documents import DocumentOut, _filename_for
from app.db import documents
from app.db import source_documents as store
from app.models.source_documents import EditRequest, GenerateRequest
from app.services import knowledge_jobs
from app.services.source_documents import jobs, pipeline
from app.services.wiki.service import provenance

router = APIRouter(prefix="/source-documents", tags=["source documents"])


def result(db, document_id, revision_id=None):
    document = documents.get_document(db, document_id)
    revision = (
        store.revision(db, document_id, revision_id)
        if revision_id
        else store.current(db, document_id)
    )
    if revision is None:
        raise LookupError("This is not a source-driven document.")
    out = DocumentOut.of(document, db).model_dump()
    out.update(
        title=revision["title"],
        content=revision["content"],
        revision=revision,
        revisions=store.revisions(db, document_id),
        provenance_markdown=pipeline.provenance_markdown(revision["metadata"]),
    )
    out["revision"]["metadata"]["citations"] = provenance(db, revision["metadata"]["citations"])
    return out


@router.post("/generate", status_code=202)
def generate(request: GenerateRequest, db: sqlite3.Connection = Depends(get_db)):
    try:
        job = jobs.enqueue(db, request)
        return {"job": job, "request": jobs.public_request(db, job["subject_id"])}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/requests")
def requests(conversation_id: str | None = None, db: sqlite3.Connection = Depends(get_db)):
    result = []
    for row in db.execute("SELECT id FROM source_document_requests ORDER BY rowid DESC LIMIT 100"):
        request = jobs.public_request(db, row[0])
        if conversation_id and request["request"]["conversation_id"] != conversation_id:
            continue
        job = db.execute(
            "SELECT id FROM knowledge_jobs WHERE kind='source_document' AND subject_id=? "
            "ORDER BY rowid DESC LIMIT 1",
            (row[0],),
        ).fetchone()
        result.append({"request": request, "job": knowledge_jobs.get(db, job[0]) if job else None})
    return result


@router.get("/{document_id}")
def read(document_id: str, revision: str | None = None, db: sqlite3.Connection = Depends(get_db)):
    try:
        return result(db, document_id, revision)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/{document_id}")
def edit(document_id: str, request: EditRequest, db: sqlite3.Connection = Depends(get_db)):
    try:
        store.edit(db, document_id, request.expected_revision, request.title, request.content)
        return result(db, document_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{document_id}/export.md")
def export(
    document_id: str,
    revision: str | None = None,
    provenance: bool = False,
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        head = (
            store.current(db, document_id)
            if revision is None
            else store.revision(db, document_id, revision)
        )
        if head is None:
            raise LookupError("This source-driven document does not exist.")
        content = head["content"] + (
            "\n\n" + pipeline.provenance_markdown(head["metadata"]) if provenance else ""
        )
        return Response(
            content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": (
                    "attachment; filename*=UTF-8''" + _filename_for(head["title"])
                )
            },
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
