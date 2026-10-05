"""Bounded polling watcher, stable-write coalescing and startup reconciliation."""

import os
import stat
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import sources_dir
from app.db import files as file_store
from app.db import jobs
from app.db.database import connect, init_schema
from app.models.files import FileType
from app.services import ingestion
from app.services.folders import (
    SourceError,
    emit,
    excluded,
    read_original,
    root_handle,
    root_record,
)
from app.services.workspace_access import WorkspaceBusy, request_access

folder_lock = threading.RLock()
QUIET_SECONDS = 2.0
POLL_SECONDS = 1.0
MAX_ENTRIES = 100_000


def collect(root, *, show_excluded=False):
    inventory, tree = {}, []
    with root_handle(root) as root_fd:

        def walk(fd, prefix=""):
            with os.scandir(fd) as entries:
                for entry in entries:
                    relative = prefix + entry.name
                    if excluded(relative) or entry.is_symlink():
                        if show_excluded:
                            info = entry.stat(follow_symlinks=False)
                            tree.append(
                                {
                                    "relative_path": relative,
                                    "kind": "directory" if stat.S_ISDIR(info.st_mode) else "file",
                                    "excluded": True,
                                }
                            )
                        continue
                    info = entry.stat(follow_symlinks=False)
                    if len(tree) >= MAX_ENTRIES:
                        raise SourceError("unavailable", "Folder scan exceeds 100000 entries.")
                    if stat.S_ISDIR(info.st_mode):
                        tree.append({"relative_path": relative, "kind": "directory"})
                        child = os.open(
                            entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                        )
                        try:
                            walk(child, relative + "/")
                        finally:
                            os.close(child)
                    elif stat.S_ISREG(info.st_mode):
                        tree.append({"relative_path": relative, "kind": "file"})
                        try:
                            FileType.from_filename(entry.name)
                        except ValueError:
                            continue
                        inventory[relative] = (
                            info.st_dev,
                            info.st_ino,
                            info.st_size,
                            info.st_mtime_ns,
                        )

        walk(root_fd)
    return inventory, sorted(tree, key=lambda item: item["relative_path"])


def snapshot_bytes(file_id, file_type, data, version):
    target = sources_dir() / f"{file_id}__{version}.{file_type.value}"
    if not target.exists():
        try:
            with target.open("xb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            target.unlink(missing_ok=True)
            raise
    else:
        from app.services.integrity import hash_file

        if target.is_symlink() or hash_file(target) != version:
            raise SourceError("stale_version", "An internal original snapshot is damaged.")
    return target


class FolderScanner:
    def __init__(self, *, clock=time.monotonic, dispatch=None):
        self.clock = clock
        self.observed = {}
        self.absent = {}
        self.dispatch = dispatch

    def scan_root(self, connection, root_id):
        with folder_lock:
            return self._scan(connection, root_id)

    def _scan(self, connection, root_id):
        root = root_record(connection, root_id)
        if not root["connected"]:
            return []
        try:
            inventory, _ = collect(root)
        except (SourceError, OSError):
            message = "Folder unavailable. Check its drive, permissions or reconnect it."
            with connection:
                connection.execute(
                    "UPDATE source_roots SET availability='unavailable',error=?,"
                    "updated_at=? WHERE id=?",
                    (message, jobs.now(), root_id),
                )
                connection.execute(
                    "UPDATE sources SET availability='unavailable',error=? WHERE root_id=?",
                    (message, root_id),
                )
                if root["availability"] != "unavailable":
                    emit(connection, "unavailable", root_id=root_id, error=message)
            return []
        with connection:
            connection.execute(
                "UPDATE source_roots SET availability='available',error=NULL WHERE id=?", (root_id,)
            )
        rows = [
            dict(row)
            for row in connection.execute("SELECT * FROM sources WHERE root_id=?", (root_id,))
        ]
        by_path = {row["relative_path"]: row for row in rows}
        identities = Counter(signature[:2] for signature in inventory.values())
        queued = []
        timestamp = self.clock()
        for relative, signature in inventory.items():
            key = root_id, relative
            self.absent.pop(key, None)
            previous = self.observed.get(key)
            if previous is None or previous[0] != signature:
                self.observed[key] = signature, timestamp
                continue
            if timestamp - previous[1] < QUIET_SECONDS or not root["processing"]:
                continue
            source = by_path.get(relative)
            if source and ingestion.is_ingesting(source["file_id"]):
                continue
            if (
                source
                and source["availability"] == "available"
                and signature
                == (source["device"], source["inode"], source["size"], source["mtime_ns"])
            ):
                continue
            try:
                data, version, info = read_original(root, relative)
                if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != signature:
                    self.observed.pop(key, None)
                    continue
                if not data:
                    continue  # Empty files can be the first phase of a write.
                moved = False
                if source is None and identities[signature[:2]] == 1:
                    candidates = [
                        row
                        for row in rows
                        if row["relative_path"] not in inventory
                        and row["availability"] != "missing"
                        and (row["device"], row["inode"]) == signature[:2]
                        and row["version"] == version
                    ]
                    if len(candidates) == 1 and not ingestion.is_ingesting(
                        candidates[0]["file_id"]
                    ):
                        source = candidates[0]
                        moved = True
                file_id = source["file_id"] if source else file_store.new_file_id()
                changed = source is None or source["version"] != version
                if changed:
                    ingestion.reserve_ingestion(file_id)
                try:
                    file_type = FileType.from_filename(relative)
                    snapshot = (
                        snapshot_bytes(file_id, file_type, data, version) if changed else None
                    )
                    with connection:
                        if source is None:
                            connection.execute(
                                "INSERT INTO files(id,name,file_type,path,size,status,content_hash,"
                                "created_at,updated_at) VALUES (?,?,?,?,?,'UPLOADING',?,?,?)",
                                (
                                    file_id,
                                    Path(relative).name,
                                    file_type.value,
                                    str(snapshot),
                                    len(data),
                                    version,
                                    jobs.now(),
                                    jobs.now(),
                                ),
                            )
                            connection.execute(
                                "INSERT INTO sources(file_id,root_id,relative_path,"
                                "device,inode,size,"
                                "mtime_ns,version,availability) "
                                "VALUES (?,?,?,?,?,?,?,?,'available')",
                                (file_id, root_id, relative, *signature, version),
                            )
                        else:
                            connection.execute(
                                "UPDATE sources SET relative_path=?,device=?,inode=?,"
                                "size=?,mtime_ns=?,"
                                "version=?,availability='available',error=NULL WHERE file_id=?",
                                (relative, *signature, version, file_id),
                            )
                            connection.execute(
                                "UPDATE files SET name=?,size=? WHERE id=?",
                                (Path(relative).name, len(data), file_id),
                            )
                            if changed:
                                connection.execute(
                                    "UPDATE files SET path=?,status='UPLOADING',error=NULL "
                                    "WHERE id=?",
                                    (str(snapshot), file_id),
                                )
                        if changed:
                            connection.execute(
                                "INSERT OR IGNORE INTO source_versions VALUES (?,?,?,?)",
                                (file_id, version, str(snapshot), jobs.now()),
                            )
                            jobs.queue(connection, file_id, transaction=False)
                        if changed or moved or source["availability"] != "available":
                            current = dict(
                                connection.execute(
                                    "SELECT * FROM sources WHERE file_id=?", (file_id,)
                                ).fetchone()
                            )
                            emit(
                                connection,
                                "added"
                                if source is None
                                else "changed"
                                if changed
                                else "moved"
                                if moved
                                else "reconnected",
                                source=current,
                            )
                    if changed:
                        if self.dispatch:
                            self.dispatch(file_id)
                        queued.append(file_id)
                    if moved:
                        by_path.pop(source["relative_path"], None)
                except BaseException:
                    if changed:
                        ingestion.release_file(file_id)
                    raise
            except ingestion.AlreadyIngesting:
                continue  # Maintenance or another request owns the source.
            except (SourceError, OSError) as exc:
                if isinstance(exc, SourceError) and exc.code == "busy":
                    self.observed.pop(key, None)
                    continue
                message = (
                    "Source unavailable or still changing. Check permissions and retry a scan."
                )
                if source:
                    with connection:
                        connection.execute(
                            "UPDATE sources SET availability='unavailable',error=? WHERE file_id=?",
                            (message, source["file_id"]),
                        )
                        if source["availability"] != "unavailable":
                            emit(connection, "unavailable", source=source, error=message)
        # A missing declaration requires a complete accessible scan and a quiet interval.
        for relative, source in by_path.items():
            if relative in inventory or source["availability"] == "missing":
                continue
            key = root_id, relative
            first = self.absent.setdefault(key, timestamp)
            if timestamp - first < QUIET_SECONDS or ingestion.is_ingesting(source["file_id"]):
                continue
            with connection:
                connection.execute(
                    "UPDATE sources SET availability='missing',error=NULL WHERE file_id=?",
                    (source["file_id"],),
                )
                emit(connection, "missing", source=source)
        return queued


class FolderWatcher:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.pool = None
        self.scanner = None

    def start(self):
        self.stop_event = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="folder-ingestion")
        pool = self.pool
        self.scanner = FolderScanner(dispatch=lambda file_id: pool.submit(self.process, file_id))
        self.thread = threading.Thread(
            target=self.run,
            args=(self.stop_event, self.scanner),
            daemon=True,
            name="folder-reconciliation",
        )
        self.thread.start()

    def process(self, file_id):
        ingestion.ingest_in_background(file_id)

    def run(self, stop_event, scanner):
        from app.logging_config import get_logger
        from app.services.filing import recover_filing

        logger = get_logger("folder_watcher")
        while not stop_event.is_set():
            try:
                with request_access():
                    connection = connect()
                    try:
                        init_schema(connection)
                        recover_filing(connection)
                        roots = connection.execute("SELECT id FROM source_roots WHERE connected=1")
                        for root in roots.fetchall():
                            if stop_event.is_set():
                                break
                            scanner.scan_root(connection, root["id"])
                    finally:
                        connection.close()
            except WorkspaceBusy:
                pass
            except Exception:
                logger.exception("Folder reconciliation failed")
            stop_event.wait(POLL_SECONDS)

    def stop(self):
        self.stop_event.set()
        ingestion.cancel_all_ingestion()
        if self.thread:
            self.thread.join(timeout=3)
        if self.pool:
            self.pool.shutdown(wait=False, cancel_futures=False)


watcher = FolderWatcher()
