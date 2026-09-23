"""Domain models for conversations and their messages.

Plain dataclasses, like the file models: the schema is shallow and the plan's
code-design rules ask for the simplest thing that works. Persistence lives in
:mod:`app.db.conversations`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

#: A title is derived from the first question rather than asked for, and a long
#: question makes a useless sidebar entry.
TITLE_MAX_LENGTH = 60

#: Shown for a conversation that somehow has no question to derive a title from.
UNTITLED = "New conversation"


class Role(str, Enum):
    """Who said a message.

    ``str`` mixin so the value serializes directly to JSON and stores as TEXT.
    """

    USER = "user"
    ASSISTANT = "assistant"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class MessageCitation:
    """One source behind an answer, as it was at the time of answering.

    Stored rather than recomputed. ``file_name`` is a copy, so an answer keeps
    naming what it was based on after that file is deleted; ``file_id`` is kept
    too, so the original can still be opened while it exists.

    ``page_number`` is ``None`` for formats without pages, and the label names
    the file alone rather than inventing a page.
    """

    file_id: str
    file_name: str
    page_number: int | None
    #: Every retrieved chunk that contributed, so the passages stay inspectable.
    chunk_indexes: tuple[int, ...]
    best_score: float

    @property
    def label(self) -> str:
        if self.page_number is None:
            return self.file_name
        return f"{self.file_name} — page {self.page_number}"


@dataclass
class Message:
    """One turn in a conversation.

    ``error`` is set when answering failed. The user's question is still stored
    in that case — losing what someone typed because a local model was down is
    the wrong trade — and the failure is recorded against the assistant's turn.
    """

    id: str
    conversation_id: str
    role: Role
    content: str
    error: str | None = None
    citations: list[MessageCitation] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)

    @property
    def failed(self) -> bool:
        return self.error is not None

    @property
    def is_grounded(self) -> bool:
        """Whether this answer has sources behind it."""
        return self.role is Role.ASSISTANT and bool(self.citations)


@dataclass
class Conversation:
    """A titled sequence of messages.

    ``updated_at`` moves whenever a message is added, because the sidebar is
    ordered by most recent activity rather than by when a conversation started.
    """

    id: str
    title: str
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    #: Populated when a conversation is read with its messages; empty in a list.
    messages: list[Message] = field(default_factory=list)


def derive_title(question: str) -> str:
    """Turn a first question into a sidebar title.

    Collapses whitespace and truncates on a word boundary where one is close
    enough, so a title does not end mid-word. Asking the user to name a
    conversation before they have had it is a question they cannot answer yet.
    """
    collapsed = " ".join(question.split())
    if not collapsed:
        return UNTITLED
    if len(collapsed) <= TITLE_MAX_LENGTH:
        return collapsed

    cut = collapsed[:TITLE_MAX_LENGTH]
    boundary = cut.rfind(" ")
    # Only honour a boundary in the last third; otherwise a long first word
    # would leave a stub.
    if boundary > TITLE_MAX_LENGTH * 2 // 3:
        cut = cut[:boundary]
    return f"{cut.rstrip()}…"
