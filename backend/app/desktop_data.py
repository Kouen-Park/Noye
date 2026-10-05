"""Explicit, non-destructive import of a closed web workspace into desktop.

Copy originals and use SQLite's backup API (including committed WAL data).
Rewrite copied source paths only; never move/delete the original or copy secrets,
logs or derived vectors. Destination must be new. Rebuild the separate desktop
Qdrant collection explicitly after importing.
"""

import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


def import_workspace(source: Path, destination: Path) -> None:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    database = source / "app.db"
    if not database.is_file() or database.is_symlink():
        raise ValueError("The source must contain a regular Noye app.db file.")
    if destination.exists():
        raise ValueError("The destination already exists; importing never overwrites saved work.")
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Source and destination must be separate workspace directories.")
    for name in ("sources", "documents"):
        folder = source / name
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise ValueError("Workspace folders must be regular directories.")
        if folder.exists() and any(item.is_symlink() for item in folder.rglob("*")):
            raise ValueError("Workspace imports do not follow symbolic links.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".noye-import-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "workspace"
        staged.mkdir()
        for name in ("sources", "documents"):
            if (source / name).exists():
                shutil.copytree(source / name, staged / name)
            else:
                (staged / name).mkdir()
        with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(staged / "app.db")) as copied, copied:
                original.backup(copied)
                rows = copied.execute("SELECT id, path FROM files").fetchall()
                for file_id, saved_path in rows:
                    old = Path(saved_path)
                    if not old.is_absolute():
                        old = source.parent / old
                    try:
                        relative = old.resolve().relative_to(source / "sources")
                    except ValueError as error:
                        raise ValueError(
                            "A saved source path is outside the source workspace."
                        ) from error
                    copied.execute("UPDATE files SET path = ? WHERE id = ?", (
                        str(destination / "sources" / relative), file_id,
                    ))
        # Files and the copied database appear together. Refuse a destination
        # created during the import as well, never merging two workspaces.
        if destination.exists():
            raise ValueError("The destination was created during import; nothing was overwritten.")
        staged.rename(destination)
