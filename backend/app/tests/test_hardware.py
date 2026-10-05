"""Hardware probes use synthetic measurements, without user files or models."""

import subprocess
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import hardware


@pytest.mark.parametrize("page_size", [4096, 16384])
def test_mac_memory_uses_reported_page_size(page_size):
    text = (
        f"Mach Virtual Memory Statistics: (page size of {page_size} bytes)\n"
        "Pages free: 3.\nPages inactive: 5.\nPages wired down: 99."
    )
    assert hardware._mac_memory(str(2**30), text) == (2**30, 8 * page_size)


@pytest.mark.parametrize("total,pages", [(None, None), ("invalid", ""), ("0", ""), ("1024", "bad")])
def test_unknown_measurements_are_not_zero(total, pages):
    assert hardware._mac_memory(total, pages)[1] is None


def test_impossible_available_memory_is_unknown():
    pages = "page size of 4096 bytes\nPages free: 3.\nPages inactive: 5."
    assert hardware._mac_memory("1024", pages) == (1024, None)


def test_probe_commands_are_bounded_and_have_no_shell(monkeypatch):
    run = Mock(side_effect=subprocess.TimeoutExpired("probe", 1))
    monkeypatch.setattr(hardware.subprocess, "run", run)
    assert hardware._command(["/usr/bin/vm_stat"]) is None
    assert run.call_args.kwargs["timeout"] == 1
    assert run.call_args.kwargs["shell"] is False


def test_unsupported_host_reports_unknown_and_does_not_run_commands(monkeypatch, tmp_path):
    monkeypatch.setattr(hardware.platform, "system", lambda: "Windows")
    monkeypatch.setattr(hardware.platform, "machine", lambda: "AMD64")
    command = Mock(side_effect=AssertionError("unexpected command"))
    monkeypatch.setattr(hardware, "_command", command)
    info = hardware.inspect_hardware(tmp_path / "not-created")
    assert info.total_memory_bytes is None
    assert info.acceleration == "unknown"
    assert info.workspace_disk_free_bytes is not None
    assert not (tmp_path / "not-created").exists()


def test_api_exposes_only_measurements(monkeypatch, tmp_path):
    monkeypatch.setattr("app.api.runtime.data_directory", lambda: tmp_path)
    monkeypatch.setattr("app.api.runtime.inspect_hardware", lambda _: hardware.HardwareInfo(
        os="Darwin", architecture="arm64", total_memory_bytes=8 * 2**30,
    ))
    response = TestClient(app).get("/runtime/hardware")
    assert response.status_code == 200
    assert response.json()["total_memory_bytes"] == 8 * 2**30
    assert set(response.json()) == set(hardware.HardwareInfo.model_fields)
    assert str(tmp_path) not in response.text


def test_mac_probe_marks_estimate_and_candidate_without_claiming_speed(monkeypatch, tmp_path):
    monkeypatch.setattr(hardware.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(hardware.platform, "machine", lambda: "arm64")
    command = Mock(side_effect=[str(8 * 2**30),
        "page size of 16384 bytes\nPages free: 3.\nPages inactive: 5."])
    monkeypatch.setattr(hardware, "_command", command)
    info = hardware.inspect_hardware(tmp_path)
    assert info.available_memory_bytes == 8 * 16384
    assert info.memory_measurement == "free_and_inactive_estimate"
    assert info.acceleration == "apple_silicon_candidate"
    assert command.call_args_list[0].args[0] == ["/usr/sbin/sysctl", "-n", "hw.memsize"]


def test_disk_failure_keeps_measurement_unknown(monkeypatch, tmp_path):
    monkeypatch.setattr(hardware.platform, "system", lambda: "Other")
    monkeypatch.setattr(hardware.shutil, "disk_usage", Mock(side_effect=OSError("unavailable")))
    assert hardware.inspect_hardware(tmp_path).workspace_disk_free_bytes is None
