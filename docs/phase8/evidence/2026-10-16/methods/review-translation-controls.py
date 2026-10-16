"""Review retained synthetic outputs; no new model call, retry or document publication.

Primary-agent semantic judgments compare each output with its fixed original.
Wire comparisons reconstruct the current schema/system/prompt, not model behavior.
Guard replay reuses exact recorded prose; it is not another live extraction run.
"""
import hashlib
import json
from pathlib import Path

from app.models.source_documents import Extraction, SupportVerification
from app.services.source_documents import local, presentation

root = Path('/private/tmp/noye-phase8-20261016')
report_path = root / 'translation-controls-v19.json'
report = json.loads(report_path.read_text())
judgments = {
    'magpie': (True, 'Correct capacity 29 and current amount 8; old guard carried capacity across the first quantity.'),
    'heron': (True, 'Rated limit 80 and observed temperature 23 remain distinct; the name is transliterated.'),
    'cormorant': (True, 'Tuesday-only permission and inactive-maintenance condition retained.'),
    'robin': (False, 'Falcon is corrupted to 페이커ン; the approval states are retained but entity naming fails.'),
    'swift': (True, 'Queue use and measured first-job runtime 17 ms remain independent statements.'),
    'wren': (True, '2 failed and 11 successful messages retained; Korean wording is awkward.'),
    'finch': (False, 'Independent encryption and B-tree-index facts were linked by an unsupported using relationship.'),
    'tern': (True, 'Three daily backups and Friday write pause retained.'),
}
rows = []
for case, row in zip(report['suite']['cases'], report['rows'], strict=True):
    accepted, note = judgments[row['id']]
    current_guard_error = None
    try:
        for claim in row['result']['claims']:
            presentation.check_language(claim['text'], case['output_language'])
            presentation.check_volume_properties(claim['text'], [case['original']])
    except local.DocumentError as exc:
        current_guard_error = str(exc)
    rows.append({'id': row['id'], 'semantic_accepted': accepted, 'manual_note': note,
                 'original_guards_passed': row['guards_passed'],
                 'current_replayed_guards_passed': current_guard_error is None,
                 'current_guard_error': current_guard_error})
wire = []
audit = json.loads((root / 'reference-holdout-v18.json').read_text())
for suite, schema in [(report, Extraction), (audit, SupportVerification)]:
    for call in suite['model_calls']:
        if call['task'] == 'model_preflight':
            continue
        request = call['request']
        payload = json.loads(request['prompt'])
        payload.pop('output_schema')
        constraints = {}
        for definition in request['format'].get('$defs', {}).values():
            for name, prop in definition.get('properties', {}).items():
                values = (prop.get('items', {}) if prop.get('type') == 'array' else prop).get('enum')
                if values is not None:
                    constraints[name] = values
        wire.append({'task': call['task'],
                     'system_equal': local.system(payload) == request['system'],
                     'prompt_equal': local.prompt(payload, schema, constraints) == request['prompt'],
                     'format_equal': local.output_schema(schema, constraints, payload=payload) == request['format']})
out = {'method': __doc__,
       'report_sha256': hashlib.sha256(report_path.read_bytes()).hexdigest(),
       'prompt_version_current': local.PROMPT_VERSION,
       'presentation_code_sha256': hashlib.sha256(Path(presentation.__file__).read_bytes()).hexdigest(),
       'original_presentation_code_sha256_at_e738de2': 'b955f3f934ce191f66bb3b5bed902d3793da17576ba27851ab5d3bbc12aaded6',
       'semantic_accepted': sum(r['semantic_accepted'] for r in rows),
       'count': len(rows), 'full_document_acceptance': False, 'rows': rows,
       'wire_comparisons': wire}
(root / 'translation-controls-review-v20.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'semantic_accepted': out['semantic_accepted'], 'count': len(rows),
                  'replayed_guards_passed': sum(r['current_replayed_guards_passed'] for r in rows),
                  'wire_comparisons': len(wire),
                  'all_wire_equal': all(r['system_equal'] and r['prompt_equal'] and r['format_equal'] for r in wire)}))
