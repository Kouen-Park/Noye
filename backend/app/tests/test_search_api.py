"""Tests for the search API.

The retrieval service itself is already covered in `test_retrieval.py`; these
tests are about the contract the route adds on top of it — the file-name join,
the READY-only restriction, input validation, and how an unavailable Ollama or
Qdrant reaches the user.

`search` is stubbed in most tests. What the route must get right is which files
it searches and how it shapes the answer, and driving that through a real
embedding call would test the model instead. The integration test at the bottom
runs the genuine path when the services are up.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import search as search_api
from app.config import get_settings
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.main import app
from app.models.files import FileStatus, FileType
from app.services.embeddings import EmbeddingError
from app.services.indexing import IndexingError
from app.services.retrieval import SearchResult


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    connection = connect(tmp_path / "search.db")
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def client(db: sqlite3.Connection) -> TestClient:
    app.dependency_overrides[search_api.get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_file(
    db: sqlite3.Connection,
    *,
    name: str,
    status: FileStatus = FileStatus.READY,
    file_type: FileType = FileType.PDF,
    embedding_model: str | None = None,
) -> str:
    record = file_store.create_file(
        db, name=name, file_type=file_type, path=f"/tmp/{name}", size=1024
    )
    if embedding_model is not None:
        file_store.set_embedding_model(db, record.id, embedding_model)
    file_store.set_status(
        db, record.id, status, error="boom" if status is FileStatus.FAILED else None
    )
    return record.id


def hit(file_id: str, *, content: str = "A passage.", page: int | None = 3,
        index: int = 0, score: float = 0.9) -> SearchResult:
    return SearchResult(
        content=content, file_id=file_id, page_number=page, chunk_index=index, score=score
    )


def stub_search(monkeypatch: pytest.MonkeyPatch, results, capture: dict | None = None):
    """Replace retrieval with a stub, optionally recording its arguments."""

    def fake(query, *, limit, file_ids=None, **kwargs):
        if capture is not None:
            capture.update(query=query, limit=limit, file_ids=file_ids)
        if isinstance(results, Exception):
            raise results
        return results

    monkeypatch.setattr(search_api, "search", fake)


# --- shaping the answer ------------------------------------------------------


def test_a_hit_carries_the_file_name_from_sqlite(client, db, monkeypatch) -> None:
    file_id = add_file(db, name="Algorithms-lecture-07.pdf")
    stub_search(monkeypatch, [hit(file_id, content="Dijkstra picks the smallest.", page=34)])

    body = client.get("/search", params={"q": "how does dijkstra choose"}).json()

    assert body["query"] == "how does dijkstra choose"
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["file_name"] == "Algorithms-lecture-07.pdf"
    assert result["content"] == "Dijkstra picks the smallest."
    assert result["page_number"] == 34
    assert result["file_id"] == file_id


def test_results_keep_the_order_retrieval_gave_them(client, db, monkeypatch) -> None:
    first = add_file(db, name="best.pdf")
    second = add_file(db, name="worse.pdf")
    stub_search(
        monkeypatch,
        [hit(first, score=0.91, content="closest"), hit(second, score=0.42, content="further")],
    )

    results = client.get("/search", params={"q": "graphs"}).json()["results"]

    assert [r["file_name"] for r in results] == ["best.pdf", "worse.pdf"]
    assert results[0]["score"] > results[1]["score"]


def test_a_pageless_source_reports_no_page(client, db, monkeypatch) -> None:
    """Markdown and text have no pages, and 0 would read as a real one."""
    file_id = add_file(db, name="study-notes.md", file_type=FileType.MARKDOWN)
    stub_search(monkeypatch, [hit(file_id, page=None)])

    result = client.get("/search", params={"q": "notes"}).json()["results"][0]

    assert result["page_number"] is None


def test_a_hit_whose_file_disappeared_is_dropped(client, db, monkeypatch) -> None:
    file_id = add_file(db, name="present.pdf")
    stub_search(monkeypatch, [hit(file_id), hit("ghost-id")])

    results = client.get("/search", params={"q": "anything"}).json()["results"]

    assert [r["file_id"] for r in results] == [file_id]


# --- which files get searched ------------------------------------------------


def test_only_ready_files_are_searched(client, db, monkeypatch) -> None:
    """A half-indexed or failed source would be a partial document presented as
    a whole one."""
    ready = add_file(db, name="ready.pdf", status=FileStatus.READY)
    add_file(db, name="working.pdf", status=FileStatus.EMBEDDING)
    add_file(db, name="broken.pdf", status=FileStatus.FAILED)
    captured: dict = {}
    stub_search(monkeypatch, [hit(ready)], captured)

    body = client.get("/search", params={"q": "x"}).json()

    assert captured["file_ids"] == [ready]
    assert body["searched_files"] == 1


def test_a_file_from_a_superseded_embedding_model_is_not_searched(
    client, db, monkeypatch
) -> None:
    """READY is necessary but not sufficient.

    A cosine score between two embedding spaces is meaningless, so including such a
    file would rank confidently and wrongly — and a plausible passage list is exactly
    what a working search looks like, so the user could not tell.
    """
    current = add_file(db, name="current.pdf", embedding_model="embeddinggemma")
    add_file(db, name="from-old-model.pdf", embedding_model="nomic-embed-text")
    captured: dict = {}
    stub_search(monkeypatch, [hit(current)], captured)

    body = client.get("/search", params={"q": "x"}).json()

    assert captured["file_ids"] == [current]
    assert body["searched_files"] == 1


def test_a_file_with_no_recorded_model_is_still_searched(client, db, monkeypatch) -> None:
    """NULL means unknown, not mismatched.

    Excluding it would make an existing library unsearchable on upgrade alone.
    """
    older = add_file(db, name="indexed-before-noye-recorded-it.pdf")
    captured: dict = {}
    stub_search(monkeypatch, [hit(older)], captured)

    client.get("/search", params={"q": "x"})

    assert captured["file_ids"] == [older]


def test_an_empty_library_returns_no_results_without_searching(client, db, monkeypatch) -> None:
    """No embedding call should be spent on a query that cannot match anything."""
    called = False

    def fake(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(search_api, "search", fake)

    body = client.get("/search", params={"q": "anything"}).json()

    assert body["results"] == []
    assert body["searched_files"] == 0
    assert called is False


def test_a_library_with_only_unfinished_files_searches_nothing(client, db, monkeypatch) -> None:
    add_file(db, name="working.pdf", status=FileStatus.CHUNKING)
    stub_search(monkeypatch, [])

    body = client.get("/search", params={"q": "x"}).json()

    assert body["searched_files"] == 0


def test_no_matches_is_distinct_from_an_empty_library(client, db, monkeypatch) -> None:
    add_file(db, name="ready.pdf")
    stub_search(monkeypatch, [])

    body = client.get("/search", params={"q": "nothing like this"}).json()

    assert body["results"] == []
    assert body["searched_files"] == 1


# --- validation --------------------------------------------------------------


def test_a_missing_query_is_rejected(client) -> None:
    assert client.get("/search").status_code == 422


def test_an_empty_query_is_rejected(client) -> None:
    assert client.get("/search", params={"q": ""}).status_code == 422


def test_a_whitespace_query_is_rejected_with_a_readable_reason(client, db) -> None:
    add_file(db, name="ready.pdf")
    response = client.get("/search", params={"q": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "Enter something to search for."


def test_the_query_is_trimmed_before_searching(client, db, monkeypatch) -> None:
    add_file(db, name="ready.pdf")
    captured: dict = {}
    stub_search(monkeypatch, [], captured)

    body = client.get("/search", params={"q": "  dijkstra  "}).json()

    assert captured["query"] == "dijkstra"
    assert body["query"] == "dijkstra"


def test_the_limit_is_bounded(client, db) -> None:
    """The limit goes straight to Qdrant, so it must not be unbounded."""
    add_file(db, name="ready.pdf")
    assert client.get("/search", params={"q": "x", "limit": 0}).status_code == 422
    assert (
        client.get("/search", params={"q": "x", "limit": search_api.MAX_LIMIT + 1}).status_code
        == 422
    )


def test_the_limit_is_passed_through(client, db, monkeypatch) -> None:
    add_file(db, name="ready.pdf")
    captured: dict = {}
    stub_search(monkeypatch, [], captured)

    client.get("/search", params={"q": "x", "limit": 7})

    assert captured["limit"] == 7


def test_the_default_limit_is_used_when_absent(client, db, monkeypatch) -> None:
    add_file(db, name="ready.pdf")
    captured: dict = {}
    stub_search(monkeypatch, [], captured)

    client.get("/search", params={"q": "x"})

    assert captured["limit"] == search_api.DEFAULT_LIMIT


# --- upstream failures -------------------------------------------------------


def test_an_unreachable_embedding_model_is_a_service_error(client, db, monkeypatch) -> None:
    add_file(db, name="ready.pdf")
    stub_search(monkeypatch, EmbeddingError("connection refused"))

    response = client.get("/search", params={"q": "x"})

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "not responding" in detail
    assert "connection refused" in detail


def test_an_unsearchable_index_is_a_service_error(client, db, monkeypatch) -> None:
    add_file(db, name="ready.pdf")
    stub_search(monkeypatch, IndexingError("Qdrant is down"))

    response = client.get("/search", params={"q": "x"})

    assert response.status_code == 503
    assert "Qdrant is down" in response.json()["detail"]


def test_a_rejected_input_from_retrieval_is_a_bad_request(client, db, monkeypatch) -> None:
    add_file(db, name="ready.pdf")
    stub_search(monkeypatch, ValueError("limit must be positive, got -1"))

    response = client.get("/search", params={"q": "x"})

    assert response.status_code == 400
    assert "limit must be positive" in response.json()["detail"]


def test_search_appears_in_the_openapi_schema(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/search" in paths
    assert "get" in paths["/search"]


# --- integration -------------------------------------------------------------


def services_available() -> bool:
    settings = get_settings()
    for url in (f"{settings.ollama_base_url}/api/version", f"{settings.qdrant_url}/healthz"):
        try:
            httpx.get(url, timeout=2.0)
        except Exception:  # noqa: BLE001
            return False
    return True


requires_services = pytest.mark.skipif(
    not services_available(), reason="Ollama and Qdrant must be running"
)


@requires_services
def test_search_finds_a_real_passage_end_to_end(db, tmp_path) -> None:
    """The genuine path: index a document, then find it by meaning."""
    from app.services.indexing import delete_file_chunks
    from app.services.ingestion import ingest_file

    source = tmp_path / "graphs.md"
    source.write_text(
        "# Shortest paths\n\n"
        "Dijkstra's algorithm repeatedly selects the unvisited vertex whose "
        "distance estimate is smallest, taking it from a priority queue.\n",
        encoding="utf-8",
    )
    record = file_store.create_file(
        db,
        name="graphs.md",
        file_type=FileType.MARKDOWN,
        path=str(source),
        size=source.stat().st_size,
    )

    try:
        ingested = ingest_file(db, record.id)
        assert ingested.status is FileStatus.READY

        app.dependency_overrides[search_api.get_db] = lambda: db
        with TestClient(app) as test_client:
            body = test_client.get(
                "/search", params={"q": "how does the algorithm pick the next vertex"}
            ).json()
        app.dependency_overrides.clear()

        assert body["searched_files"] == 1
        assert body["results"], "a semantically related query should match"
        top = body["results"][0]
        assert top["file_name"] == "graphs.md"
        assert top["page_number"] is None, "Markdown has no pages"
        assert "priority queue" in top["content"]
        assert top["score"] > 0
    finally:
        delete_file_chunks(record.id)
