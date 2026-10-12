"""Recommendation thresholds are Noye heuristics, tested without local AI."""

import pytest

from app.services.hardware import HardwareInfo
from app.services.model_recommendations import GIB, recommend_models


def measured(total=16, available=8, acceleration="apple_silicon_candidate", disk=50):
    return HardwareInfo(
        os="Darwin", architecture="arm64",
        total_memory_bytes=None if total is None else int(total * GIB),
        available_memory_bytes=None if available is None else int(available * GIB),
        acceleration=acceleration,
        workspace_disk_free_bytes=None if disk is None else int(disk * GIB),
    )


@pytest.mark.parametrize("total,available,tag", [
    (8, 3, "0.8b"), (12, 5, "2b"), (16, 6, "4b"), (32, 10, "9b"),
    (32, 5, "2b"), (16, 2.5, "0.8b"),
])
def test_ram_and_current_headroom_both_limit_recommendations(total, available, tag):
    result = recommend_models(measured(total, available), "embeddinggemma")
    assert result.generation.name == f"qwen3.5:{tag}"
    assert result.memory_status == "estimated_fit"


def test_busy_host_keeps_small_candidate_but_requires_freeing_memory():
    result = recommend_models(measured(8, 1), "embeddinggemma")
    assert result.generation.name == "qwen3.5:0.8b"
    assert result.memory_status == "close_apps"


def test_unknown_available_memory_does_not_claim_fit():
    result = recommend_models(measured(16, None), "embeddinggemma")
    assert result.generation.name == "qwen3.5:0.8b"
    assert result.memory_status == "unknown"


@pytest.mark.parametrize("total,status", [(None, "unknown"), (4, "insufficient_total")])
def test_unknown_or_low_total_ram_has_no_generation_recommendation(total, status):
    result = recommend_models(measured(total, 3), "embeddinggemma")
    assert result.generation is None
    assert result.memory_status == status


def test_unverified_acceleration_only_considers_smallest_model():
    result = recommend_models(measured(64, 50, "unknown"), "embeddinggemma")
    assert result.generation.name == "qwen3.5:0.8b"
    assert result.acceleration_unverified


def test_custom_embedding_model_is_preserved_without_invented_size():
    result = recommend_models(measured(), "custom:embedding")
    assert result.embedding_model == "custom:embedding"
    assert result.approximate_embedding_download_bytes is None


@pytest.mark.parametrize("disk,status", [
    (None, "unknown"), (1, "low"), (50, "check_model_location"),
])
def test_disk_space_is_not_claimed_as_ollama_storage_verification(disk, status):
    result = recommend_models(measured(disk=disk), "embeddinggemma")
    assert result.workspace_disk_status == status


def test_threshold_boundary_and_catalog_metadata():
    result = recommend_models(measured(16, 6 - 1 / GIB), "embeddinggemma:latest")
    assert result.generation.name == "qwen3.5:2b"
    assert result.approximate_embedding_download_bytes == 622_000_000
    assert result.generation.approximate_download_bytes == 2_700_000_000
    assert result.generation.source_url == "https://ollama.com/library/qwen3.5:2b"
