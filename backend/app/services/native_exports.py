"""Save only through destinations selected by the desktop's native dialog.

This handler is private stdin IPC, never an HTTP endpoint accepting a path.
Backups stay on disk throughout; ZIP bytes do not cross the webview's memory.
"""

import os
import tempfile
from pathlib import Path

from app.config import data_directory
from app.db.database import database_path
from app.services.filing import rename_exclusive
from app.services.workspace_access import snapshot_access
from app.services.workspace_backup import create_backup


def dispatch(action, values):
    if action != "backup":
        raise ValueError("Unknown native export action.")
    destination = Path(values["destination"])
    if not destination.is_absolute():
        raise ValueError("Choose a destination in the native save dialog.")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Choose a new filename. Existing files are preserved.")
    if destination.resolve().is_relative_to(data_directory().resolve()):
        raise ValueError("Save the backup outside the active workspace.")
    # Stage on the destination volume. An exclusive rename publishes the
    # complete ZIP without overwriting a file created while backup was running.
    with tempfile.TemporaryDirectory(prefix=".noye-export-", dir=destination.parent) as temporary:
        archive = Path(temporary) / "workspace.noye.zip"
        with snapshot_access():
            create_backup(data_directory(), database_path(), archive)
        with archive.open("rb") as completed:
            os.fsync(completed.fileno())
        old_fd = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY)
        try:
            new_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                rename_exclusive(old_fd, archive.name, new_fd, destination.name)
            finally:
                os.close(new_fd)
        finally:
            os.close(old_fd)
    return "saved"
