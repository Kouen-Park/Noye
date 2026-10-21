"""Diagnostic only: unchanged production v13 relation system/schema, thinking enabled with 3072 output tokens on four fixed difficult controls. This does not change the RAG default or establish production acceptance."""
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

sys.path.insert(0, '/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-19/methods')
from production_holdout_client import RecordedClient as BaseRecordedClient

class RecordedClient(BaseRecordedClient):
    def post(self,url,*,json):
        events=Path('/private/tmp/noye-phase8-20261021-native/thinking-events.jsonl')
        with events.open('a') as out:out.write(__import__('json').dumps({'state':'started','endpoint':url,'request':json,'at':time.time()},ensure_ascii=False)+'\n')
        response=super().post(url,json=json)
        with events.open('a') as out:out.write(__import__('json').dumps({'state':'returned','endpoint':url,'status':response.status_code,'body_sha256':hashlib.sha256(response.content).hexdigest(),'at':time.time()})+'\n')
        return response

root = Path('/private/tmp/noye-phase8-20261021-native')
prior = Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-17/methods')
target = root / 'thinking-relations.json'
if target.exists():
    raise FileExistsError(target)
case_file=Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-21/model/relations-current.json')
base=json.loads(case_file.read_text())['suite']['cases']
new_file=Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-21-followup/methods/relation-fresh-controls.json')
fresh=json.loads(new_file.read_text())['cases']
wanted={'new-v11-omitted-fact','new-v11-compatible-exception','fresh-v14-opposite-with-shared-extra','fresh-v14-disjoint-subjects'}
suite={'cases':[c for c in base+fresh if c['id'] in wanted]}
assert len(suite['cases'])==4
settings = Settings(_env_file=None, ollama_base_url='http://127.0.0.1:11439',
                    ollama_model='qwen3.5:4b', generation_context_tokens=8192,
                    generation_output_tokens=3072, ollama_thinking=True)


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
          'new_case_sha256': hashlib.sha256(new_file.read_bytes()).hexdigest(),
          'diagnostic_only': True, 'thinking': True, 'output_tokens':3072,
          'source_commit': __import__('subprocess').check_output(['git','-c','core.fsmonitor=false','rev-parse','HEAD'],text=True).strip(),
          'prompt_version': local.PROMPT_VERSION,
          'runtime_hashes': {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                             for m in (relations, local)}, 'rows': []}
with httpx.Client(timeout=30,trust_env=False) as c:
    assert not c.get(settings.ollama_base_url+'/api/ps').json()['models']
started = time.monotonic()
with closing(RecordedClient()) as client:
    report['model_calls'] = client.calls
    for case in suite['cases']:
        before = time.monotonic()
        origin, other = passage(case['origin'], 'origin'), passage(case['target'], 'target')
        revision = {'id': 'target-revision', 'metadata': metadata(case, 'target'),
                    'evidence': [other.model_dump()]}
        row = {'id': case['id'], 'regression': not case['id'].startswith('new-v11-'), 'valid': False}
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
    report['loaded_after']=client.get(settings.ollama_base_url+'/api/ps').json()
target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
