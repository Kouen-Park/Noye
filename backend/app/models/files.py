"""Domain models for stored files and their chunks.

These are plain dataclasses rather than ORM entities: the schema is small, the
relationships are one-deep, and the plan's code-design rules call for the
simplest thing that works. Persistence lives in :mod:`app.db.files`, which maps
these to and from SQLite rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class FileStatus(str, Enum):
    """Where a file is in the ingestion pipeline.

    The user sees these as real stages rather than a fake percentage, so each
    one corresponds to work that actually happens. ``str`` mixin so the value
    serializes directly to JSON and stores as TEXT.
    """

    UPLOADING = "UPLOADING"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    READY = "READY"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in (FileStatus.READY, FileStatus.FAILED)

    @property
    def is_processing(self) -> bool:
        return not self.is_terminal


class FileType(str, Enum):
    """Supported source formats.

    PDF is page-aware; the others are not, which is why ``Chunk.page_number``
    is optional.
    """

    PDF = "pdf"
    MARKDOWN = "md"
    TEXT = "txt"

    @property
    def has_pages(self) -> bool:
        return self is FileType.PDF

    @classmethod
    def from_filename(cls, name: str) -> FileType:
        """Infer the type from a filename's extension.

        Raises:
            ValueError: the extension is not supported. The caller turns this
                into a rejected upload rather than storing a file Noye cannot
                read.
        """
        suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        aliases = {
            "pdf": cls.PDF,
            "md": cls.MARKDOWN,
            "markdown": cls.MARKDOWN,
            "txt": cls.TEXT,
            "text": cls.TEXT,
        }
        if suffix not in aliases:
            supported = ", ".join(sorted({t.value for t in cls}))
            raise ValueError(f"Unsupported file type '{suffix or name}'. Supported: {supported}")
        return aliases[suffix]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class File:
    """A source document the user uploaded.

    The file on disk at ``path`` is the source of truth; everything derived
    from it — chunks, vectors — can be rebuilt. ``error`` carries the reason a
    FAILED file failed, so the UI can say what went wrong instead of only that
    something did.
    """

    id: str
    name: str
    file_type: FileType
    path: str
    size: int
    status: FileStatus = FileStatus.UPLOADING
    error: str | None = None
    page_count: int | None = None
    chunk_count: int = 0
    #: sha256 of the file's bytes, computed while the upload was written. Identifies
    #: a duplicate — not the filename, since the same name in two folders is
    #: legitimately two files and a renamed copy is still the same file — and
    #: detects a source edited on disk after it was indexed.
    #:
    #: None for a file indexed before Noye recorded it. That means *unknown*, not
    #: *unchanged*: reading it as a mismatch would make an existing library look
    #: broken on upgrade alone.
    content_hash: str | None = None
    #: The embedding model whose vectors are in the index for this file. Written by
    #: ingestion, not by upload, because that is when the vectors are made.
    embedding_model: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @property
    def is_ready(self) -> bool:
        return self.status is FileStatus.READY


@dataclass
class Chunk:
    """A stored chunk row, linking a file's text to its vector.

    Mirrors :class:`app.services.chunking.Chunk` but adds what only storage
    knows: the ``vector_id`` in Qdrant. Keeping the row lets Noye delete a
    file's vectors and rebuild its index without re-reading Qdrant, and
    ``page_number`` is nullable because Markdown and text files have no pages.
    """

    id: str
    file_id: str
    chunk_index: int
    content: str
    page_number: int | None
    vector_id: str
