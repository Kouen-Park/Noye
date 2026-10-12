"""Capability-protected desktop service preparation; web mode stays read-only."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.models import desktop_control
from app.services.desktop_services import Service, ServiceStatus, manager

router = APIRouter(
    prefix="/services", tags=["desktop services"], dependencies=[Depends(desktop_control)]
)


class StartIn(BaseModel):
    service: Service
    confirmed: bool = False


class OpenIn(BaseModel):
    confirmed: bool = False


class GuideIn(BaseModel):
    guide: Literal["ollama", "docker"]


@router.get("", response_model=ServiceStatus)
async def status():
    return await manager.status()


@router.post("/start", response_model=ServiceStatus, status_code=202)
async def start(body: StartIn):
    return await manager.start(body.service, body.confirmed)


@router.post("/docker")
async def open_docker(body: OpenIn):
    return await manager.open_docker(body.confirmed)


@router.post("/guide")
async def open_guide(body: GuideIn):
    return await manager.open_guide(body.guide)
