"""Bounded, read-only service checks. Never generate, embed or download."""

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.config import data_directory, get_settings
from app.services.hardware import HardwareInfo, inspect_hardware
from app.services.model_recommendations import Recommendation, recommend_models
from app.services.runtime_checks import InstalledModel, ServicesOut, inspect_services, readiness

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/hardware", response_model=HardwareInfo)
def hardware() -> HardwareInfo:
    # Sync handler keeps bounded OS probes off the asynchronous event loop.
    return inspect_hardware(data_directory())


@router.get("/services", response_model=ServicesOut)
async def services() -> ServicesOut:
    return (await inspect_services(get_settings())).services


class SetupOut(BaseModel):
    hardware: HardwareInfo
    recommendation: Recommendation
    services: ServicesOut
    installed_models: list[InstalledModel]
    configured_generation_model: str
    gemini_configured: bool
    readiness: dict


@router.get("/setup", response_model=SetupOut)
async def setup() -> SetupOut:
    settings = get_settings()
    measured = await run_in_threadpool(inspect_hardware, data_directory())
    snapshot = await inspect_services(settings)
    return SetupOut(
        hardware=measured,
        recommendation=recommend_models(measured, settings.ollama_embedding_model),
        services=snapshot.services, installed_models=snapshot.installed_models,
        configured_generation_model=settings.ollama_model,
        gemini_configured=bool(settings.gemini_api_key.get_secret_value().strip()),
        readiness=readiness(settings, snapshot.services),
    )
