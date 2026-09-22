"""Citation mapping.

Citations are computed from retrieval metadata, never asked of the language
model. That is the whole point of this module's existence as a separate step:
the provenance attached at index time flows through search into the citation
list unchanged, so a citation can be wrong only if the index is wrong — not
because a model guessed.

Several retrieved chunks often come from the same page, so they are collapsed
into one citation per (file, page) pair. A user does not want to be told
"page 34" three times.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.services.retrieval import SearchResult


@dataclass(frozen=True)
class Citation:
    """One source a user can follow: a file, and a page inside it when there is
    one.

    ``page_number`` is ``None`` for Markdown and text files, which have no
    pages. The label then names the file alone rather than inventing a page the
    user could not check against the document.

    ``file_name`` is optional because the display name lives in SQLite file
    metadata; callers pass a name map to :func:`build_citations`.

    ``chunk_indexes`` records every retrieved chunk that contributed, so the
    exact passages behind a citation stay inspectable rather than being
    flattened away.
    """

    file_id: str
    page_number: int | None
    chunk_indexes: tuple[int, ...]
    best_score: float
    file_name: str | None = None

    @property
    def label(self) -> str:
        """Human-readable citation.

        ``Algorithms.pdf — page 34`` for a paged source, ``notes.md`` for one
        without pages.
        """
        source = self.file_name or self.file_id
        if self.page_number is None:
            return source
        return f"{source} — page {self.page_number}"


def build_citations(
    results: Sequence[SearchResult],
    *,
    file_names: dict[str, str] | None = None,
) -> list[Citation]:
    """Map retrieved chunks to citations, strongest match first.

    Chunks sharing a file and page become one citation. Ordering follows the
    best score within each group, so the citation list mirrors how relevant
    each source actually was; ties break on file then page for a stable,
    deterministic result.

    ``file_names`` maps ``file_id`` to a display name; unknown ids simply keep
    ``file_name`` unset rather than raising, since a citation is still useful
    without a pretty name.
    """
    grouped: dict[tuple[str, int], list[SearchResult]] = {}
    for result in results:
        grouped.setdefault((result.file_id, result.page_number), []).append(result)

    citations = [
        Citation(
            file_id=file_id,
            page_number=page_number,
            chunk_indexes=tuple(sorted(item.chunk_index for item in items)),
            best_score=max(item.score for item in items),
            file_name=(file_names or {}).get(file_id),
        )
        for (file_id, page_number), items in grouped.items()
    ]

    # Strongest match first; file then page break ties so the result is stable.
    # A missing page sorts before numbered ones and never compares None to int.
    citations.sort(
        key=lambda citation: (
            -citation.best_score,
            citation.file_id,
            citation.page_number is not None,
            citation.page_number or 0,
        )
    )
    return citations


def format_citations(citations: Sequence[Citation]) -> str:
    """Render citations as the plain block shown under an answer.

    Returns an empty string for no citations, so an ungrounded answer is
    displayed without a stray "Sources:" heading.
    """
    if not citations:
        return ""

    lines = "\n".join(citation.label for citation in citations)
    return f"Sources:\n{lines}"
