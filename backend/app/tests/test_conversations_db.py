"""Tests for conversation persistence.

Three behaviours here are guarantees rather than details, and have their own
tests: citations are stored and read back verbatim, a citation outlives the file
it names, and a failed answer keeps the user's question in the conversation.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.db import conversations as store
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.models.conversations import (
    TITLE_MAX_LENGTH,
    UNTITLED,
    MessageCitation,
    Role,
    derive_title,
)
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


def test_a_title_is_derived_from_the_first_question(db) -> None:
    conversation = store.create_conversation(
        db, first_question="How does Dijkstra choose the next vertex?"
    )
    assert conversation.title == "How does Dijkstra choose the next vertex?"


def test_a_long_question_is_truncated_on_a_word_boundary() -> None:
    question = (
        "How does Dijkstra's algorithm decide which unvisited vertex to take "
        "from the priority queue next?"
    )
    title = derive_title(question)
    assert len(title) <= TITLE_MAX_LENGTH + 1  # the ellipsis
    assert title.endswith("…")
    assert not title[:-1].endswith(" ")


def test_a_title_collapses_whitespace() -> None:
    assert derive_title("  how   does\n\nit work ") == "how does it work"


def test_a_conversation_with_no_question_is_untitled() -> None:
    assert derive_title("") == UNTITLED
    assert derive_title("   ") == UNTITLED


def test_an_explicit_title_wins_over_the_question(db) -> None:
    conversation = store.create_conversation(
        db, title="Graph algorithms", first_question="anything"
    )
    assert conversation.title == "Graph algorithms"


def test_renaming_trims_and_rejects_blank(db) -> None:
    conversation = store.create_conversation(db, first_question="x")
    renamed = store.rename_conversation(db, conversation.id, "  Shortest  paths  ")
    assert renamed.title == "Shortest paths"
    with pytest.raises(ValueError):
        store.rename_conversation(db, conversation.id, "   ")


def test_renaming_an_unknown_conversation_raises(db) -> None:
    with pytest.raises(store.ConversationNotFound):
        store.rename_conversation(db, "nope", "Title")


# --- ordering ----------------------------------------------------------------


def test_conversations_are_listed_by_most_recent_activity(db) -> None:
    """The sidebar should surface what was last discussed, not what started
    longest ago."""
    first = store.create_conversation(db, first_question="first")
    second = store.create_conversation(db, first_question="second")

    # Activity on the older conversation should move it to the top.
    store.add_message(db, first.id, role=Role.USER, content="more")

    listed = [c.id for c in store.list_conversations(db)]
    assert listed[0] == first.id
    assert second.id in listed


def test_messages_are_returned_in_order(db) -> None:
    conversation = store.create_conversation(db, first_question="q")
    store.add_message(db, conversation.id, role=Role.USER, content="one")
    store.add_message(db, conversation.id, role=Role.ASSISTANT, content="two")
    store.add_message(db, conversation.id, role=Role.USER, content="three")

    contents = [m.content for m in store.list_messages(db, conversation.id)]
    assert contents == ["one", "two", "three"]


def test_adding_a_message_marks_the_conversation_active(db) -> None:
    conversation = store.create_conversation(db, first_question="q")
    before = store.get_conversation(db, conversation.id).updated_at
    store.add_message(db, conversation.id, role=Role.USER, content="hello")
    assert store.get_conversation(db, conversation.id).updated_at >= before


# --- citations are stored, not recomputed ------------------------------------


def test_citations_are_read_back_exactly_as_stored(db) -> None:
    conversation = store.create_conversation(db, first_question="q")
    stored = store.add_message(
        db,
        conversation.id,
        role=Role.ASSISTANT,
        content="It takes the smallest estimate.",
        citations=[citation(), citation(file_id="file-2", file_name="notes.md", page=None,
                             chunks=(0,), score=0.42)],
    )

    read = store.get_message(db, stored.id)

    assert [c.file_name for c in read.citations] == ["Algorithms.pdf", "notes.md"]
    assert read.citations[0].page_number == 34
    assert read.citations[0].chunk_indexes == (5, 6)
    assert read.citations[0].best_score == pytest.approx(0.71)
    # Pageless sources keep no page rather than gaining a fabricated one.
    assert read.citations[1].page_number is None
    assert read.citations[1].chunk_indexes == (0,)


def test_citation_order_is_preserved(db) -> None:
    """Position is stored, so the strongest-first order survives a reload."""
    conversation = store.create_conversation(db, first_question="q")
    stored = store.add_message(
        db,
        conversation.id,
        role=Role.ASSISTANT,
        content="answer",
        citations=[
            citation(file_name="first.pdf", score=0.9),
            citation(file_name="second.pdf", score=0.5),
            citation(file_name="third.pdf", score=0.1),
        ],
    )

    names = [c.file_name for c in store.get_message(db, stored.id).citations]
    assert names == ["first.pdf", "second.pdf", "third.pdf"]


def test_a_citation_survives_its_source_file_being_deleted(db) -> None:
    """Storing only a file_id would make an old answer lose its provenance the
    moment the user tidied their library."""
    record = file_store.create_file(
        db, name="Algorithms.pdf", file_type=FileType.PDF, path="/tmp/a.pdf", size=10
    )
    conversation = store.create_conversation(db, first_question="q")
    stored = store.add_message(
        db,
        conversation.id,
        role=Role.ASSISTANT,
        content="answer",
        citations=[citation(file_id=record.id, file_name="Algorithms.pdf")],
    )

    file_store.delete_file(db, record.id)

    read = store.get_message(db, stored.id)
    assert read.citations[0].file_name == "Algorithms.pdf"
    assert read.citations[0].page_number == 34
    # The id is kept too, so the source can still be opened while it exists.
    assert read.citations[0].file_id == record.id


def test_an_answer_without_sources_has_no_citations(db) -> None:
    conversation = store.create_conversation(db, first_question="q")
    stored = store.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="I could not find anything."
    )
    read = store.get_message(db, stored.id)
    assert read.citations == []
    assert read.is_grounded is False


def test_citations_are_grouped_to_the_right_messages(db) -> None:
    conversation = store.create_conversation(db, first_question="q")
    store.add_message(db, conversation.id, role=Role.USER, content="first question")
    first = store.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="a",
        citations=[citation(file_name="one.pdf")],
    )
    store.add_message(db, conversation.id, role=Role.USER, content="second question")
    second = store.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="b",
        citations=[citation(file_name="two.pdf"), citation(file_name="three.pdf")],
    )

    by_id = {m.id: m for m in store.list_messages(db, conversation.id)}

    assert [c.file_name for c in by_id[first.id].citations] == ["one.pdf"]
    assert [c.file_name for c in by_id[second.id].citations] == ["two.pdf", "three.pdf"]
    # The user's own turns carry none.
    assert all(m.citations == [] for m in by_id.values() if m.role is Role.USER)


# --- failures ----------------------------------------------------------------


def test_a_failed_answer_keeps_the_question_and_records_why(db) -> None:
    """Losing what someone typed because a local model was down is the wrong
    trade."""
    conversation = store.create_conversation(db, first_question="How does it work?")
    store.add_message(db, conversation.id, role=Role.USER, content="How does it work?")
    store.add_message(
        db,
        conversation.id,
        role=Role.ASSISTANT,
        content="",
        error="Could not reach Ollama.",
    )

    messages = store.list_messages(db, conversation.id)

    assert messages[0].content == "How does it work?"
    assert messages[0].failed is False
    assert messages[1].failed is True
    assert messages[1].error == "Could not reach Ollama."


# --- cascades and absences ---------------------------------------------------


def test_deleting_a_conversation_removes_its_messages_and_citations(db) -> None:
    conversation = store.create_conversation(db, first_question="q")
    store.add_message(
        db, conversation.id, role=Role.ASSISTANT, content="a", citations=[citation()]
    )
    assert store.count_messages(db, conversation.id) == 1

    store.delete_conversation(db, conversation.id)

    assert store.count_messages(db) == 0
    remaining = db.execute("SELECT COUNT(*) AS n FROM message_citations").fetchone()["n"]
    assert remaining == 0


def test_deleting_an_unknown_conversation_raises(db) -> None:
    with pytest.raises(store.ConversationNotFound):
        store.delete_conversation(db, "nope")


def test_reading_an_unknown_conversation_raises(db) -> None:
    with pytest.raises(store.ConversationNotFound):
        store.read_conversation(db, "nope")


def test_getting_an_unknown_message_raises(db) -> None:
    with pytest.raises(store.MessageNotFound):
        store.get_message(db, "nope")


def test_adding_to_an_unknown_conversation_raises_a_domain_error(db) -> None:
    """Not a raw SQLite foreign-key failure."""
    with pytest.raises(store.ConversationNotFound):
        store.add_message(db, "nope", role=Role.USER, content="hello")


def test_reading_a_conversation_includes_its_messages(db) -> None:
    conversation = store.create_conversation(db, first_question="q")
    store.add_message(db, conversation.id, role=Role.USER, content="hello")

    read = store.read_conversation(db, conversation.id)

    assert [m.content for m in read.messages] == ["hello"]
    # Listing does not pay for messages it will not show.
    assert store.list_conversations(db)[0].messages == []


def test_an_empty_conversation_reads_as_empty(db) -> None:
    conversation = store.create_conversation(db, first_question="q")
    assert store.read_conversation(db, conversation.id).messages == []
