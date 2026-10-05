"""Desktop workspace backups and copy-first restore, protected by its capability."""

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api.models import desktop_control
from app.config import data_directory
from app.db.database import database_path
from app.services.ingestion import MaintenanceBusy
from app.services.workspace_access import WorkspaceBusy, snapshot_access
from app.services.workspace_backup import MAX_BYTES, create_backup, restore_backup

router = APIRouter(prefix="/workspace", tags=["workspace"], dependencies=[Depends(desktop_control)])


@router.get("")
def workspace():
    return {
        "directory": str(data_directory()),
        "backup_format": 1,
        "restore_limit_bytes": MAX_BYTES,
    }


@router.post("/backup")
def backup():
    temporary = tempfile.TemporaryDirectory(prefix="noye-backup-")
    archive = Path(temporary.name) / "workspace.noye.zip"
    try:
        with snapshot_access():
            create_backup(data_directory(), database_path(), archive)
    except (WorkspaceBusy, MaintenanceBusy) as exc:
        temporary.cleanup()
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, OSError) as exc:
        temporary.cleanup()
        raise HTTPException(400, str(exc)) from exc
    except BaseException:
        temporary.cleanup()
        raise
    return FileResponse(
        archive,
        filename="noye-workspace.noye.zip",
        media_type="application/zip",
        background=BackgroundTask(temporary.cleanup),
    )


@router.post("/restore", status_code=201)
def restore(file: UploadFile):
    # No arbitrary destination path supplied by a browser. Native switching is
    # an additional explicit operation after this sibling workspace is verified.
    destination = data_directory().parent / f"noye-restored-{uuid.uuid4()}"
    try:
        with tempfile.TemporaryDirectory(prefix="noye-restore-upload-") as temporary:
            archive = Path(temporary) / "backup.zip"
            size = 0
            with archive.open("wb") as output:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError("The uploaded backup exceeds the 20 GiB restore limit.")
                    output.write(chunk)
            return restore_backup(archive, destination)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        file.file.close()
