"""Tests for the models and SQLite persistence.

Every test runs against an in-memory database, so nothing touches
``data/app.db`` and the suite stays fast.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.db.database import connect, database_path, init_schema
from app.db.files import (
    FileRecordNotFound,
    count_chunks,
    create_file,
    delete_file,
    file_names,
    get_file,
    list_chunks,
    list_files,
    replace_chunks,
    set_counts,
    set_status,
)
from app.models.files import Chunk, File, FileStatus, FileType


@pytest.fixture
def db() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_schema(connection)
    yield connection
    connection.close()


def add(db: sqlite3.Connection, name: str = "algorithms.pdf", **kwargs) -> File:
    return create_file(
        db,
        name=name,
        file_type=kwargs.pop("file_type", FileType.PDF),
        path=kwargs.pop("path", f"data/sources/{name}"),
        size=kwargs.pop("size", 1024),
        **kwargs,
    )


def chunk(file_id: str, index: int, *, page: int | None = 1) -> Chunk:
    return Chunk(
        id=f"{file_id}-{index}",
        file_id=file_id,
        chunk_index=index,
        content=f"chunk {index}",
        page_number=page,
        vector_id=f"vec-{file_id}-{index}",
    )


# --- models ------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("notes.pdf", FileType.PDF),
        ("NOTES.PDF", FileType.PDF),
        ("readme.md", FileType.MARKDOWN),
        ("readme.markdown", FileType.MARKDOWN),
        ("log.txt", FileType.TEXT),
        ("log.text", FileType.TEXT),
    ],
)
def test_file_type_inferred_from_extension(name: str, expected: FileType) -> None:
    assert FileType.from_filename(name) is expected


@pytest.mark.parametrize("name", ["archive.zip", "photo.png", "noextension", "script.py"])
def test_unsupported_extension_is_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="Unsupported file type"):
        FileType.from_filename(name)


def test_only_pdf_has_pages() -> None:
    assert FileType.PDF.has_pages
    assert not FileType.MARKDOWN.has_pages
    assert not FileType.TEXT.has_pages


def test_terminal_and_processing_statuses_are_complementary() -> None:
    for status in FileStatus:
        assert status.is_terminal != status.is_processing
    assert FileStatus.READY.is_terminal
    assert FileStatus.FAILED.is_terminal
    assert FileStatus.EMBEDDING.is_processing


def test_status_values_serialize_as_strings() -> None:
    # The API returns these directly and SQLite stores them as TEXT.
    assert FileStatus.READY.value == "READY"
    assert FileType.MARKDOWN.value == "md"


# --- schema ------------------------------------------------------------------


def test_init_schema_is_idempotent(db: sqlite3.Connection) -> None:
    init_schema(db)
    init_schema(db)

    tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"files", "chunks"} <= tables


def test_foreign_keys_are_enforced(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        with db:
            db.execute(
                "INSERT INTO chunks VALUES ('c1', 'no-such-file', 0, 'text', 1, 'v1')"
            )


def test_database_path_is_absolute() -> None:
    assert database_path().is_absolute()


# --- files -------------------------------------------------------------------


def test_created_file_starts_as_uploading(db: sqlite3.Connection) -> None:
    record = add(db)

    assert record.status is FileStatus.UPLOADING
    assert record.error is None
    assert record.chunk_count == 0
    assert record.page_count is None


def test_created_file_round_trips(db: sqlite3.Connection) -> None:
    created = add(db, "lecture.pdf", size=4096)

    fetched = get_file(db, created.id)

    assert fetched == created


def test_ids_are_unique(db: sqlite3.Connection) -> None:
    assert add(db, "a.pdf").id != add(db, "b.pdf").id


def test_explicit_file_id_is_respected(db: sqlite3.Connection) -> None:
    record = add(db, file_id="chosen-id")

    assert get_file(db, "chosen-id").id == record.id


def test_get_missing_file_raises(db: sqlite3.Connection) -> None:
    with pytest.raises(FileRecordNotFound, match="No file with id"):
        get_file(db, "absent")


def test_list_files_is_newest_first(db: sqlite3.Connection) -> None:
    first = add(db, "first.pdf")
    second = add(db, "second.pdf")
    # created_at can tie at this resolution, so id breaks the tie deterministically.
    names = {f.id for f in list_files(db)}

    assert names == {first.id, second.id}
    assert len(list_files(db)) == 2


def test_list_files_is_empty_initially(db: sqlite3.Connection) -> None:
    assert list_files(db) == []


def test_file_names_maps_id_to_name(db: sqlite3.Connection) -> None:
    one = add(db, "algorithms.pdf")
    two = add(db, "notes.md", file_type=FileType.MARKDOWN)

    assert file_names(db) == {one.id: "algorithms.pdf", two.id: "notes.md"}


# --- status transitions ------------------------------------------------------


def test_status_advances_through_the_pipeline(db: sqlite3.Connection) -> None:
    record = add(db)

    for status in (
        FileStatus.EXTRACTING,
        FileStatus.CHUNKING,
        FileStatus.EMBEDDING,
        FileStatus.READY,
    ):
        updated = set_status(db, record.id, status)
        assert updated.status is status

    assert get_file(db, record.id).is_ready


def test_failed_status_stores_its_reason(db: sqlite3.Connection) -> None:
    record = add(db)

    updated = set_status(db, record.id, FileStatus.FAILED, error="Could not open PDF")

    assert updated.status is FileStatus.FAILED
    assert updated.error == "Could not open PDF"


def test_failed_status_without_a_reason_is_rejected(db: sqlite3.Connection) -> None:
    record = add(db)

    # A failure the UI cannot explain is worse than no failure state.
    with pytest.raises(ValueError, match="requires an error message"):
        set_status(db, record.id, FileStatus.FAILED)


def test_recovering_from_failure_clears_the_error(db: sqlite3.Connection) -> None:
    record = add(db)
    set_status(db, record.id, FileStatus.FAILED, error="transient Ollama outage")

    recovered = set_status(db, record.id, FileStatus.EMBEDDING)

    assert recovered.error is None


def test_status_update_bumps_updated_at(db: sqlite3.Connection) -> None:
    record = add(db)

    updated = set_status(db, record.id, FileStatus.EXTRACTING)

    assert updated.updated_at >= record.updated_at
    assert updated.created_at == record.created_at


def test_status_update_on_missing_file_raises(db: sqlite3.Connection) -> None:
    with pytest.raises(FileRecordNotFound):
        set_status(db, "absent", FileStatus.READY)


def test_counts_are_recorded(db: sqlite3.Connection) -> None:
    record = add(db)

    updated = set_counts(db, record.id, page_count=34, chunk_count=88)

    assert updated.page_count == 34
    assert updated.chunk_count == 88


def test_counts_can_be_set_independently(db: sqlite3.Connection) -> None:
    record = add(db)
    set_counts(db, record.id, page_count=6)

    updated = set_counts(db, record.id, chunk_count=15)

    assert updated.page_count == 6
    assert updated.chunk_count == 15


def test_setting_no_counts_changes_nothing(db: sqlite3.Connection) -> None:
    record = add(db)

    assert set_counts(db, record.id) == record


# --- chunks ------------------------------------------------------------------


def test_chunks_round_trip_in_reading_order(db: sqlite3.Connection) -> None:
    record = add(db)
    chunks = [chunk(record.id, i, page=i + 1) for i in range(3)]

    stored = replace_chunks(db, record.id, chunks)

    assert stored == 3
    assert list_chunks(db, record.id) == chunks


def test_chunks_keep_a_null_page_for_pageless_files(db: sqlite3.Connection) -> None:
    record = add(db, "notes.md", file_type=FileType.MARKDOWN)

    replace_chunks(db, record.id, [chunk(record.id, 0, page=None)])

    assert list_chunks(db, record.id)[0].page_number is None


def test_replacing_chunks_does_not_accumulate(db: sqlite3.Connection) -> None:
    record = add(db)
    replace_chunks(db, record.id, [chunk(record.id, i) for i in range(3)])

    replace_chunks(db, record.id, [chunk(record.id, i) for i in range(2)])

    assert count_chunks(db, record.id) == 2


def test_replacing_chunks_only_affects_one_file(db: sqlite3.Connection) -> None:
    keep = add(db, "keep.pdf")
    other = add(db, "other.pdf")
    replace_chunks(db, keep.id, [chunk(keep.id, 0)])
    replace_chunks(db, other.id, [chunk(other.id, 0), chunk(other.id, 1)])

    replace_chunks(db, other.id, [])

    assert count_chunks(db, keep.id) == 1
    assert count_chunks(db, other.id) == 0


def test_duplicate_chunk_index_is_rejected(db: sqlite3.Connection) -> None:
    record = add(db)
    duplicate = [chunk(record.id, 0), chunk(record.id, 0)]

    # Two chunks claiming the same index would make provenance ambiguous.
    with pytest.raises(sqlite3.IntegrityError):
        replace_chunks(db, record.id, duplicate)


def test_count_chunks_across_all_files(db: sqlite3.Connection) -> None:
    one, two = add(db, "a.pdf"), add(db, "b.pdf")
    replace_chunks(db, one.id, [chunk(one.id, 0)])
    replace_chunks(db, two.id, [chunk(two.id, 0), chunk(two.id, 1)])

    assert count_chunks(db) == 3


# --- deletion ----------------------------------------------------------------


def test_deleting_a_file_cascades_to_its_chunks(db: sqlite3.Connection) -> None:
    record = add(db)
    replace_chunks(db, record.id, [chunk(record.id, i) for i in range(3)])

    delete_file(db, record.id)

    # Orphaned chunk rows would keep a deleted document present in the index.
    assert count_chunks(db, record.id) == 0
    with pytest.raises(FileRecordNotFound):
        get_file(db, record.id)


def test_deleting_one_file_leaves_others_intact(db: sqlite3.Connection) -> None:
    keep = add(db, "keep.pdf")
    remove = add(db, "remove.pdf")
    replace_chunks(db, keep.id, [chunk(keep.id, 0)])
    replace_chunks(db, remove.id, [chunk(remove.id, 0)])

    delete_file(db, remove.id)

    assert get_file(db, keep.id).id == keep.id
    assert count_chunks(db, keep.id) == 1


def test_deleting_a_missing_file_raises(db: sqlite3.Connection) -> None:
    with pytest.raises(FileRecordNotFound):
        delete_file(db, "absent")
