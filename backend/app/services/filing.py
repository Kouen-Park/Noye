"""No-overwrite original moves with a durable recovery journal."""

import ctypes
import os
import sys
import uuid
from pathlib import PurePosixPath

from app.db.jobs import now
from app.services import ingestion
from app.services.folder_scanner import folder_lock
from app.services.folders import (
    SourceError,
    emit,
    excluded,
    parent_handle,
    read_original,
    root_record,
)


def rename_exclusive(old_fd, old_name, new_fd, new_name):
    """OS atomic rename with no replacement; exists() followed by rename is unsafe."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function, flag = libc.renameatx_np, 4  # RENAME_EXCL
    elif sys.platform.startswith("linux"):
        function, flag = libc.renameat2, 1  # RENAME_NOREPLACE
    else:
        raise SourceError("invalid_path", "Safe filing is currently supported on macOS/Linux.")
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    if function(old_fd, os.fsencode(old_name), new_fd, os.fsencode(new_name), flag) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _within(path, prefix):
    return prefix and PurePosixPath(path).is_relative_to(PurePosixPath(prefix))


def _validate(root, source, destination, manual):
    from app.models.files import FileType

    if not root["connected"] or root["availability"] != "available":
        raise SourceError("unavailable", "Reconnect this folder before filing.")
    if not manual and not root["processing"]:
        raise SourceError("busy", "Resume processing before automatic filing.")
    if not (
        _within(source["relative_path"], root["organization_prefix"])
        and _within(destination, root["organization_prefix"])
    ):
        raise SourceError(
            "out_of_scope", "Enable organization for both original and destination area."
        )
    if excluded(destination) or destination == source["relative_path"]:
        raise SourceError("invalid_path", "Choose a different source destination.")
    if FileType.from_filename(destination) != FileType.from_filename(source["relative_path"]):
        raise SourceError("invalid_path", "Filing cannot change the source format.")
    if source["manual_category"] and not manual:
        raise SourceError("out_of_scope", "This source has a manually fixed category.")


def _move(root, journal):
    _, digest, info = read_original(root, journal["old_path"])
    if digest != journal["version"] or (info.st_dev, info.st_ino) != (
        journal["device"],
        journal["inode"],
    ):
        raise SourceError("stale_version", "The original changed before filing.")
    with (
        parent_handle(root, journal["old_path"]) as (old_fd, old_name),
        parent_handle(root, journal["new_path"], create=True) as (new_fd, new_name),
    ):
        current = os.stat(old_name, dir_fd=old_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
        ):
            raise SourceError("stale_version", "The original changed before filing.")
        rename_exclusive(old_fd, old_name, new_fd, new_name)
        os.fsync(old_fd)
        os.fsync(new_fd)


def _finish(connection, journal, info):
    with connection:
        connection.execute(
            "UPDATE sources SET relative_path=?,device=?,inode=?,size=?,mtime_ns=?,"
            "manual_category=CASE WHEN ? THEN ? ELSE manual_category END WHERE file_id=?",
            (
                journal["new_path"],
                info.st_dev,
                info.st_ino,
                info.st_size,
                info.st_mtime_ns,
                journal["manual"],
                str(PurePosixPath(journal["new_path"]).parent),
                journal["source_id"],
            ),
        )
        connection.execute(
            "UPDATE files SET name=? WHERE id=?",
            (PurePosixPath(journal["new_path"]).name, journal["source_id"]),
        )
        connection.execute(
            "UPDATE filing_journal SET state='complete',error=NULL,updated_at=? WHERE id=?",
            (now(), journal["id"]),
        )
        source = dict(
            connection.execute(
                "SELECT * FROM sources WHERE file_id=?", (journal["source_id"],)
            ).fetchone()
        )
        emit(connection, "moved", source=source)


def file_source(connection, source_id, destination, expected_version, manual=False):
    with folder_lock:
        source = connection.execute(
            "SELECT * FROM sources WHERE file_id=?", (source_id,)
        ).fetchone()
        if not source:
            raise SourceError("unavailable", "This is not a connected-folder source.")
        source = dict(source)
        root = root_record(connection, source["root_id"])
        _validate(root, source, destination, manual)
        if source["version"] != expected_version:
            raise SourceError(
                "stale_version", "Classification refers to a superseded source version."
            )
        if connection.execute(
            "SELECT 1 FROM filing_journal WHERE source_id=? AND state IN ('prepared','moved')",
            (source_id,),
        ).fetchone():
            raise SourceError("busy", "A previous filing operation needs recovery.")
        ingestion.reserve_delete(source_id)
        identifier = str(uuid.uuid4())
        journal = {
            "id": identifier,
            "source_id": source_id,
            "root_id": root["id"],
            "old_path": source["relative_path"],
            "new_path": destination,
            "version": expected_version,
            "device": source["device"],
            "inode": source["inode"],
            "manual": manual,
        }
        try:
            with connection:
                connection.execute(
                    "INSERT INTO filing_journal(id,source_id,root_id,old_path,new_path,version,"
                    "device,inode,manual,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,"
                    "'prepared',?,?)",
                    (*journal.values(), now(), now()),
                )
            _move(root, journal)
            with connection:
                connection.execute(
                    "UPDATE filing_journal SET state='moved',updated_at=? WHERE id=?",
                    (now(), identifier),
                )
            _, digest, info = read_original(root, destination)
            if digest != expected_version:
                raise SourceError(
                    "stale_version", "Moved original changed. Reconcile before recovery."
                )
            _finish(connection, journal, info)
            return dict(
                connection.execute(
                    "SELECT * FROM filing_journal WHERE id=?", (identifier,)
                ).fetchone()
            )
        except (SourceError, OSError) as exc:
            # Exclusive rename reports EEXIST without moving anything. Close that
            # attempt so choosing a new destination does not require deleting the
            # colliding file. Other failures may follow a move: keep them recoverable.
            collision = isinstance(exc, FileExistsError)
            with connection:
                connection.execute(
                    "UPDATE filing_journal SET state=CASE WHEN ? THEN 'failed' ELSE state END,"
                    "error=?,updated_at=? WHERE id=?",
                    (
                        collision,
                        "Destination exists. Choose another name; original preserved."
                        if collision
                        else "Filing needs recovery. Check the original and destination.",
                        now(),
                        identifier,
                    ),
                )
            raise SourceError(
                "invalid_path", "Filing failed safely: check collisions and permissions."
            ) from exc
        finally:
            ingestion.release_file(source_id)


def recover_filing(connection):
    with folder_lock:
        journals = connection.execute(
            "SELECT * FROM filing_journal WHERE state IN ('prepared','moved')"
        )
        for row in journals.fetchall():
            journal = dict(row)
            if ingestion.is_ingesting(journal["source_id"]):
                continue
            try:
                root = root_record(connection, journal["root_id"])
                if not root["connected"]:
                    continue
                ingestion.reserve_delete(journal["source_id"])
                try:
                    try:
                        _, digest, info = read_original(root, journal["new_path"])
                    except SourceError:
                        source = {"relative_path": journal["old_path"], "manual_category": None}
                        _validate(root, source, journal["new_path"], journal["manual"])
                        _move(root, journal)
                        _, digest, info = read_original(root, journal["new_path"])
                    if digest != journal["version"] or (info.st_dev, info.st_ino) != (
                        journal["device"],
                        journal["inode"],
                    ):
                        raise SourceError(
                            "stale_version", "Destination belongs to a different source."
                        )
                    with parent_handle(root, journal["old_path"]) as (fd, name):
                        try:
                            os.stat(name, dir_fd=fd, follow_symlinks=False)
                        except FileNotFoundError:
                            pass
                        else:
                            raise SourceError(
                                "busy", "Both locations exist. Resolve the filing conflict."
                            )
                    _finish(connection, journal, info)
                finally:
                    ingestion.release_file(journal["source_id"])
            except (SourceError, OSError, ingestion.AlreadyIngesting):
                # Keep the journal pending, and retain its original bytes at either location.
                with connection:
                    connection.execute(
                        "UPDATE filing_journal SET error=? WHERE id=?",
                        (
                            "Filing recovery blocked. Check both paths and reconnect the folder.",
                            journal["id"],
                        ),
                    )
