"""Documents API.

Two kinds of route. The CRUD ones are thin over :mod:`app.db.documents`. The
generate route is the interesting one: it reads a stored answer, drafts Markdown
from it, and saves the result as a document the user then owns.

The ordering there matters. Drafting can take minutes and can fail, and a failure
must leave **nothing** behind — a half-written document in the list is worse than
no document, because the user cannot tell it apart from one they meant to keep. So
the document is created only after the draft succeeds, which is the opposite of
what chat does with a question, and for the opposite reason: a question is the
user's own words and must survive, while a draft is the model's and is
reproducible.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.db import conversations as conversation_store
from app.db import documents as document_store
from app.logging_config import get_logger
from app.models.conversations import Role
from app.models.documents import Document
from app.services.documents import draft_document
from app.services.generation import GenerationError

router = APIRouter(prefix="/documents", tags=["documents"])

logger = get_logger("api.documents")


class DocumentCitationOut(BaseModel):
    """A source the document's first draft was built from, as it was then."""

    file_id: str
    file_name: str
    page_number: int | None
    chunk_indexes: list[int]
    score: float
    label: str


class DocumentOut(BaseModel):
    """A document as the API reports it."""

    id: str
    title: str
    content: str
    #: Where a generated document came from. These ids may point at a conversation
    #: that has since been deleted — a document outlives its scaffolding.
    source_conversation_id: str | None
    source_message_id: str | None
    source_instruction: str | None
    citations: list[DocumentCitationOut]
    created_at: str
    updated_at: str

    @classmethod
    def of(cls, document: Document) -> DocumentOut:
        return cls(
            id=document.id,
            title=document.title,
            content=document.content,
            source_conversation_id=document.source_conversation_id,
            source_message_id=document.source_message_id,
            source_instruction=document.source_instruction,
            citations=[
                DocumentCitationOut(
                    file_id=citation.file_id,
                    file_name=citation.file_name,
                    page_number=citation.page_number,
                    chunk_indexes=list(citation.chunk_indexes),
                    score=citation.best_score,
                    label=citation.label,
                )
                for citation in document.citations
            ],
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
        )


class DocumentSummary(BaseModel):
    """A document in the list. No content: the list shows titles and dates."""

    id: str
    title: str
    #: Enough to show a line of context without sending the whole body.
    excerpt: str
    is_generated: bool
    created_at: str
    updated_at: str

    @classmethod
    def of(cls, document: Document) -> DocumentSummary:
        collapsed = " ".join(document.content.split())
        return cls(
            id=document.id,
            title=document.title,
            excerpt=collapsed[:160],
            is_generated=document.is_generated,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
        )


class CreateRequest(BaseModel):
    """A blank or pasted document."""

    title: str = Field(..., min_length=1)
    content: str = ""


class UpdateRequest(BaseModel):
    """An edit. Omitted fields are left alone; an empty content is a real value."""

    title: str | None = None
    content: str | None = None


class GenerateRequest(BaseModel):
    """Draft a document from a stored answer."""

    message_id: str = Field(..., min_length=1)
    #: What the person wants made of it: "turn this into revision notes".
    instruction: str = Field(..., min_length=1)
    #: Overrides the title derived from the instruction.
    title: str | None = None


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    request: CreateRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db),
) -> DocumentOut:
    """Create a document from nothing, or from text the user already has."""
    title = " ".join(request.title.split())
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Give the document a name."
        )
    return DocumentOut.of(
        document_store.create_document(db, content=request.content, title=title)
    )


@router.post("/generate", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def generate_document(
    request: GenerateRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db),
) -> DocumentOut:
    """Draft a document from an answer, and keep it.

    The answer's citations are copied onto the document, so it carries the same
    provenance the answer did — and keeps it after those files are deleted.

    Nothing is stored unless the draft succeeds: a half-written document cannot be
    told apart from one the user meant to keep.
    """
    instruction = request.instruction.strip()
    if not instruction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Say what you want made of this answer.",
        )

    try:
        message = conversation_store.get_message(db, request.message_id)
    except conversation_store.MessageNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if message.role is not Role.ASSISTANT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Documents are made from an answer, not from a question.",
        )

    if message.failed or not message.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That answer is empty, so there is nothing to make a document from.",
        )

    try:
        content = draft_document(instruction, message.content, message.citations)
    except GenerationError as exc:
        # The instruction and the draft are the user's; only the source
        # message id and the failure go in.
        logger.warning(
            "Document drafting failed message=%s error=%s: %s",
            request.message_id,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Could not draft the document. The local model that writes it is not "
                f"responding: {exc}"
            ),
        ) from exc

    return DocumentOut.of(
        document_store.create_document(
            db,
            content=content,
            title=request.title,
            instruction=instruction,
            source_conversation_id=message.conversation_id,
            source_message_id=message.id,
            citations=message.citations,
        )
    )


@router.get("", response_model=list[DocumentSummary])
def list_documents(db: sqlite3.Connection = Depends(get_db)) -> list[DocumentSummary]:
    """List documents, most recently edited first."""
    return [DocumentSummary.of(document) for document in document_store.list_documents(db)]


@router.get("/{document_id}", response_model=DocumentOut)
def read_document(
    document_id: str, db: sqlite3.Connection = Depends(get_db)
) -> DocumentOut:
    """Read one document with its citations."""
    try:
        return DocumentOut.of(document_store.get_document(db, document_id))
    except document_store.DocumentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: str,
    request: UpdateRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db),
) -> DocumentOut:
    """Save an edit.

    What is saved is what the user wrote. There is no path here that regenerates
    content, because AI-generated text must stay theirs once they have touched it.
    """
    try:
        return DocumentOut.of(
            document_store.update_document(
                db, document_id, title=request.title, content=request.content
            )
        )
    except document_store.DocumentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{document_id}/export.md")
def export_markdown(
    document_id: str, db: sqlite3.Connection = Depends(get_db)
) -> Response:
    """Download the document as a `.md` file.

    Exactly the stored body, with nothing added: an export that differed from the
    editor would make the file a lossy copy of the user's work.
    """
    try:
        document = document_store.get_document(db, document_id)
    except document_store.DocumentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return Response(
        content=document.content,
        media_type="text/markdown; charset=utf-8",
        headers={
            # RFC 5987 form, so a non-ASCII title survives the round trip.
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{_filename_for(document.title)}"
            )
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: sqlite3.Connection = Depends(get_db)) -> None:
    """Delete a document and its citations. Files and conversations are untouched."""
    try:
        document_store.delete_document(db, document_id)
    except document_store.DocumentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _filename_for(title: str) -> str:
    """Percent-encode a title into a `.md` filename.

    Path separators and control characters are dropped rather than escaped: a
    title is display text, and nothing in it should be able to steer where a
    download lands.
    """
    from urllib.parse import quote

    cleaned = "".join(
        character for character in title if character.isprintable() and character not in '/\\:'
    ).strip()
    return quote(f"{cleaned or 'document'}.md")
