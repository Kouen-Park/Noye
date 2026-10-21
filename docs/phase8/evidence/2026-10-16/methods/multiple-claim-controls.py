"""Fixed multi-claim source-ownership diagnostics through production verify.

These component calls do not publish documents. Gold labels are evaluator-only.
Invalid audit/transport results never count as correct negative semantic decisions.
No mechanical number guard is used: this isolates the semantic audit protocol.
"""
import hashlib
import json
import sqlite3
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import httpx

from app.config import get_settings
from app.db import source_documents as store
from app.db.database import init_schema
from app.services.source_documents import local, pipeline
from production_holdout_client import RecordedClient

root = Path('/private/tmp/noye-phase8-20261016')
case_file, target = root / 'multiple-claim-controls.json', Path(sys.argv[1])
if target.exists():
    raise FileExistsError(target)
suite = json.loads(case_file.read_text())
settings = get_settings()
with closing(sqlite3.connect(':memory:')) as db, closing(RecordedClient()) as client:
    db.row_factory = sqlite3.Row
    init_schema(db)
    identifier = str(uuid.uuid4())
    db.execute('INSERT INTO source_document_requests'
               '(id,request_json,manifest_json,created_at,updated_at) '
               "VALUES (?,'{}','[]','test','test')", (identifier,))
    req = store.request(db, identifier)
    events = []
    context = SimpleNamespace(connection=db, checkpoint=lambda *a: None,
                              report=lambda *a, **kw: events.append({'stage': a[0], 'state': a[1], **kw}))
    report = {
        'method': __doc__, 'suite': suite,
        'case_file_sha256': hashlib.sha256(case_file.read_bytes()).hexdigest(),
        'prompt_version': local.PROMPT_VERSION, 'model': settings.ollama_model,
        'context_tokens': settings.generation_context_tokens,
        'output_tokens': settings.generation_output_tokens, 'thinking': settings.ollama_thinking,
        'code_hashes': {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                        for m in (local, pipeline)},
        'rows': [], 'model_calls': client.calls,
    }
    began = time.monotonic()
    for number, (label, cases) in enumerate(suite['batches']):
        one = time.monotonic()
        expected = [c[0] for c in cases]
        claims = [{'text': c[1], 'quotes': c[2], 'original_passages': c[2]} for c in cases]
        row = {'id': label, 'expected': expected, 'actual': None,
               'valid_semantic_decision': False, 'matches_rubric': [False] * len(cases)}
        try:
            actual = pipeline.verify(context, req, f'batch-{number}', claims,
                                     settings, client, strict=False)
            row.update(actual=actual, valid_semantic_decision=True,
                       matches_rubric=[g == a for g, a in zip(expected, actual, strict=True)])
        except Exception as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        row['seconds'] = round(time.monotonic() - one, 3)
        report['rows'].append(row)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report['seconds'] = round(time.monotonic() - began, 3)
    report['events'] = events
with httpx.Client(timeout=30, trust_env=False) as client:
    report['unload_http_status'] = client.post(
        settings.ollama_base_url.rstrip('/') + '/api/generate',
        json={'model': settings.ollama_model, 'keep_alive': 0}).status_code
    report['remaining_loaded_models'] = client.get(
        settings.ollama_base_url.rstrip('/') + '/api/ps').json()
target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'batches': len(report['rows']),
                  'matches': sum(sum(row['matches_rubric']) for row in report['rows']),
                  'claims': sum(len(row['expected']) for row in report['rows']),
                  'seconds': report['seconds']}), flush=True)
