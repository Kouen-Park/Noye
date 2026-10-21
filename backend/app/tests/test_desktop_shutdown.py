"""An uncooperative request must not orphan the managed backend after parent EOF."""

import json
import os
import queue
import subprocess
import sys
import threading
import time

import httpx

from app.config import PROJECT_ROOT


def test_parent_eof_bounds_a_blocked_executor_and_rolls_back_its_edit(tmp_path):
    root = tmp_path / "workspace"
    marker = tmp_path / "blocked"
    launcher = tmp_path / "blocked_backend.py"
    launcher.write_text(
        """import importlib.util, sqlite3, sys, threading
from pathlib import Path
spec = importlib.util.spec_from_file_location('managed_desktop', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.configure_data_directory(Path(sys.argv[2]))
from app.main import app
from app.db.database import database_path
@app.get('/qa-blocked-request')
def blocked(identifier: str):
    def hold_transaction():
        with sqlite3.connect(database_path()) as connection:
            connection.execute('UPDATE documents SET content=? WHERE id=?',
                               ('uncommitted replacement', identifier))
            Path(sys.argv[3]).write_text('transaction held')
            threading.Event().wait()
    return hold_transaction()
sys.argv = [sys.argv[0], '--data-dir', sys.argv[2]]
module.main()
""".replace(
            "Path(sys.argv[3]).write_text('transaction held')",
            f"Path({str(marker)!r}).write_text('transaction held')",
        )
    )
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "backend"), "LOG_TO_FILE": "false"}

    def start(command):
        child = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(child.stdout.readline()), daemon=True).start()
        try:
            ready = json.loads(lines.get(timeout=20))
            assert ready["event"] == "ready"
            return child, ready["url"]
        except BaseException:
            child.kill()
            child.wait(timeout=5)
            child.stdin.close()
            child.stdout.close()
            raise

    command = [
        sys.executable,
        str(launcher),
        str(PROJECT_ROOT / "backend/desktop.py"),
        str(root),
        str(marker),
    ]
    child, url = start(command)
    response = []
    try:
        with httpx.Client(base_url=url, timeout=5, trust_env=False) as client:
            saved = client.post(
                "/documents",
                json={"title": "Saved before EOF", "content": "한글 `x -> y` · 37 litres"},
            )
            assert saved.status_code == 201
            document = saved.json()

        def request():
            try:
                with httpx.Client(timeout=25, trust_env=False) as client:
                    response.append(
                        client.get(
                            url + "/qa-blocked-request", params={"identifier": document["id"]}
                        )
                    )
            except httpx.HTTPError as error:
                response.append(error)

        pending = threading.Thread(target=request, daemon=True)
        pending.start()
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists(), "The request never held its uncommitted edit"
        started = time.monotonic()
        child.stdin.close()
        assert child.wait(timeout=18) == 0
        assert time.monotonic() - started < 18
        pending.join(timeout=3)
        assert not pending.is_alive()
        assert response
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        child.stdout.close()

    restored, url = start(
        [sys.executable, str(PROJECT_ROOT / "backend/desktop.py"), "--data-dir", str(root)]
    )
    try:
        with httpx.Client(base_url=url, timeout=5, trust_env=False) as client:
            assert client.get("/documents/" + document["id"]).json() == document
        restored.stdin.write("shutdown\n")
        restored.stdin.flush()
        assert restored.wait(timeout=10) == 0
    finally:
        if restored.poll() is None:
            restored.kill()
            restored.wait(timeout=5)
        restored.stdin.close()
        restored.stdout.close()
