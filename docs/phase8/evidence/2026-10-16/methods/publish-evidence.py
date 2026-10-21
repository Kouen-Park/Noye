"""Publish only explicit synthetic evidence; never runtime folders or credentials."""
import hashlib
import json
import re
from pathlib import Path


base = Path('/private/tmp/noye-phase8-20261016')
root = Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-16')
root.mkdir(exist_ok=True)
record_file = root / 'publication.json'
record = json.loads(record_file.read_text()) if record_file.exists() else {
    'method': __doc__, 'files': [],
}
files = {entry['file']: entry for entry in record['files']}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(source, relative, kind='copy'):
    raw = source.read_bytes()
    data, transformation = raw, 'Byte-for-byte copy'
    if kind == 'report':
        report = json.loads(raw)
        for call in (report.get('model_calls', []) if isinstance(report, dict) else []):
            if (call.get('task') == 'model_preflight' and call.get('http_status') == 200
                    and call.get('raw_response')):
                omitted = call.pop('raw_response').encode()
                call['publication'] = {
                    'omitted': 'Repeated successful model metadata; generation response unchanged',
                    'original_sha256': sha(omitted), 'original_bytes': len(omitted),
                }
        data = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
        transformation = 'Repeated model-preflight raw metadata omitted with hash; generation inputs/outputs unchanged'
    elif kind == 'log':
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', raw.decode())
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text, redactions = re.subn(
            r'((?:control_token|control-token|x-noye-control)[\"\s:=]+)[A-Za-z0-9_-]{20,}',
            r'\1[REDACTED_QA_CONTROL_TOKEN]', text, flags=re.I,
        )
        data = ('\n'.join(line.rstrip() for line in text.splitlines()).strip() + '\n').encode()
        transformation = f'ANSI/CR/trailing whitespace normalized; {redactions} ephemeral control token redactions'
    elif kind == 'xml':
        data = ('\n'.join(line.rstrip() for line in raw.decode().splitlines()) + '\n').encode()
        transformation = 'JUnit XML diagnostic trailing whitespace normalized; original raw XML hash retained'
    target = root / relative
    if relative in files and target.read_bytes() != data:
        raise ValueError(f'Refusing to overwrite changed published evidence: {relative}')
    target.parent.mkdir(exist_ok=True, parents=True)
    target.write_bytes(data)
    files[relative] = {
        'file': relative, 'source': str(source), 'source_bytes': len(raw),
        'source_sha256': sha(raw), 'published_bytes': len(data),
        'published_sha256': sha(data), 'transformation': transformation,
    }


for name in ['model-metadata', 'transport-canary', 'schema-holdout',
             'audit-calibration', 'chat-thinking-diagnostic', 'production-holdout-v15']:
    put(base / f'{name}.json', f'model/{name}.json', 'report')
for name in ['transport-canary.py', 'schema-holdout.py', 'audit-diagnostic.py',
             'chat-thinking-diagnostic.py', 'production-holdout.py',
             'unseen-audit-cases.json', 'reference-holdout-cases.json',
             'document-scenarios.py', 'startup-probe.py']:
    put(base / name, f'methods/{name}')
put(base / 'recorded-documents.py', 'methods/recorded-documents-v16-pinned.py')
put(Path('/private/tmp/noye-phase8-20261014/support-holdout.py'),
    'methods/known-calibration-cases.py')
for name in ['backend-product-coverage', 'model-memory-before',
             'model-memory-after-holdout', 'native-original-observation',
             'verifier-wire-stability', 'v16-manual-review']:
    put(base / f'{name}.json', f'{name}.json')
put(base / 'startup/measurements.json', 'startup/measurements.json')
for name in ['transport-canary', 'schema-holdout', 'audit-calibration',
             'chat-thinking-diagnostic', 'production-holdout-v15',
             'import-profile', 'v16-regressions', 'backend-full', 'backend-build',
             'frozen-v16', 'startup-probe', 'audit-regressions',
             'audit-regressions-loopback', 'v17-first-regressions',
             'v17-regressions', 'v18-regressions']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for source in (base / 'comparison').glob('comparison-*.json'):
    put(source, 'model/comparison-v15.json', 'report')
# Only invoke this extension once the scenario runner has finished all attempts.
if (base / 'v16-scenarios.json').exists():
    scenarios = json.loads((base / 'v16-scenarios.json').read_text())
    if len(scenarios['rows']) == 5:
        put(base / 'v16-scenarios.json', 'model/v16-scenarios.json')
        for source in (base / 'v16-documents').glob('*.json'):
            put(source, 'model/v16/' + source.name, 'report')
        for name in ['comparison', 'collection', 'report', 'partial', 'empty']:
            put(base / f'outputs/v16-{name}.log', f'logs/v16-{name}.txt', 'log')
record['files'] = sorted(files.values(), key=lambda entry: entry['file'])
for name in ['backend-v18-product-coverage', 'v18-sidecar', 'v18-code-hashes',
             'v18-bundled-payload', 'bundled-sidecar-failure',
             'signing-argument-contract', 'tauri-qa-hardened-failure', 'tauri-qa',
             'original-port-observation', 'native-original-command-observation',
             'native-original-command-build']:
    put(base / f'{name}.json', f'{name}.json')
for name in ['backend-v18-full', 'backend-v18-build', 'frozen-v18',
             'native-v18-bundle', 'native-v18-signature',
             'native-v18-hardened-sidecar-signature', 'native-v18-local-bundle',
             'native-v18-local-signature', 'original-command-first-tests',
             'original-command-tests', 'frontend-original-command-full',
             'frontend-original-command-lint', 'frontend-original-command-types',
             'frontend-original-command-build', 'native-original-command-bundle',
             'native-original-command-signature', 'frozen-original-command-bundled',
             'frozen-original-command-folder']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for name in ['recorded-documents-current.py', 'document-scenarios-v18.py']:
    put(base / name, f'methods/{name}')
put(base / 'reference-holdout-v18.json', 'model/reference-holdout-v18.json', 'report')
put(base / 'outputs/reference-holdout-v18.log', 'logs/reference-holdout-v18.txt', 'log')
for name in ['translation-controls.py', 'production_holdout_client.py',
             'review-translation-controls.py', 'translation-reference-cases.json',
             'document-scenarios-v20.py']:
    put(base / name, f'methods/{name}')
put(base / 'translation-controls-v19.json', 'model/translation-controls-v19.json', 'report')
put(base / 'translation-controls-review-v20.json', 'translation-controls-review-v20.json')
put(base / 'v20-code-hashes.json', 'v20-code-hashes.json')
for name in ['translation-controls-harness-failure', 'translation-controls-v19',
             'v19-regressions', 'backend-v19-full', 'v20-regressions', 'backend-v20-full']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for name in ['native-print-fixture', 'native-print-fixture-fixed',
             'native-original-print-check', 'native-original-print-fixed-check',
             'v20-tested-bundled-sidecar', 'v20-final-sidecar-equality']:
    put(base / f'{name}.json', f'{name}.json')
put(base / 'inspect-native-print.py', 'methods/inspect-native-print.py')
for name in ['Phase 8 original command print QA.pdf',
             'Phase 8 original command print fixed QA.pdf',
             'original-command-page-1.png', 'original-command-fixed-page-1.png']:
    put(base / 'exports' / name, 'pdf/' + name)
for name in ['backend-v20-build', 'native-v20-bundle', 'native-v20-signature',
             'frozen-v20-bundled', 'frontend-print-url-build',
             'native-print-url-bundle', 'native-print-url-signature']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for name in ['native-save-panel-refresh-observation', 'v20-comparison-manual',
             'v20-collection-manual']:
    put(base / f'{name}.json', f'{name}.json')
put(base / 'multiple-original-controls.json', 'methods/multiple-original-controls.json')
for name in ['save-panel-refresh-tests', 'save-panel-refresh-clippy',
             'native-save-panel-refresh-bundle']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for name in ['Phase8 generated AT-201.pdf', 'save-panel-refresh-page-1.png']:
    put(base / 'exports' / name, 'pdf/' + name)
for name in ['v20-report-manual', 'v20-partial-manual', 'v20-runtime-bindings']:
    put(base / f'{name}.json', f'{name}.json')
if len(json.loads((base / 'v20-scenarios.json').read_text())['rows']) == 5:
    put(base / 'v20-scenarios.json', 'model/v20-scenarios.json')
    for source in (base / 'v20-documents').glob('*.json'):
        put(source, 'model/v20/' + source.name, 'report')
    for name in ['comparison', 'collection', 'report', 'partial', 'empty']:
        put(base / f'outputs/v20-{name}.log', f'logs/v20-{name}.txt', 'log')
if (base / 'v18-scenarios.json').exists():
    scenarios = json.loads((base / 'v18-scenarios.json').read_text())
    if len(scenarios['rows']) == 5:
        put(base / 'v18-scenarios.json', 'model/v18-scenarios.json')
        for source in (base / 'v18-documents').glob('*.json'):
            put(source, 'model/v18/' + source.name, 'report')
        for name in ['comparison', 'collection', 'report', 'partial', 'empty']:
            put(base / f'outputs/v18-{name}.log', f'logs/v18-{name}.txt', 'log')
for name in ['v21-code-hashes', 'native-v21-literal-build',
             'native-literal-final-initial-checks', 'native-literal-final-review']:
    put(base / f'{name}.json', f'{name}.json')
for name in ['multiple-claim-controls.json', 'multiple-claim-controls.py',
             'inspect-literal-final.py']:
    put(base / name, f'methods/{name}')
for name in ['backend-v21-full', 'v21-regressions', 'backend-v21-build',
             'frozen-v21-bundled', 'frontend-literal-print-build',
             'native-v21-literal-bundle', 'native-v21-literal-signature']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for name in ['Phase8 generated AT-201.pdf', 'Phase 8 complex PDF QA.pdf']:
    put(base / 'exports/literal-final' / name, 'pdf/literal-final/' + name)
for kind, count in [('short', 1), ('complex', 7)]:
    for n in range(1, count + 1):
        name = f'native-literal-{kind}-page-{n}.png'
        put(base / name, 'pdf/literal-final/' + name)
for name in ['multiple-original-v21', 'multiple-claim-v21', 'v20-candidates-replayed-v21']:
    put(base / f'{name}.json', f'model/{name}.json', 'report')
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
put(base / 'multiple-original-v21-manual.json', 'multiple-original-v21-manual.json')
for name in ['review-multiple-original-v21.py', 'v20-candidate-replay-cases.json',
             'replay-v20-candidates.py', 'isolated-evidence-controls.json',
             'isolated-evidence-controls.py']:
    put(base / name, f'methods/{name}')
for name in ['v22-code-hashes']:
    put(base / f'{name}.json', f'{name}.json')
for name in ['v22-regressions', 'backend-v22-full']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for name in ['isolated-evidence-v22', 'multiple-claim-replayed-v22']:
    put(base / f'{name}.json', f'model/{name}.json', 'report')
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for name in ['multiple-claim-v21-manual', 'multiple-claim-v22-manual',
             'v21-single-wire-v22-equality', 'native-v22-build-review']:
    put(base / f'{name}.json', f'{name}.json')
for name in ['verify-v21-single-wire-v22.py', 'build-v22-native.py']:
    put(base / name, f'methods/{name}')
for name in ['backend-v22-build', 'native-v22-bundle', 'native-v22-signature',
             'frozen-v22-bundled']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for name in ['live-integration-v22', 'live-integration-corrected', 'live-integration-review']:
    put(base / f'{name}.json', f'{name}.json')
for name in ['run-live-integration.py', 'run-live-integration-corrected.py',
             'live-integration-nodeids.json']:
    put(base / name, f'methods/{name}')
for name in ['live-integration-v22', 'live-integration-corrected', 'live-fixture-regressions']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
for group in ['live-integration', 'live-integration-corrected']:
    for source in sorted((base / group).glob('case-*.log')):
        put(source, f'logs/{group}/' + source.stem + '.txt', 'log')
    for source in sorted((base / group).glob('case-*.xml')):
        put(source, f'logs/{group}/' + source.name, 'xml')
for name in ['native-folder-wiki-observations', 'wiki-suggestion-sidecar-equality']:
    put(base / f'{name}.json', f'{name}.json')
for name in ['wiki-suggestion-tests', 'frontend-wiki-suggestion-build',
             'native-wiki-suggestion-bundle', 'native-wiki-suggestion-signature']:
    put(base / f'outputs/{name}.log', f'logs/{name}.txt', 'log')
put(base / 'validate-evidence.py', 'methods/validate-evidence.py')
put(base / 'publish-current.py', 'methods/publish-evidence.py')
record['files'] = sorted(files.values(), key=lambda entry: entry['file'])
record_file.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'curated_records': len(files)}))
