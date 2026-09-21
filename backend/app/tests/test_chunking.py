"""Tests for chunking.

These tests take ``ExtractedPage`` objects directly, so unlike the extraction
tests they can use Korean text — no PDF font rendering is involved.
"""

from __future__ import annotations

import pytest

from app.services.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    Chunk,
    chunk_pages,
)
from app.services.extraction import ExtractedPage

FILE_ID = "file-123"


def page(number: int, content: str) -> ExtractedPage:
    return ExtractedPage(page_number=number, content=content)


def sentences(count: int, marker: str = "Sentence") -> str:
    """Build prose long enough to need splitting, with findable landmarks."""
    return " ".join(f"{marker} number {index} carries some filler words." for index in range(count))


def test_short_page_becomes_one_chunk() -> None:
    chunks = chunk_pages([page(1, "A single short paragraph.")], file_id=FILE_ID)

    assert chunks == [
        Chunk(
            file_id=FILE_ID,
            page_number=1,
            chunk_index=0,
            content="A single short paragraph.",
        )
    ]


def test_long_page_splits_into_several_chunks() -> None:
    chunks = chunk_pages([page(1, sentences(200))], file_id=FILE_ID)

    assert len(chunks) > 1


def test_no_chunk_exceeds_the_chunk_size() -> None:
    chunks = chunk_pages([page(1, sentences(300))], file_id=FILE_ID)

    for chunk in chunks:
        assert len(chunk.content) <= DEFAULT_CHUNK_SIZE


def test_chunk_index_counts_across_the_whole_file() -> None:
    chunks = chunk_pages(
        [page(1, sentences(60)), page(2, sentences(60)), page(3, sentences(60))],
        file_id=FILE_ID,
    )

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_every_chunk_keeps_the_page_it_came_from() -> None:
    first = "Page one discusses Dijkstra and nothing else. " + sentences(40, "Alpha")
    second = "Page two discusses Bellman-Ford and nothing else. " + sentences(40, "Beta")

    chunks = chunk_pages([page(1, first), page(2, second)], file_id=FILE_ID)

    for chunk in chunks:
        if "Alpha" in chunk.content or "Dijkstra" in chunk.content:
            assert chunk.page_number == 1
        if "Beta" in chunk.content or "Bellman-Ford" in chunk.content:
            assert chunk.page_number == 2


def test_no_chunk_mixes_text_from_two_pages() -> None:
    chunks = chunk_pages(
        [page(1, sentences(50, "Alpha")), page(2, sentences(50, "Beta"))],
        file_id=FILE_ID,
    )

    for chunk in chunks:
        assert not ("Alpha" in chunk.content and "Beta" in chunk.content)


def test_page_numbers_appear_in_reading_order() -> None:
    chunks = chunk_pages(
        [page(1, sentences(40)), page(2, sentences(40)), page(3, sentences(40))],
        file_id=FILE_ID,
    )

    page_numbers = [chunk.page_number for chunk in chunks]
    assert page_numbers == sorted(page_numbers)
    assert set(page_numbers) == {1, 2, 3}


def test_consecutive_chunks_advance_without_gaps() -> None:
    text = sentences(200)
    chunks = chunk_pages([page(1, text)], file_id=FILE_ID, chunk_size=400, overlap=100)

    assert len(chunks) > 2
    # Every chunk must appear in the source, later than the one before it, and
    # start no further along than where the previous chunk ended — otherwise
    # text between them would be missing from the index entirely.
    previous_start = -1
    previous_end = 0
    for chunk in chunks:
        start = text.find(chunk.content, previous_start + 1)
        assert start != -1, "chunk content is not a verbatim slice of the page"
        assert start > previous_start
        assert start <= previous_end
        previous_start = start
        previous_end = start + len(chunk.content)

    assert previous_end == len(text.rstrip())


def test_overlap_repeats_real_text_from_the_previous_chunk() -> None:
    text = sentences(200)
    chunks = chunk_pages([page(1, text)], file_id=FILE_ID, chunk_size=500, overlap=120)

    first, second = chunks[0], chunks[1]
    # Some suffix of the first chunk must be a prefix of the second.
    assert any(
        second.content.startswith(first.content[-length:])
        for length in range(20, min(len(first.content), 120) + 1)
    )


def test_zero_overlap_is_allowed() -> None:
    chunks = chunk_pages(
        [page(1, sentences(100))], file_id=FILE_ID, chunk_size=300, overlap=0
    )

    assert len(chunks) > 1


def test_empty_page_produces_no_chunks_but_keeps_later_page_numbers() -> None:
    chunks = chunk_pages(
        [page(1, "Page one has text."), page(2, ""), page(3, "Page three has text.")],
        file_id=FILE_ID,
    )

    assert [chunk.page_number for chunk in chunks] == [1, 3]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


def test_document_of_only_empty_pages_produces_nothing() -> None:
    chunks = chunk_pages([page(1, ""), page(2, "")], file_id=FILE_ID)

    assert chunks == []


def test_no_pages_produces_nothing() -> None:
    assert chunk_pages([], file_id=FILE_ID) == []


def test_whitespace_only_page_produces_nothing() -> None:
    chunks = chunk_pages([page(1, "   \n\n  \t ")], file_id=FILE_ID)

    assert chunks == []


def test_chunk_content_is_stripped_and_non_empty() -> None:
    chunks = chunk_pages([page(1, sentences(150))], file_id=FILE_ID)

    for chunk in chunks:
        assert chunk.content
        assert chunk.content == chunk.content.strip()


def test_chunking_is_deterministic() -> None:
    pages = [page(1, sentences(80)), page(2, sentences(80))]

    assert chunk_pages(pages, file_id=FILE_ID) == chunk_pages(pages, file_id=FILE_ID)


def test_file_id_is_attached_to_every_chunk() -> None:
    chunks = chunk_pages([page(1, sentences(100))], file_id="another-file")

    assert {chunk.file_id for chunk in chunks} == {"another-file"}


def test_korean_text_is_chunked_without_losing_characters() -> None:
    korean = "다익스트라 알고리즘은 방문하지 않은 정점 중 거리 추정값이 가장 작은 정점을 선택한다. " * 30

    chunks = chunk_pages([page(7, korean)], file_id=FILE_ID)

    assert len(chunks) > 1
    assert all(chunk.page_number == 7 for chunk in chunks)
    assert "다익스트라" in chunks[0].content
    for chunk in chunks:
        assert len(chunk.content) <= DEFAULT_CHUNK_SIZE


def test_unbroken_text_still_splits() -> None:
    # No spaces or punctuation to snap to: the hard cut must still apply.
    chunks = chunk_pages([page(1, "x" * 3000)], file_id=FILE_ID, chunk_size=500, overlap=50)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.content) <= 500


def test_boundary_snapping_prefers_paragraph_breaks() -> None:
    first_part = "A" * 700
    second_part = "B" * 700
    chunks = chunk_pages(
        [page(1, f"{first_part}\n\n{second_part}")],
        file_id=FILE_ID,
        chunk_size=1000,
        overlap=0,
    )

    # The paragraph break sits at 60-100% of the first window, so the first
    # chunk should end there rather than 300 characters into the second part.
    assert chunks[0].content == first_part


def test_defaults_are_consistent() -> None:
    assert DEFAULT_CHUNK_OVERLAP < DEFAULT_CHUNK_SIZE


@pytest.mark.parametrize("chunk_size", [0, -1, -100])
def test_non_positive_chunk_size_is_rejected(chunk_size: int) -> None:
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        chunk_pages([page(1, "text")], file_id=FILE_ID, chunk_size=chunk_size)


def test_negative_overlap_is_rejected() -> None:
    with pytest.raises(ValueError, match="overlap must not be negative"):
        chunk_pages([page(1, "text")], file_id=FILE_ID, overlap=-1)


@pytest.mark.parametrize("overlap", [500, 900])
def test_overlap_not_smaller_than_chunk_size_is_rejected(overlap: int) -> None:
    with pytest.raises(ValueError, match="must be smaller than chunk_size"):
        chunk_pages([page(1, "text")], file_id=FILE_ID, chunk_size=500, overlap=overlap)
