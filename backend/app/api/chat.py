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
from app.config import GenerationProvider
from app.db import conversations as conversation_store
from app.db import files as file_store
from app.db import knowledge as knowledge_store
from app.logging_config import get_logger
from app.models.conversations import Conversation, Message, MessageCitation, Role
from app.models.evidence import EvidenceSnapshot
from app.models.files import FileStatus
from app.services import knowledge_query
from app.services.conversation_context import recent_context, retrieval_question
from app.services.embeddings import EmbeddingError
from app.services.evidence import capture_citations, original_status
from app.services.generation import NO_CONTEXT_ANSWER, GenerationError, answer_question
from app.services.indexing import IndexingError
from app.services.integrity import searchable_file_ids
from app.services.retrieval import DEFAULT_LIMIT
from app.services.source_catalog import SourceError
from app.services.wiki.local import WikiError

router = APIRouter(prefix="/chat", tags=["chat"])

logger = get_logger("api.chat")

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
    evidence: EvidenceSnapshot | None = None
    original_status: str = "unknown"

    @classmethod
    def of(cls, citation: MessageCitation, db: sqlite3.Connection | None = None) -> CitationOut:
        return cls(
            file_id=citation.file_id,
            file_name=citation.file_name,
            page_number=citation.page_number,
            chunk_indexes=list(citation.chunk_indexes),
            score=citation.best_score,
            label=citation.label,
            evidence=citation.evidence,
            original_status=original_status(db, citation) if db is not None else "unknown",
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
    knowledge: dict | None = None

    @classmethod
    def of(cls, message: Message, db: sqlite3.Connection | None = None) -> MessageOut:
        return cls(
            id=message.id,
            role=message.role,
            content=message.content,
            error=message.error,
            citations=[CitationOut.of(citation, db) for citation in message.citations],
            created_at=message.created_at.isoformat(),
            knowledge=knowledge_store.read(db, message.id) if db is not None else None,
        )


class ConversationOut(BaseModel):
    """A conversation, with its messages when they were read."""

    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[MessageOut]
    source_scope: list[str] | None = None

    @classmethod
    def of(
        cls, conversation: Conversation, db: sqlite3.Connection | None = None
    ) -> ConversationOut:
        return cls(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
            messages=[MessageOut.of(message, db) for message in conversation.messages],
            source_scope=conversation.source_scope,
        )


class ConversationSummary(BaseModel):
    """A conversation in the sidebar list. No messages: they are not shown there."""

    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int

    @classmethod
    def of(cls, conversation: Conversation, message_count: int) -> ConversationSummary:
        return cls(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
            message_count=message_count,
        )


class AskRequest(BaseModel):
    """A question, optionally continuing an existing conversation."""

    question: str = Field(..., min_length=1, max_length=4000)
    #: Omit to start a new conversation, titled from this question.
    conversation_id: str | None = None
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    provider: GenerationProvider = "ollama"
    file_ids: list[str] | None = Field(default=None, max_length=200)


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


class ScopeRequest(BaseModel):
    file_ids: list[str] | None = Field(default=None, max_length=200)


@router.put("/conversations/{conversation_id}/scope", response_model=ConversationOut)
def update_scope(
    conversation_id: str, request: ScopeRequest, db: sqlite3.Connection = Depends(get_db)
) -> ConversationOut:
    try:
        conversation = conversation_store.set_source_scope(db, conversation_id, request.file_ids)
        return ConversationOut.of(conversation)
    except conversation_store.ConversationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ready_file_names(db: sqlite3.Connection) -> dict[str, str]:
    """Display names of the files a question may be answered from.

    Delegates to the integrity service rather than filtering on READY here, so chat
    and search cannot drift apart on which files are safe to use. A READY file whose
    vectors came from a superseded embedding model is excluded: mixing embedding
    spaces produces a ranking that is wrong while looking right.
    """
    return searchable_file_ids(db)


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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ask something first.")

    if request.conversation_id is None:
        conversation = conversation_store.create_conversation(db, first_question=question)
    else:
        try:
            conversation = conversation_store.get_conversation(db, request.conversation_id)
        except conversation_store.ConversationNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if "file_ids" in request.model_fields_set:
        conversation = conversation_store.set_source_scope(db, conversation.id, request.file_ids)
    scope = conversation.source_scope
    previous = conversation_store.recent_messages(db, conversation.id)

    # Written before the model is called: generation can take minutes and can
    # fail, and the user's question must survive either.
    stored_question = conversation_store.add_message(
        db, conversation.id, role=Role.USER, content=question
    )

    ready = {}
    context = None
    try:
        ready = _ready_file_names(db) if scope != [] else {}
        if scope is not None:
            ready = {file_id: name for file_id, name in ready.items() if file_id in scope}

        if not ready:
            answer = conversation_store.add_message(
                db,
                conversation.id,
                role=Role.ASSISTANT,
                content=(
                    "No files are selected for this conversation. Select a file to answer from."
                    if scope == []
                    else "None of the selected files has a compatible, ready index. "
                    "Open the library to check the selected files."
                    if scope is not None
                    else "No compatible index is available for the ready files. "
                    "Open the library to check index compatibility and rebuild when needed."
                    if any(r.status is FileStatus.READY for r in file_store.list_files(db))
                    else "There is nothing in your library to answer from yet. Add a file, or "
                    "wait for one that is still processing."
                ),
            )
            return AskResponse(
                conversation_id=conversation.id,
                conversation_title=conversation.title,
                question=MessageOut.of(stored_question),
                answer=MessageOut.of(answer, db),
                searched_files=0,
            )

        # Expanded Wiki/original context stays local. Explicit cloud requests keep
        # the existing retrieval payload and provider; no automatic switching occurs.
        if (
            request.provider == "ollama"
            and db.execute(
                "SELECT 1 FROM sources UNION SELECT 1 FROM wiki_pages LIMIT 1"
            ).fetchone()
        ):
            material_scope = (
                {"mode": "all"} if scope is None else {"mode": "chosen", "source_ids": scope}
            )
            context = knowledge_query.discover(
                db,
                retrieval_question(question, previous),
                material_scope,
                file_ids=list(ready),
                limit=request.limit,
            )
            generated = knowledge_query.answer(context, question, history=recent_context(previous))
        else:
            generated = answer_question(
                question,
                limit=request.limit,
                file_ids=list(ready),
                provider=request.provider,
                **(
                    {
                        "history": recent_context(previous),
                        "retrieval_query": retrieval_question(question, previous),
                    }
                    if previous
                    else {}
                ),
            )
    except (EmbeddingError, IndexingError, GenerationError, SourceError, WikiError) as exc:
        # Neither the question nor the answer is logged. The conversation id
        # locates the turn for anyone who needs the text, in the database
        # where the user already keeps it.
        logger.warning(
            "Answer failed conversation=%s error=%s: %s",
            conversation.id,
            type(exc).__name__,
            exc,
        )
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
    citations = capture_citations(generated.sources, ready)

    def save_answer():
        stored = conversation_store.add_message(
            db,
            conversation.id,
            role=Role.ASSISTANT,
            content=generated.text,
            citations=citations,
            knowledge=context.snapshot if context is not None else None,
        )
        return stored

    if context is not None:
        try:
            with context.session.commit_guard():
                answer = save_answer()
        except SourceError as exc:
            answer = conversation_store.add_message(
                db,
                conversation.id,
                role=Role.ASSISTANT,
                content="",
                error=str(exc),
            )
    else:
        answer = save_answer()

    return AskResponse(
        conversation_id=conversation.id,
        conversation_title=conversation.title,
        question=MessageOut.of(stored_question),
        answer=MessageOut.of(answer, db),
        searched_files=len(ready),
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(db: sqlite3.Connection = Depends(get_db)) -> list[ConversationSummary]:
    """List conversations, most recently active first."""
    return [
        ConversationSummary.of(conversation, conversation_store.count_messages(db, conversation.id))
        for conversation in conversation_store.list_conversations(db)
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def read_conversation(
    conversation_id: str, db: sqlite3.Connection = Depends(get_db)
) -> ConversationOut:
    """Read one conversation with its messages and their stored citations."""
    try:
        return ConversationOut.of(conversation_store.read_conversation(db, conversation_id), db)
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
    return ConversationOut.of(conversation_store.read_conversation(db, conversation_id), db)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, db: sqlite3.Connection = Depends(get_db)) -> None:
    """Delete a conversation and its messages.

    Only the record of the discussion goes; the documents it drew on are
    untouched, and nothing in the vector index changes.
    """
    try:
        conversation_store.delete_conversation(db, conversation_id)
    except conversation_store.ConversationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["MAX_LIMIT", "NO_CONTEXT_ANSWER", "router"]
