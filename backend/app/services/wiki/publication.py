"""Recoverable Markdown projection; disk edits become authored revisions, never overwritten."""

import os
import uuid
from contextlib import contextmanager
from pathlib import Path

from app.config import data_directory
from app.db import wiki as store


@contextmanager
def target_handle(connection, page):
    revision = store.revision(connection, page["current_revision"])
    relative = f"wiki/{page['kind']}s/{page['id']}.md"
    root_id = revision["metadata"].get("output_root_id")
    from app.services.folders import parent_handle, root_record

    if root_id:
        root = root_record(connection, root_id)
    else:
        path = data_directory().resolve()
        path.mkdir(parents=True, exist_ok=True)
        info = path.stat()
        root = {"path": str(path), "connected": True, "device": info.st_dev, "inode": info.st_ino}
    # A's descriptor-relative NOFOLLOW traversal holds the parent through the atomic rename.
    with parent_handle(root, relative, create=True) as target:
        yield target


def read_at(parent, name):
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    except FileNotFoundError:
        return None
    import stat

    with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32 * 1024 * 1024:
            raise ValueError("Wiki Markdown is not a supported regular file.")
        return handle.read()


def capture_disk_edit(connection, identifier):
    page = store.page(connection, identifier)
    if not page["current_revision"]:
        return
    with target_handle(connection, page) as (parent, name):
        content = read_at(parent, name)
    if content is None:
        return
    current = store.revision(connection, page["current_revision"])
    actual = store.digest(content)
    if actual in (page["published_hash"], store.digest(current["content"])):
        return
    links = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM wiki_relations WHERE revision_id=?", (current["id"],)
        )
    ]
    store.write_revision(
        connection,
        identifier,
        title=current["title"],
        content=content,
        metadata=current["metadata"],
        evidence=current["evidence"],
        expected=current["id"],
        origin="user",
        relations=links,
    )
    with connection:
        connection.execute(
            "UPDATE wiki_pages SET published_hash=? WHERE id=?", (actual, identifier)
        )


def materialize(connection, identifier):
    try:
        capture_disk_edit(connection, identifier)
        page = store.page(connection, identifier)
        if not page["current_revision"]:
            return
        revision = store.revision(connection, page["current_revision"])
        with target_handle(connection, page) as (parent, name):
            temporary = ".noye-wiki-" + uuid.uuid4().hex
            try:
                fd = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent,
                )
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(revision["content"])
                    handle.flush()
                    os.fsync(handle.fileno())
                before = read_at(parent, name)
                if before is not None and store.digest(before) not in (
                    page["published_hash"],
                    store.digest(revision["content"]),
                ):
                    capture_disk_edit(connection, identifier)
                    return
                os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass
        with connection:
            connection.execute(
                "UPDATE wiki_pages SET published_hash=?,publication_error=NULL WHERE id=?",
                (store.digest(revision["content"]), identifier),
            )
    except (OSError, ValueError):
        with connection:
            connection.execute(
                "UPDATE wiki_pages SET publication_error=? WHERE id=?",
                ("Markdown output unavailable. SQLite revisions are preserved.", identifier),
            )


def recover_publications(connection):
    for page in store.list_pages(connection, limit=1000):
        materialize(connection, page["id"])


def disk_path(connection, identifier):
    """Application-only diagnostic path, never returned to a model or web API."""
    page = store.page(connection, identifier)
    revision = store.revision(connection, page["current_revision"])
    root_id = revision["metadata"].get("output_root_id")
    if root_id:
        from app.services.folders import root_record

        root = Path(root_record(connection, root_id)["path"])
    else:
        root = data_directory()
    return root / "wiki" / (page["kind"] + "s") / (page["id"] + ".md")
