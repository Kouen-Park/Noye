"""PDF text extraction with page provenance.

Noye's citations are only trustworthy if every piece of retrieved text can be
traced back to the page it came from, so extraction returns one result per
page instead of concatenating the document into a single string. The page
number travels with the text from here all the way to the citation shown to
the user.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf


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
