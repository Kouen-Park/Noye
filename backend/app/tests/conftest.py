"""Unit tests use an explicit synthetic model identity; live tests resolve it."""

import pytest

from app.services import index_identity


@pytest.fixture(autouse=True)
def synthetic_index_identity(request, monkeypatch):
    # Existing live integration tests have a service-availability skip marker.
    # Do not turn their genuine model identity lookup into a mock when enabled.
    if any("Ollama" in str(marker.kwargs.get("reason", ""))
           for marker in request.node.iter_markers("skipif")):
        return
    monkeypatch.setattr(
        index_identity, "current_index_identity",
        lambda **kwargs: index_identity.build_identity("a" * 64),
    )
