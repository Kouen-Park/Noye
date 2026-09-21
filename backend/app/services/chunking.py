"""Split extracted pages into chunks that keep their provenance.

A chunk is the unit Noye embeds, stores, retrieves, and cites, so each one
carries enough metadata to point back at exactly where it came from:

    file_id + page_number + chunk_index

Chunks never span two pages. That is the central constraint here: a chunk
covering the end of page 3 and the start of page 4 could not be cited as
either page, and page-level citation is a core product requirement. The cost
is that a sentence straddling a page break is divided between two chunks,
which is an acceptable trade for unambiguous provenance.

Chunking is deliberately simple — a size window with overlap, snapped to a
nearby text boundary. The plan calls for measuring retrieval quality before
reaching for semantic chunking.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.extraction import ExtractedPage

#: Target chunk size in characters. The embedding model (embeddinggemma) has a
#: 2048-token context and silently truncates beyond it, which would drop the
#: tail of an oversized chunk from the index without any error. 1000
#: characters stays well inside that limit even for Korean text, which uses
#: far more tokens per character than English.
DEFAULT_CHUNK_SIZE = 1000

#: Characters of the previous chunk repeated at the start of the next, so a
#: passage split across a boundary is still retrievable from both sides.
DEFAULT_CHUNK_OVERLAP = 150

#: Break points preferred when snapping a chunk boundary, strongest first.
#: The full-width marks matter for CJK sources, where sentences end without a
#: following space.
_BOUNDARIES = ("\n\n", "\n", ". ", "? ", "! ", "。", "？", "！", " ")

#: A boundary is only used if it falls in the last part of the window, so
#: snapping shortens a chunk a little rather than halving it.
_MIN_FILL = 0.6


@dataclass(frozen=True)
class Chunk:
    """One embeddable piece of a source file.

    ``chunk_index`` is 0-based and counts across the whole file in reading
    order, not per page, so it identifies a chunk within the file on its own.
    Page-local ordering is still recoverable by grouping on ``page_number``.
    """

    file_id: str
    page_number: int
    chunk_index: int
    content: str


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    file_id: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Turn extracted pages into chunks, preserving page provenance.

    Pages are processed in order and each page is split independently, so
    ``chunk_index`` increases monotonically across the returned list and every
    chunk's ``page_number`` is the page its text actually came from.

    Pages with no extractable text produce no chunks — there is nothing to
    embed — but they do not disturb the page numbers of later chunks.

    Raises:
        ValueError: ``chunk_size`` is not positive, or ``overlap`` is negative
            or not smaller than ``chunk_size`` (which could not make progress).
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    if overlap < 0:
        raise ValueError(f"overlap must not be negative, got {overlap}")
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be smaller than chunk_size ({chunk_size})"
        )

    chunks: list[Chunk] = []
    chunk_index = 0

    for page in pages:
        for content in _split_text(page.content, chunk_size, overlap):
            chunks.append(
                Chunk(
                    file_id=file_id,
                    page_number=page.page_number,
                    chunk_index=chunk_index,
                    content=content,
                )
            )
            chunk_index += 1

    return chunks


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split one page's text into overlapping pieces, longest-first windows."""
    pieces: list[str] = []
    length = len(text)
    start = 0

    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            end = _snap_to_boundary(text, start, end)

        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)

        if end >= length:
            break
        # max() guarantees forward progress even if a boundary snapped back
        # into the overlap region.
        start = max(end - overlap, start + 1)

    return pieces


def _snap_to_boundary(text: str, start: int, end: int) -> int:
    """Move ``end`` back to the nearest sensible break, if one is close enough.

    Falls back to the hard cut at ``end`` when the window holds no boundary in
    its final stretch, which is what happens with unbroken text such as a long
    table row or a URL.
    """
    window = text[start:end]
    floor = int(len(window) * _MIN_FILL)

    for boundary in _BOUNDARIES:
        found = window.rfind(boundary)
        if found >= floor:
            return start + found + len(boundary)

    return end
