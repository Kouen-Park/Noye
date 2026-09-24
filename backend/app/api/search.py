"""Search API.

Thin over :mod:`app.services.retrieval`, which already embeds a query and returns
ranked chunks with their provenance. This route adds the two things retrieval
deliberately does not do: it joins the human-readable file name from SQLite, and
it restricts the search to sources that are actually finished.

Restricting to READY files is the part that matters. A file mid-ingestion has
some of its passages in the index and not others, and a FAILED file may have left
none at all; presenting either as a search result would show the user a partial
document without saying so.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.db import files as file_store
from app.logging_config import get_logger
from app.models.files import FileStatus
from app.services.embeddings import EmbeddingError
from app.services.indexing import IndexingError
from app.services.retrieval import DEFAULT_LIMIT, search

router = APIRouter(prefix="/search", tags=["search"])

logger = get_logger("api.search")

#: Most results one request may ask for.
#:
#: Bounded because the limit goes straight to Qdrant, and an unbounded request
#: would let a single query pull the whole collection into memory. Twenty is well
#: past what the first search UI shows.
MAX_LIMIT = 20


class SearchHit(BaseModel):
    """One matching passage and where it came from."""

    content: str
    file_id: str
    #: Joined from SQLite. Absent from the vector payload on purpose, so a rename
    #: cannot leave a stale copy behind in the index.
    file_name: str
    #: ``None`` for formats without pages, such as Markdown and text. Never 0:
    #: that would read as a real page.
    page_number: int | None
    chunk_index: int
    score: float


class SearchResponse(BaseModel):
    """Results for one query, best match first."""

    query: str
    results: list[SearchHit]
    #: How many sources the query was allowed to match against. Zero means the
    #: library has nothing finished yet, which is a different message from a
    #: query that simply found nothing.
    searched_files: int = Field(ge=0)


@router.get("", response_model=SearchResponse)
def search_knowledge(
    q: str = Query(..., min_length=1, description="What to search for, in plain language"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum results"),
    db: sqlite3.Connection = Depends(get_db),
) -> SearchResponse:
    """Find passages whose meaning matches the query.

    Searches only sources that finished indexing. Results carry the file name and,
    where the format has them, the page number, so a hit can be cited and opened.
    """
    query = q.strip()
    if not query:
        # `min_length` catches the empty string but not a space, and a
        # whitespace query would otherwise be embedded and matched against
        # nothing meaningful.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter something to search for.",
        )

    ready = {
        record.id: record.name
        for record in file_store.list_files(db)
        if record.status is FileStatus.READY
    }
    if not ready:
        # Nothing to search. Returning early also avoids spending an embedding
        # call on a query that could not match anything.
        return SearchResponse(query=query, results=[], searched_files=0)

    try:
        results = search(query, limit=limit, file_ids=list(ready))
    except EmbeddingError as exc:
        # The query text is NOT logged: it is the user's words. The model name
        # and the failure are what a developer needs.
        logger.warning("Search embedding failed error=%s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Could not turn your question into a search. The local model that does "
                f"that is not responding: {exc}"
            ),
        ) from exc
    except IndexingError as exc:
        logger.warning("Search index query failed error=%s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not search the index: {exc}",
        ) from exc
    except ValueError as exc:
        # Retrieval validates its own inputs; anything reaching here is a bad
        # request rather than a service failure.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SearchResponse(
        query=query,
        searched_files=len(ready),
        results=[
            SearchHit(
                content=result.content,
                file_id=result.file_id,
                # A hit whose file vanished between the query and now is dropped
                # below rather than shown with a blank name.
                file_name=ready[result.file_id],
                page_number=result.page_number,
                chunk_index=result.chunk_index,
                score=result.score,
            )
            for result in results
            if result.file_id in ready
        ],
    )
