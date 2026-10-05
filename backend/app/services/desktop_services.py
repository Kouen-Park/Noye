"""Opt-in macOS prerequisites, with ownership limited to this backend session.

No shell, package-manager installer, port/name-based kill, model download or
index reset. Docker Desktop itself is external even when opened by Noye.
"""

import asyncio
import json
import os
import re
import signal
import socket
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from app.config import Settings, data_directory, get_settings
from app.logging_config import get_logger

Service = Literal["ollama", "qdrant"]
QDRANT_IMAGE = "qdrant/qdrant:v1.19.1"
OWNER_LABEL = "com.noye.desktop.workspace"
logger = get_logger("desktop_services")


class ServiceState(BaseModel):
    state: Literal["offline", "starting", "ready", "failed"] = "offline"
    ownership: Literal["none", "noye", "external"] = "none"
    detail: str = "Not running."
    can_start: bool = False


class ServiceStatus(BaseModel):
    ollama: ServiceState
    qdrant: ServiceState
    docker_installed: bool
    docker_open_available: bool


class PreparationError(Exception):
    """Only fixed, non-secret user-facing explanations may be passed here."""


def managed_endpoint(url: str, port: int) -> bool:
    """Never start a different service than the backend is configured to use."""
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "http"
            and parsed.hostname in {"localhost", "127.0.0.1"}
            and parsed.port == port
            and parsed.path in {"", "/"}
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def safe_child_environment() -> dict[str, str]:
    # Never pass backend credentials/control capability to prerequisite processes.
    allowed = {
        "HOME",
        "USER",
        "PATH",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "OLLAMA_MODELS",
        "HTTPS_PROXY",
        "NO_PROXY",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    }
    return {key: value for key, value in os.environ.items() if key in allowed}


class ServiceHost:
    """Small OS boundary replaced by fakes in tests; not an arbitrary CLI API."""

    def executable(self, name: Literal["ollama", "docker"]) -> Path | None:
        candidates = {
            "ollama": [
                "/Applications/Ollama.app/Contents/Resources/ollama",
                "/opt/homebrew/bin/ollama",
                "/usr/local/bin/ollama",
            ],
            "docker": [
                "/Applications/Docker.app/Contents/Resources/bin/docker",
                "/usr/local/bin/docker",
                "/opt/homebrew/bin/docker",
            ],
        }
        return next((Path(p) for p in candidates[name] if os.access(p, os.X_OK)), None)

    def docker_app(self) -> bool:
        return Path("/Applications/Docker.app").is_dir()

    def docker_environment(self) -> dict[str, str]:
        # Ignore remote Docker contexts/hosts. Support local Docker Desktop only.
        candidates = [Path.home() / ".docker/run/docker.sock", Path("/var/run/docker.sock")]
        endpoint = next((p for p in candidates if p.is_socket()), None)
        if endpoint is None:
            raise PreparationError(
                "Open Docker Desktop, wait until its engine is running, then retry."
            )
        return {**safe_child_environment(), "DOCKER_HOST": f"unix://{endpoint}"}

    def port_free(self, port: int) -> bool:
        try:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False

    async def ready(self, service: Service, settings: Settings) -> bool:
        base = settings.ollama_base_url if service == "ollama" else settings.qdrant_url
        path = "/api/tags" if service == "ollama" else "/healthz"
        try:
            async with httpx.AsyncClient(
                timeout=1.5,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream("GET", f"{base.rstrip('/')}{path}") as response:
                    if not response.is_success:
                        return False
                    if service == "qdrant":
                        return True
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 128_000:
                            return False
                    body = json.loads(content)
                    return isinstance(body, dict) and isinstance(body.get("models"), list)
        except (httpx.HTTPError, ValueError, TypeError):
            return False

    async def spawn_ollama(self, executable: Path):
        return await asyncio.create_subprocess_exec(
            str(executable),
            "serve",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env={
                **safe_child_environment(),
                "OLLAMA_HOST": "127.0.0.1:11434",
                "OLLAMA_NO_CLOUD": "1",
            },
        )

    async def command(
        self, executable: Path, args: list[str], timeout: float, env: dict[str, str] | None = None
    ) -> tuple[int, bytes]:
        spawning = asyncio.create_task(
            asyncio.create_subprocess_exec(
                str(executable),
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env or safe_child_environment(),
            )
        )
        try:
            process = await asyncio.shield(spawning)
        except asyncio.CancelledError:
            # Cancellation between OS spawn and receiving its handle must not
            # leave an untracked CLI child (e.g. an image-pull client).
            process = await spawning
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        try:
            async with asyncio.timeout(timeout):
                output = bytearray()
                while chunk := await process.stdout.read(4096):
                    output.extend(chunk)
                    if len(output) > 128_000:
                        raise PreparationError(
                            "Service returned too much output. Check it outside Noye."
                        )
                await process.wait()
                return process.returncode, bytes(output)
        finally:
            if process.returncode is None:
                process.kill()  # This exact CLI child only, never the daemon.
                await process.wait()

    async def stop_ollama(self, child) -> None:
        if child.returncode is None:
            try:
                child.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(child.wait(), 2)
            except TimeoutError:
                child.kill()
                await child.wait()


def workspace_storage(root: Path) -> tuple[str, Path]:
    """Persistent identity and isolated derived data; refuse escaping symlinks."""
    root = root.resolve()
    record = root / "desktop-service-id"
    storage = root / "qdrant/storage"
    if (
        record.is_symlink()
        or (root / "qdrant").is_symlink()
        or storage.is_symlink()
        or not storage.resolve().is_relative_to(root)
    ):
        raise PreparationError("Service storage contains an unsafe link. Restore it outside Noye.")
    try:
        if record.exists():
            if record.stat().st_size > 100:
                raise ValueError("invalid identity")
            identity = str(UUID(record.read_text().strip()))
        else:
            identity = str(uuid4())
            with record.open("x") as file:
                file.write(identity)
        storage.mkdir(parents=True, exist_ok=True)
        return identity, storage.resolve()
    except (OSError, ValueError):
        raise PreparationError(
            "Could not prepare Noye's Qdrant storage. Check app-data permissions."
        ) from None


def qdrant_create_args(identity: str, storage: Path) -> list[str]:
    # --mount is CSV; reject separator-containing paths instead of broadening it.
    if any(char in str(storage) for char in ',\n\r"'):
        raise PreparationError(
            "The app-data path is not supported by Docker. Use an external Qdrant."
        )
    return [
        "container",
        "create",
        "--name",
        f"noye-qdrant-{identity}",
        "--label",
        f"{OWNER_LABEL}={identity}",
        "--restart",
        "no",
        "--publish",
        "127.0.0.1:6333:6333",
        "--mount",
        f"type=bind,source={storage},target=/qdrant/storage",
        "--security-opt",
        "no-new-privileges:true",
        "--cap-drop",
        "ALL",
        "--log-opt",
        "max-size=5m",
        "--log-opt",
        "max-file=2",
        QDRANT_IMAGE,
    ]


def verify_container(info: dict, identity: str, storage: Path) -> str:
    """A familiar name/label alone never grants permission to start/stop it."""
    config, host = info.get("Config", {}), info.get("HostConfig", {})
    mounts = info.get("Mounts", [])
    container_id = info.get("Id", "")
    if not (
        isinstance(config, dict)
        and isinstance(host, dict)
        and isinstance(config.get("Labels"), dict)
        and isinstance(host.get("RestartPolicy"), dict)
        and isinstance(mounts, list)
        and len(mounts) == 1
        and isinstance(mounts[0], dict)
        and isinstance(info.get("State"), dict)
        and isinstance(info["State"].get("Running"), bool)
        and isinstance(container_id, str)
        and re.fullmatch(r"[a-f0-9]{64}", container_id)
        and config.get("Image") == QDRANT_IMAGE
        and config.get("Labels", {}).get(OWNER_LABEL) == identity
        and host.get("PortBindings") == {"6333/tcp": [{"HostIp": "127.0.0.1", "HostPort": "6333"}]}
        and host.get("RestartPolicy", {}).get("Name") == "no"
        and not host.get("Privileged")
        and mounts[0].get("Type") == "bind"
        and mounts[0].get("Source") == str(storage)
        and mounts[0].get("Destination") == "/qdrant/storage"
        and mounts[0].get("RW") is True
    ):
        raise PreparationError(
            "The existing Noye container has different settings. It was left untouched."
        )
    return container_id


class DesktopServices:
    def __init__(self, host: ServiceHost | None = None):
        self.host = host or ServiceHost()
        self.states = {name: ServiceState() for name in ("ollama", "qdrant")}
        self.task: asyncio.Task | None = None
        self.ollama_child = None
        self.qdrant_owned: tuple[Path, dict[str, str], str, str, Path] | None = None
        self.closing = False

    async def _ready(self, service: Service, settings: Settings) -> bool:
        # HTTP read timeouts reset for each chunk. An absolute deadline also
        # bounds a slow/streaming listener and DNS resolution.
        try:
            async with asyncio.timeout(2):
                return await self.host.ready(service, settings)
        except TimeoutError:
            return False

    async def status(self) -> ServiceStatus:
        settings = get_settings()
        for service, port in (("ollama", 11434), ("qdrant", 6333)):
            state = self.states[service]
            url = settings.ollama_base_url if service == "ollama" else settings.qdrant_url
            managed = sys.platform == "darwin" and managed_endpoint(url, port)
            state.can_start = (
                managed
                and self.host.executable("ollama" if service == "ollama" else "docker") is not None
            )
            if state.state == "starting":
                continue
            running = await self._ready(service, settings)
            owned = (
                self.ollama_child is not None and self.ollama_child.returncode is None
                if service == "ollama"
                else self.qdrant_owned is not None
            )
            ownership_unknown = False
            if service == "qdrant" and self.qdrant_owned is not None:
                executable, env, container_id, identity, storage = self.qdrant_owned
                try:
                    info = await self._inspect(executable, env, container_id, timeout=1)
                    if verify_container(info, identity, storage) != container_id:
                        raise PreparationError("Docker returned a different container identity.")
                    owned = info.get("State", {}).get("Running") is True
                except (PreparationError, OSError, TimeoutError, ValueError, KeyError, TypeError):
                    owned = False
                    ownership_unknown = True
            state.ownership = (
                "none"
                if ownership_unknown
                else "noye"
                if owned
                else "external"
                if running
                else "none"
            )
            if running:
                state.state = "ready"
                state.detail = (
                    "Running, but ownership could not be verified. Check Docker Desktop."
                    if ownership_unknown
                    else "Started by Noye; stops when this app quits."
                    if owned
                    else "Already running outside this Noye session; left running on quit."
                )
            elif state.state != "failed":
                state.state = "failed" if owned else "offline"
                state.detail = (
                    "Noye's service is not healthy. Use Retry to restart only that owned service."
                    if owned
                    else "Custom service address; start it outside Noye."
                    if not managed
                    else "Not running. Start explicitly when you need it."
                )
        return ServiceStatus(
            **self.states,
            docker_installed=self.host.executable("docker") is not None,
            docker_open_available=self.host.docker_app(),
        )

    async def start(self, service: Service, confirmed: bool) -> ServiceStatus:
        if not confirmed:
            raise HTTPException(400, "Confirm service preparation and any Qdrant image download.")
        if self.closing or (self.task and not self.task.done()):
            raise HTTPException(409, "A service operation is already running. Wait, then retry.")
        settings = get_settings()
        url, port = (
            (settings.ollama_base_url, 11434)
            if service == "ollama"
            else (settings.qdrant_url, 6333)
        )
        if sys.platform != "darwin" or not managed_endpoint(url, port):
            raise HTTPException(
                400, "Automatic preparation supports default local macOS services only."
            )
        # Reserve before the first await: two concurrent start requests cannot pass.
        self.states[service] = ServiceState(state="starting", detail="Checking prerequisites…")
        self.task = asyncio.create_task(self._prepare(service, settings))
        return ServiceStatus(
            **self.states,
            docker_installed=self.host.executable("docker") is not None,
            docker_open_available=self.host.docker_app(),
        )

    async def _prepare(self, service: Service, settings: Settings):
        try:
            if await self._ready(service, settings):
                return  # Reuse, never adopt or restart an external service.
            # Retry can recover an unhealthy child/container from this session,
            # but an external or previous-session service is never restarted.
            await self._release_owned(service)
            if not self.host.port_free(11434 if service == "ollama" else 6333):
                raise PreparationError(
                    "The service port is occupied but not ready. Noye did not stop it."
                )
            if service == "ollama":
                await self._ollama()
            else:
                await self._qdrant()
            async with asyncio.timeout(20):
                for _ in range(30):
                    if await self._ready(service, settings):
                        return
                    if service == "ollama" and self.ollama_child.returncode is not None:
                        raise PreparationError(
                            "Ollama stopped during startup. Open it outside Noye, then retry."
                        )
                    await asyncio.sleep(0.5)
            raise PreparationError(
                "The service did not become ready. Check it outside Noye, then retry."
            )
        except asyncio.CancelledError:
            self.states[service].detail = "Preparation stopped because Noye is closing."
            raise
        except (PreparationError, OSError, TimeoutError, ValueError, KeyError, TypeError) as error:
            self.states[service].state = "failed"
            self.states[service].detail = (
                str(error)
                if isinstance(error, PreparationError)
                else "Could not prepare the service. Check prerequisites and retry."
            )
            logger.warning(
                "Desktop service preparation failed service=%s cause=%s",
                service,
                type(error).__name__,
            )
        finally:
            if self.states[service].state == "starting":
                self.states[service].state = "offline"
            if not self.closing:
                await self.status()

    async def _ollama(self):
        executable = self.host.executable("ollama")
        if executable is None:
            raise PreparationError("Install Ollama for macOS, then reopen Settings and retry.")
        if self.ollama_child is not None:
            await self.host.stop_ollama(self.ollama_child)
        spawning = asyncio.create_task(self.host.spawn_ollama(executable))
        try:
            self.ollama_child = await asyncio.shield(spawning)
        except asyncio.CancelledError:
            self.ollama_child = await spawning
            raise  # Shutdown can now stop the exact child, even at this boundary.
        self.states["ollama"].ownership = "noye"
        self.states["ollama"].detail = "Starting local-only Ollama; no model is downloaded."

    async def _docker(self, executable, env, args, timeout=5) -> bytes:
        code, output = await self.host.command(executable, args, timeout, env)
        if code:
            raise PreparationError(
                "Docker could not complete this operation. Check Docker Desktop and retry."
            )
        return output

    async def _inspect(self, executable, env, identifier, timeout=5) -> dict:
        output = await self._docker(executable, env, ["container", "inspect", identifier], timeout)
        result = json.loads(output)
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            raise PreparationError(
                "Docker returned an invalid container description. Nothing was stopped."
            )
        return result[0]

    async def _qdrant(self):
        executable = self.host.executable("docker")
        if executable is None:
            raise PreparationError(
                "Install Docker Desktop for macOS to prepare Qdrant, or run it externally."
            )
        env = self.host.docker_environment()
        await self._docker(executable, env, ["info", "--format", "{{.ServerVersion}}"])
        identity, storage = workspace_storage(data_directory())
        name = f"noye-qdrant-{identity}"
        listed = (
            (
                await self._docker(
                    executable,
                    env,
                    [
                        "container",
                        "ls",
                        "--all",
                        "--no-trunc",
                        "--filter",
                        f"name=^/{name}$",
                        "--format",
                        "{{.ID}}",
                    ],
                )
            )
            .decode()
            .strip()
        )
        if listed:
            info = await self._inspect(executable, env, name)
            container_id = verify_container(info, identity, storage)
            if info.get("State", {}).get("Running"):
                raise PreparationError(
                    "A previous Qdrant session is running but not healthy. It was left untouched."
                )
        else:
            code, _ = await self.host.command(
                executable, ["image", "inspect", QDRANT_IMAGE], 5, env
            )
            if code:
                self.states[
                    "qdrant"
                ].detail = "Downloading the pinned Qdrant image. This may take several minutes."
                await self._docker(executable, env, ["image", "pull", "--quiet", QDRANT_IMAGE], 600)
            # Record a created (not running) container before starting it. A failed
            # start can never make an untracked running container via `docker run`.
            await self._docker(executable, env, qdrant_create_args(identity, storage))
            info = await self._inspect(executable, env, name)
            container_id = verify_container(info, identity, storage)
        self.qdrant_owned = (executable, env, container_id, identity, storage)
        self.states["qdrant"].ownership = "noye"
        self.states["qdrant"].detail = "Starting Qdrant with persistent Noye storage…"
        await self._docker(executable, env, ["container", "start", container_id])

    async def open_docker(self, confirmed: bool):
        if not confirmed or sys.platform != "darwin" or not self.host.docker_app():
            raise HTTPException(400, "Install Docker Desktop and confirm opening it first.")
        code, _ = await self.host.command(
            Path("/usr/bin/open"), ["-a", "/Applications/Docker.app"], 5
        )
        if code:
            raise HTTPException(503, "Could not open Docker Desktop. Open it manually, then retry.")
        # Docker is shared infrastructure, never owned or closed by Noye.
        return {"opened": True}

    async def open_guide(self, guide: Literal["ollama", "docker"]):
        # macOS WebKit does not automatically open target=_blank links without
        # a new-window handler. Only these two fixed official pages are allowed.
        urls = {
            "ollama": "https://ollama.com/download/mac",
            "docker": "https://docs.docker.com/desktop/setup/install/mac-install/",
        }
        if sys.platform != "darwin":
            raise HTTPException(400, "Setup guides currently support the macOS desktop app.")
        code, _ = await self.host.command(Path("/usr/bin/open"), [urls[guide]], 5)
        if code:
            raise HTTPException(
                503, "Could not open the guide. Open the official website manually."
            )
        return {"opened": True}

    async def shutdown(self):
        self.closing = True
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        results = await asyncio.gather(
            self._release_owned("ollama"),
            self._release_owned("qdrant"),
            return_exceptions=True,
        )
        if any(isinstance(result, Exception) for result in results):
            logger.warning(
                "Could not stop an owned desktop service; external services/data untouched"
            )

    async def _release_owned(self, service: Service):
        if service == "ollama" and self.ollama_child is not None:
            await self.host.stop_ollama(self.ollama_child)
            self.ollama_child = None
        if service == "qdrant" and self.qdrant_owned is not None:
            executable, env, container_id, identity, storage = self.qdrant_owned
            info = await self._inspect(executable, env, container_id, timeout=1.5)
            if verify_container(info, identity, storage) != container_id:
                raise PreparationError("Docker returned a different container identity.")
            # Immutable ID, not a reused name; no rm, volume prune or daemon stop.
            await self._docker(
                executable, env, ["container", "stop", "--timeout", "2", container_id], 4
            )
            self.qdrant_owned = None


manager = DesktopServices()
