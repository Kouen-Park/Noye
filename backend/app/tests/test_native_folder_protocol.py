"""Real sidecar stdin authorization and persisted scanner recovery, without AI services."""

import hashlib
import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import httpx

from app.config import PROJECT_ROOT


@contextmanager
def sidecar(root):
    command = (
        [os.environ["NOYE_TEST_SIDECAR"]]
        if os.environ.get("NOYE_TEST_SIDECAR")
        else [sys.executable, str(PROJECT_ROOT / "backend/desktop.py")]
    )
    child = subprocess.Popen(
        [*command, "--data-dir", str(root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "LOG_TO_FILE": "false",
            "NOYE_CONTROL_TOKEN": "synthetic-control",
            "OLLAMA_BASE_URL": "http://127.0.0.1:41434",
            "QDRANT_URL": "http://127.0.0.1:46333",
        },
    )
    output = queue.Queue()

    def read():
        for line in child.stdout:
            output.put(json.loads(line))

    threading.Thread(target=read, daemon=True).start()
    try:
        ready = output.get(timeout=30)
        assert ready["event"] == "ready"
        with httpx.Client(
            base_url=ready["url"], timeout=10, headers={"X-Noye-Control": "synthetic-control"}
        ) as client:
            yield child, output, client
        child.stdin.write("shutdown\n")
        child.stdin.flush()
        assert child.wait(timeout=15) == 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def await_files(client, count):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        values = client.get("/files").json()
        if len(values) == count and all(v["status"] == "FAILED" for v in values):
            return values
        time.sleep(0.1)
    raise AssertionError("Stable files were not processed by the real sidecar watcher")


def test_private_folder_authorization_scans_and_recovers_on_real_sidecar_restart(tmp_path):
    workspace, folder = tmp_path / "workspace", tmp_path / "originals"
    folder.mkdir()
    original = folder / "first.txt"
    original.write_bytes(b"Version one: 37 units, Sunday exception 29.")
    secret = tmp_path / "outside.txt"
    secret.write_text("outside synthetic bytes")
    (folder / "escape.txt").symlink_to(secret)
    with sidecar(workspace) as (child, output, client):
        assert client.post("/folders", json={"path": str(folder)}).status_code == 405
        child.stdin.write(
            json.dumps(
                {
                    "event": "native_folder",
                    "id": 71,
                    "action": "register_root",
                    "values": {"path": str(folder), "kind": "connected"},
                }
            )
            + "\n"
        )
        child.stdin.flush()
        reply = output.get(timeout=10)
        assert reply["event"] == "native_folder_result" and reply["id"] == 71
        root_id = reply["result"]
        assert "path" not in client.get("/folders").json()[0]
        values = await_files(client, 1)
        source_id = values[0]["id"]
        assert "path" not in values[0]
        with sqlite3.connect(workspace / "app.db") as saved:
            snapshot, digest = saved.execute(
                "SELECT path,content_hash FROM files WHERE id=?", (source_id,)
            ).fetchone()
        assert Path(snapshot).read_bytes() == original.read_bytes()
        assert digest == hashlib.sha256(original.read_bytes()).hexdigest()
    original.rename(folder / "renamed.txt")
    (folder / "closed.txt").write_text("Discovered at the next actual sidecar launch.")
    with sidecar(workspace) as (_, _, client):
        values = await_files(client, 2)
        assert next(v for v in values if v["name"] == "renamed.txt")["id"] == source_id
        assert client.patch(f"/folders/{root_id}", json={"disconnect": True}).status_code == 200
        assert (folder / "renamed.txt").exists()
        assert client.get(f"/files/{source_id}/source-status").json()["status"] == "unavailable"
    db = sqlite3.connect(workspace / "app.db")
    try:
        assert (
            db.execute("SELECT COUNT(*) FROM jobs WHERE file_id=?", (source_id,)).fetchone()[0] == 1
        )
        assert (
            db.execute(
                "SELECT relative_path FROM sources WHERE file_id=?", (source_id,)
            ).fetchone()[0]
            == "renamed.txt"
        )
    finally:
        db.close()
