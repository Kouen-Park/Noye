"""Native-selected roots and descriptor-relative access. No model paths."""

import hashlib
import os
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from app.config import data_directory, get_settings
from app.db.jobs import now


class SourceError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def relative_parts(relative):
    path = PurePosixPath(relative)
    if (
        not relative
        or path.is_absolute()
        or "\\" in relative
        or any(part in (".", "..") for part in relative.split("/"))
        or path.as_posix() != relative
        or "\x00" in relative
    ):
        raise SourceError("invalid_path", "Choose a relative path inside this folder.")
    return path.parts


def excluded(relative):
    parts = relative_parts(relative)
    return (
        parts[0].lower() in {"wiki", "documents", "app-data", "qdrant", "logs"}
        or any(part.startswith(".") or part.startswith("~") for part in parts)
        or parts[-1].lower().endswith((".tmp", ".part", ".swp", ".crdownload"))
        or parts[-1].lower() in {"app.db", "app.db-wal", "app.db-shm"}
    )


def root_record(connection, root_id):
    row = connection.execute("SELECT * FROM source_roots WHERE id=?", (root_id,)).fetchone()
    if not row:
        raise SourceError("unavailable", "This folder is not registered.")
    return dict(row)


@contextmanager
def root_handle(root):
    if not root["connected"]:
        raise SourceError("unavailable", "Reconnect this folder using the native picker.")
    try:
        path = Path(root["path"])
        if path.resolve(strict=True) != path:
            raise SourceError("invalid_path", "The registered folder path now contains a link.")
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise SourceError(
            "unavailable", "Folder unavailable. Check its drive and permissions."
        ) from exc
    try:
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != (root["device"], root["inode"]):
            raise SourceError("unavailable", "The folder identity changed. Re-select it.")
        yield fd
    finally:
        os.close(fd)


@contextmanager
def parent_handle(root, relative, *, create=False):
    parts = relative_parts(relative)
    with root_handle(root) as root_fd:
        fd = os.dup(root_fd)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            yield fd, parts[-1]
        finally:
            os.close(fd)


def read_original(root, relative):
    """Open every component without links; hash/stat the same bounded byte copy."""
    try:
        with parent_handle(root, relative) as (parent, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, "rb") as handle:
                before = os.fstat(handle.fileno())
                limit = get_settings().max_upload_mb * 1024 * 1024
                if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                    raise SourceError(
                        "invalid_path", "Source is not a regular supported-size file."
                    )
                data = handle.read(limit + 1)
                after = os.fstat(handle.fileno())

        def signature(value):
            return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns

        if len(data) > limit or signature(before) != signature(after):
            raise SourceError("busy", "The file is still changing. Wait for a stable write.")
        return data, hashlib.sha256(data).hexdigest(), after
    except FileNotFoundError as exc:
        raise SourceError(
            "unavailable", "The original is unavailable. Reconcile this folder."
        ) from exc
    except OSError as exc:
        raise SourceError(
            "invalid_path", "Cannot access this source safely. Check links/permissions."
        ) from exc


def emit(connection, kind, *, source=None, root_id=None, error=None):
    source = source or {}
    connection.execute(
        "INSERT INTO source_events(kind,source_id,root_id,relative_path,version,error,created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            kind,
            source.get("file_id"),
            root_id or source.get("root_id"),
            source.get("relative_path"),
            source.get("version"),
            error,
            now(),
        ),
    )


def register_root(connection, selected, kind, *, reconnect_id=None):
    """Only called by the private desktop stdin protocol, after native selection."""
    if kind not in {"managed", "connected"}:
        raise SourceError("invalid_path", "Unknown folder kind.")
    path = Path(selected).expanduser().resolve(strict=True)
    info = path.stat()
    if not path.is_dir() or path == Path(path.anchor):
        raise SourceError("invalid_path", "Choose a knowledge folder, not a filesystem root.")
    app_data = data_directory().resolve()
    if path.is_relative_to(app_data) or app_data.is_relative_to(path):
        raise SourceError("invalid_path", "Choose a folder separate from Noye application data.")
    for row in connection.execute("SELECT * FROM source_roots"):
        other = Path(row["path"])
        if str(path) != str(other) and (path.is_relative_to(other) or other.is_relative_to(path)):
            raise SourceError("invalid_path", "This overlaps another registered folder.")
    old = connection.execute("SELECT * FROM source_roots WHERE path=?", (str(path),)).fetchone()
    if reconnect_id:
        old = root_record(connection, reconnect_id)
        if old["kind"] != kind:
            raise SourceError("invalid_path", "Keep the registered folder kind when reconnecting.")
    identifier = old["id"] if old else str(uuid.uuid4())
    with connection:
        if old:
            connection.execute(
                "UPDATE source_roots SET path=?,device=?,inode=?,connected=1,"
                "availability='available',"
                "error=NULL,updated_at=? WHERE id=?",
                (str(path), info.st_dev, info.st_ino, now(), identifier),
            )
        else:
            connection.execute(
                "INSERT INTO source_roots(id,name,path,kind,device,inode,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (identifier, path.name, str(path), kind, info.st_dev, info.st_ino, now(), now()),
            )
        emit(connection, "reconnected" if old else "added", root_id=identifier)
    if kind == "managed" and not old:
        registered = root_record(connection, identifier)
        for relative in ("sources/inbox/.keep", "wiki/sources/.keep", "documents/.keep"):
            with parent_handle(registered, relative, create=True):
                pass
    return identifier


def update_root(
    connection,
    root_id,
    *,
    processing=None,
    organization_prefix=None,
    set_organization=False,
    disconnect=False,
):
    root = root_record(connection, root_id)
    if set_organization and organization_prefix is not None:
        relative_parts(organization_prefix)
        if excluded(organization_prefix):
            raise SourceError(
                "invalid_path", "Generated and application folders cannot be organized."
            )
    with connection:
        if processing is not None:
            connection.execute(
                "UPDATE source_roots SET processing=? WHERE id=?", (processing, root_id)
            )
            if bool(processing) != bool(root["processing"]):
                emit(connection, "resumed" if processing else "paused", root_id=root_id)
        if set_organization:
            connection.execute(
                "UPDATE source_roots SET organization_prefix=? WHERE id=?",
                (organization_prefix, root_id),
            )
        if disconnect:
            connection.execute(
                "UPDATE source_roots SET connected=0,availability='disconnected' WHERE id=?",
                (root_id,),
            )
            connection.execute(
                "UPDATE sources SET availability='disconnected' WHERE root_id=?", (root_id,)
            )
            emit(connection, "disconnected", root_id=root_id)
        connection.execute("UPDATE source_roots SET updated_at=? WHERE id=?", (now(), root_id))
    return root_record(connection, root["id"])


def output_path(connection, root_id, relative):
    """Application-only destination, never an LLM tool. B must use atomic revision saves."""
    if relative_parts(relative)[0] not in {"wiki", "documents"}:
        raise SourceError("invalid_path", "Generated output must stay in wiki or documents.")
    root = root_record(connection, root_id)
    with parent_handle(root, relative, create=True) as (fd, name):
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise SourceError("invalid_path", "Output cannot replace links or special files.")
        except FileNotFoundError:
            pass
    return Path(root["path"]) / relative


def validate_folder_retry(connection, file_id):
    source = connection.execute("SELECT * FROM sources WHERE file_id=?", (file_id,)).fetchone()
    if source is None:
        return
    root = root_record(connection, source["root_id"])
    if not root["processing"]:
        raise SourceError("unavailable", "Resume folder processing before retrying.")
    _, version, _ = read_original(root, source["relative_path"])
    if version != source["version"]:
        raise SourceError(
            "stale_version", "The original changed. Wait for stable folder reconciliation."
        )
