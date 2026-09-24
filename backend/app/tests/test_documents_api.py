"""Tests for the documents API.

Drafting is stubbed in almost every test: what the route must get right is the
ordering — nothing stored unless the draft succeeds — the provenance it copies, and
what it refuses to make a document from. The integration test at the bottom drafts
with the real model when the services are up.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import documents as documents_api
from app.config import get_settings
from app.db import conversations as conversation_store
from app.db import documents as document_store
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.main import app
from app.models.conversations import MessageCitation, Role
from app.models.files import FileType
from app.services.generation import GenerationError


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    connection = connect(tmp_path / "documents.db")
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def client(db: sqlite3.Connection) -> TestClient:
    app.dependency_overrides[documents_api.get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def citation(
    *, file_id: str = "file-1", file_name: str = "Algorithms.pdf", page: int | None = 34
) -> MessageCitation:
    return MessageCitation(
        file_id=file_id,
        file_name=file_name,
        page_number=page,
        chunk_indexes=(5,),
        best_score=0.7,
    )


def stored_answer(
    db: sqlite3.Connection,
    *,
    content: str = "Dijkstra takes the smallest estimate from a priority queue.",
    citations=(citation(),),
    error: str | None = None,
    role: Role = Role.ASSISTANT,
) -> tuple[str, str]:
    """A conversation with one answer in it. Returns (conversation_id, message_id)."""
    conversation = conversation_store.create_conversation(db, first_question="How?")
    message = conversation_store.add_message(
        db,
        conversation.id,
        role=role,
        content=content,
        error=error,
        citations=list(citations),
    )
    return conversation.id, message.id


def stub_draft(monkeypatch: pytest.MonkeyPatch, result, capture: dict | None = None):
    """Replace drafting with a stub, optionally recording its arguments."""

    def fake(instruction, answer, citations=(), **kwargs):
        if capture is not None:
            capture.update(instruction=instruction, answer=answer, citations=list(citations))
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(documents_api, "draft_document", fake)


# --- generating --------------------------------------------------------------


def test_generating_stores_the_draft_and_its_provenance(client, db, monkeypatch) -> None:
    conversation_id, message_id = stored_answer(db)
    stub_draft(monkeypatch, "# Revision notes\n\n- Takes the smallest estimate\n")

    response = client.post(
        "/documents/generate",
        json={"message_id": message_id, "instruction": "Turn this into revision notes"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["content"].startswith("# Revision notes")
    assert body["title"] == "Turn this into revision notes"
    assert body["source_instruction"] == "Turn this into revision notes"
    assert body["source_conversation_id"] == conversation_id
    assert body["source_message_id"] == message_id


def test_the_answers_citations_are_copied_onto_the_document(client, db, monkeypatch) -> None:
    _, message_id = stored_answer(db, citations=(citation(file_name="Algorithms.pdf"),))
    stub_draft(monkeypatch, "# Notes")

    citations = client.post(
        "/documents/generate",
        json={"message_id": message_id, "instruction": "notes"},
    ).json()["citations"]

    assert len(citations) == 1
    assert citations[0]["file_name"] == "Algorithms.pdf"
    assert citations[0]["label"] == "Algorithms.pdf — page 34"


def test_the_draft_receives_the_answer_and_its_sources(client, db, monkeypatch) -> None:
    _, message_id = stored_answer(db, content="An answer.", citations=(citation(),))
    captured: dict = {}
    stub_draft(monkeypatch, "# Notes", captured)

    client.post(
        "/documents/generate",
        json={"message_id": message_id, "instruction": "  make notes  "},
    )

    assert captured["instruction"] == "make notes"
    assert captured["answer"] == "An answer."
    assert [c.file_name for c in captured["citations"]] == ["Algorithms.pdf"]


def test_an_explicit_title_overrides_the_instruction(client, db, monkeypatch) -> None:
    _, message_id = stored_answer(db)
    stub_draft(monkeypatch, "# Notes")

    body = client.post(
        "/documents/generate",
        json={"message_id": message_id, "instruction": "notes", "title": "Week 7"},
    ).json()

    assert body["title"] == "Week 7"


def test_a_failed_draft_stores_nothing(client, db, monkeypatch) -> None:
    """A half-written document cannot be told apart from one the user kept."""
    _, message_id = stored_answer(db)
    stub_draft(monkeypatch, GenerationError("Could not reach Ollama."))

    response = client.post(
        "/documents/generate",
        json={"message_id": message_id, "instruction": "notes"},
    )

    assert response.status_code == 503
    assert "not responding" in response.json()["detail"]
    assert document_store.count_documents(db) == 0
    assert client.get("/documents").json() == []


def test_generating_from_an_unknown_message_is_404(client) -> None:
    response = client.post(
        "/documents/generate", json={"message_id": "nope", "instruction": "notes"}
    )
    assert response.status_code == 404


def test_a_question_cannot_become_a_document(client, db, monkeypatch) -> None:
    _, message_id = stored_answer(db, role=Role.USER, content="How does it work?", citations=())
    stub_draft(monkeypatch, "# Notes")

    response = client.post(
        "/documents/generate", json={"message_id": message_id, "instruction": "notes"}
    )

    assert response.status_code == 400
    assert "not from a question" in response.json()["detail"]


def test_a_failed_answer_cannot_become_a_document(client, db, monkeypatch) -> None:
    _, message_id = stored_answer(db, content="", error="Ollama was down.", citations=())
    stub_draft(monkeypatch, "# Notes")

    response = client.post(
        "/documents/generate", json={"message_id": message_id, "instruction": "notes"}
    )

    assert response.status_code == 400
    assert "nothing to make a document from" in response.json()["detail"]


def test_an_empty_instruction_is_rejected(client, db) -> None:
    _, message_id = stored_answer(db)
    assert (
        client.post(
            "/documents/generate", json={"message_id": message_id, "instruction": ""}
        ).status_code
        == 422
    )
    response = client.post(
        "/documents/generate", json={"message_id": message_id, "instruction": "   "}
    )
    assert response.status_code == 400


def test_a_document_survives_its_conversation_being_deleted(client, db, monkeypatch) -> None:
    conversation_id, message_id = stored_answer(db)
    stub_draft(monkeypatch, "# Notes")
    document = client.post(
        "/documents/generate", json={"message_id": message_id, "instruction": "notes"}
    ).json()

    conversation_store.delete_conversation(db, conversation_id)

    body = client.get(f"/documents/{document['id']}").json()
    assert body["content"] == "# Notes"
    # The id is still reported, pointing at a conversation that is gone.
    assert body["source_conversation_id"] == conversation_id


def test_a_citation_outlives_the_file_it_names(client, db, monkeypatch) -> None:
    record = file_store.create_file(
        db, name="Algorithms.pdf", file_type=FileType.PDF, path="/tmp/a.pdf", size=10
    )
    _, message_id = stored_answer(db, citations=(citation(file_id=record.id),))
    stub_draft(monkeypatch, "# Notes")
    document = client.post(
        "/documents/generate", json={"message_id": message_id, "instruction": "notes"}
    ).json()

    file_store.delete_file(db, record.id)

    citations = client.get(f"/documents/{document['id']}").json()["citations"]
    assert citations[0]["file_name"] == "Algorithms.pdf"


# --- creating, editing, deleting ---------------------------------------------


def test_a_blank_document_can_be_created(client) -> None:
    body = client.post("/documents", json={"title": "Scratch"}).json()
    assert body["title"] == "Scratch"
    assert body["content"] == ""
    assert body["source_message_id"] is None


def test_a_created_document_can_hold_pasted_text(client) -> None:
    body = client.post("/documents", json={"title": "Pasted", "content": "# Mine"}).json()
    assert body["content"] == "# Mine"


def test_a_blank_title_is_rejected(client) -> None:
    assert client.post("/documents", json={"title": ""}).status_code == 422
    assert client.post("/documents", json={"title": "   "}).status_code == 400


def test_an_edit_is_what_persists(client, db, monkeypatch) -> None:
    """Nothing regenerates over what the user wrote."""
    _, message_id = stored_answer(db)
    stub_draft(monkeypatch, "# Generated")
    document = client.post(
        "/documents/generate", json={"message_id": message_id, "instruction": "notes"}
    ).json()

    client.patch(f"/documents/{document['id']}", json={"content": "# Rewritten by hand"})

    assert client.get(f"/documents/{document['id']}").json()["content"] == "# Rewritten by hand"


def test_editing_keeps_the_citations(client, db, monkeypatch) -> None:
    _, message_id = stored_answer(db)
    stub_draft(monkeypatch, "# Generated")
    document = client.post(
        "/documents/generate", json={"message_id": message_id, "instruction": "notes"}
    ).json()

    client.patch(f"/documents/{document['id']}", json={"content": "changed"})

    assert len(client.get(f"/documents/{document['id']}").json()["citations"]) == 1


def test_a_document_can_be_renamed(client) -> None:
    document = client.post("/documents", json={"title": "Old"}).json()
    body = client.patch(f"/documents/{document['id']}", json={"title": "  New  name  "}).json()
    assert body["title"] == "New name"


def test_renaming_to_blank_is_rejected(client) -> None:
    document = client.post("/documents", json={"title": "Keep"}).json()
    assert (
        client.patch(f"/documents/{document['id']}", json={"title": "   "}).status_code == 400
    )


def test_content_can_be_emptied(client) -> None:
    """An empty body is a real edit, not an omitted field."""
    document = client.post("/documents", json={"title": "T", "content": "# Body"}).json()
    body = client.patch(f"/documents/{document['id']}", json={"content": ""}).json()
    assert body["content"] == ""


def test_editing_an_unknown_document_is_404(client) -> None:
    assert client.patch("/documents/nope", json={"content": "x"}).status_code == 404


def test_documents_list_by_most_recently_edited_without_their_bodies(client) -> None:
    first = client.post("/documents", json={"title": "First", "content": "a" * 300}).json()
    client.post("/documents", json={"title": "Second"})
    client.patch(f"/documents/{first['id']}", json={"content": "edited"})

    listed = client.get("/documents").json()

    assert listed[0]["title"] == "First"
    assert "content" not in listed[0]
    assert len(listed[0]["excerpt"]) <= 160


def test_the_list_says_which_documents_were_generated(client, db, monkeypatch) -> None:
    _, message_id = stored_answer(db)
    stub_draft(monkeypatch, "# Generated")
    client.post("/documents/generate", json={"message_id": message_id, "instruction": "notes"})
    client.post("/documents", json={"title": "Written by hand"})

    flags = {d["title"]: d["is_generated"] for d in client.get("/documents").json()}

    assert flags["notes"] is True
    assert flags["Written by hand"] is False


def test_an_empty_list_is_not_an_error(client) -> None:
    assert client.get("/documents").json() == []


def test_reading_an_unknown_document_is_404(client) -> None:
    assert client.get("/documents/nope").status_code == 404


def test_deleting_a_document(client) -> None:
    document = client.post("/documents", json={"title": "Drop"}).json()
    assert client.delete(f"/documents/{document['id']}").status_code == 204
    assert client.get("/documents").json() == []


def test_deleting_an_unknown_document_is_404(client) -> None:
    assert client.delete("/documents/nope").status_code == 404


# --- markdown export ---------------------------------------------------------


def test_markdown_export_is_exactly_the_stored_body(client) -> None:
    """An export that differed from the editor would be a lossy copy of the
    user's work."""
    body = "# Notes\n\n- one\n- two\n"
    document = client.post("/documents", json={"title": "Notes", "content": body}).json()

    response = client.get(f"/documents/{document['id']}/export.md")

    assert response.status_code == 200
    assert response.text == body
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]


def test_the_export_is_named_after_the_document(client) -> None:
    document = client.post("/documents", json={"title": "Week 7 notes"}).json()
    disposition = client.get(f"/documents/{document['id']}/export.md").headers[
        "content-disposition"
    ]
    assert "Week 7 notes.md" in unquote(disposition)


def test_a_non_ascii_title_survives_the_export_filename(client) -> None:
    document = client.post("/documents", json={"title": "최단 경로"}).json()
    disposition = client.get(f"/documents/{document['id']}/export.md").headers[
        "content-disposition"
    ]
    assert "최단 경로.md" in unquote(disposition)


def test_a_title_cannot_steer_where_the_download_lands(client) -> None:
    """Path separators are dropped rather than escaped."""
    document = client.post("/documents", json={"title": "../../etc/passwd"}).json()
    disposition = client.get(f"/documents/{document['id']}/export.md").headers[
        "content-disposition"
    ]
    assert "/" not in unquote(disposition).split("filename*=UTF-8''")[1]


def test_exporting_an_unknown_document_is_404(client) -> None:
    assert client.get("/documents/nope/export.md").status_code == 404


def test_document_routes_appear_in_the_openapi_schema(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths["/documents"]) >= {"get", "post"}
    assert "post" in paths["/documents/generate"]
    assert set(paths["/documents/{document_id}"]) >= {"get", "patch", "delete"}
    assert "get" in paths["/documents/{document_id}/export.md"]


# --- integration -------------------------------------------------------------


def services_available() -> bool:
    settings = get_settings()
    try:
        httpx.get(f"{settings.ollama_base_url}/api/version", timeout=2.0)
    except Exception:  # noqa: BLE001
        return False
    return True


requires_ollama = pytest.mark.skipif(
    not services_available(), reason="Ollama must be running"
)


@requires_ollama
def test_a_real_draft_is_markdown_and_editable(db) -> None:
    """The genuine path: draft from an answer with the real model, then edit it."""
    _, message_id = stored_answer(
        db,
        content=(
            "Dijkstra's algorithm repeatedly selects the unvisited vertex whose distance "
            "estimate is smallest, taking it from a priority queue. Negative edge weights "
            "break its correctness guarantee."
        ),
        citations=(citation(file_name="Algorithms.pdf"),),
    )

    app.dependency_overrides[documents_api.get_db] = lambda: db
    with TestClient(app) as test_client:
        created = test_client.post(
            "/documents/generate",
            json={
                "message_id": message_id,
                "instruction": "Turn this into short revision notes with a heading",
            },
        )
        assert created.status_code == 201, created.text
        document = created.json()

        assert document["content"].strip(), "the model should have written something"
        # The prompt asks for Markdown; a heading or a list is the signal.
        assert any(
            marker in document["content"] for marker in ("#", "- ", "* ", "1.")
        ), document["content"][:200]
        # The model is told not to write its own source list.
        assert "Sources:" not in document["content"]
        # Provenance came from the answer, not from the model.
        assert document["citations"][0]["file_name"] == "Algorithms.pdf"

        edited = test_client.patch(
            f"/documents/{document['id']}", json={"content": "# Mine now"}
        ).json()
        assert edited["content"] == "# Mine now"
        assert len(edited["citations"]) == 1

    app.dependency_overrides.clear()
