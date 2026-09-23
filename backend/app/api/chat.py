"""Chat API.

Joins three things that already exist: retrieval, grounded generation, and
citation mapping. This module's own work is the conversation — writing the turn
down, in the right order, with the sources that were actually used.

Two properties matter more than the happy path.

**The question is stored before the model is called.** Generation can take
minutes on local hardware and can fail outright. Writing the user's turn first
means a failure records a reason against the answer instead of losing what they
typed.

**Only READY files are searched**, the same restriction `/search` applies. A file
mid-ingestion has some of its passages indexed and not others, so answering from
it would ground an answer in a document the user has not finished adding.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.db import conversations as conversation_store
from app.db import files as file_store
from app.models.conversations import Conversation, Message, MessageCitation, Role
from app.models.files import FileStatus
from app.services.citations import build_citations
from app.services.embeddings import EmbeddingError
from app.services.generation import NO_CONTEXT_ANSWER, GenerationError, answer_question
from app.services.indexing import IndexingError
from app.services.retrieval import DEFAULT_LIMIT

router = APIRouter(prefix="/chat", tags=["chat"])

#: Most passages one answer may be grounded in.
#:
#: Bounded because every excerpt goes into the prompt, and a local model's
#: context is the scarce resource here — past a point more context makes answers
#: worse, not better, as well as slower.
MAX_LIMIT = 10


class CitationOut(BaseModel):
    """One passage that was given to the model as context for this answer.

    Precisely that, and not "a source that supports the answer". Vector search
    always returns its nearest neighbours, so a question the documents do not
    cover still retrieves passages; the model then declines — correctly — while
    these citations remain attached.

    Separating the two cases needs either a calibrated relevance threshold or a
    signal from the model, and neither exists yet: measurement so far gives 0.675
    for a covered question and 0.52 for an uncovered one against the same
    document, which is two data points, not a boundary. The plan warns against
    imposing a threshold without that evidence, so the honest move is to keep the
    data and let the surface that displays it say what it is.
    """

    file_id: str
    file_name: str
    page_number: int | None
    #: The retrieved chunks behind this citation, so the passages stay inspectable.
    chunk_indexes: list[int]
    score: float
    #: Ready-made label: "Algorithms.pdf — page 34", or just the name.
    label: str

    @classmethod
    def of(cls, citation: MessageCitation) -> "CitationOut":
        return cls(
            file_id=citation.file_id,
            file_name=citation.file_name,
            page_number=citation.page_number,
            chunk_indexes=list(citation.chunk_indexes),
            score=citation.best_score,
            label=citation.label,
        )


class MessageOut(BaseModel):
    """One turn as the API reports it."""

    id: str
    role: Role
    content: str
    #: Set when answering failed. The question is still here.
    error: str | None
    citations: list[CitationOut]
    created_at: str

    @classmethod
    def of(cls, message: Message) -> "MessageOut":
        return cls(
            id=message.id,
            role=message.role,
            content=message.content,
            error=message.error,
            citations=[CitationOut.of(citation) for citation in message.citations],
            created_at=message.created_at.isoformat(),
        )


class ConversationOut(BaseModel):
    """A conversation, with its messages when they were read."""

    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[MessageOut]

    @classmethod
    def of(cls, conversation: Conversation) -> "ConversationOut":
        return cls(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
            messages=[MessageOut.of(message) for message in conversation.messages],
        )


class ConversationSummary(BaseModel):
    """A conversation in the sidebar list. No messages: they are not shown there."""

    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int

    @classmethod
    def of(cls, conversation: Conversation, message_count: int) -> "ConversationSummary":
        return cls(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
            message_count=message_count,
        )


class AskRequest(BaseModel):
    """A question, optionally continuing an existing conversation."""

    question: str = Field(..., min_length=1)
    #: Omit to start a new conversation, titled from this question.
    conversation_id: str | None = None
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)


class AskResponse(BaseModel):
    """The turn that was just recorded."""

    conversation_id: str
    #: Present when the conversation was created by this request, so the client
    #: can add it to the sidebar without re-listing.
    conversation_title: str
    question: MessageOut
    answer: MessageOut
    #: How many sources the question could be answered from. Zero means nothing
    #: has finished indexing, which is different from finding no passage.
    searched_files: int


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1)


def _ready_file_names(db: sqlite3.Connection) -> dict[str, str]:
    """Display names of the files a question may be answered from."""
    return {
        record.id: record.name
        for record in file_store.list_files(db)
        if record.status is FileStatus.READY
    }


@router.post("", response_model=AskResponse, status_code=status.HTTP_201_CREATED)
def ask(
    request: AskRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db),
) -> AskResponse:
    """Ask a question and record the exchange.

    Creates a conversation when none is given. The answer is grounded in the
    user's own indexed documents, and its citations are stored with it rather
    than recomputed later.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Ask something first."
        )

    if request.conversation_id is None:
        conversation = conversation_store.create_conversation(db, first_question=question)
    else:
        try:
            conversation = conversation_store.get_conversation(db, request.conversation_id)
        except conversation_store.ConversationNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc

    # Written before the model is called: generation can take minutes and can
    # fail, and the user's question must survive either.
    stored_question = conversation_store.add_message(
        db, conversation.id, role=Role.USER, content=question
    )

    ready = _ready_file_names(db)

    if not ready:
        answer = conversation_store.add_message(
            db,
            conversation.id,
            role=Role.ASSISTANT,
            content=(
                "There is nothing in your library to answer from yet. Add a file, or "
                "wait for one that is still processing."
            ),
        )
        return AskResponse(
            conversation_id=conversation.id,
            conversation_title=conversation.title,
            question=MessageOut.of(stored_question),
            answer=MessageOut.of(answer),
            searched_files=0,
        )

    try:
        generated = answer_question(question, limit=request.limit, file_ids=list(ready))
    except (EmbeddingError, IndexingError, GenerationError) as exc:
        # A failure is recorded as the assistant's turn, so the conversation
        # shows what was asked and why it could not be answered.
        failed = conversation_store.add_message(
            db,
            conversation.id,
            role=Role.ASSISTANT,
            content="",
            error=str(exc),
        )
        return AskResponse(
            conversation_id=conversation.id,
            conversation_title=conversation.title,
            question=MessageOut.of(stored_question),
            answer=MessageOut.of(failed),
            searched_files=len(ready),
        )

    # Citations come from the retrieval metadata, never from the model. The file
    # name is copied in here so the citation survives that file being deleted.
    citations = [
        MessageCitation(
            file_id=citation.file_id,
            file_name=citation.file_name or ready.get(citation.file_id, citation.file_id),
            page_number=citation.page_number,
            chunk_indexes=citation.chunk_indexes,
            best_score=citation.best_score,
        )
        for citation in build_citations(generated.sources, file_names=ready)
    ]

    answer = conversation_store.add_message(
        db,
        conversation.id,
        role=Role.ASSISTANT,
        content=generated.text,
        citations=citations,
    )

    return AskResponse(
        conversation_id=conversation.id,
        conversation_title=conversation.title,
        question=MessageOut.of(stored_question),
        answer=MessageOut.of(answer),
        searched_files=len(ready),
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(db: sqlite3.Connection = Depends(get_db)) -> list[ConversationSummary]:
    """List conversations, most recently active first."""
    return [
        ConversationSummary.of(
            conversation, conversation_store.count_messages(db, conversation.id)
        )
        for conversation in conversation_store.list_conversations(db)
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def read_conversation(
    conversation_id: str, db: sqlite3.Connection = Depends(get_db)
) -> ConversationOut:
    """Read one conversation with its messages and their stored citations."""
    try:
        return ConversationOut.of(conversation_store.read_conversation(db, conversation_id))
    except conversation_store.ConversationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def rename_conversation(
    conversation_id: str,
    request: RenameRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db),
) -> ConversationOut:
    """Rename a conversation, now that the user knows what it was about."""
    try:
        conversation_store.rename_conversation(db, conversation_id, request.title)
    except conversation_store.ConversationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConversationOut.of(conversation_store.read_conversation(db, conversation_id))


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str, db: sqlite3.Connection = Depends(get_db)
) -> None:
    """Delete a conversation and its messages.

    Only the record of the discussion goes; the documents it drew on are
    untouched, and nothing in the vector index changes.
    """
    try:
        conversation_store.delete_conversation(db, conversation_id)
    except conversation_store.ConversationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router", "NO_CONTEXT_ANSWER", "MAX_LIMIT"]
