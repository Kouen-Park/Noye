"""Conservative Noye heuristics, not vendor RAM requirements or benchmarks."""

from typing import Literal

from pydantic import BaseModel

from app.services.hardware import HardwareInfo

GIB = 2**30
CATALOG_DATE = "2026-10-05"


class ModelCandidate(BaseModel):
    name: str
    approximate_download_bytes: int
    minimum_total_memory_bytes: int
    estimated_working_memory_bytes: int
    source_url: str


# Approximate decimal download sizes verified against Ollama's official library.
# RAM thresholds reserve space for the OS, app, local embeddings and short context.
# They are deliberately not the model's advertised maximum context capacity.
GENERATION_MODELS = tuple(ModelCandidate(
    name=f"qwen3.5:{tag}", approximate_download_bytes=size,
    minimum_total_memory_bytes=total * GIB,
    estimated_working_memory_bytes=int(working * GIB),
    source_url=f"https://ollama.com/library/qwen3.5:{tag}",
) for tag, size, total, working in [
    ("0.8b", 1_000_000_000, 8, 2.5),
    ("2b", 2_700_000_000, 12, 5),
    ("4b", 3_400_000_000, 16, 6),
    ("9b", 6_600_000_000, 32, 10),
])


class Recommendation(BaseModel):
    generation: ModelCandidate | None
    memory_status: Literal["estimated_fit", "close_apps", "unknown", "insufficient_total"]
    acceleration_unverified: bool
    embedding_model: str
    approximate_embedding_download_bytes: int | None
    workspace_disk_status: Literal["unknown", "low", "check_model_location"]
    catalog_checked_on: str = CATALOG_DATE


def recommend_models(hardware: HardwareInfo, embedding_model: str) -> Recommendation:
    total, available = hardware.total_memory_bytes, hardware.available_memory_bytes
    acceleration_unverified = hardware.acceleration != "apple_silicon_candidate"
    candidates = [model for model in GENERATION_MODELS
                  if total is not None and total >= model.minimum_total_memory_bytes]
    if acceleration_unverified:
        candidates = candidates[:1]
    fit = [model for model in candidates
           if available is not None and available >= model.estimated_working_memory_bytes]
    generation = fit[-1] if fit else candidates[0] if candidates else None
    if total is None or available is None:
        memory_status = "unknown"
    elif not candidates:
        memory_status = "insufficient_total"
    else:
        memory_status = "estimated_fit" if fit else "close_apps"
    embedding_bytes = 622_000_000 if embedding_model in {
        "embeddinggemma", "embeddinggemma:latest", "embeddinggemma:300m",
    } else None
    # Workspace disk is not necessarily Ollama's model-storage volume.
    disk_status = "unknown"
    if hardware.workspace_disk_free_bytes is not None:
        disk_status = "check_model_location"
        if generation and embedding_bytes is not None:
            reserve = 2 * (generation.approximate_download_bytes + embedding_bytes) + GIB
            if hardware.workspace_disk_free_bytes < reserve:
                disk_status = "low"
    return Recommendation(
        generation=generation, memory_status=memory_status,
        acceleration_unverified=acceleration_unverified, embedding_model=embedding_model,
        approximate_embedding_download_bytes=embedding_bytes,
        workspace_disk_status=disk_status,
    )
