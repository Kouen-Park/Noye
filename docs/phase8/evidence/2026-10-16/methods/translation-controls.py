"""Fixed novel cross-language extraction controls through production transport.

Use the captured production extraction payload as a template. Case labels and
expected facts remain evaluator-only. This component diagnostic does not publish
documents or establish whole-document acceptance; manual semantic review follows.
"""
import copy
import hashlib
import json
import sys
import time
from contextlib import closing
from pathlib import Path

import httpx

from app.config import get_settings
from app.models.source_documents import Extraction
from app.services.source_documents import local, presentation

from production_holdout_client import RecordedClient


root = Path('/private/tmp/noye-phase8-20261016')
case_file = root / 'translation-reference-cases.json'
target = Path(sys.argv[1])
if target.exists():
    raise FileExistsError(target)
suite = json.loads(case_file.read_text())
comparison = next((root / 'v18-documents').glob('comparison-*.json'))
prior = json.loads(comparison.read_text())
template = next(json.loads(c['request']['prompt']) for c in prior['model_calls']
                if c['task'] == 'process_original_sections')
template.pop('output_schema')
settings = get_settings()
report = {
    'method': __doc__, 'suite': suite,
    'case_file_sha256': hashlib.sha256(case_file.read_bytes()).hexdigest(),
    'template_report_sha256': hashlib.sha256(comparison.read_bytes()).hexdigest(),
    'prompt_version': local.PROMPT_VERSION,
    'local_code_sha256': hashlib.sha256(Path(local.__file__).read_bytes()).hexdigest(),
    'model': settings.ollama_model, 'context_tokens': settings.generation_context_tokens,
    'output_tokens': settings.generation_output_tokens, 'thinking': settings.ollama_thinking,
    'rows': [], 'full_document_acceptance': False,
}
began = time.monotonic()
with closing(RecordedClient()) as client:
    report['model_calls'] = client.calls
    for case in suite['cases']:
        payload = copy.deepcopy(template)
        language = case['output_language']
        payload['intent'] = {
            'purpose': 'Record only facts established by this original.',
            'topic': 'Source facts', 'document_type': 'Notes', 'language': language,
            'inventory_mode': 'relevant', 'collection_query': '', 'clarification': None,
        }
        payload['output_language'] = language
        title = 'Source facts' if language == 'English' else '원문 사실'
        payload['outline'] = {'title': title, 'sections': [{'id': 'facts', 'title': title}]}
        payload['passages'] = [{'evidence_id': 'qa-original', 'text': case['original']}]
        one = time.monotonic()
        row = {'id': case['id'], 'output_language': language, 'result': None,
               'guards_passed': False, 'manual_semantic_acceptance': None}
        try:
            result = local.structured(payload, Extraction, settings=settings, client=client,
                                      constraints={'section_id': ['facts'],
                                                   'evidence_ids': ['qa-original']})
            row['result'] = result.model_dump()
            if not result.claims:
                raise local.DocumentError('No facts extracted.')
            for claim in result.claims:
                if claim.section_id != 'facts' or claim.evidence_ids != ['qa-original']:
                    raise local.DocumentError('Unknown extraction reference.')
                presentation.check_language(claim.text, language)
                presentation.check_volume_properties(claim.text, [case['original']])
            row['guards_passed'] = True
        except Exception as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        row['seconds'] = round(time.monotonic() - one, 3)
        report['rows'].append(row)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)
report['seconds'] = round(time.monotonic() - began, 3)
with httpx.Client(timeout=30, trust_env=False) as client:
    response = client.post(settings.ollama_base_url.rstrip('/') + '/api/generate',
                           json={'model': settings.ollama_model, 'keep_alive': 0})
    report['unload_http_status'] = response.status_code
    report['remaining_loaded_models'] = client.get(
        settings.ollama_base_url.rstrip('/') + '/api/ps').json()
target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'count': len(report['rows']),
                  'guards_passed': sum(r['guards_passed'] for r in report['rows']),
                  'seconds': report['seconds']}), flush=True)
