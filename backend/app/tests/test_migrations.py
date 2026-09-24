"""Tests for the schema migration runner.

The case that matters is the one that cannot be produced by a fresh database: a
database created before this module existed, which reports ``user_version = 0``
with every table already present. A fresh-database test passes trivially and
proves nothing about an upgrade, so most of these build the legacy shape by hand.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.db.database import connect, init_schema
from app.db.migrations import (
    LATEST_VERSION,
    MIGRATIONS,
    add_column_if_missing,
    apply_migrations,
    current_version,
)

#: The `files` table as it stood before Phase 6 — no content_hash, no
#: embedding_model. Written out rather than derived from SCHEMA, because deriving
#: it from the thing under test would make the test agree with any change to it.
LEGACY_FILES = """
CREATE TABLE files (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    file_type    TEXT NOT NULL,
    path         TEXT NOT NULL,
    size         INTEGER NOT NULL,
    status       TEXT NOT NULL,
    error        TEXT,
    page_count   INTEGER,
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


@pytest.fixture
def legacy(tmp_path) -> sqlite3.Connection:
    """A pre-Phase-6 database with a file row in it."""
    connection = sqlite3.connect(tmp_path / "legacy.db")
    connection.row_factory = sqlite3.Row
    connection.executescript(LEGACY_FILES)
    connection.execute(
        "INSERT INTO files (id, name, file_type, path, size, status, chunk_count,"
        " created_at, updated_at) VALUES"
        " ('f1', 'notes.pdf', 'pdf', '/tmp/notes.pdf', 100, 'READY', 7,"
        " '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    connection.commit()
    return connection


class TestTheProblemThisSolves:
    def test_create_table_if_not_exists_does_not_add_a_column(self, legacy):
        """The silent failure this module exists to prevent.

        If this ever starts passing a column through, the module can be simplified.
        Until then it documents why ALTER TABLE is necessary at all.
        """
        legacy.executescript(
            "CREATE TABLE IF NOT EXISTS files ("
            " id TEXT PRIMARY KEY, name TEXT, content_hash TEXT);"
        )
        assert "content_hash" not in columns(legacy, "files")


class TestApplyMigrations:
    def test_upgrades_a_legacy_database(self, legacy):
        assert current_version(legacy) == 0

        ran = apply_migrations(legacy)

        assert ran == len(MIGRATIONS)
        assert {"content_hash", "embedding_model"} <= columns(legacy, "files")
        assert current_version(legacy) == LATEST_VERSION

    def test_keeps_every_existing_row(self, legacy):
        apply_migrations(legacy)

        rows = legacy.execute("SELECT * FROM files").fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "notes.pdf"
        assert rows[0]["chunk_count"] == 7

    def test_leaves_the_new_columns_null_rather_than_guessing(self, legacy):
        """Backfilling the configured model would manufacture a certainty.

        The column's whole purpose is detecting a mismatch, so seeding it with the
        current configuration would defeat it. NULL means "indexed before Noye
        recorded this", which is true.
        """
        apply_migrations(legacy)

        row = legacy.execute("SELECT * FROM files").fetchone()
        assert row["content_hash"] is None
        assert row["embedding_model"] is None

    def test_is_a_no_op_the_second_time(self, legacy):
        apply_migrations(legacy)
        assert apply_migrations(legacy) == 0

    def test_runs_nothing_on_an_already_current_database(self, tmp_path):
        connection = connect(tmp_path / "fresh.db")
        init_schema(connection)

        assert current_version(connection) == LATEST_VERSION
        assert apply_migrations(connection) == 0
        connection.close()

    def test_a_failing_step_leaves_no_trace(self, legacy, monkeypatch):
        """Atomicity, which is not free here.

        Python's sqlite3 begins an implicit transaction only for DML, so ALTER
        TABLE and PRAGMA commit immediately unless a transaction is opened
        explicitly. Without that, a raising step would leave the column added AND
        the version bumped — and the next startup would skip the steps that never
        ran, which is the one outcome that must not happen.
        """

        def exploding(connection: sqlite3.Connection) -> None:
            add_column_if_missing(connection, "files", "half_applied", "TEXT")
            raise RuntimeError("step failed")

        monkeypatch.setattr("app.db.migrations.MIGRATIONS", (exploding,))
        monkeypatch.setattr("app.db.migrations.LATEST_VERSION", 1)

        with pytest.raises(RuntimeError, match="step failed"):
            apply_migrations(legacy)

        assert "half_applied" not in columns(legacy, "files")
        assert current_version(legacy) == 0


class TestAddColumnIfMissing:
    def test_adds_a_column_once(self, legacy):
        assert add_column_if_missing(legacy, "files", "extra", "TEXT") is True
        assert add_column_if_missing(legacy, "files", "extra", "TEXT") is False

    def test_refuses_a_table_that_is_not_there(self, legacy):
        """Skipping would leave a column quietly missing until a query failed."""
        with pytest.raises(RuntimeError, match="does not exist"):
            add_column_if_missing(legacy, "nonexistent", "c", "TEXT")


class TestInitSchemaOrdering:
    def test_a_fresh_database_ends_where_a_migrated_one_does(self, tmp_path):
        """Both paths have to converge, or behaviour depends on install date."""
        fresh = connect(tmp_path / "fresh.db")
        init_schema(fresh)

        upgraded = sqlite3.connect(tmp_path / "upgraded.db")
        upgraded.executescript(LEGACY_FILES)
        upgraded.commit()
        init_schema(upgraded)

        assert columns(fresh, "files") == columns(upgraded, "files")
        assert current_version(fresh) == current_version(upgraded)
        fresh.close()
        upgraded.close()

    def test_init_schema_is_safe_to_re_run(self, tmp_path):
        connection = connect(tmp_path / "twice.db")
        init_schema(connection)
        init_schema(connection)
        assert {"content_hash", "embedding_model"} <= columns(connection, "files")
        connection.close()
