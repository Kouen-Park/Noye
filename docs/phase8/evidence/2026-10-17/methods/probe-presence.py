"""One controlled sampler experiment, not product behavior or fresh document acceptance.

Only presence_penalty=0 is added at the evaluation transport boundary. Production
prompt/schema/validator/context/output/thinking/temperature remain unchanged.
The fourteen recorded v23 claims and saved unsafe comparison are regressions;
six additional claims were frozen before this experiment. No failed-job retry.
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
target = root / 'presence-zero-probe.json'
if target.exists():
    raise FileExistsError(target)
fresh_file = root / 'sampling-neutral-controls.json'
fresh = json.loads(fresh_file.read_text())
prior = json.loads((root / 'support-v23.json').read_text())
batches = [(name, False, cases) for name, cases in fresh['batches']]
batches += [(name, True, cases) for name, _, cases in prior['input_batches']]
# Fixed before this experiment's first call. This derived, previously unrun
# counterfactual checks that an apparent translation improvement is not merely
# agreement with the claim's own count. It is not a fresh holdout case.
for name, _, cases in prior['input_batches']:
    if name == 'translated-adjoining-true':
        _, text, originals = cases[0]
        batches.append(('known-count-counterfactual-not-previously-run', True,
                        [[False, text.replace('four days', 'five days'), originals]]))
comparison_file = next((root / 'v23-documents').glob('comparison-*.json'))
comparison = json.loads(comparison_file.read_text())
for call in comparison['model_calls']:
    if call['task'] != 'verify_support' or 'stores 92 litres using' not in call['request']['prompt']:
        continue
    payload = json.loads(call['request']['prompt'])
    originals = {p['original_index']: p['text'] for p in payload['original_passages']}
    batches.append(('recorded-unsafe-comparison', True, [
        [False, c['text'], [originals[i] for i in c['original_indexes']]] for c in payload['claims']]))
settings = Settings(_env_file=None, ollama_base_url='http://127.0.0.1:11439',
    ollama_model='qwen3.5:4b', generation_context_tokens=8192,
    generation_output_tokens=2048, ollama_thinking=False)


class NeutralClient(RecordedClient):
    def post(self, url, *, json):
        if 'prompt' in json:
            json = {**json, 'options': {**json['options'], 'presence_penalty': 0}}
        return super().post(url, json=json)


report = {'method': __doc__, 'experiment_not_production': True,
    'override': {'presence_penalty': 0}, 'fresh_sha256': hashlib.sha256(fresh_file.read_bytes()).hexdigest(),
    'baseline_report_sha256': hashlib.sha256((root / 'support-v23.json').read_bytes()).hexdigest(),
    'unsafe_comparison_body_sha256': comparison['revision_body_sha256'],
    'prompt_version': local.PROMPT_VERSION, 'input_batches': batches,
    'runtime_hashes': {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                       for m in (local, pipeline, models)}, 'rows': []}
with closing(sqlite3.connect(':memory:')) as db, closing(NeutralClient()) as client:
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
            actual = pipeline.verify(context, req, f'neutral:{n}', claims, settings, client, strict=False)
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
