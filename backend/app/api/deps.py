"""Shared request dependencies.

``get_db`` lives here rather than in one router so a second router does not have
to import the first just to reach the database. Tests that override it keep
working either way: FastAPI keys ``dependency_overrides`` on the function object,
and every router imports this same one.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from app.db.database import connect, init_schema


def get_db() -> Iterator[sqlite3.Connection]:
    """Per-request database connection."""
    connection = connect()
    try:
        init_schema(connection)
        yield connection
    finally:
        connection.close()
