"""Text extraction with page provenance.

Noye's citations are only trustworthy if every piece of retrieved text can be
traced back to where it came from, so extraction returns one result per page
instead of concatenating a document into a single string. The page number
travels with the text from here all the way to the citation shown to the user.

PDFs are page-aware. Markdown and text files are not, so they come back as one
"page" whose number ingestion discards — a citation for them names the file
only, rather than inventing a page a reader could not verify.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.models.files import FileType


class ExtractionError(Exception):
    """A source file could not be extracted.

    Raised instead of letting a PyMuPDF error surface directly, so callers can
    map extraction failures to a FAILED processing state without depending on
    the PDF library's exception types.
    """


@dataclass(frozen=True)
class ExtractedPage:
    """One page of extracted text.

    ``page_number`` is 1-based, matching how a reader would cite the page.
    ``content`` is stripped of surrounding whitespace and is an empty string
    for a page that holds no extractable text, such as a scanned image or a
    deliberately blank page.
    """

    page_number: int
    content: str

    @property
    def is_empty(self) -> bool:
        return not self.content


def extract_pdf(path: str | Path) -> list[ExtractedPage]:
    """Extract every page of a PDF, preserving page numbers.

    Returns one :class:`ExtractedPage` per page, in document order, including
    pages whose text is empty. Empty pages are kept rather than dropped so
    that a page number always refers to the same physical page; filtering them
    out is the caller's decision.

    Raises:
        ExtractionError: the file is missing, is not a readable PDF, is
            password protected, or contains no pages.
    """
    pdf_path = Path(path)

    if not pdf_path.is_file():
        raise ExtractionError(f"File not found: {pdf_path}")

    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:  # PyMuPDF raises several unrelated types here.
        raise ExtractionError(f"Could not open PDF: {pdf_path.name}") from exc

    with document:
        if document.needs_pass:
            raise ExtractionError(f"PDF is password protected: {pdf_path.name}")

        if document.page_count == 0:
            raise ExtractionError(f"PDF contains no pages: {pdf_path.name}")

        pages: list[ExtractedPage] = []
        for index, page in enumerate(document):
            page_number = index + 1
            try:
                text = page.get_text()
            except Exception as exc:
                raise ExtractionError(
                    f"Could not read page {page_number} of {pdf_path.name}"
                ) from exc

            pages.append(ExtractedPage(page_number=page_number, content=text.strip()))

    return pages


def extract_text_file(path: str | Path) -> list[ExtractedPage]:
    """Extract a Markdown or plain-text file as a single unit.

    These formats have no pages, so the whole file is returned as one
    :class:`ExtractedPage` with ``page_number=1``. That number is a placeholder:
    ingestion discards it for formats whose ``FileType.has_pages`` is false, so a
    citation reads ``notes.md`` rather than inventing a page a reader could not
    verify.

    Returning one page rather than slicing the file into artificial pages also
    keeps chunk overlap flowing across the whole document instead of resetting
    at boundaries that do not exist in the source.

    Line endings are normalised to ``\\n`` so CRLF files do not carry stray
    carriage returns into chunk text and citations.

    Raises:
        ExtractionError: the file is missing, unreadable, or not valid UTF-8.
    """
    text_path = Path(path)

    if not text_path.is_file():
        raise ExtractionError(f"File not found: {text_path}")

    try:
        raw = text_path.read_bytes()
    except OSError as exc:
        raise ExtractionError(f"Could not read {text_path.name}: {exc}") from exc

    try:
        # utf-8-sig also decodes plain UTF-8, and strips a byte-order mark that
        # would otherwise become an invisible character at the start of chunk 0.
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError(
            f"{text_path.name} is not valid UTF-8 text. Re-save it as UTF-8 and "
            "upload it again."
        ) from exc

    normalised = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    return [ExtractedPage(page_number=1, content=normalised)]


def extract_file(path: str | Path, file_type: FileType) -> list[ExtractedPage]:
    """Extract any supported file, dispatching on its type.

    Raises:
        ExtractionError: extraction failed, or the type has no extractor.
    """
    if file_type is FileType.PDF:
        return extract_pdf(path)
    if file_type in (FileType.MARKDOWN, FileType.TEXT):
        return extract_text_file(path)
    raise ExtractionError(f"No extractor for {file_type.value} files")
