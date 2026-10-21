"""Desktop sidecar entry point; owns one loopback server, not external services.

Stdout is a newline-delimited readiness protocol. Logging goes to stderr/files.
The parent keeps stdin open: a shutdown line or EOF (parent exit/crash) asks
uvicorn to stop gracefully, with a parent-only deadline for blocked handlers.
No fixed port, no killing processes by port or name.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import threading
from pathlib import Path

_protocol_lock = threading.Lock()
PARENT_SHUTDOWN_SECONDS = 15


def finish_parent_shutdown() -> None:
    # asyncio.run can still wait for a blocked executor after uvicorn's grace
    # period. Match the native parent's 16-second fallback even if it crashed
    # and cannot enforce that bound. Exit this sidecar only; SQLite rolls back
    # open transactions and durable jobs recover at the next startup.
    # A daemon deadline disappears with a clean process exit. Do not cancel it
    # when asyncio.run returns: AnyIO worker threads can keep Python alive even
    # after the event loop has closed.
    threading.Event().wait(PARENT_SHUTDOWN_SECONDS)
    os._exit(0)


def protocol_message(value):
    with _protocol_lock:
        print(json.dumps(value), flush=True)


def configure_data_directory(directory: Path) -> Path:
    root = directory.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ["NOYE_DATA_DIR"] = str(root)
    # A developer's inherited DATABASE_URL must not make the desktop app open
    # the web database accidentally. Explicitly using the legacy dir is allowed.
    os.environ["DATABASE_URL"] = f"sqlite:///{root / 'app.db'}"
    return root


def native_reply(frame):
    """Private parent-only actions; never print configuration or input frames."""
    event = frame["event"]
    try:
        if event == "native_export":
            from app.services.native_exports import dispatch
        else:
            from app.services.native_folders import dispatch
        reply = {
            "event": event + "_result",
            "id": frame["id"],
            "result": dispatch(frame["action"], frame["values"]),
        }
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, AttributeError) as error:
        message = "Folder action failed. Check permissions."
        if event == "native_export":
            message = (
                str(error)
                if isinstance(error, ValueError)
                else (
                    "Could not save the backup. Finish processing, choose a new filename "
                    "and check folder permissions."
                )
            )
        reply = {"event": event + "_result", "id": frame["id"], "error": message}
    protocol_message(reply)


async def serve() -> None:
    # Import only after setting the storage root; settings/logging are cached.
    import uvicorn

    from app.main import app

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            access_log=False,
            loop="asyncio",
            http="h11",
            ws="none",
            timeout_graceful_shutdown=5,
        )
        server = uvicorn.Server(config)
        loop = asyncio.get_running_loop()

        def request_shutdown() -> None:
            from app.services.ingestion import cancel_all_ingestion

            cancel_all_ingestion()
            server.should_exit = True

        def watch_parent() -> None:
            try:
                from app.config import apply_desktop_configuration

                for line in sys.stdin:
                    if line.strip() == "shutdown":
                        break
                    try:
                        frame = json.loads(line)
                        if frame.get("event") == "native_export":
                            # Disk-heavy export must not block settings or the
                            # parent shutdown protocol. Rust permits one export.
                            threading.Thread(
                                target=native_reply, args=(frame,), daemon=True
                            ).start()
                            continue
                        if frame.get("event") == "native_folder":
                            native_reply(frame)
                            continue
                        if frame.get("event") != "configure":
                            continue
                        apply_desktop_configuration(frame["values"])
                        protocol_message({"event": "configured", "id": frame["id"]})
                    except (ValueError, KeyError, TypeError, AttributeError):
                        # Never log stdin or validation errors: they contain keys.
                        protocol_message({"event": "configuration_failed"})
            finally:
                threading.Thread(target=finish_parent_shutdown, daemon=True).start()
                if not loop.is_closed():
                    loop.call_soon_threadsafe(request_shutdown)

        threading.Thread(target=watch_parent, daemon=True).start()
        task = asyncio.create_task(server.serve(sockets=[listener]))
        while not server.started and not task.done():
            await asyncio.sleep(0.05)
        if server.started and not server.should_exit:
            protocol_message({"event": "ready", "url": f"http://127.0.0.1:{port}"})
        await task


def main() -> None:
    parser = argparse.ArgumentParser(description="Noye managed desktop backend")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--import-data",
        type=Path,
        help="Copy a closed web workspace to a NEW data dir, then exit",
    )
    parser.add_argument(
        "--restore-backup",
        type=Path,
        help="Validate a workspace backup into a NEW data dir, then exit",
    )
    args = parser.parse_args()
    if args.restore_backup is not None:
        from app.services.workspace_backup import restore_backup

        if args.import_data is not None:
            parser.error("Choose either import-data or restore-backup")
        try:
            report = restore_backup(args.restore_backup, args.data_dir)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(json.dumps(report))
        return
    if args.import_data is not None:
        from app.desktop_data import import_workspace

        try:
            import_workspace(args.import_data, args.data_dir)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(
            "Workspace copied. Originals are unchanged; rebuild the desktop index before searching."
        )
        return
    configure_data_directory(args.data_dir)
    asyncio.run(serve())


if __name__ == "__main__":
    main()
