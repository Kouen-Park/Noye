"""Tests for document persistence.

Three behaviours are the point of this layer rather than details of it: an edit
becomes the document, a document outlives the conversation it was generated from,
and a citation outlives the file it names.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.db import conversations as conversation_store
from app.db import documents as store
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.models.conversations import MessageCitation, Role
from app.models.documents import TITLE_MAX_LENGTH, UNTITLED, derive_title
from app.models.files import FileType


@pytest.fixture
def db() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_schema(connection)
    yield connection
    connection.close()


def citation(
    *,
    file_id: str = "file-1",
    file_name: str = "Algorithms.pdf",
    page: int | None = 34,
    chunks: tuple[int, ...] = (5, 6),
    score: float = 0.71,
) -> MessageCitation:
    return MessageCitation(
        file_id=file_id,
        file_name=file_name,
        page_number=page,
        chunk_indexes=chunks,
        best_score=score,
    )


# --- titles ------------------------------------------------------------------


def test_a_title_comes_from_the_instruction(db) -> None:
    document = store.create_document(
        db, content="# Notes", instruction="Turn this into exam revision notes"
    )
    assert document.title == "Turn this into exam revision notes"


def test_an_explicit_title_wins(db) -> None:
    document = store.create_document(
        db, content="x", title="Revision notes", instruction="something else"
    )
    assert document.title == "Revision notes"


def test_a_long_instruction_is_truncated_on_a_word_boundary() -> None:
    title = derive_title(
        "Turn this explanation into a set of exam revision notes with worked examples"
    )
    assert len(title) <= TITLE_MAX_LENGTH + 1  # the ellipsis
    assert title.endswith("…")
    assert not title[:-1].endswith(" ")


def test_a_document_with_no_instruction_is_untitled(db) -> None:
    assert derive_title("") == UNTITLED
    assert store.create_document(db, content="x").title == UNTITLED


def test_renaming_trims_and_rejects_blank(db) -> None:
    document = store.create_document(db, content="x", instruction="i")
    renamed = store.update_document(db, document.id, title="  Shortest  paths  ")
    assert renamed.title == "Shortest paths"
    with pytest.raises(ValueError):
        store.update_document(db, document.id, title="   ")


# --- edits are the document --------------------------------------------------


def test_an_edit_replaces_the_generated_content(db) -> None:
    """Nothing regenerates behind the user's back."""
    document = store.create_document(
        db, content="# Generated draft", instruction="make notes"
    )

    edited = store.update_document(db, document.id, content="# My own version\n\nRewritten.")

    assert edited.content == "# My own version\n\nRewritten."
    assert store.get_document(db, document.id).content == "# My own version\n\nRewritten."


def test_content_can_be_cleared(db) -> None:
    """An empty body is a real value, not 'leave alone'."""
    document = store.create_document(db, content="# Draft", instruction="i")
    cleared = store.update_document(db, document.id, content="")
    assert cleared.content == ""
    assert cleared.is_empty is True


def test_updating_only_the_title_leaves_the_content(db) -> None:
    document = store.create_document(db, content="# Body", instruction="i")
    updated = store.update_document(db, document.id, title="New title")
    assert updated.content == "# Body"


def test_updating_only_the_content_leaves_the_title(db) -> None:
    document = store.create_document(db, content="a", title="Keep me")
    updated = store.update_document(db, document.id, content="b")
    assert updated.title == "Keep me"


def test_an_update_with_nothing_to_change_is_harmless(db) -> None:
    document = store.create_document(db, content="a", title="T")
    unchanged = store.update_document(db, document.id)
    assert unchanged.title == "T"
    assert unchanged.content == "a"


def test_an_edit_moves_the_document_up_the_list(db) -> None:
    first = store.create_document(db, content="a", title="first")
    store.create_document(db, content="b", title="second")

    store.update_document(db, first.id, content="edited")

    assert [d.title for d in store.list_documents(db)][0] == "first"


# --- provenance --------------------------------------------------------------


def test_a_generated_document_records_where_it_came_from(db) -> None:
    conversation = conversation_store.create_conversation(db, first_question="q")
    answer = conversation_store.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="an answer"
    )

    document = store.create_document(
        db,
        content="# Notes",
        instruction="make notes",
        source_conversation_id=conversation.id,
        source_message_id=answer.id,
    )

    assert document.is_generated is True
    assert document.source_conversation_id == conversation.id
    assert document.source_message_id == answer.id
    assert document.source_instruction == "make notes"


def test_a_blank_document_is_not_generated(db) -> None:
    assert store.create_document(db, content="", title="Blank").is_generated is False


def test_a_document_outlives_the_conversation_it_came_from(db) -> None:
    """The document is the user's work; the conversation was scaffolding. A
    foreign key here would delete their writing when they tidied up."""
    conversation = conversation_store.create_conversation(db, first_question="q")
    answer = conversation_store.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="an answer"
    )
    document = store.create_document(
        db,
        content="# Notes",
        instruction="make notes",
        source_conversation_id=conversation.id,
        source_message_id=answer.id,
    )

    conversation_store.delete_conversation(db, conversation.id)

    survived = store.get_document(db, document.id)
    assert survived.content == "# Notes"
    # The ids are returned as stored, even though they now point at nothing.
    assert survived.source_conversation_id == conversation.id


# --- citations ---------------------------------------------------------------


def test_citations_are_read_back_exactly_as_stored(db) -> None:
    document = store.create_document(
        db,
        content="# Notes",
        instruction="i",
        citations=[
            citation(),
            citation(file_id="f2", file_name="notes.md", page=None, chunks=(0,), score=0.4),
        ],
    )

    read = store.get_document(db, document.id)

    assert [c.file_name for c in read.citations] == ["Algorithms.pdf", "notes.md"]
    assert read.citations[0].page_number == 34
    assert read.citations[0].chunk_indexes == (5, 6)
    assert read.citations[1].page_number is None
    assert read.citations[0].label == "Algorithms.pdf — page 34"


def test_a_citation_outlives_the_file_it_names(db) -> None:
    record = file_store.create_file(
        db, name="Algorithms.pdf", file_type=FileType.PDF, path="/tmp/a.pdf", size=10
    )
    document = store.create_document(
        db,
        content="# Notes",
        instruction="i",
        citations=[citation(file_id=record.id, file_name="Algorithms.pdf")],
    )

    file_store.delete_file(db, record.id)

    read = store.get_document(db, document.id)
    assert read.citations[0].file_name == "Algorithms.pdf"
    assert read.citations[0].page_number == 34


def test_editing_a_document_leaves_its_citations_alone(db) -> None:
    document = store.create_document(
        db, content="# Draft", instruction="i", citations=[citation()]
    )

    store.update_document(db, document.id, content="# Rewritten by hand")

    assert len(store.get_document(db, document.id).citations) == 1


def test_a_document_list_does_not_pay_for_citations(db) -> None:
    store.create_document(db, content="x", instruction="i", citations=[citation()])
    assert store.list_documents(db)[0].citations == []


# --- absence and cascade -----------------------------------------------------


def test_deleting_a_document_removes_its_citations(db) -> None:
    document = store.create_document(
        db, content="x", instruction="i", citations=[citation()]
    )

    store.delete_document(db, document.id)

    assert store.count_documents(db) == 0
    left = db.execute("SELECT COUNT(*) AS n FROM document_citations").fetchone()["n"]
    assert left == 0


def test_deleting_a_document_leaves_the_others(db) -> None:
    keep = store.create_document(db, content="keep", title="Keep")
    drop = store.create_document(db, content="drop", title="Drop")

    store.delete_document(db, drop.id)

    assert [d.id for d in store.list_documents(db)] == [keep.id]


def test_reading_an_unknown_document_raises(db) -> None:
    with pytest.raises(store.DocumentNotFound):
        store.get_document(db, "nope")


def test_updating_an_unknown_document_raises(db) -> None:
    with pytest.raises(store.DocumentNotFound):
        store.update_document(db, "nope", content="x")


def test_deleting_an_unknown_document_raises(db) -> None:
    with pytest.raises(store.DocumentNotFound):
        store.delete_document(db, "nope")


def test_an_empty_library_of_documents_lists_as_empty(db) -> None:
    assert store.list_documents(db) == []
    assert store.count_documents(db) == 0
