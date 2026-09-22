"""Tests for Markdown and plain-text extraction.

Unlike the PDF fixtures, these can use Korean text directly — no font rendering
is involved, so the bytes on disk are exactly what extraction reads back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.files import FileType
from app.services.extraction import (
    ExtractedPage,
    ExtractionError,
    extract_file,
    extract_text_file,
)


def write(path: Path, content: str, encoding: str = "utf-8") -> Path:
    path.write_bytes(content.encode(encoding))
    return path


def test_text_file_becomes_a_single_page(tmp_path: Path) -> None:
    path = write(tmp_path / "notes.txt", "First line.\nSecond line.")

    pages = extract_text_file(path)

    assert pages == [ExtractedPage(page_number=1, content="First line.\nSecond line.")]


def test_markdown_structure_is_preserved(tmp_path: Path) -> None:
    source = "# Title\n\nSome prose.\n\n## Section\n\n- item one\n- item two"
    path = write(tmp_path / "readme.md", source)

    content = extract_text_file(path)[0].content

    # Markdown is indexed as written; no parsing or stripping of syntax.
    assert content == source


def test_page_number_is_a_placeholder(tmp_path: Path) -> None:
    path = write(tmp_path / "notes.md", "Content.")

    # Ingestion discards this for pageless types, so a citation names the file
    # only. It is 1 rather than 0 purely for consistency with PDF numbering.
    assert extract_text_file(path)[0].page_number == 1


def test_whole_file_is_one_page_regardless_of_length(tmp_path: Path) -> None:
    long_text = "\n\n".join(f"Paragraph {i} with some words in it." for i in range(500))
    path = write(tmp_path / "long.md", long_text)

    pages = extract_text_file(path)

    # One page keeps chunk overlap flowing across the document rather than
    # resetting at boundaries the source does not have.
    assert len(pages) == 1
    assert len(pages[0].content) > 10_000


def test_korean_text_round_trips(tmp_path: Path) -> None:
    source = "다익스트라 알고리즘은 음수 가중치를 허용하지 않는다.\n우선순위 큐를 사용한다."
    path = write(tmp_path / "한글.md", source)

    assert extract_text_file(path)[0].content == source


def test_byte_order_mark_is_stripped(tmp_path: Path) -> None:
    path = write(tmp_path / "bom.txt", "# Title\n\nBody.", encoding="utf-8-sig")

    content = extract_text_file(path)[0].content

    # A surviving BOM would be an invisible character at the start of chunk 0.
    assert content.startswith("# Title")
    assert "\ufeff" not in content


def test_crlf_line_endings_are_normalised(tmp_path: Path) -> None:
    path = write(tmp_path / "windows.txt", "First line.\r\nSecond line.\r\n")

    content = extract_text_file(path)[0].content

    assert "\r" not in content
    assert content == "First line.\nSecond line."


def test_lone_carriage_returns_are_normalised(tmp_path: Path) -> None:
    path = write(tmp_path / "classic.txt", "First.\rSecond.")

    assert extract_text_file(path)[0].content == "First.\nSecond."


def test_surrounding_whitespace_is_stripped(tmp_path: Path) -> None:
    path = write(tmp_path / "padded.md", "\n\n   # Title\n\nBody.\n\n  \n")

    content = extract_text_file(path)[0].content

    assert content.startswith("# Title")
    assert content.endswith("Body.")


def test_empty_file_yields_empty_content(tmp_path: Path) -> None:
    path = write(tmp_path / "empty.txt", "")

    # Extraction succeeds; ingestion is what decides an empty document fails.
    assert extract_text_file(path)[0].content == ""


def test_whitespace_only_file_yields_empty_content(tmp_path: Path) -> None:
    path = write(tmp_path / "blank.txt", "   \n\n\t  \n")

    assert extract_text_file(path)[0].content == ""


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="File not found"):
        extract_text_file(tmp_path / "absent.md")


def test_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="File not found"):
        extract_text_file(tmp_path)


def test_non_utf8_bytes_raise_with_guidance(tmp_path: Path) -> None:
    path = tmp_path / "legacy.txt"
    # CP949, as a Korean file saved by older Windows software would be.
    path.write_bytes("다익스트라".encode("cp949"))

    with pytest.raises(ExtractionError, match="not valid UTF-8"):
        extract_text_file(path)


def test_accepts_a_path_given_as_a_string(tmp_path: Path) -> None:
    path = write(tmp_path / "notes.md", "Content.")

    assert extract_text_file(str(path))[0].content == "Content."


# --- dispatcher --------------------------------------------------------------


def test_dispatcher_routes_markdown_and_text(tmp_path: Path) -> None:
    md = write(tmp_path / "a.md", "# Markdown")
    txt = write(tmp_path / "b.txt", "Plain text")

    assert extract_file(md, FileType.MARKDOWN)[0].content == "# Markdown"
    assert extract_file(txt, FileType.TEXT)[0].content == "Plain text"


def test_dispatcher_routes_pdf(tmp_path: Path) -> None:
    import pymupdf

    path = tmp_path / "doc.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "PDF content here.", fontsize=12)
    document.save(path)
    document.close()

    pages = extract_file(path, FileType.PDF)

    assert len(pages) == 1
    assert "PDF content" in pages[0].content


def test_dispatcher_reports_a_missing_file_through_either_route(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="File not found"):
        extract_file(tmp_path / "absent.md", FileType.MARKDOWN)
    with pytest.raises(ExtractionError, match="File not found"):
        extract_file(tmp_path / "absent.pdf", FileType.PDF)
