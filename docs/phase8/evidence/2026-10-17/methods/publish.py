"""Explicit synthetic QA evidence publication; excludes runtime state and credentials."""
import hashlib
import json
import re
from pathlib import Path

base = Path('/private/tmp/noye-phase8-20261017')
root = Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-17')
final = json.loads((base / 'v7-final/checks.json').read_text())
assert len(final['stages']) == 4 and all(s['exit_code'] == 0 for s in final['stages']), 'Final execution stages unfinished; semantic acceptance is reviewed separately'
assert (base / 'v7-final/manual.json').exists(), 'Actual final Wiki text has not been manually reviewed'
root.mkdir(parents=True, exist_ok=True)
index = root / 'publication.json'
record = json.loads(index.read_text()) if index.exists() else {'method': __doc__, 'files': []}
entries = {x['file']: x for x in record['files']}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def put(source, relative, kind='copy'):
    raw = source.read_bytes()
    data, transformation = raw, 'Byte-for-byte copy'
    if kind == 'report':
        report = json.loads(raw)
        for call in report.get('model_calls', []):
            if call.get('task') == 'model_preflight' and call.get('http_status') == 200:
                metadata = call.pop('raw_response', None)
                if metadata:
                    call['publication'] = {'omitted': 'Repeated successful model metadata',
                        'sha256': digest(metadata.encode()), 'bytes': len(metadata.encode())}
        data = (json.dumps(report, ensure_ascii=False, indent=2)+'\n').encode()
        transformation = 'Repeated successful preflight metadata omitted with hash; generation inputs/outputs unchanged'
    elif kind == 'log':
        value = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', raw.decode()).replace('\r', '\n')
        data = ('\n'.join(line.rstrip() for line in value.splitlines()).strip()+'\n').encode()
        transformation = 'ANSI/CR/trailing whitespace normalized'
    target = root / relative
    if relative in entries and target.read_bytes() != data:
        raise ValueError('Refusing to overwrite changed published evidence: '+relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    entries[relative] = {'file': relative, 'source': str(source),
        'source_bytes': len(raw), 'source_sha256': digest(raw),
        'published_bytes': len(data), 'published_sha256': digest(data),
        'transformation': transformation}


for name in ['analysis-probe', 'analysis-probe-corrected', 'support-v23', 'relations-v4', 'relations-v5', 'relations-v6', 'presence-zero-probe', 'stances-probe', 'wiki-support-probe']:
    put(base / (name+'.json'), 'model/'+name+'.json', 'report')
for name in ['analysis-probe-cases.json', 'analysis-acceptance-controls.json',
             'relation-controls.json', 'relation-original-only-controls.json', 'relation-schema-controls.json',
             'sampling-neutral-controls.json', 'stance-controls.json', 'coverage.ini',
             'probe-analysis.py', 'verify-v23.py',
             'probe-relations.py', 'probe-relations-v5.py', 'probe-relations-v6.py',
             'probe-presence.py', 'probe-stances.py', 'probe-wiki-support.py', 'after-scenarios.py',
             'document-scenarios-v23.py', 'replay-wiki-quantity.py', 'check-relation-wire-v7.py',
             'build-native-v7.py', 'build-native-v7-final.py', 'checks-v7.py', 'checks-v7-final.py',
             'check-wiki-v6.py', 'build-native.py', 'finish-checks.py', 'publish.py']:
    put(base / name, 'methods/'+name)
for name in ['analysis-probe', 'analysis-probe-corrected', 'support-v23', 'relations-v4',
             'relations-v5', 'relations-v6', 'wiki-tests', 'source-v23-tests', 'backend-full',
             'wiki-v5-tests', 'wiki-v6-tests', 'presence-zero-probe', 'stances-probe',
             'wiki-support-probe', 'experiment-sequence', 'backend-final', 'backend-lint',
             'packaging-checks', 'final-checks', 'wiki-v6-whole', 'wiki-v6-sequence', 'wiki-v7-tests', 'wiki-v7-tests-corrected']:
    put(base / (name+'.log'), 'logs/'+name+'.txt', 'log')
put(base / 'native-original-observation.json', 'native-original-observation.json')
# Finished whole-scenario, packaging and manual-review records are appended
# explicitly at publication time; this script must never glob runtime folders.
for name in ['v23-scenarios.json', 'model-review.json', 'build-review.json',
             'model-sampling-defaults.json', 'sampling-comparison-review.json',
             'experiment-sequence.json', 'final-checks.json', 'backend-product-coverage.json',
             'wiki-v6-whole-review.json', 'wiki-v6-whole-manual.json',
             'wiki-v7-quantity-replay.json', 'relation-wire-v7.json', 'cleanup.json']:
    if (base / name).exists():
        put(base / name, name)
for scenario in ['comparison', 'collection', 'report', 'partial', 'empty', 'wiki']:
    source = base / ('v23-'+scenario+'-manual.json')
    if source.exists():
        put(source, source.name)
if (base / 'v23-scenarios.json').exists():
    if len(json.loads((base / 'v23-scenarios.json').read_text())['rows']) != 6:
        raise ValueError('Whole-scenario runner has not finished')
    for source in (base / 'v23-documents').glob('*.json'):
        put(source, 'model/v23/'+source.name, 'report')
    for scenario in ['comparison', 'collection', 'report', 'partial', 'empty', 'wiki']:
        put(base / ('v23-'+scenario+'.log'), 'logs/v23-'+scenario+'.txt', 'log')
for source in (base / 'v6-wiki').glob('*.json'):
    put(source, 'model/v6-wiki/'+source.name, 'report')
for name in ['sidecar-build', 'native-bundle', 'native-signature', 'frozen-bundled']:
    if (base / (name+'.log')).exists():
        put(base / (name+'.log'), 'logs/'+name+'.txt', 'log')
for directory in ['v7', 'v7-final']:
    for name in ['checks.json', 'build-review.json', 'backend-product-coverage.json', 'manual.json']:
        source = base / directory / name
        if source.exists():
            put(source, directory+'/'+name)
    put(base / directory / 'coverage.ini', 'methods/'+directory+'-coverage.ini')
    for name in ['checks', 'backend-final', 'backend-lint', 'packaging-checks',
                 'sidecar-build', 'native-bundle', 'native-signature', 'frozen-bundled', 'wiki-whole']:
        source = base / directory / (name+'.log')
        if source.exists():
            put(source, 'logs/'+directory+'/'+name+'.txt', 'log')
    for source in (base / directory / 'wiki').glob('*.json'):
        put(source, 'model/'+directory+'/'+source.name, 'report')
record['files'] = sorted(entries.values(), key=lambda x: x['file'])
index.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
for entry in record['files']:
    data = (root / entry['file']).read_bytes()
    assert digest(data) == entry['published_sha256'] and len(data) == entry['published_bytes']
    if entry['file'].endswith('.json'):
        json.loads(data, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
    assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)', data)
listed = set(entries) | {'publication.json'}
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} == listed
print(json.dumps({'files': len(entries), 'hashes_and_strict_json_valid': True,
                  'common_credential_pattern_matches': 0}))
