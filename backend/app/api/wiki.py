"""Thin Wiki APIs with revision comparisons, explicit scopes and local durable work."""

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from app.api.deps import get_db
from app.db import wiki as store
from app.models.wiki import EditWiki, SaveAnalysis, StrictModel, WikiScope
from app.services.wiki import jobs, publication, relations, service, sources

router = APIRouter(prefix="/wiki", tags=["wiki"])


class GenerateWiki(StrictModel):
    source_id: str
    scope: WikiScope = Field(default_factory=WikiScope)


class AdoptWiki(StrictModel):
    expected_revision: str
    revision_id: str


def guard(action):
    try:
        return action()
    except LookupError as error:
        raise HTTPException(404, str(error)) from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


def detail(connection, identifier):
    page = store.page(connection, identifier)
    current = None
    if page["current_revision"]:
        # An unavailable root must not hide SQLite's authored text.
        try:
            publication.capture_disk_edit(connection, identifier)
        except (ValueError, OSError):
            publication.materialize(connection, identifier)
        page = store.page(connection, identifier)
        current = store.revision(connection, page["current_revision"])
        current["evidence"] = service.provenance(connection, current["evidence"])
    return {
        **page,
        "revision": current,
        "revisions": store.revisions(connection, identifier),
        "relations": store.relations(connection, identifier),
    }


@router.get("/sources")
def source_list(db: sqlite3.Connection = Depends(get_db)):
    return sources.catalog(db).list_sources({"mode": "all"})


@router.post("/generate", status_code=202)
def generate(request: GenerateWiki, db: sqlite3.Connection = Depends(get_db)):
    return guard(lambda: jobs.enqueue(db, request.source_id, request.scope))


@router.post("/analyses", status_code=201)
def analysis(request: SaveAnalysis, db: sqlite3.Connection = Depends(get_db)):
    identifier = guard(lambda: service.save_analysis(db, request))
    return detail(db, identifier)


@router.post("/list")
def scoped_list(scope: WikiScope, db: sqlite3.Connection = Depends(get_db)):
    result = []
    for page in store.list_pages(db):
        if page["current_revision"]:
            revision = store.revision(db, page["current_revision"])
            if not sources.in_scope(revision, scope):
                continue
        elif scope.mode != "all":
            continue
        result.append(
            {
                **page,
                "metadata": json.loads(page["metadata"]) if page["metadata"] else {},
                "proposal_count": sum(
                    r["origin"] == "proposal" for r in store.revisions(db, page["id"])
                ),
            }
        )
    return result


@router.get("")
def list_pages(db: sqlite3.Connection = Depends(get_db)):
    return scoped_list(WikiScope(), db)


@router.post("/search")
def search(
    scope: WikiScope,
    q: str = Query(min_length=1, max_length=1000),
    db: sqlite3.Connection = Depends(get_db),
):
    return relations.search(db, q, scope, sources.freeze(db, scope))


@router.get("/{identifier}")
def read(identifier: str, db: sqlite3.Connection = Depends(get_db)):
    return guard(lambda: detail(db, identifier))


@router.get("/{identifier}/revisions/{revision_id}")
def read_revision(identifier: str, revision_id: str, db: sqlite3.Connection = Depends(get_db)):
    revision = guard(lambda: store.revision(db, revision_id))
    if revision["wiki_id"] != identifier:
        raise HTTPException(404, "This revision belongs to a different Wiki page.")
    revision["evidence"] = service.provenance(db, revision["evidence"])
    return revision


@router.patch("/{identifier}")
def edit(identifier: str, request: EditWiki, db: sqlite3.Connection = Depends(get_db)):
    guard(lambda: service.edit(db, identifier, request))
    return detail(db, identifier)


@router.post("/{identifier}/adopt")
def adopt(identifier: str, request: AdoptWiki, db: sqlite3.Connection = Depends(get_db)):
    guard(lambda: service.adopt(db, identifier, request.revision_id, request.expected_revision))
    return detail(db, identifier)


@router.post("/{identifier}/related")
def related(
    identifier: str,
    scope: WikiScope,
    depth: int = Query(default=1, ge=0, le=2),
    limit: int = Query(default=20, ge=1, le=20),
    db: sqlite3.Connection = Depends(get_db),
):
    return guard(
        lambda: relations.traverse(db, identifier, scope, sources.freeze(db, scope), depth, limit)
    )
