"""Tests for refusing a file the user already has.

The interesting half is where detection must NOT fire: a pre-Phase-6 file whose hash
was never recorded, and a file the user deleted and wants back. A rule that refuses
too much is worse here than one that misses a duplicate, because a missed duplicate
costs disk while a wrongly refused upload costs the user their document.
"""

from __future__ import annotations

import pytest

from app.db import files as file_store
from app.models.files import FileStatus, FileType

# Fixtures live in test_files_api rather than a conftest.
from app.tests.test_files_api import (
    client,
    db,
    db_file,
    finish_scheduled,
    scheduled,
    uploads,
)

PDF_ISH = b"%PDF-1.7\n" + b"x" * 200
OTHER_PDF = b"%PDF-1.7\n" + b"y" * 300


def post(client, name: str, content: bytes, mime: str = "application/pdf"):
    return client.post("/files", files={"file": (name, content, mime)})


class TestRefusingADuplicate:
    def test_the_same_bytes_are_refused(self, client):
        assert post(client, "notes.pdf", PDF_ISH).status_code == 201

        second = post(client, "notes.pdf", PDF_ISH)

        assert second.status_code == 409

    def test_the_message_names_the_file_the_user_already_has(self, client):
        """Their real question is "do I already have this?".

        The useful answer is a name they recognise, not a hash or an id.
        """
        post(client, "week-7-lecture.pdf", PDF_ISH)

        second = post(client, "downloaded (1).pdf", PDF_ISH)

        detail = second.json()["detail"]
        assert "week-7-lecture.pdf" in detail
        assert "Delete that one first" in detail

    def test_nothing_is_stored_for_the_refused_upload(self, client, db, uploads):
        post(client, "first.pdf", PDF_ISH)
        before_files = set(uploads.iterdir())
        before_rows = len(file_store.list_files(db))

        post(client, "second.pdf", PDF_ISH)

        assert set(uploads.iterdir()) == before_files
        assert len(file_store.list_files(db)) == before_rows

    def test_different_bytes_are_accepted(self, client):
        assert post(client, "a.pdf", PDF_ISH).status_code == 201
        assert post(client, "b.pdf", OTHER_PDF).status_code == 201

    def test_one_added_byte_makes_it_a_different_file(self, client):
        """A hash is all-or-nothing, which is the point.

        An edited document is a new document as far as the index is concerned,
        because every chunk downstream of the edit moves.
        """
        assert post(client, "v1.pdf", PDF_ISH).status_code == 201
        assert post(client, "v2.pdf", PDF_ISH + b"!").status_code == 201


class TestWhereItMustNotFire:
    def test_a_deleted_file_can_be_uploaded_again(self, client, db, scheduled):
        """Deleting then re-uploading has to work.

        If the lookup ever matched a removed row, a user who deleted something by
        mistake could not put it back.
        """
        first = post(client, "notes.pdf", PDF_ISH)
        file_id = first.json()["id"]
        finish_scheduled(db, file_id)
        assert client.delete(f"/files/{file_id}").status_code == 204

        again = post(client, "notes.pdf", PDF_ISH)

        assert again.status_code == 201

    def test_a_file_with_no_recorded_hash_is_not_treated_as_a_duplicate(
        self, client, db, tmp_path
    ):
        """A pre-Phase-6 file has content_hash NULL, meaning unknown.

        Two unknowns must not compare equal, or every old file would be a duplicate
        of every other old file.
        """
        source = tmp_path / "old.pdf"
        source.write_bytes(PDF_ISH)
        file_store.create_file(
            db,
            name="old.pdf",
            file_type=FileType.PDF,
            path=str(source),
            size=source.stat().st_size,
            # No content_hash: this is what a row from before #27 looks like.
        )

        response = post(client, "new.pdf", PDF_ISH)

        assert response.status_code == 201

    def test_a_failed_file_still_blocks_its_own_bytes(self, client, db):
        """Deliberate: re-uploading identical bytes would fail identically.

        The action that helps is re-indexing the file that is already there, which
        is what the message points at.
        """
        first = post(client, "broken.pdf", PDF_ISH)
        file_id = first.json()["id"]
        file_store.set_status(db, file_id, FileStatus.FAILED, error="Ollama was down")

        second = post(client, "broken.pdf", PDF_ISH)

        assert second.status_code == 409
        assert "re-index" in second.json()["detail"]


class TestFindByContentHash:
    def test_returns_none_when_the_bytes_are_new(self, db):
        assert file_store.find_by_content_hash(db, "a" * 64) is None

    def test_refuses_an_empty_hash(self, db):
        """Guards against a caller passing a NULL through.

        Matching on empty would make every unhashed file a duplicate of the next
        upload, which is the one outcome that loses a user's document.
        """
        with pytest.raises(ValueError, match="empty content hash"):
            file_store.find_by_content_hash(db, "")

    def test_returns_the_oldest_when_several_share_bytes(self, db, tmp_path):
        """Rows can share a hash from before detection existed.

        The oldest is the one the user has had longest, and the one whose
        conversations and documents cite it.
        """
        source = tmp_path / "f.pdf"
        source.write_bytes(PDF_ISH)
        shared = "b" * 64

        older = file_store.create_file(
            db,
            name="older.pdf",
            file_type=FileType.PDF,
            path=str(source),
            size=10,
            content_hash=shared,
        )
        file_store.create_file(
            db,
            name="newer.pdf",
            file_type=FileType.PDF,
            path=str(source),
            size=10,
            content_hash=shared,
        )

        found = file_store.find_by_content_hash(db, shared)

        assert found is not None
        assert found.id == older.id
