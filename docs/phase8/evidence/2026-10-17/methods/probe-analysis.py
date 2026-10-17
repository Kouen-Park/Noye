"""One frozen verifier experiment; no product mutation or automatic retry.

Known cases are regressions, not holdout. Novel controls are fixed here before
the first call. Gold labels and names are not passed to the local model.
"""
import hashlib
import json
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated

import httpx
from pydantic import Field

from app.config import get_settings
from app.db import source_documents as store
from app.db.database import init_schema
from app.models.source_documents import Strict
from app.services.source_documents import local, pipeline

sys.path.insert(0, '/private/tmp/noye-phase8-20261016')
from production_holdout_client import RecordedClient


class AnalysisAudit(Strict):
    claim_index: int = Field(ge=0)
    original_indexes: list[Annotated[int, Field(ge=0)]] = Field(max_length=4)
    analysis: str = Field(min_length=1, max_length=1000, description=(
        'Briefly compare each assertion with the allowed originals before deciding. '
        'Identify its subject, property or relationship and any conditions. '
        'Explain whether those same assertions are established in the originals.'))
    unestablished: list[Annotated[str, Field(min_length=1, max_length=1800)]] = Field(max_length=6)
    supported: bool


class AnalysisVerification(Strict):
    audits: list[AnalysisAudit] = Field(max_length=12)


root = Path('/private/tmp/noye-phase8-20261017')
target = root / sys.argv[1]
if target.exists():
    raise FileExistsError(target)
old = Path('/private/tmp/noye-phase8-20261016')
cases = json.loads((old / 'multiple-original-controls.json').read_text())['cases']
novel = [
    ['mixed-power-true', True, 'Pine draws 14 watts, while Elm is rated for up to 70 watts.',
     ['Pine was measured drawing 14 watts.', 'Elm has a maximum power rating of 70 watts.']],
    ['mixed-power-false', False, 'Pine and Elm draw 14 and 70 watts, respectively.',
     ['Pine was measured drawing 14 watts.', 'Elm has a maximum power rating of 70 watts.']],
    ['independent-tool-true', True, 'Vega keeps signed bundles and uses a trie.',
     ['Vega keeps signed bundles. Separately, Vega uses a trie.']],
    ['independent-tool-false', False, 'Vega signs bundles using a trie.',
     ['Vega keeps signed bundles. Separately, Vega uses a trie.']],
    ['adjoining-true', True, 'Lyra records a snapshot every six hours.',
     ['Lyra stores confidential notes. Its snapshots are recorded every six hours.']],
    ['adjoining-false', False, 'Lyra records a snapshot every hour.',
     ['Lyra stores confidential notes. Its snapshots are recorded every six hours.']],
    ['translated-exception-true', True,
     'Eris permits imports on Tuesdays except during a safety inspection.',
     ['Eris는 안전 점검 중인 경우를 제외하고 화요일에 가져오기를 허용한다.']],
    ['translated-exception-false', False, 'Eris always permits imports on Tuesdays.',
     ['Eris는 안전 점검 중인 경우를 제외하고 화요일에 가져오기를 허용한다.']],
]
cases += novel
case_file = root / 'analysis-probe-cases.json'
case_file.write_text(json.dumps({'known_count': 14, 'cases': cases}, ensure_ascii=False, indent=2)+'\n')
pipeline.SupportVerification = AnalysisVerification
local.SUPPORT_SYSTEM += (' Before listing unestablished text or a verdict, write a brief '
                         'evidence comparison in analysis. Use all relevant adjoining sentences. '
                         'Do not treat presence of the same words or quantities as entailment.')
settings = get_settings().model_copy(update={
    'ollama_base_url': 'http://127.0.0.1:11439',
    'ollama_model': 'qwen3.5:4b',
    'generation_context_tokens': 8192,
    'generation_output_tokens': 2048,
    'ollama_thinking': False,
})
report = {'method': __doc__, 'experiment_not_production': True,
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'case_sha256': hashlib.sha256(case_file.read_bytes()).hexdigest(),
          'system': local.SUPPORT_SYSTEM, 'rows': [], 'model_calls': []}
with closing(sqlite3.connect(':memory:')) as db, closing(RecordedClient()) as client:
    db.row_factory = sqlite3.Row
    init_schema(db)
    db.execute("INSERT INTO source_document_requests(id,request_json,manifest_json,created_at,updated_at) VALUES ('probe','{}','[]','test','test')")
    req = store.request(db, 'probe')
    context = SimpleNamespace(connection=db, checkpoint=lambda *a: None, report=lambda *a, **kw: None)
    report['model_calls'] = client.calls
    started = time.monotonic()
    for n, (name, expected, text, originals) in enumerate(cases):
        one = time.monotonic()
        row = {'name': name, 'known': n < 14, 'expected': expected, 'actual': None, 'valid': False}
        try:
            row['actual'] = pipeline.verify(context, req, f'probe:{n}',
                [{'text': text, 'quotes': originals, 'original_passages': originals}],
                settings, client, strict=False)[0]
            row['valid'] = True
            row['correct'] = row['actual'] == expected
        except Exception as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        row['seconds'] = round(time.monotonic()-one, 3)
        report['rows'].append(row)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report['seconds'] = round(time.monotonic()-started, 3)
with httpx.Client(timeout=30, trust_env=False) as client:
    report['unload_status'] = client.post(settings.ollama_base_url+'/api/generate',
        json={'model': settings.ollama_model, 'keep_alive': 0}).status_code
target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
