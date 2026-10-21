"""Diagnostic: verify whether the installed model receives system instructions."""
import json
import time
from pathlib import Path

import httpx

OUT = Path('/private/tmp/noye-phase8-20261016/transport-canary.json')
system = 'Return JSON with result equal to the exact text NoyeCanary17. No other value is valid.'
schema = {'type': 'object', 'properties': {'result': {'type': 'string'}}, 'required': ['result'], 'additionalProperties': False}
rows = []
with httpx.Client(timeout=180, trust_env=False) as client:
    for label, endpoint, extra in [
        ('generate-system-only', '/api/generate', {'system': system, 'prompt': 'Follow the system instruction.'}),
        ('chat-system-message', '/api/chat', {'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': 'Follow the system instruction.'}]}),
        ('generate-inline-system', '/api/generate', {'system': system, 'prompt': system + '\nFollow the system instruction.'}),
    ]:
        body = {'model': 'qwen3.5:4b', 'think': False, 'stream': False, 'format': schema,
                'options': {'num_ctx': 8192, 'num_predict': 128, 'temperature': 0}, **extra}
        start = time.monotonic()
        response = client.post('http://127.0.0.1:11439' + endpoint, json=body)
        rows.append({'label': label, 'request': body, 'status': response.status_code,
                     'seconds': round(time.monotonic()-start, 3), 'body': response.json()})
        OUT.write_text(json.dumps(rows, indent=2) + '\n')
        print(json.dumps(rows[-1]), flush=True)
