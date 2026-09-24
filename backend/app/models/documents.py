"""Domain model for generated documents.

A document starts as generated Markdown and becomes the user's own the moment it
exists. Nothing here re-derives its content: the plan's requirement for this phase
is that AI-generated text always remain editable, which means the stored body is
the document rather than a cache of something reproducible.

Citations reuse :class:`app.models.conversations.MessageCitation`. They carry the
same fields and the same guarantee — a copied file name, so a citation outlives
the file it names — and a second identical type would only let the two drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.conversations import MessageCitation

#: A title is derived from the instruction when none is given, and a long
#: instruction makes a useless list entry.
TITLE_MAX_LENGTH = 60

UNTITLED = "Untitled document"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Document:
    """A Markdown document the user owns.

    ``source_conversation_id`` and ``source_message_id`` record where a generated
    document came from, but hold no foreign key: deleting the conversation must
    leave the document alone, because the document is the work and the
    conversation was scaffolding.

    ``source_instruction`` is what the person asked for, kept so they can see it
    again months later.
    """

    id: str
    title: str
    content: str
    source_conversation_id: str | None = None
    source_message_id: str | None = None
    source_instruction: str | None = None
    citations: list[MessageCitation] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @property
    def is_generated(self) -> bool:
        """Whether this document began as a generated draft rather than blank."""
        return self.source_message_id is not None

    @property
    def is_empty(self) -> bool:
        return not self.content.strip()


def derive_title(instruction: str) -> str:
    """Turn a generation instruction into a document title.

    Collapses whitespace and truncates on a word boundary where one is close
    enough. The instruction is what the person actually said they wanted, which
    makes a better title than asking them to name a document before they have
    read it.
    """
    collapsed = " ".join(instruction.split())
    if not collapsed:
        return UNTITLED
    if len(collapsed) <= TITLE_MAX_LENGTH:
        return collapsed

    cut = collapsed[:TITLE_MAX_LENGTH]
    boundary = cut.rfind(" ")
    # Only honour a boundary in the last third, or a long first word leaves a stub.
    if boundary > TITLE_MAX_LENGTH * 2 // 3:
        cut = cut[:boundary]
    return f"{cut.rstrip()}…"
