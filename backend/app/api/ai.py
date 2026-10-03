"""Non-secret generation configuration for the provider selector."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import GenerationProvider, get_settings

router = APIRouter(prefix="/ai", tags=["ai"])


class ProviderOut(BaseModel):
    id: GenerationProvider
    model: str
    configured: bool


@router.get("/providers", response_model=list[ProviderOut])
def providers() -> list[ProviderOut]:
    settings = get_settings()
    return [
        ProviderOut(id="ollama", model=settings.ollama_model, configured=True),
        ProviderOut(
            id="gemini", model=settings.gemini_model,
            configured=bool(settings.gemini_api_key.get_secret_value().strip()),
        ),
    ]
