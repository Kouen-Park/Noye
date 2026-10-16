"""Explicit fresh production attempts, sequential; never retry a failed job.

The QA runner unloads its own model between scenarios to limit retained memory.
This affects warm-cache latency and is not a product behavior change.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx


root = Path('/private/tmp/noye-phase8-20261016')
env = {
    **os.environ,
    'OLLAMA_BASE_URL': 'http://127.0.0.1:11439',
    'OLLAMA_MODEL': 'qwen3.5:4b',
    'OLLAMA_EMBEDDING_MODEL': 'embeddinggemma',
    'GENERATION_CONTEXT_TOKENS': '8192',
    'GENERATION_OUTPUT_TOKENS': '2048',
    'OLLAMA_THINKING': 'false',
    'LOG_TO_FILE': 'false',
    'PYTHONPATH': '/Users/gavinpark/Projects/Noye/backend',
}
rows = []
target = root / 'v16-scenarios.json'
if target.exists():
    raise FileExistsError(target)
for scenario in ['comparison', 'collection', 'report', 'partial', 'empty']:
    began = time.monotonic()
    with (root / f'outputs/v16-{scenario}.log').open('x') as output:
        completed = subprocess.run([
            sys.executable, str(root / 'recorded-documents.py'),
            '--workspace', str(root / 'v16-documents'), '--scenario', scenario,
        ], env=env, stdout=output, stderr=subprocess.STDOUT, check=False)
    row = {'scenario': scenario, 'process_exit_code': completed.returncode,
           'wall_seconds': round(time.monotonic() - began, 3)}
    # These are separate explicit attempts, not retries of earlier requests.
    with httpx.Client(timeout=60, trust_env=False) as client:
        response = client.post(env['OLLAMA_BASE_URL'] + '/api/generate',
                               json={'model': env['OLLAMA_MODEL'], 'keep_alive': 0})
        row['unload_http_status'] = response.status_code
        row['remaining_loaded_models'] = client.get(
            env['OLLAMA_BASE_URL'] + '/api/ps').json()
    rows.append(row)
    target.write_text(json.dumps({'method': __doc__, 'rows': rows}, indent=2) + '\n')
    print(json.dumps(row), flush=True)
