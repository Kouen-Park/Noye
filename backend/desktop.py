"""Desktop sidecar entry point; owns one loopback server, not external services.

Stdout is a newline-delimited readiness protocol. Logging goes to stderr/files.
The parent keeps stdin open: a shutdown line or EOF (parent exit/crash) asks
uvicorn to stop gracefully. No fixed port, no killing processes by port or name.
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


def configure_data_directory(directory: Path) -> Path:
    root = directory.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ["NOYE_DATA_DIR"] = str(root)
    # A developer's inherited DATABASE_URL must not make the desktop app open
    # the web database accidentally. Explicitly using the legacy dir is allowed.
    os.environ["DATABASE_URL"] = f"sqlite:///{root / 'app.db'}"
    return root


async def serve() -> None:
    # Import only after setting the storage root; settings/logging are cached.
    import uvicorn

    from app.main import app

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        config = uvicorn.Config(
            app, host="127.0.0.1", port=port, access_log=False,
            loop="asyncio", http="h11", ws="none", timeout_graceful_shutdown=5,
        )
        server = uvicorn.Server(config)
        loop = asyncio.get_running_loop()

        def request_shutdown() -> None:
            server.should_exit = True

        def watch_parent() -> None:
            try:
                # Parent writes a line on normal exit; closed stdin means it
                # died. Neither requires a second public HTTP endpoint.
                sys.stdin.readline()
            finally:
                if not loop.is_closed():
                    loop.call_soon_threadsafe(request_shutdown)

        threading.Thread(target=watch_parent, daemon=True).start()
        task = asyncio.create_task(server.serve(sockets=[listener]))
        while not server.started and not task.done():
            await asyncio.sleep(0.05)
        if server.started and not server.should_exit:
            print(json.dumps({"event": "ready", "url": f"http://127.0.0.1:{port}"}), flush=True)
        await task


def main() -> None:
    parser = argparse.ArgumentParser(description="Noye managed desktop backend")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--import-data", type=Path,
        help="Copy a closed web workspace to a NEW data dir, then exit",
    )
    args = parser.parse_args()
    if args.import_data is not None:
        from app.desktop_data import import_workspace

        try:
            import_workspace(args.import_data, args.data_dir)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(
            "Workspace copied. Originals are unchanged; "
            "rebuild the desktop index before searching."
        )
        return
    configure_data_directory(args.data_dir)
    asyncio.run(serve())


if __name__ == "__main__":
    main()
