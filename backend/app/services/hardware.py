"""Read-only host measurements for desktop onboarding, not speed guarantees."""

import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class HardwareInfo(BaseModel):
    os: str
    architecture: str
    logical_cpus: int | None = Field(default=None, ge=1)
    total_memory_bytes: int | None = Field(default=None, gt=0)
    available_memory_bytes: int | None = Field(default=None, ge=0)
    memory_measurement: Literal["free_and_inactive_estimate", "unknown"] = "unknown"
    workspace_disk_free_bytes: int | None = Field(default=None, ge=0)
    acceleration: Literal["apple_silicon_candidate", "unknown"] = "unknown"


def _command(arguments: list[str]) -> str | None:
    try:
        return subprocess.run(
            arguments, capture_output=True, text=True, timeout=1,
            check=True, shell=False,
        ).stdout
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None


def _mac_memory(
    total_output: str | None, pages_output: str | None,
) -> tuple[int | None, int | None]:
    """Count free/inactive pages only; compressed/wired memory is not available."""
    total = None
    try:
        value = int(total_output or "")
        total = value if value > 0 else None
    except ValueError:
        pass
    page_size = re.search(r"page size of (\d+) bytes", pages_output or "")
    free = re.search(r"Pages free:\s+(\d+)\.", pages_output or "")
    inactive = re.search(r"Pages inactive:\s+(\d+)\.", pages_output or "")
    if not (total and page_size and free and inactive):
        return total, None
    size = int(page_size[1])
    available = (int(free[1]) + int(inactive[1])) * size
    if size <= 0 or available > total:
        return total, None
    return total, available


def inspect_hardware(workspace: Path) -> HardwareInfo:
    system, architecture = platform.system(), platform.machine()
    info = HardwareInfo(os=system, architecture=architecture, logical_cpus=os.cpu_count())
    if system == "Darwin":
        info.total_memory_bytes, info.available_memory_bytes = _mac_memory(
            _command(["/usr/sbin/sysctl", "-n", "hw.memsize"]),
            _command(["/usr/bin/vm_stat"]),
        )
        if info.available_memory_bytes is not None:
            info.memory_measurement = "free_and_inactive_estimate"
        # Architecture suggests a candidate, not tested Metal availability/VRAM.
        if architecture in {"arm64", "aarch64"}:
            info.acceleration = "apple_silicon_candidate"
    try:
        existing = workspace
        while not existing.exists() and existing != existing.parent:
            existing = existing.parent
        info.workspace_disk_free_bytes = shutil.disk_usage(existing).free
    except OSError:
        pass
    return info
