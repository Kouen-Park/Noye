import sqlite3

import pytest

from app.db.database import connect, init_schema
from app.desktop_data import import_workspace


def workspace(path):
    (path / "sources").mkdir(parents=True)
    original = path / "sources/example.txt"
    original.write_text("private source")
    connection = connect(path / "app.db")
    init_schema(connection)
    with connection:
        connection.execute("""
            INSERT INTO files (id, name, file_type, path, size, status, created_at, updated_at)
            VALUES ('source', 'example.txt', 'txt', ?, 14, 'READY', 'now', 'now')
        """, (str(original),))
        connection.execute("INSERT INTO conversations VALUES ('chat', 'Saved chat', 'now', 'now')")
        connection.execute("""
            INSERT INTO documents (id, title, content, created_at, updated_at)
            VALUES ('doc', 'Saved doc', 'edited document', 'now', 'now')
        """)
    return connection


def test_import_preserves_saved_work_and_original_with_committed_wal(tmp_path):
    source, destination = tmp_path / "web", tmp_path / "desktop"
    connection = workspace(source)
    (source / ".env").write_text("SECRET=never-copy")
    (source / "logs").mkdir()
    (source / "logs/noye.log").write_text("diagnostic")
    try:
        import_workspace(source, destination)
        with sqlite3.connect(destination / "app.db") as copied:
            assert copied.execute("SELECT title FROM conversations").fetchone()[0] == "Saved chat"
            assert copied.execute("SELECT content FROM documents").fetchone()[0] == (
                "edited document"
            )
            assert copied.execute("SELECT path FROM files").fetchone()[0] == str(
                destination / "sources/example.txt"
            )
        assert (destination / "sources/example.txt").read_text() == "private source"
        assert (source / "sources/example.txt").read_text() == "private source"
        assert connection.execute("SELECT path FROM files").fetchone()[0] == str(
            source / "sources/example.txt"
        )
        assert not (destination / ".env").exists()
        assert not (destination / "logs").exists()
    finally:
        connection.close()


def test_import_never_overwrites_existing_workspace(tmp_path):
    source, destination = tmp_path / "web", tmp_path / "desktop"
    workspace(source).close()
    destination.mkdir()
    (destination / "keep.txt").write_text("saved work")
    with pytest.raises(ValueError, match="already exists"):
        import_workspace(source, destination)
    assert (destination / "keep.txt").read_text() == "saved work"


def test_import_rejects_source_paths_outside_workspace(tmp_path):
    source, destination = tmp_path / "web", tmp_path / "desktop"
    connection = workspace(source)
    with connection:
        connection.execute("UPDATE files SET path = ?", (str(tmp_path / "outside.txt"),))
    connection.close()
    with pytest.raises(ValueError, match="outside"):
        import_workspace(source, destination)
    assert not destination.exists()


def test_import_does_not_follow_source_symlinks(tmp_path):
    source, destination = tmp_path / "web", tmp_path / "desktop"
    workspace(source).close()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (source / "sources/link.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="symbolic"):
        import_workspace(source, destination)
    assert not destination.exists()
