"""Source/frozen startup measurements; no AI service or model is started.

Two bounded, owned CPU workers model contention. This is not a physical cold-boot
or memory-pressure experiment. The existing twenty-second test bound is retained.
"""
import hashlib
import json
import os
import platform
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx


root = Path('/private/tmp/noye-phase8-20261016/startup')
root.mkdir(exist_ok=True)
binary = Path('/Users/gavinpark/Projects/Noye/frontend/src-tauri/binaries/noye-backend-aarch64-apple-darwin')
source = Path('/Users/gavinpark/Projects/Noye/backend/desktop.py')
report = {
    'method': __doc__,
    'platform': platform.platform(),
    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'rows': [],
}
env = {**os.environ, 'LOG_TO_FILE': 'false',
       'OLLAMA_BASE_URL': 'http://127.0.0.1:1', 'QDRANT_URL': 'http://127.0.0.1:1'}
env.pop('NOYE_CONTROL_TOKEN', None)
target = root / 'measurements.json'
if target.exists():
    raise FileExistsError(target)
workers = []
try:
    for mode, kinds in [('idle', ['source', 'frozen', 'frozen', 'source']),
                        ('two_cpu_workers', ['source', 'frozen', 'frozen'])]:
        if mode == 'two_cpu_workers':
            for _ in range(2):
                workers.append(subprocess.Popen([
                    sys.executable, '-c',
                    'import hashlib,time; end=time.monotonic()+90; value=b"qa"\n'
                    'while time.monotonic()<end: value=hashlib.sha256(value).digest()'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for kind in kinds:
            position = len(report['rows'])
            command = [str(binary)] if kind == 'frozen' else [sys.executable, str(source)]
            row = {'mode': mode, 'kind': kind, 'ready': False, 'error': None,
                   'cpu_workers_running': sum(worker.poll() is None for worker in workers)}
            began = time.monotonic()
            with (root / f'{position}-stderr.txt').open('w') as log, subprocess.Popen(
                [*command, '--data-dir', str(root / f'workspace-{position}')],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                text=True, env=env,
            ) as child:
                try:
                    lines = queue.Queue()
                    threading.Thread(target=lambda: lines.put(child.stdout.readline()),
                                     daemon=True).start()
                    line = lines.get(timeout=20)
                    frame = json.loads(line)
                    row['ready_seconds'] = round(time.monotonic() - began, 3)
                    assert frame['event'] == 'ready'
                    assert frame['url'].startswith('http://127.0.0.1:')
                    with httpx.Client(trust_env=False, timeout=3) as client:
                        row['health'] = client.get(frame['url'] + '/health').json()
                    assert row['health'] == {'status': 'ok'}
                    row['ready'] = True
                    child.stdin.write('shutdown\n')
                    child.stdin.flush()
                    row['exit_code'] = child.wait(timeout=10)
                    assert row['exit_code'] == 0
                except Exception as exc:
                    row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait(timeout=5)
                    row['total_seconds'] = round(time.monotonic() - began, 3)
                    report['rows'].append(row)
                    target.write_text(json.dumps(report, indent=2) + '\n')
                    print(json.dumps(row), flush=True)
finally:
    for worker in workers:
        if worker.poll() is None:
            worker.terminate()
        worker.wait(timeout=5)
