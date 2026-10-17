"""Production v23 verifier: fresh eight controls, then recorded failure regressions.

Candidate selection is evaluator-only; exact production requests are captured.
No auto retry, no document publication, no acceptance of malformed refusals.
"""
import hashlib
import json
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import httpx

from app.config import Settings
from app.db import source_documents as store
from app.db.database import init_schema
from app.services.source_documents import local, pipeline
from app.models import source_documents as models

sys.path.insert(0, '/private/tmp/noye-phase8-20261016')
from production_holdout_client import RecordedClient

root = Path('/private/tmp/noye-phase8-20261017')
target = root / 'support-v23.json'
if target.exists():
    raise FileExistsError(target)
fresh_file = root / 'analysis-acceptance-controls.json'
fresh = json.loads(fresh_file.read_text())['cases']
batches = [(name, False, [(expected, text, originals)]) for name, expected, text, originals in fresh]
old = Path('/private/tmp/noye-phase8-20261016')
known = json.loads((old / 'multiple-original-controls.json').read_text())['cases']
for name, expected, text, originals in known:
    if name in ('temperature-properties-unsupported', 'translated-conditions-supported'):
        batches.append((name, True, [(expected, text, originals)]))
known_multi = json.loads((old / 'multiple-claim-controls.json').read_text())['batches']
for name, cases in known_multi:
    if name in ('separate-relationship', 'shared-duplicate'):
        batches.append((name, True, cases))
settings = Settings(_env_file=None, ollama_base_url='http://127.0.0.1:11439',
                    ollama_model='qwen3.5:4b', generation_context_tokens=8192,
                    generation_output_tokens=2048, ollama_thinking=False)
report = {'method': __doc__, 'fresh_case_sha256': hashlib.sha256(fresh_file.read_bytes()).hexdigest(),
          'prompt_version': local.PROMPT_VERSION,
          'runtime_hashes': {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                             for m in (local, pipeline, models)},
          'input_batches': batches, 'rows': []}
with closing(sqlite3.connect(':memory:')) as db, closing(RecordedClient()) as client:
    db.row_factory = sqlite3.Row
    init_schema(db)
    db.execute("INSERT INTO source_document_requests(id,request_json,manifest_json,created_at,updated_at) VALUES ('probe','{}','[]','test','test')")
    req = store.request(db, 'probe')
    context = SimpleNamespace(connection=db, checkpoint=lambda *a: None, report=lambda *a, **kw: None)
    report['model_calls'] = client.calls
    began = time.monotonic()
    for n, (name, known, cases) in enumerate(batches):
        one = time.monotonic()
        expected = [case[0] for case in cases]
        claims = [{'text': c[1], 'quotes': c[2], 'original_passages': c[2]} for c in cases]
        row = {'id': name, 'regression': known, 'expected': expected, 'valid': False}
        try:
            actual = pipeline.verify(context, req, f'v23:{n}', claims, settings, client, strict=False)
            row.update(actual=actual, valid=True,
                       matches=[a == e for a, e in zip(actual, expected, strict=True)])
        except Exception as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        row['seconds'] = round(time.monotonic()-one, 3)
        report['rows'].append(row)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report['seconds'] = round(time.monotonic()-began, 3)
with httpx.Client(timeout=30, trust_env=False) as client:
    report['unload_status'] = client.post(settings.ollama_base_url+'/api/generate',
        json={'model': settings.ollama_model, 'keep_alive': 0}).status_code
target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
