"""Faked service/CLI boundaries: no real daemon, model or container mutation."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.services import desktop_services as module
from app.services.desktop_services import (
    OWNER_LABEL,
    QDRANT_IMAGE,
    DesktopServices,
    PreparationError,
    ServiceHost,
    managed_endpoint,
    qdrant_create_args,
    safe_child_environment,
    verify_container,
    workspace_storage,
)

IDENTITY = "acaf8272-2a4e-4c2c-bbb0-6fbb02684738"
CONTAINER = "a" * 64


def container_info(storage):
    return {
        "Id": CONTAINER,
        "Config": {"Image": QDRANT_IMAGE, "Labels": {OWNER_LABEL: IDENTITY}},
        "HostConfig": {
            "Privileged": False,
            "RestartPolicy": {"Name": "no"},
            "PortBindings": {"6333/tcp": [{"HostIp": "127.0.0.1", "HostPort": "6333"}]},
        },
        "Mounts": [
            {"Type": "bind", "Source": str(storage), "Destination": "/qdrant/storage", "RW": True}
        ],
        "State": {"Running": False},
    }


class FakeHost(ServiceHost):
    def __init__(self, root):
        self.running = set()
        self.calls = []
        self.children = []
        self.installed = True
        self.free = True
        self.created = False
        self.image = False
        self.fail_start = False
        self.info = container_info(root / "qdrant/storage")
        self.block_pull = None

    def executable(self, name):
        return Path(f"/synthetic/{name}") if self.installed else None

    def docker_app(self):
        return self.installed

    def docker_environment(self):
        return {"DOCKER_HOST": "unix:///synthetic/docker.sock"}

    def port_free(self, port):
        self.calls.append(["port", port])
        return self.free

    async def ready(self, service, settings):
        return service in self.running

    async def spawn_ollama(self, executable):
        child = SimpleNamespace(returncode=None)
        self.children.append(child)
        self.running.add("ollama")
        self.calls.append(["ollama", "serve"])
        return child

    async def stop_ollama(self, child):
        child.returncode = 0
        self.running.discard("ollama")
        self.calls.append(["stop-own-ollama"])

    async def command(self, executable, args, timeout, env=None):
        self.calls.append(args)
        if args[:2] == ["container", "ls"]:
            return 0, CONTAINER.encode() if self.created else b""
        if args[:2] == ["container", "inspect"]:
            return 0, json.dumps([self.info]).encode()
        if args[:2] == ["image", "inspect"]:
            return (0 if self.image else 1), b""
        if args[:2] == ["image", "pull"] and self.block_pull is not None:
            await self.block_pull.wait()
        if args[:2] == ["container", "create"]:
            self.created = True
        if args[:2] == ["container", "start"]:
            if self.fail_start:
                return 1, b"private error never shown"
            self.running.add("qdrant")
            self.info["State"]["Running"] = True
        if args[:2] == ["container", "stop"]:
            self.running.discard("qdrant")
            self.info["State"]["Running"] = False
        return 0, b"ok"


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    monkeypatch.setattr(module.sys, "platform", "darwin")
    monkeypatch.setattr(module, "data_directory", lambda: tmp_path)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(_env_file=None))
    (tmp_path / "desktop-service-id").write_text(IDENTITY)
    host = FakeHost(tmp_path)
    return DesktopServices(host), host, tmp_path


@pytest.mark.parametrize("url", ["http://localhost:6333", "http://127.0.0.1:6333/"])
def test_accepts_only_default_local_endpoints(url):
    assert managed_endpoint(url, 6333)


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost:6333",
        "http://remote.example:6333",
        "http://localhost:6334",
        "http://user:secret@localhost:6333",
        "http://localhost:6333/a",
        "http://localhost:6333/?x=1",
        "http://localhost:6333/#a",
        "http://localhost:invalid",
    ],
)
def test_remote_or_advanced_endpoints_are_not_managed(url):
    assert not managed_endpoint(url, 6333)


def test_command_plan_is_pinned_local_persistent_and_shell_free(tmp_path):
    args = qdrant_create_args(IDENTITY, tmp_path / "storage with spaces")
    assert args[-1] == QDRANT_IMAGE
    assert args[args.index("--publish") + 1] == "127.0.0.1:6333:6333"
    assert not any("6334" in arg for arg in args)
    assert "--rm" not in args and "--privileged" not in args
    assert "target=/qdrant/storage" in args[args.index("--mount") + 1]
    with pytest.raises(PreparationError):
        qdrant_create_args(IDENTITY, Path("/bad,path"))


def test_child_environment_drops_secrets_and_remote_docker(monkeypatch):
    for key in [
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "NOYE_CONTROL_TOKEN",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_CERT_PATH",
    ]:
        monkeypatch.setenv(key, "synthetic-private")
    assert "synthetic-private" not in safe_child_environment().values()


def test_storage_identity_survives_relaunch_without_deleting_data(tmp_path):
    identity, storage = workspace_storage(tmp_path)
    marker = storage / "keep-index"
    marker.write_text("derived data")
    assert workspace_storage(tmp_path) == (identity, storage)
    assert marker.read_text() == "derived data"


def test_storage_refuses_escaping_links_and_invalid_identity(tmp_path):
    (tmp_path / "qdrant").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(PreparationError):
        workspace_storage(tmp_path)
    (tmp_path / "qdrant").unlink()
    (tmp_path / "desktop-service-id").write_text("not a uuid")
    with pytest.raises(PreparationError):
        workspace_storage(tmp_path)


@pytest.mark.parametrize("field", ["label", "image", "mount", "binding", "id", "malformed"])
def test_name_or_label_alone_does_not_grant_container_ownership(tmp_path, field):
    info = container_info(tmp_path)
    assert verify_container(info, IDENTITY, tmp_path) == CONTAINER
    invalid = deepcopy(info)
    if field == "label":
        invalid["Config"]["Labels"][OWNER_LABEL] = "other"
    elif field == "image":
        invalid["Config"]["Image"] = "different:latest"
    elif field == "mount":
        invalid["Mounts"][0]["Source"] = "/other-user-data"
    elif field == "binding":
        invalid["HostConfig"]["PortBindings"]["6333/tcp"][0]["HostIp"] = "0.0.0.0"
    elif field == "id":
        invalid["Id"] = "arbitrary-name"
    else:
        invalid["Config"] = None
    with pytest.raises(PreparationError):
        verify_container(invalid, IDENTITY, tmp_path)


def test_ready_external_services_are_reused_never_stopped(prepared):
    manager, host, _ = prepared

    async def run():
        host.running.update(["ollama", "qdrant"])
        for service in ("ollama", "qdrant"):
            await manager.start(service, True)
            await manager.task
        status = await manager.status()
        assert status.ollama.ownership == status.qdrant.ownership == "external"
        await manager.shutdown()
        assert not host.calls
        assert host.running == {"ollama", "qdrant"}

    asyncio.run(run())


def test_owned_services_stop_by_handle_and_id_without_removing_storage(prepared):
    manager, host, root = prepared

    async def run():
        for service in ("ollama", "qdrant"):
            await manager.start(service, True)
            await manager.task
        status = await manager.status()
        assert status.ollama.ownership == status.qdrant.ownership == "noye"
        await manager.shutdown()
        assert ["container", "stop", "--timeout", "2", CONTAINER] in host.calls
        assert ["stop-own-ollama"] in host.calls
        assert not host.running
        assert (root / "qdrant/storage").is_dir()
        assert not any(call[:2] in [["container", "rm"], ["volume", "rm"]] for call in host.calls)

    asyncio.run(run())


def test_existing_stopped_container_is_verified_and_reused(prepared):
    manager, host, _ = prepared
    host.created = True

    async def run():
        await manager.start("qdrant", True)
        await manager.task
        assert manager.states["qdrant"].state == "ready"
        assert not any(call[:2] == ["container", "create"] for call in host.calls)
        assert not any(call[:2] == ["image", "pull"] for call in host.calls)
        await manager.shutdown()

    asyncio.run(run())


def test_foreign_or_previous_unhealthy_container_is_not_started_or_stopped(prepared):
    manager, host, _ = prepared
    host.created = True
    host.info["State"]["Running"] = True

    async def run():
        await manager.start("qdrant", True)
        await manager.task
        assert manager.states["qdrant"].state == "failed"
        assert "left untouched" in manager.states["qdrant"].detail
        await manager.shutdown()
        assert not any(
            call[:2] in [["container", "start"], ["container", "stop"]] for call in host.calls
        )

    asyncio.run(run())


def test_start_failure_is_sanitized_and_retry_recovers_only_owned_container(prepared):
    manager, host, _ = prepared

    async def run():
        host.fail_start = True
        await manager.start("qdrant", True)
        await manager.task
        assert manager.states["qdrant"].state == "failed"
        assert "private error" not in manager.states["qdrant"].detail
        host.fail_start = False
        await manager.start("qdrant", True)
        await manager.task
        assert manager.states["qdrant"].state == "ready"
        assert ["container", "stop", "--timeout", "2", CONTAINER] in host.calls
        await manager.shutdown()

    asyncio.run(run())


def test_busy_port_does_not_kill_an_unknown_process(prepared):
    manager, host, _ = prepared
    host.free = False

    async def run():
        await manager.start("ollama", True)
        await manager.task
        assert "occupied" in manager.states["ollama"].detail
        await manager.shutdown()
        assert host.calls == [["port", 11434]]

    asyncio.run(run())


def test_confirmation_reservation_and_shutdown_cancel(prepared):
    manager, host, _ = prepared

    async def run():
        with pytest.raises(HTTPException) as error:
            await manager.start("qdrant", False)
        assert error.value.status_code == 400 and not host.calls
        host.block_pull = asyncio.Event()
        await manager.start("qdrant", True)
        with pytest.raises(HTTPException) as error:
            await manager.start("ollama", True)
        assert error.value.status_code == 409
        await asyncio.sleep(0)
        await manager.shutdown()
        assert manager.task.done()
        assert not any(call[:2] == ["container", "start"] for call in host.calls)

    asyncio.run(run())


def test_tampered_owned_container_is_not_stopped(prepared):
    manager, host, _ = prepared

    async def run():
        await manager.start("qdrant", True)
        await manager.task
        host.info["Mounts"][0]["Source"] = "/other-data"
        await manager.shutdown()
        assert "qdrant" in host.running
        assert not any(call[:2] == ["container", "stop"] for call in host.calls)

    asyncio.run(run())


def test_open_docker_never_adopts_or_closes_shared_engine(prepared):
    manager, host, _ = prepared

    async def run():
        assert await manager.open_docker(True) == {"opened": True}
        await manager.shutdown()
        assert host.calls == [["-a", "/Applications/Docker.app"]]

    asyncio.run(run())


@pytest.mark.parametrize(
    "guide,url",
    [
        ("ollama", "https://ollama.com/download/mac"),
        ("docker", "https://docs.docker.com/desktop/setup/install/mac-install/"),
    ],
)
def test_native_setup_guides_only_open_fixed_official_pages(prepared, guide, url):
    manager, host, _ = prepared
    assert asyncio.run(manager.open_guide(guide)) == {"opened": True}
    assert host.calls == [[url]]


def test_service_routes_require_desktop_capability_and_confirmation(monkeypatch, tmp_path):
    monkeypatch.setenv("NOYE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NOYE_CONTROL_TOKEN", "synthetic-capability")
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        for method, path in [
            ("GET", "/services"),
            ("POST", "/services/start"),
            ("POST", "/services/docker"),
            ("POST", "/services/guide"),
        ]:
            assert client.request(method, path).status_code == 403
            assert (
                client.request(method, path, headers={"X-Noye-Control": "wrong"}).status_code == 403
            )
        result = client.post(
            "/services/start",
            headers={"X-Noye-Control": "synthetic-capability"},
            json={"service": "qdrant"},
        )
        assert result.status_code == 400
        assert (
            client.post(
                "/services/guide",
                headers={"X-Noye-Control": "synthetic-capability"},
                json={"guide": "https://arbitrary.example"},
            ).status_code
            == 422
        )
    finally:
        get_settings.cache_clear()


def test_health_probe_is_get_only_bounded_and_no_proxy(monkeypatch):
    original = httpx.AsyncClient
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"models": []})

    options = []

    def client(**kwargs):
        options.append(kwargs)
        return original(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", client)

    async def run():
        host = ServiceHost()
        assert await host.ready("ollama", Settings(_env_file=None))
        assert await host.ready("qdrant", Settings(_env_file=None))

    asyncio.run(run())
    assert all(request.method == "GET" for request in requests)
    assert options == [dict(timeout=1.5, follow_redirects=False, trust_env=False)] * 2


def test_owned_stopped_container_does_not_claim_an_external_listener(prepared):
    manager, host, root = prepared
    manager.qdrant_owned = (
        Path("/synthetic/docker"),
        {},
        CONTAINER,
        IDENTITY,
        root / "qdrant/storage",
    )
    host.running.add("qdrant")
    status = asyncio.run(manager.status())
    assert status.qdrant.ownership == "external"


@pytest.mark.parametrize("reason", ["output", "timeout", "cancel"])
def test_cli_output_timeout_and_cancellation_kill_only_the_exact_child(monkeypatch, reason):
    class FakeProcess:
        def __init__(self):
            self.returncode = None
            self.stdout = self
            self.killed = False

        async def read(self, size):
            if reason == "output":
                return b"x" * 128_001
            await asyncio.Event().wait()

        def kill(self):
            self.killed = True
            self.returncode = -9

        async def wait(self):
            return self.returncode

    child = FakeProcess()
    seen = []

    async def spawn(*args, **kwargs):
        seen.append((args, kwargs))
        return child

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)

    async def run():
        task = asyncio.create_task(
            ServiceHost().command(Path("/synthetic/docker"), ["image", "pull", QDRANT_IMAGE], 0.01)
        )
        if reason == "cancel":
            await asyncio.sleep(0.005)
            task.cancel()
        expected = (
            PreparationError
            if reason == "output"
            else TimeoutError
            if reason == "timeout"
            else asyncio.CancelledError
        )
        with pytest.raises(expected):
            await task
        assert child.killed

    asyncio.run(run())
    assert seen[0][0] == ("/synthetic/docker", "image", "pull", QDRANT_IMAGE)
    assert "shell" not in seen[0][1]


def test_cancellation_during_ollama_spawn_keeps_the_child_tracked(prepared):
    manager, host, _ = prepared

    async def run():
        entered, proceed = asyncio.Event(), asyncio.Event()
        original = host.spawn_ollama

        async def spawn(executable):
            entered.set()
            await proceed.wait()
            return await original(executable)

        host.spawn_ollama = spawn
        await manager.start("ollama", True)
        await entered.wait()
        manager.task.cancel()
        proceed.set()
        await manager.shutdown()
        assert host.children[0].returncode == 0
        assert ["stop-own-ollama"] in host.calls

    asyncio.run(run())
