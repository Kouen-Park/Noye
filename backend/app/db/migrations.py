"""Schema migrations.

Every phase up to this one only ever ADDED tables, and ``CREATE TABLE IF NOT
EXISTS`` in ``database.SCHEMA`` was enough for that. Phase 6 is the first that
must add COLUMNS to a table that already exists, and that is where the old
approach fails silently: re-running a ``CREATE TABLE IF NOT EXISTS`` that names a
new column against a database where the table is already there is a **no-op**. The
column never appears, nothing complains, and the first query using it fails at
runtime instead.

So columns are added here instead, and `SCHEMA` keeps describing the current shape
for anyone reading it.

Why not Alembic
---------------
It would mean a dependency, a config file, a versions directory and an offline/
online distinction, to run a handful of ``ALTER TABLE`` statements against a
single-user local SQLite file. Noye's claim is that it works without setup, and
this is a place that claim is cheap to keep. Reconsider if the schema ever starts
changing *shape* — renaming or retyping columns, splitting tables — because that
is where hand-written steps stop being obviously correct.

How a step must behave
----------------------
``PRAGMA user_version`` records how far a database has come, but it is NOT what
makes this safe, because it cannot be trusted on a database created before this
module existed: such a database has ``user_version = 0`` and a full set of tables,
which is indistinguishable from a brand-new one.

Every step is therefore written to be **idempotent by construction** — it checks
the live schema before changing it. Running the whole list against an
already-current database does nothing at all. `user_version` is kept as a record
and a fast path, not as the correctness mechanism.

What a step may not do
----------------------
**Additive only.** The files under ``data/sources/`` are the source of truth and
the Qdrant index is derived, but SQLite holds what is *not* derived: conversations
and documents, which are the user's own questions and writing. A step that would
drop or rewrite a column has to copy the database file first, and none does yet.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    """The column names a table currently has, or nothing if it does not exist."""
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def add_column_if_missing(
    connection: sqlite3.Connection, table: str, column: str, declaration: str
) -> bool:
    """Add a column unless it is already there. Returns whether it was added.

    SQLite has no ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``, so the check has to
    be explicit. Without it, re-running a step raises "duplicate column name" and
    a startup that should be a no-op becomes a crash.

    A column added to an existing table is NULL for every existing row. That is
    information, not a gap to paper over — see step 1.
    """
    if not _table_exists(connection, table):
        # The table is created by SCHEMA, which runs first. If it is missing, the
        # caller has the order wrong and silently skipping would hide that.
        raise RuntimeError(
            f"Cannot add {table}.{column}: the table does not exist. "
            "init_schema must run before migrations."
        )
    if column in _columns(connection, table):
        return False
    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
    return True


def _step_1_file_provenance(connection: sqlite3.Connection) -> None:
    """Record what produced a file's vectors, and what the file's bytes were.

    ``content_hash`` — a sha256 of the file's bytes, which is how duplicate
    detection identifies a file. Not the filename: the same name in two folders is
    legitimately two files, and a renamed copy is still the same file. It also
    detects a source edited on disk after it was indexed.

    ``embedding_model`` — the model whose vectors are in the index for this file.
    Search must never mix two embedding spaces in one ranking: a cosine score
    between them is meaningless, so the results would be confidently wrong, which
    is worse than empty because wrongness here is invisible.

    **Both stay NULL for files that already existed, deliberately.** Backfilling
    the currently configured model would manufacture a certainty we do not have —
    the column exists precisely to detect a mismatch, so seeding it with a guess
    defeats it. Backfilling by re-reading and re-hashing every file would make a
    startup migration do unbounded disk I/O. NULL means "indexed before Noye
    recorded this", which is the truth; the detection added later must treat it as
    unknown rather than as a proven mismatch, so an existing library keeps working.
    """
    add_column_if_missing(connection, "files", "content_hash", "TEXT")
    add_column_if_missing(connection, "files", "embedding_model", "TEXT")


#: Ordered steps. Append only — never renumber or edit a released step, because a
#: database that already ran it will not run it again.
MIGRATIONS: Sequence[Callable[[sqlite3.Connection], None]] = (_step_1_file_provenance,)

#: Where a fully migrated database stands.
LATEST_VERSION = len(MIGRATIONS)


def current_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def apply_migrations(connection: sqlite3.Connection) -> int:
    """Bring a database up to ``LATEST_VERSION``. Returns how many steps ran.

    Every step is re-runnable, so this runs the ones a database has not recorded
    and relies on each step's own check for the rest. A database created before
    this module existed reports version 0 with every table present; its steps find
    their work already done where it is, and do it where it is not.

    The ``BEGIN`` is explicit and load-bearing. Python's ``sqlite3`` starts an
    implicit transaction only for DML — ``INSERT``, ``UPDATE``, ``DELETE``,
    ``REPLACE`` — so ``ALTER TABLE`` and ``PRAGMA user_version`` run outside it and
    commit the moment they execute. Measured, not assumed: with the usual
    ``with connection:`` block, a step that raised left the column added *and* the
    version bumped, which is the one outcome that must not happen — the next
    startup would see a current version and skip the steps that never ran. With an
    explicit ``BEGIN`` both roll back.
    """
    version = current_version(connection)
    if version >= LATEST_VERSION:
        return 0

    ran = 0
    connection.execute("BEGIN")
    try:
        for step in MIGRATIONS[version:]:
            step(connection)
            ran += 1
        # PRAGMA does not accept a placeholder; the value is a computed int from
        # this module, never user input.
        connection.execute(f"PRAGMA user_version = {LATEST_VERSION}")
    except BaseException:
        connection.rollback()
        raise
    connection.commit()
    return ran
