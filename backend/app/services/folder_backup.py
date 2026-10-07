"""Portable authored assets from authorized roots, without external originals."""

import hashlib
import os
import sqlite3
import stat
import uuid
from pathlib import Path

from app.services.folders import SourceError, read_original, root_handle


def stage_assets(connection, staged):
    connection.row_factory = sqlite3.Row
    missing_roots, captured = [], []
    for row in connection.execute("SELECT * FROM source_roots ORDER BY id"):
        root = dict(row)
        try:
            with root_handle(root) as root_fd:
                paths = []

                def walk(fd, prefix, paths=paths):
                    with os.scandir(fd) as entries:
                        for entry in entries:
                            relative = prefix + "/" + entry.name
                            info = entry.stat(follow_symlinks=False)
                            if len(paths) > 100000 or entry.is_symlink():
                                raise SourceError(
                                    "invalid_path", "Wiki backup cannot follow links."
                                )
                            if stat.S_ISDIR(info.st_mode):
                                child = os.open(
                                    entry.name,
                                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=fd,
                                )
                                try:
                                    walk(child, relative)
                                finally:
                                    os.close(child)
                            elif stat.S_ISREG(info.st_mode):
                                paths.append(relative)
                            else:
                                raise SourceError(
                                    "invalid_path", "Wiki backup cannot copy special files."
                                )

                for name in ("wiki", "documents"):
                    try:
                        fd = os.open(
                            name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd
                        )
                    except FileNotFoundError:
                        continue
                    try:
                        walk(fd, name)
                    finally:
                        os.close(fd)
            for relative in paths:
                data, digest, _ = read_original(root, relative)
                target = staged / "knowledge" / root["id"] / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                captured.append((root, relative, digest))
        except (SourceError, OSError) as exc:
            if isinstance(exc, SourceError) and exc.code == "invalid_path":
                raise ValueError(str(exc)) from exc
            missing_roots.append(root["id"])
    # External writers do not share the application snapshot guard.
    for root, relative, digest in captured:
        try:
            _, current, _ = read_original(root, relative)
        except SourceError as exc:
            raise ValueError(
                "Authored knowledge changed or became unavailable during backup."
            ) from exc
        if current != digest:
            raise ValueError("Authored knowledge changed during backup. Retry when idle.")
    return missing_roots, captured


def verify_assets(captured):
    for root, relative, digest in captured:
        try:
            _, current, _ = read_original(root, relative)
        except SourceError as exc:
            raise ValueError("Authored knowledge became unavailable during backup.") from exc
        if current != digest:
            raise ValueError("Authored knowledge changed during backup. Retry when idle.")


def reconnect_assets(connection, root_id, workspace):
    """Copy recovered authored files only after native reconnection. Never overwrite edits."""
    from app.services.filing import rename_exclusive
    from app.services.folders import parent_handle, root_record

    root = root_record(connection, root_id)
    recovered = Path(workspace) / "knowledge" / root_id
    if not recovered.is_dir():
        return
    conflicts = 0
    for path in recovered.rglob("*"):
        if path.is_symlink():
            raise SourceError("invalid_path", "Recovered knowledge contains a link.")
        if not path.is_file():
            continue
        relative = path.relative_to(recovered).as_posix()
        if relative.split("/")[0] not in {"wiki", "documents"}:
            raise SourceError("invalid_path", "Recovered content is not an authored asset.")
        with parent_handle(root, relative, create=True) as (fd, name):
            temporary = ".noye-reconnect-" + uuid.uuid4().hex
            try:
                output_fd = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=fd,
                )
                with os.fdopen(output_fd, "wb") as output:
                    output.write(path.read_bytes())
                    output.flush()
                    os.fsync(output.fileno())
                try:
                    rename_exclusive(fd, temporary, fd, name)
                    os.fsync(fd)
                except FileExistsError:
                    _, digest, _ = read_original(root, relative)
                    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                        conflicts += 1
            finally:
                try:
                    os.unlink(temporary, dir_fd=fd)
                except FileNotFoundError:
                    pass
    if conflicts:
        with connection:
            connection.execute(
                "UPDATE source_roots SET error=? WHERE id=?",
                (
                    f"{conflicts} recovered Wiki/output conflicts retained in the restored "
                    "workspace. Existing edits were preserved.",
                    root_id,
                ),
            )
