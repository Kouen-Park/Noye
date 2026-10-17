"""Actual original-only relation controls; three fresh cases then six v4 regressions; only candidate lookup is fixed."""
import hashlib
import json
import sys
import time
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import httpx

from app.config import Settings
from app.models.wiki import Passage, SourceRef, WikiScope
from app.services.wiki import relations, local

sys.path.insert(0, '/private/tmp/noye-phase8-20261016')
from production_holdout_client import RecordedClient

root = Path('/private/tmp/noye-phase8-20261017')
target = root / 'relations-v5.json'
if target.exists():
    raise FileExistsError(target)
case_file = root / 'relation-controls.json'
suite = json.loads(case_file.read_text())
fresh_file = root / 'relation-original-only-controls.json'
fresh = json.loads(fresh_file.read_text())
suite = {'cases': fresh['cases'] + suite['cases']}
settings = Settings(_env_file=None, ollama_base_url='http://127.0.0.1:11439',
                    ollama_model='qwen3.5:4b', generation_context_tokens=8192,
                    generation_output_tokens=2048, ollama_thinking=False)


def passage(text, side):
    digest = hashlib.sha256(text.encode()).hexdigest()
    return Passage(id=side, source=SourceRef(source_id=side+'-source', root_id=None,
        relative_path=side+'.txt', name=side+'.txt', source_hash=digest,
        source_version=digest, availability='available', indexing_status='READY'),
        passage_index=0, start=0, end=len(text), text=text)


def metadata(case, side):
    return {'sections': [{'summary': {'text': case[side+'_summary'],
        'evidence_id': side, 'quote': case[side].split('. ')[0]}, 'key_points': []}]}


report = {'method': __doc__, 'suite': suite,
          'known_case_sha256': hashlib.sha256(case_file.read_bytes()).hexdigest(),
          'fresh_case_sha256': hashlib.sha256(fresh_file.read_bytes()).hexdigest(),
          'prompt_version': local.PROMPT_VERSION,
          'runtime_hashes': {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                             for m in (relations, local)}, 'rows': []}
started = time.monotonic()
with closing(RecordedClient()) as client:
    report['model_calls'] = client.calls
    for case in suite['cases']:
        before = time.monotonic()
        origin, other = passage(case['origin'], 'origin'), passage(case['target'], 'target')
        revision = {'id': 'target-revision', 'metadata': metadata(case, 'target'),
                    'evidence': [other.model_dump()]}
        row = {'id': case['id'], 'regression': not case['id'].startswith('fresh-'), 'valid': False}
        before_calls = len(client.calls)
        try:
            with patch.object(relations, 'candidates', return_value=[(1, {'id': 'target-wiki'}, revision)]):
                actual = relations.infer(None, 'origin-wiki', metadata(case, 'origin'),
                    [origin], WikiScope(), [], settings, client)
            kinds = [item['kind'] for item in actual]
            if not any(c['task'] == 'verify_relation' for c in client.calls[before_calls:]):
                raise RuntimeError('No semantic model decision: original pair exceeded budget')
            row.update(valid=True, actual=actual,
                matches_rubric=all(k in case['allowed'] for k in kinds)
                  and (bool(kinds) or not case.get('required', False)))
        except Exception as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        row['seconds'] = round(time.monotonic()-before, 3)
        report['rows'].append(row)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report['seconds'] = round(time.monotonic()-started, 3)
with httpx.Client(timeout=30, trust_env=False) as client:
    report['unload_status'] = client.post(settings.ollama_base_url+'/api/generate',
        json={'model': settings.ollama_model, 'keep_alive': 0}).status_code
target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
