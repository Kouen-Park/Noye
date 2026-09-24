"""Tests for what the upload endpoint refuses, and what it records.

The assertion that matters most is not the status code — it is that an oversized
upload leaves **nothing on disk**. Checking the size after the copy finished, which
is what this replaced, returns the same 413 while the file is already stored. A test
that only looks at the response cannot tell those two implementations apart.
"""

from __future__ import annotations

import hashlib
import io

import pytest

from app.api import files as files_api
from app.config import get_settings
from app.db import files as file_store
from app.models.files import FileType

# The upload fixtures live in test_files_api rather than a conftest, so they are
# imported. ruff's per-file-ignores allow F401/F811 in tests for exactly this: the
# names look unused here but pytest resolves fixtures by name.
from app.tests.test_files_api import (
    client,
    db,
    db_file,
    scheduled,
    uploads,
)


def post(client, name: str, content: bytes, mime: str = "application/pdf"):
    return client.post("/files", files={"file": (name, content, mime)})


#: A minimal payload that passes the PDF magic-byte check. Not a valid PDF —
#: extraction still rejects it — but these tests are about the upload gate, and
#: making every one of them carry a real PDF would test PyMuPDF instead.
PDF_ISH = b"%PDF-1.7\n" + b"x" * 200


class TestSizeLimit:
    def test_refuses_a_file_over_the_limit(self, client, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "max_upload_mb", 1, raising=False)

        response = post(client, "big.pdf", b"%PDF-1.7\n" + b"x" * (2 * 1024 * 1024))

        assert response.status_code == 413
        assert "1 MB" in response.json()["detail"]

    def test_leaves_nothing_on_disk_when_it_refuses(self, client, uploads, monkeypatch):
        """The whole reason the limit is enforced while writing.

        Checking the size after the copy returns the same 413 with the file already
        stored, so only this assertion distinguishes the two implementations.
        """
        settings = get_settings()
        monkeypatch.setattr(settings, "max_upload_mb", 1, raising=False)
        before = set(uploads.iterdir())

        post(client, "big.pdf", b"%PDF-1.7\n" + b"x" * (2 * 1024 * 1024))

        assert set(uploads.iterdir()) == before

    def test_creates_no_row_when_it_refuses(self, client, db, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "max_upload_mb", 1, raising=False)

        post(client, "big.pdf", b"%PDF-1.7\n" + b"x" * (2 * 1024 * 1024))

        assert file_store.list_files(db) == []

    def test_accepts_a_file_at_the_limit(self, client, monkeypatch):
        """The boundary is inclusive: exactly the limit is allowed.

        Off by one here would refuse a file the user was told was acceptable.
        """
        settings = get_settings()
        monkeypatch.setattr(settings, "max_upload_mb", 1, raising=False)
        exact = b"%PDF-1.7\n" + b"x" * (1024 * 1024 - 9)
        assert len(exact) == 1024 * 1024

        response = post(client, "exact.pdf", exact)

        assert response.status_code == 201

    def test_the_limit_is_configurable(self):
        assert isinstance(get_settings().max_upload_mb, int)


class TestContentHash:
    def test_records_the_sha256_of_the_bytes(self, client, db):
        response = post(client, "notes.pdf", PDF_ISH)
        assert response.status_code == 201

        record = file_store.get_file(db, response.json()["id"])
        assert record.content_hash == hashlib.sha256(PDF_ISH).hexdigest()

    def test_the_same_bytes_under_two_names_hash_alike(self, client, db):
        """What makes the hash the right identity for a duplicate.

        A renamed copy is still the same file, which a filename comparison cannot
        see. Branch 4 relies on this.
        """
        first = post(client, "notes.pdf", PDF_ISH)
        second = post(client, "notes-copy.pdf", PDF_ISH)

        hashes = {
            file_store.get_file(db, first.json()["id"]).content_hash,
            file_store.get_file(db, second.json()["id"]).content_hash,
        }
        assert len(hashes) == 1

    def test_different_bytes_hash_differently(self, client, db):
        first = post(client, "a.pdf", PDF_ISH)
        second = post(client, "b.pdf", PDF_ISH + b"more")

        assert (
            file_store.get_file(db, first.json()["id"]).content_hash
            != file_store.get_file(db, second.json()["id"]).content_hash
        )


class TestMislabelledPdf:
    def test_refuses_a_file_that_is_not_a_pdf(self, client):
        """The commonest corrupt upload: something renamed to .pdf.

        Extraction already fails on it with a clear reason, but only after the file
        is stored and a row exists, leaving a FAILED entry to clean up. Refusing it
        here makes it an error the user can act on.
        """
        response = post(client, "renamed.pdf", b"This is plain text, not a PDF.\n" * 5)

        assert response.status_code == 400
        assert "not one" in response.json()["detail"]

    def test_leaves_nothing_behind_when_it_refuses(self, client, db, uploads):
        before = set(uploads.iterdir())

        post(client, "renamed.pdf", b"Definitely not a PDF\n" * 5)

        assert set(uploads.iterdir()) == before
        assert file_store.list_files(db) == []

    def test_does_not_check_magic_bytes_on_text_formats(self, client):
        """Markdown and text have none — anything that decodes as UTF-8 is text.

        Extraction already rejects what does not decode, and its message says how
        to fix it, which a magic-byte check here could not.
        """
        response = post(client, "notes.md", b"# Heading\n\nBody text.\n", "text/markdown")

        assert response.status_code == 201


class TestSaveUpload:
    """The helper directly, for the cases a request cannot easily produce."""

    def test_returns_size_and_hash(self, tmp_path):
        target = tmp_path / "out.bin"
        payload = b"some bytes to store"

        size, digest = files_api._save_upload(
            io.BytesIO(payload), target, limit_bytes=1000
        )

        assert size == len(payload)
        assert digest == hashlib.sha256(payload).hexdigest()
        assert target.read_bytes() == payload

    def test_raises_and_removes_the_partial_file(self, tmp_path):
        target = tmp_path / "out.bin"

        with pytest.raises(files_api.UploadTooLarge):
            files_api._save_upload(
                io.BytesIO(b"x" * 5000), target, limit_bytes=100
            )

        assert not target.exists()

    def test_hashes_a_file_larger_than_one_read(self, tmp_path):
        """Chunked reading must not change the digest.

        A hash computed over multiple update() calls has to equal one computed in a
        single pass, or the whole identity scheme is wrong for exactly the large
        files it matters for.
        """
        target = tmp_path / "out.bin"
        payload = bytes(range(256)) * 8000  # > 1 MiB, so several reads

        _, digest = files_api._save_upload(
            io.BytesIO(payload), target, limit_bytes=10 * 1024 * 1024
        )

        assert digest == hashlib.sha256(payload).hexdigest()


class TestEmbeddingModelIsRecorded:
    def test_a_ready_file_names_the_model_that_embedded_it(self, db, tmp_path, monkeypatch):
        from app.services import ingestion

        source = tmp_path / "notes.md"
        source.write_text("# Notes\n\n" + ("A sentence about indexing. " * 30), encoding="utf-8")
        record = file_store.create_file(
            db,
            name="notes.md",
            file_type=FileType.MARKDOWN,
            path=str(source),
            size=source.stat().st_size,
        )
        assert record.embedding_model is None

        monkeypatch.setattr(
            ingestion, "embed_chunks", lambda chunks, **kw: [[0.01] * 768 for _ in chunks]
        )
        monkeypatch.setattr(ingestion, "delete_file_chunks", lambda *a, **kw: None)
        monkeypatch.setattr(ingestion, "index_chunks", lambda *a, **kw: None)

        result = ingestion.ingest_file(db, record.id)

        assert result.embedding_model == get_settings().ollama_embedding_model

    def test_a_failed_file_claims_no_model(self, db, tmp_path, monkeypatch):
        """A FAILED file's vectors are removed, so the model must go with them.

        Leaving it would have a broken file claiming an embedding space it no longer
        occupies -- the confusion the column exists to prevent.
        """
        from app.services import ingestion

        source = tmp_path / "notes.md"
        source.write_text("# Notes\n\n" + ("A sentence. " * 30), encoding="utf-8")
        record = file_store.create_file(
            db,
            name="notes.md",
            file_type=FileType.MARKDOWN,
            path=str(source),
            size=source.stat().st_size,
        )

        def refuse(*args, **kwargs):
            raise RuntimeError("Ollama is not running")

        monkeypatch.setattr(ingestion, "embed_chunks", refuse)
        monkeypatch.setattr(ingestion, "delete_file_chunks", lambda *a, **kw: None)

        result = ingestion.ingest_file(db, record.id)

        assert result.status.value == "FAILED"
        assert result.embedding_model is None
