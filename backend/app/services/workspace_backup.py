"""Portable workspace snapshots. Never copy credentials, models or vector storage."""

import hashlib
import json
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from app.db.database import init_schema
from app.db.migrations import LATEST_VERSION, current_version

FORMAT_VERSION = 1
MAX_ENTRIES = 100_000
MAX_BYTES = 20 * 1024**3
CHUNK_BYTES = 1024 * 1024


def _digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _portable(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != name
        or (
            name not in {"app.db", "manifest.json"}
            and (len(path.parts) < 2 or path.parts[0] not in {"sources", "documents"})
        )
    ):
        raise ValueError("The backup contains an invalid workspace path.")
    return path


def _validate_database(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ValueError("The backup database failed its integrity check.")
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if not {
        "files",
        "chunks",
        "conversations",
        "messages",
        "documents",
        "message_citations",
        "document_citations",
    }.issubset(tables):
        raise ValueError("The backup does not contain a complete Noye workspace.")
    custom = connection.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')")
    if custom.fetchone():
        raise ValueError("Workspace databases with custom triggers or views are not supported.")
    if current_version(connection) > LATEST_VERSION:
        raise ValueError("This backup requires a newer Noye version.")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("The backup database contains broken relationships.")


def create_backup(root: Path, database: Path, archive: Path) -> dict:
    """Caller holds snapshot_access, excluding requests and all library jobs."""
    root = root.resolve()
    if not database.is_file() or database.is_symlink():
        raise ValueError("The workspace database is unavailable.")
    if archive.exists() or archive.resolve().is_relative_to(root):
        raise ValueError("Backups must use a new file outside the active workspace.")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="noye-snapshot-") as temporary:
        staged = Path(temporary)
        for folder in ("sources", "documents"):
            source = root / folder
            if source.is_symlink() or (source.exists() and not source.is_dir()):
                raise ValueError("Workspace folders must be regular directories.")
            (staged / folder).mkdir()
            if source.exists():
                for item in source.rglob("*"):
                    if item.is_symlink() or not (item.is_dir() or item.is_file()):
                        raise ValueError("Workspace backups do not follow links or special files.")
                    if item.is_file():
                        before = _digest(item)
                        target = staged / folder / item.relative_to(source)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(item, target)
                        if _digest(target) != before or _digest(item) != before:
                            raise ValueError("An original changed during backup. Retry when idle.")
        database_uri = f"{database.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(database_uri, uri=True)) as original:
            with closing(sqlite3.connect(staged / "app.db")) as copied:
                original.backup(copied)
                _validate_database(copied)
                missing = []
                with copied:
                    for file_id, saved in copied.execute("SELECT id,path FROM files").fetchall():
                        path = Path(saved)
                        if not path.is_absolute():
                            from app.config import PROJECT_ROOT

                            path = PROJECT_ROOT / path
                        try:
                            relative = path.resolve().relative_to(root / "sources")
                        except ValueError as exc:
                            raise ValueError("A source path is outside this workspace.") from exc
                        portable = f"sources/{relative.as_posix()}"
                        _portable(portable)
                        copied.execute("UPDATE files SET path=? WHERE id=?", (portable, file_id))
                        if not (staged / portable).is_file():
                            missing.append(file_id)
                version = current_version(copied)
        inventory = {}
        for path in staged.rglob("*"):
            if path.is_file():
                inventory[path.relative_to(staged).as_posix()] = {
                    "size": path.stat().st_size,
                    "sha256": _digest(path),
                }
        if len(inventory) > MAX_ENTRIES or sum(v["size"] for v in inventory.values()) > MAX_BYTES:
            raise ValueError("The workspace exceeds the backup limit (20 GiB/100000 files).")
        for name, saved in inventory.items():
            if name != "app.db" and (
                not (root / name).is_file() or _digest(root / name) != saved["sha256"]
            ):
                raise ValueError("An original changed during backup. Retry when it is idle.")
        manifest = {
            "format": "noye-workspace",
            "version": FORMAT_VERSION,
            "schema_version": version,
            "created_at": datetime.now(UTC).isoformat(),
            "files": inventory,
            "missing_sources": missing,
        }
        created = False
        try:
            with archive.open("xb") as output:
                created = True
                with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as packed:
                    for name in inventory:
                        packed.write(staged / name, name)
                    packed.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        except BaseException:
            if created:
                archive.unlink(missing_ok=True)
            raise
        return manifest


def restore_backup(archive: Path, destination: Path) -> dict:
    """Validate in staging, reserve a NEW destination, then publish. No index use."""
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("The restore destination already exists; nothing will be overwritten.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".noye-restore-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "workspace"
        staged.mkdir()
        try:
            with zipfile.ZipFile(archive) as packed:
                entries = packed.infolist()
                names = [entry.filename for entry in entries]
                if len(entries) > MAX_ENTRIES + 1 or len(set(names)) != len(names):
                    raise ValueError("The backup has duplicate or excessive entries.")
                if sum(entry.file_size for entry in entries) > MAX_BYTES:
                    raise ValueError("The backup exceeds the 20 GiB restore limit.")
                for entry in entries:
                    _portable(entry.filename)
                    mode = entry.external_attr >> 16
                    if (
                        entry.is_dir()
                        or stat.S_ISLNK(mode)
                        or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                        or entry.flag_bits & 1
                    ):
                        raise ValueError("The backup contains unsupported entries.")
                meta = packed.getinfo("manifest.json")
                if meta.file_size > 32 * 1024 * 1024:
                    raise ValueError("The backup manifest is too large.")
                manifest = json.loads(packed.read(meta))
                if (
                    manifest["format"] != "noye-workspace"
                    or manifest["version"] != FORMAT_VERSION
                    or not isinstance(manifest["files"], dict)
                    or set(names) != set(manifest["files"]) | {"manifest.json"}
                    or "app.db" not in manifest["files"]
                ):
                    raise ValueError("The workspace backup manifest is invalid.")
                for name, expected in manifest["files"].items():
                    path = staged / _portable(name)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    entry = packed.getinfo(name)
                    if entry.file_size != expected["size"]:
                        raise ValueError("A backup file has the wrong size.")
                    with packed.open(entry) as source, path.open("xb") as target:
                        shutil.copyfileobj(source, target, CHUNK_BYTES)
                    if _digest(path) != expected["sha256"]:
                        raise ValueError("A backup file failed its checksum.")
        except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
            raise ValueError("The backup is incomplete or unreadable.") from exc
        try:
            with closing(sqlite3.connect(staged / "app.db")) as copied:
                _validate_database(copied)
                if current_version(copied) != manifest["schema_version"]:
                    raise ValueError("The backup schema version does not match its manifest.")
                init_schema(copied)
                actual_missing = []
                with copied:
                    for file_id, saved in copied.execute("SELECT id,path FROM files").fetchall():
                        relative = _portable(saved)
                        if relative.parts[0] != "sources":
                            raise ValueError("A restored source has an invalid location.")
                        missing = not (staged / relative).is_file()
                        if missing:
                            actual_missing.append(file_id)
                        copied.execute(
                            "UPDATE files SET path=? WHERE id=?",
                            (
                                str(destination / relative),
                                file_id,
                            ),
                        )
                        copied.execute(
                            "UPDATE files SET status='FAILED', error=?, chunk_count=0, "
                            "embedding_model=NULL, index_fingerprint=NULL, index_metadata=NULL "
                            "WHERE id=?",
                            (
                                "Original missing from backup."
                                if missing
                                else "Restored original. Rebuild the index before searching.",
                                file_id,
                            ),
                        )
                    copied.execute("DELETE FROM chunks")
                    # Future job tables must not replay work when a backup is opened.
                    if copied.execute("SELECT 1 FROM sqlite_master WHERE name='jobs'").fetchone():
                        copied.execute(
                            "UPDATE jobs SET state='interrupted', error='Restored from backup.' "
                            "WHERE state IN ('queued','running','cancelling')"
                        )
                if sorted(actual_missing) != sorted(manifest["missing_sources"]):
                    raise ValueError("The backup's missing-source report is inconsistent.")
        except sqlite3.DatabaseError as exc:
            raise ValueError("The backup database could not be restored.") from exc
        for name in ("sources", "documents"):
            (staged / name).mkdir(exist_ok=True)
        receipt = {
            "format": "noye-restored-workspace",
            "version": 1,
            "id": str(uuid.uuid4()),
            "restored_at": datetime.now(UTC).isoformat(),
            "missing_sources": actual_missing,
        }
        (staged / "noye-workspace.json").write_text(json.dumps(receipt), encoding="utf-8")
        # mkdir is exclusive, unlike rename over an existing empty directory.
        destination.mkdir()
        try:
            for item in staged.iterdir():
                item.rename(destination / item.name)
        except BaseException:
            shutil.rmtree(destination)
            raise
        return {
            "destination": str(destination),
            "missing_sources": actual_missing,
            "rebuild_required": True,
            "workspace_id": receipt["id"],
        }
