"""Tests for PDF extraction.

Fixture PDFs are generated at test time rather than committed as binaries, so
the repository holds no sample documents and the fixtures stay readable.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from app.services.extraction import ExtractedPage, ExtractionError, extract_pdf


def write_pdf(path: Path, page_texts: list[str | None]) -> Path:
    """Create a PDF where each entry produces one page.

    ``None`` produces a genuinely blank page. Text is inserted as a single
    line per page, which keeps the expected extraction result obvious.
    """
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        if text is not None:
            page.insert_text((72, 72), text, fontsize=12)
    document.save(path)
    document.close()
    return path


@pytest.fixture
def three_page_pdf(tmp_path: Path) -> Path:
    return write_pdf(
        tmp_path / "algorithms.pdf",
        [
            "Dijkstra selects the unvisited vertex with the smallest estimate.",
            "Negative edge weights break the correctness guarantee.",
            "A priority queue keeps the selection step cheap.",
        ],
    )


def test_extracts_one_result_per_page(three_page_pdf: Path) -> None:
    pages = extract_pdf(three_page_pdf)

    assert len(pages) == 3


def test_page_numbers_are_one_based_and_sequential(three_page_pdf: Path) -> None:
    pages = extract_pdf(three_page_pdf)

    assert [page.page_number for page in pages] == [1, 2, 3]


def test_page_text_stays_on_its_own_page(three_page_pdf: Path) -> None:
    pages = extract_pdf(three_page_pdf)

    assert "Dijkstra" in pages[0].content
    assert "Negative edge weights" in pages[1].content
    assert "priority queue" in pages[2].content
    # Provenance would be broken if text bled across pages.
    assert "Dijkstra" not in pages[1].content
    assert "priority queue" not in pages[0].content


def test_extraction_is_deterministic(three_page_pdf: Path) -> None:
    first = extract_pdf(three_page_pdf)
    second = extract_pdf(three_page_pdf)

    assert first == second


def test_content_is_stripped(three_page_pdf: Path) -> None:
    pages = extract_pdf(three_page_pdf)

    for page in pages:
        assert page.content == page.content.strip()
        assert page.content


def test_blank_page_is_kept_with_its_page_number(tmp_path: Path) -> None:
    pdf = write_pdf(
        tmp_path / "with-blank.pdf",
        ["First page has text.", None, "Third page has text."],
    )

    pages = extract_pdf(pdf)

    # The blank page must not be dropped, or page 3 would be reported as page 2.
    assert len(pages) == 3
    assert pages[1] == ExtractedPage(page_number=2, content="")
    assert pages[1].is_empty
    assert pages[2].page_number == 3
    assert "Third page" in pages[2].content


def test_all_blank_pages_extract_without_error(tmp_path: Path) -> None:
    pdf = write_pdf(tmp_path / "blank.pdf", [None, None])

    pages = extract_pdf(pdf)

    assert [page.is_empty for page in pages] == [True, True]


def test_accepts_a_path_given_as_a_string(three_page_pdf: Path) -> None:
    pages = extract_pdf(str(three_page_pdf))

    assert len(pages) == 3


def test_missing_file_raises_extraction_error(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="File not found"):
        extract_pdf(tmp_path / "absent.pdf")


def test_directory_path_raises_extraction_error(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="File not found"):
        extract_pdf(tmp_path)


def test_corrupt_file_raises_extraction_error(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7\nthis is not a valid PDF body")

    with pytest.raises(ExtractionError, match="Could not open PDF"):
        extract_pdf(corrupt)


def test_non_pdf_content_raises_extraction_error(tmp_path: Path) -> None:
    text_file = tmp_path / "notes.pdf"
    text_file.write_text("Just plain text, not a PDF at all.")

    with pytest.raises(ExtractionError, match="Could not open PDF"):
        extract_pdf(text_file)


def test_password_protected_pdf_raises_extraction_error(tmp_path: Path) -> None:
    protected = tmp_path / "protected.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Secret contents.", fontsize=12)
    document.save(
        protected,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="noye-test-password",
    )
    document.close()

    with pytest.raises(ExtractionError, match="password protected"):
        extract_pdf(protected)
