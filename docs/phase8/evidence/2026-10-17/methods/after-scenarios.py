"""Serialize model experiments after all six current scenarios; no automatic job retries."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

root = Path('/private/tmp/noye-phase8-20261017')
started = time.monotonic()
while True:
    try:
        ready = len(json.loads((root / 'v23-scenarios.json').read_text())['rows']) == 6
    except (FileNotFoundError, ValueError):
        ready = False
    if ready:
        break
    if time.monotonic()-started > 2700:
        raise TimeoutError('Current scenario runner did not finish; no other model job started')
    time.sleep(5)
with httpx.Client(timeout=10, trust_env=False) as client:
    assert not client.get('http://127.0.0.1:11439/api/ps').json()['models']
env = {**os.environ, 'PYTHONPATH': '/Users/gavinpark/Projects/Noye/backend'}
record = {'method': __doc__, 'stages': []}
for script, log in [('probe-relations-v5.py', 'relations-v5.log'),
                    ('probe-presence.py', 'presence-zero-probe.log')]:
    one = time.monotonic()
    print(json.dumps({'starting': script}), flush=True)
    with (root / log).open('x') as output:
        result = subprocess.run([sys.executable, str(root / script)], env=env,
            stdout=output, stderr=subprocess.STDOUT, check=False)
    row = {'script': script, 'exit_code': result.returncode,
           'seconds': round(time.monotonic()-one, 3)}
    record['stages'].append(row)
    (root / 'experiment-sequence.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(row), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
