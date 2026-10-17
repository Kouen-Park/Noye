"""Five fresh production document attempts and Wiki generation, sequential without retry.

Uses only the evaluation CLI's invented originals and real local embeddings.
The CLI's Qdrant is explicitly in-memory; no personal collection is accessed.
Each scenario unloads generation/embedding models before the next one. Cold
loads affect latency, so these are whole-attempt measurements, not a benchmark.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

root = Path('/private/tmp/noye-phase8-20261017')
target = root / 'v23-scenarios.json'
if target.exists():
    raise FileExistsError(target)
env = {**os.environ,
       'OLLAMA_BASE_URL': 'http://127.0.0.1:11439', 'OLLAMA_MODEL': 'qwen3.5:4b',
       'OLLAMA_EMBEDDING_MODEL': 'embeddinggemma', 'GENERATION_CONTEXT_TOKENS': '8192',
       'GENERATION_OUTPUT_TOKENS': '2048', 'OLLAMA_THINKING': 'false',
       'LOG_TO_FILE': 'false', 'PYTHONPATH': '/Users/gavinpark/Projects/Noye/backend',
       'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': '', 'GEMINI_API_KEY': ''}
report = {'method': __doc__, 'rows': [], 'runtime_hashes': {
    name: hashlib.sha256((Path('/Users/gavinpark/Projects/Noye/backend/app/services/source_documents') / name).read_bytes()).hexdigest()
    for name in ['local.py', 'pipeline.py', 'presentation.py', 'discovery.py']}}
for scenario in ['comparison', 'collection', 'report', 'partial', 'empty', 'wiki']:
    began = time.monotonic()
    with (root / f'v23-{scenario}.log').open('x') as output:
        completed = subprocess.run([sys.executable,
            '/private/tmp/noye-phase8-20261016/recorded-documents-current.py',
            '--workspace', str(root / 'v23-documents'), '--scenario', scenario],
            env=env, stdout=output, stderr=subprocess.STDOUT, check=False)
    row = {'scenario': scenario, 'exit_code': completed.returncode,
           'wall_seconds': round(time.monotonic()-began, 3)}
    with httpx.Client(timeout=60, trust_env=False) as client:
        row['unload_status'] = {
            model: client.post(env['OLLAMA_BASE_URL']+'/api/generate',
                json={'model': model, 'keep_alive': 0}).status_code
            for model in ['qwen3.5:4b', 'embeddinggemma']}
        row['loaded_after'] = client.get(env['OLLAMA_BASE_URL']+'/api/ps').json()
    report['rows'].append(row)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(row), flush=True)
