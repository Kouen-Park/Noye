"""Sequential local ad-hoc package checks after model unload; not trusted distribution."""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
from PyInstaller.archive.readers import CArchiveReader

root = Path('/Users/gavinpark/Projects/Noye')
qa = Path('/private/tmp/noye-phase8-20261017/v7')
target = qa / 'build-review.json'
if target.exists():
    raise FileExistsError(target)
with httpx.Client(timeout=10, trust_env=False) as client:
    assert not client.get('http://127.0.0.1:11439/api/ps').json()['models'], 'Unload QA models first'
bundle = root / 'frontend/src-tauri/target/release/bundle/macos/Noye Phase8 QA.app'
sidecar = bundle / 'Contents/MacOS/noye-backend'
env = {**os.environ, 'CARGO_HOME': str(root / '.desktop-tools/cargo'),
       'RUSTUP_HOME': str(root / '.desktop-tools/rustup'),
       'PATH': str(root / '.desktop-tools/cargo/bin')+':'+os.environ['PATH'],
       'APPLE_SIGNING_IDENTITY': '-', 'NOYE_TEST_SIDECAR': str(sidecar),
       'LOG_TO_FILE': 'false'}
stages = [
    ('sidecar-build', ['npm', 'run', 'desktop:backend'], root / 'frontend'),
    ('native-bundle', ['npx', 'tauri', 'build', '--bundles', 'app', '--config',
                      '/private/tmp/noye-phase8-20261016/tauri-qa.json'], root / 'frontend'),
    ('native-signature', ['codesign', '--verify', '--deep', '--strict', str(bundle)], root),
    ('frozen-bundled', [str(root / 'backend/.venv/bin/python'), '-m', 'pytest', '-q',
                       'app/tests/test_desktop.py', 'app/tests/test_native_folder_protocol.py'], root / 'backend'),
]
report = {'method': __doc__, 'stages': [], 'source_commit': subprocess.check_output(
    ['git', '-c', 'core.fsmonitor=false', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()}
for name, argv, cwd in stages:
    log = qa / (name+'.log')
    print(json.dumps({'starting': name}), flush=True)
    began = time.monotonic()
    with log.open('x') as output:
        run = subprocess.run(argv, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT)
    row = {'name': name, 'argv': argv, 'seconds': round(time.monotonic()-began, 3),
           'exit_code': run.returncode, 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
    report['stages'].append(row)
    target.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(row), flush=True)
    if run.returncode:
        raise SystemExit(run.returncode)
report['files'] = {str(p.relative_to(bundle)): {'bytes': p.stat().st_size,
    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    for p in [sidecar, bundle / 'Contents/MacOS/noye-desktop']}
archive = CArchiveReader(str(sidecar)).open_embedded_archive('PYZ.pyz')
report['bundled_prompt_versions'] = {}
for module, version in [('app.services.source_documents.local', 'source-document-v23'),
                        ('app.services.wiki.local', 'wiki-grounded-v7')]:
    code = archive.extract(module)
    assert version in code.co_consts, (module, version)
    report['bundled_prompt_versions'][module] = version
target.write_text(json.dumps(report, indent=2)+'\n')
