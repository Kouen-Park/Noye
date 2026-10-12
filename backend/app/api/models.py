"""Desktop-only model writes require the app's per-process capability."""

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.model_manager import manager


def desktop_control(x_noye_control: str = Header(default="")):
    token = os.environ.get("NOYE_CONTROL_TOKEN", "")
    if (
        not get_settings().noye_data_dir
        or not token
        or not hmac.compare_digest(token, x_noye_control)
    ):
        raise HTTPException(403, "Desktop management is only available in the desktop app.")


router = APIRouter(prefix="/models", tags=["models"], dependencies=[Depends(desktop_control)])


class ModelIn(BaseModel):
    model: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:/-]+$")


class PullIn(ModelIn):
    storage_path: str = Field(min_length=1, max_length=4096)
    confirmed_storage: bool


@router.get("/job")
async def job():
    return manager.job.copy()


@router.post("/pull")
async def pull(body: PullIn):
    if not body.confirmed_storage:
        raise HTTPException(400, "Confirm that this is Ollama's actual model-storage volume.")
    return await manager.pull(body.model, body.storage_path)


@router.post("/cancel")
async def cancel():
    return await manager.cancel()


@router.delete("")
async def delete(body: ModelIn):
    await manager.delete(body.model)
    return {"deleted": body.model}
