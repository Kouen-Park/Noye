"""Tests for the chat API.

Generation is stubbed in almost every test. What the route must get right is the
conversation — the order of the turns, which files may be answered from, and what
happens to the user's question when answering fails — and driving that through a
real local model would test the model instead. The integration test at the bottom
runs the genuine path when the services are up.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.config import get_settings
from app.db import conversations as conversation_store
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.main import app
from app.models.files import FileStatus, FileType
from app.services.embeddings import EmbeddingError
from app.services.generation import Answer, GenerationError
from app.services.indexing import IndexingError
from app.services.retrieval import SearchResult


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    connection = connect(tmp_path / "chat.db")
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def client(db: sqlite3.Connection) -> TestClient:
    app.dependency_overrides[chat_api.get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_ready_file(db: sqlite3.Connection, name: str = "Algorithms.pdf") -> str:
    record = file_store.create_file(
        db, name=name, file_type=FileType.PDF, path=f"/tmp/{name}", size=1024
    )
    file_store.set_status(db, record.id, FileStatus.READY)
    return record.id


def chunk(file_id: str, *, page: int | None = 34, index: int = 5, score: float = 0.71):
    return SearchResult(
        content="Dijkstra takes the smallest estimate from a priority queue.",
        file_id=file_id,
        page_number=page,
        chunk_index=index,
        score=score,
    )


def stub_answer(monkeypatch: pytest.MonkeyPatch, result, capture: dict | None = None):
    """Replace generation with a stub, optionally recording its arguments."""

    def fake(question, *, limit=None, file_ids=None, **kwargs):
        if capture is not None:
            capture.update(question=question, limit=limit, file_ids=file_ids)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(chat_api, "answer_question", fake)


# --- asking ------------------------------------------------------------------


def test_asking_creates_a_conversation_titled_from_the_question(
    client, db, monkeypatch
) -> None:
    file_id = add_ready_file(db)
    stub_answer(monkeypatch, Answer(text="It takes the smallest.", sources=[chunk(file_id)]))

    body = client.post("/chat", json={"question": "How does Dijkstra choose?"}).json()

    assert body["conversation_title"] == "How does Dijkstra choose?"
    assert body["question"]["content"] == "How does Dijkstra choose?"
    assert body["question"]["role"] == "user"
    assert body["answer"]["content"] == "It takes the smallest."
    assert body["answer"]["role"] == "assistant"


def test_the_answer_carries_citations_naming_the_real_file_and_page(
    client, db, monkeypatch
) -> None:
    file_id = add_ready_file(db, "Algorithms-lecture-07.pdf")
    stub_answer(monkeypatch, Answer(text="answer", sources=[chunk(file_id, page=34)]))

    citations = client.post("/chat", json={"question": "q"}).json()["answer"]["citations"]

    assert len(citations) == 1
    assert citations[0]["file_name"] == "Algorithms-lecture-07.pdf"
    assert citations[0]["page_number"] == 34
    assert citations[0]["label"] == "Algorithms-lecture-07.pdf — page 34"
    assert citations[0]["chunk_indexes"] == [5]


def test_a_pageless_source_is_cited_by_name_alone(client, db, monkeypatch) -> None:
    file_id = add_ready_file(db, "study-notes.md")
    stub_answer(monkeypatch, Answer(text="answer", sources=[chunk(file_id, page=None)]))

    citation = client.post("/chat", json={"question": "q"}).json()["answer"]["citations"][0]

    assert citation["page_number"] is None
    assert citation["label"] == "study-notes.md"


def test_several_chunks_on_one_page_collapse_into_one_citation(
    client, db, monkeypatch
) -> None:
    file_id = add_ready_file(db)
    stub_answer(
        monkeypatch,
        Answer(
            text="answer",
            sources=[
                chunk(file_id, page=34, index=5, score=0.8),
                chunk(file_id, page=34, index=6, score=0.6),
            ],
        ),
    )

    citations = client.post("/chat", json={"question": "q"}).json()["answer"]["citations"]

    assert len(citations) == 1
    assert citations[0]["chunk_indexes"] == [5, 6]


def test_continuing_a_conversation_appends_rather_than_starting_one(
    client, db, monkeypatch
) -> None:
    file_id = add_ready_file(db)
    stub_answer(monkeypatch, Answer(text="answer", sources=[chunk(file_id)]))

    first = client.post("/chat", json={"question": "first"}).json()
    second = client.post(
        "/chat", json={"question": "second", "conversation_id": first["conversation_id"]}
    ).json()

    assert second["conversation_id"] == first["conversation_id"]
    assert len(conversation_store.list_conversations(db)) == 1
    contents = [m.content for m in conversation_store.list_messages(db, first["conversation_id"])]
    assert contents == ["first", "answer", "second", "answer"]


def test_asking_in_an_unknown_conversation_is_404(client, db, monkeypatch) -> None:
    add_ready_file(db)
    stub_answer(monkeypatch, Answer(text="a", sources=[]))
    response = client.post("/chat", json={"question": "q", "conversation_id": "nope"})
    assert response.status_code == 404


def test_only_ready_files_can_be_answered_from(client, db, monkeypatch) -> None:
    """A file mid-ingestion has some passages indexed and not others."""
    ready = add_ready_file(db, "ready.pdf")
    working = file_store.create_file(
        db, name="working.pdf", file_type=FileType.PDF, path="/tmp/w.pdf", size=1
    )
    file_store.set_status(db, working.id, FileStatus.EMBEDDING)
    captured: dict = {}
    stub_answer(monkeypatch, Answer(text="a", sources=[chunk(ready)]), captured)

    body = client.post("/chat", json={"question": "q"}).json()

    assert captured["file_ids"] == [ready]
    assert body["searched_files"] == 1


def test_an_empty_library_answers_without_calling_the_model(client, db, monkeypatch) -> None:
    called = False

    def fake(*args, **kwargs):
        nonlocal called
        called = True
        return Answer(text="should not happen", sources=[])

    monkeypatch.setattr(chat_api, "answer_question", fake)

    body = client.post("/chat", json={"question": "q"}).json()

    assert called is False
    assert body["searched_files"] == 0
    assert "nothing in your library" in body["answer"]["content"]
    assert body["answer"]["citations"] == []
    # The question is still recorded.
    assert body["question"]["content"] == "q"


def test_an_ungrounded_answer_has_no_citations(client, db, monkeypatch) -> None:
    """Generation already refuses to call the model with no context."""
    add_ready_file(db)
    stub_answer(monkeypatch, Answer(text=chat_api.NO_CONTEXT_ANSWER, sources=[]))

    answer = client.post("/chat", json={"question": "unrelated"}).json()["answer"]

    assert answer["citations"] == []
    assert answer["error"] is None


def test_the_limit_is_bounded_and_passed_through(client, db, monkeypatch) -> None:
    add_ready_file(db)
    captured: dict = {}
    stub_answer(monkeypatch, Answer(text="a", sources=[]), captured)

    client.post("/chat", json={"question": "q", "limit": 3})
    assert captured["limit"] == 3

    assert client.post("/chat", json={"question": "q", "limit": 0}).status_code == 422
    assert (
        client.post("/chat", json={"question": "q", "limit": chat_api.MAX_LIMIT + 1}).status_code
        == 422
    )


def test_an_empty_question_is_rejected(client) -> None:
    assert client.post("/chat", json={"question": ""}).status_code == 422
    response = client.post("/chat", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "Ask something first."


def test_the_question_is_trimmed(client, db, monkeypatch) -> None:
    add_ready_file(db)
    captured: dict = {}
    stub_answer(monkeypatch, Answer(text="a", sources=[]), captured)

    body = client.post("/chat", json={"question": "  how does it work  "}).json()

    assert captured["question"] == "how does it work"
    assert body["question"]["content"] == "how does it work"


# --- failures keep the question ----------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        GenerationError("Could not reach Ollama at http://localhost:11434."),
        EmbeddingError("connection refused"),
        IndexingError("Qdrant is down"),
    ],
    ids=["generation", "embedding", "index"],
)
def test_a_failure_records_a_reason_and_keeps_the_question(
    client, db, monkeypatch, failure
) -> None:
    add_ready_file(db)
    stub_answer(monkeypatch, failure)

    response = client.post("/chat", json={"question": "How does it work?"})

    assert response.status_code == 201
    body = response.json()
    assert body["question"]["content"] == "How does it work?"
    assert body["answer"]["error"] == str(failure)
    assert body["answer"]["content"] == ""
    assert body["answer"]["citations"] == []

    # And it is durable, not just in the response.
    stored = conversation_store.list_messages(db, body["conversation_id"])
    assert [m.content for m in stored] == ["How does it work?", ""]
    assert stored[1].error == str(failure)


def test_a_failure_still_leaves_a_usable_conversation(client, db, monkeypatch) -> None:
    """The user can ask again in the same conversation once the service is back."""
    add_ready_file(db)
    stub_answer(monkeypatch, GenerationError("down"))
    first = client.post("/chat", json={"question": "first"}).json()

    stub_answer(monkeypatch, Answer(text="now it works", sources=[]))
    second = client.post(
        "/chat", json={"question": "second", "conversation_id": first["conversation_id"]}
    ).json()

    assert second["answer"]["content"] == "now it works"
    assert second["answer"]["error"] is None


# --- reading -----------------------------------------------------------------


def test_a_conversation_reads_back_with_its_citations(client, db, monkeypatch) -> None:
    """Stored, not recomputed: the same citations after a fresh read."""
    file_id = add_ready_file(db)
    stub_answer(monkeypatch, Answer(text="answer", sources=[chunk(file_id, page=12)]))
    created = client.post("/chat", json={"question": "q"}).json()

    body = client.get(f"/chat/conversations/{created['conversation_id']}").json()

    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][1]["citations"][0]["page_number"] == 12


def test_a_citation_outlives_the_file_it_names(client, db, monkeypatch) -> None:
    file_id = add_ready_file(db, "Algorithms.pdf")
    stub_answer(monkeypatch, Answer(text="answer", sources=[chunk(file_id, page=34)]))
    created = client.post("/chat", json={"question": "q"}).json()

    file_store.delete_file(db, file_id)

    body = client.get(f"/chat/conversations/{created['conversation_id']}").json()
    citation = body["messages"][1]["citations"][0]
    assert citation["file_name"] == "Algorithms.pdf"
    assert citation["label"] == "Algorithms.pdf — page 34"


def test_conversations_list_by_recent_activity_with_counts(client, db, monkeypatch) -> None:
    add_ready_file(db)
    stub_answer(monkeypatch, Answer(text="a", sources=[]))
    first = client.post("/chat", json={"question": "first"}).json()
    client.post("/chat", json={"question": "second"})
    client.post("/chat", json={"question": "again", "conversation_id": first["conversation_id"]})

    listed = client.get("/chat/conversations").json()

    assert listed[0]["id"] == first["conversation_id"]
    assert listed[0]["message_count"] == 4
    assert "messages" not in listed[0]


def test_an_empty_list_is_not_an_error(client) -> None:
    response = client.get("/chat/conversations")
    assert response.status_code == 200
    assert response.json() == []


def test_reading_an_unknown_conversation_is_404(client) -> None:
    assert client.get("/chat/conversations/nope").status_code == 404


# --- renaming and deleting ---------------------------------------------------


def test_a_conversation_can_be_renamed(client, db, monkeypatch) -> None:
    add_ready_file(db)
    stub_answer(monkeypatch, Answer(text="a", sources=[]))
    created = client.post("/chat", json={"question": "q"}).json()

    body = client.patch(
        f"/chat/conversations/{created['conversation_id']}",
        json={"title": "  Shortest  paths  "},
    ).json()

    assert body["title"] == "Shortest paths"


def test_renaming_to_blank_is_rejected(client, db, monkeypatch) -> None:
    add_ready_file(db)
    stub_answer(monkeypatch, Answer(text="a", sources=[]))
    created = client.post("/chat", json={"question": "q"}).json()

    response = client.patch(
        f"/chat/conversations/{created['conversation_id']}", json={"title": "   "}
    )

    assert response.status_code == 400


def test_renaming_an_unknown_conversation_is_404(client) -> None:
    assert client.patch("/chat/conversations/nope", json={"title": "x"}).status_code == 404


def test_deleting_a_conversation_leaves_the_documents_alone(client, db, monkeypatch) -> None:
    file_id = add_ready_file(db)
    stub_answer(monkeypatch, Answer(text="a", sources=[chunk(file_id)]))
    created = client.post("/chat", json={"question": "q"}).json()

    assert client.delete(f"/chat/conversations/{created['conversation_id']}").status_code == 204

    assert client.get("/chat/conversations").json() == []
    # The file it drew on is untouched.
    assert file_store.get_file(db, file_id).status is FileStatus.READY


def test_deleting_an_unknown_conversation_is_404(client) -> None:
    assert client.delete("/chat/conversations/nope").status_code == 404


def test_chat_routes_appear_in_the_openapi_schema(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/chat"]
    assert "get" in paths["/chat/conversations"]
    assert set(paths["/chat/conversations/{conversation_id}"]) >= {"get", "patch", "delete"}


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
def test_a_real_question_is_answered_and_cited_end_to_end(db, tmp_path) -> None:
    """The genuine path: index a document, ask about it, read the answer back."""
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
        assert ingest_file(db, record.id).status is FileStatus.READY

        app.dependency_overrides[chat_api.get_db] = lambda: db
        with TestClient(app) as test_client:
            asked = test_client.post(
                "/chat", json={"question": "How does the algorithm pick the next vertex?"}
            ).json()
            reread = test_client.get(f"/chat/conversations/{asked['conversation_id']}").json()
        app.dependency_overrides.clear()

        assert asked["searched_files"] == 1
        answer = asked["answer"]
        assert answer["error"] is None
        assert answer["content"].strip(), "the model should have said something"
        assert answer["citations"], "a grounded answer must carry its sources"
        assert answer["citations"][0]["file_name"] == "graphs.md"
        # Markdown has no pages, and none is invented.
        assert answer["citations"][0]["page_number"] is None

        # The same citations come back on a fresh read, from storage.
        assert reread["messages"][1]["citations"] == answer["citations"]
    finally:
        delete_file_chunks(record.id)
