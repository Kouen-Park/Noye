"""Bounded conversational context. Past answers never become source evidence."""

import re
from collections.abc import Sequence

from app.models.conversations import Message, Role

MAX_HISTORY_CHARS = 2400
MAX_MESSAGE_CHARS = 800
MAX_MESSAGES = 4


def recent_context(messages: Sequence[Message]) -> str:
    parts = []
    remaining = MAX_HISTORY_CHARS
    for message in reversed(messages):
        # A local-model comparison showed prior generated claims contaminating a
        # follow-up despite the warning. Keep only the user's recent questions.
        if message.role is not Role.USER or message.error or not message.content.strip():
            continue
        part = f"Previous user question (not evidence): {message.content[:MAX_MESSAGE_CHARS]}"
        if len(parts) == MAX_MESSAGES or len(part) > remaining:
            break
        parts.append(part)
        remaining -= len(part) + 2
    return "\n\n".join(reversed(parts))


def retrieval_question(question: str, messages: Sequence[Message]) -> str:
    # Include the recent user topics for anaphora without a second inference call.
    # Assistant prose is available only to generation, never indexed as evidence.
    dependent = re.search(
        r"\b(it|this|these|that|those|they|their|which|second|former|latter|both|compare)\b|"
        r"^(and|what about|how about)\b|그것|이것|그럼|두 번째|둘|이 둘|앞서|비교|차이",
        question.casefold(),
    )
    if not dependent:
        return question
    questions = [m.content[:400] for m in messages if m.role is Role.USER and not m.error][-2:]
    return "\n".join([*questions, question]) if questions else question
