"""Sequential local ad-hoc QA bundle and bundled-backend checks, model unloaded."""
import os
import json
import pathlib
import hashlib
import subprocess
import time

root = pathlib.Path('/Users/gavinpark/Projects/Noye')
qa = pathlib.Path('/private/tmp/noye-phase8-20261016')
bundle = root / 'frontend/src-tauri/target/release/bundle/macos/Noye Phase8 QA.app'
sidecar = bundle / 'Contents/MacOS/noye-backend'
env = {
    **os.environ,
    'CARGO_HOME': str(root / '.desktop-tools/cargo'),
    'RUSTUP_HOME': str(root / '.desktop-tools/rustup'),
    'PATH': str(root / '.desktop-tools/cargo/bin') + ':' + os.environ['PATH'],
    'APPLE_SIGNING_IDENTITY': '-',
    'NOYE_TEST_SIDECAR': str(sidecar),
    'LOG_TO_FILE': 'false',
}
stages = [
    ('backend-v22-build', ['npm', 'run', 'desktop:backend'], root / 'frontend'),
    ('native-v22-bundle', ['npx', 'tauri', 'build', '--bundles', 'app', '--config', str(qa / 'tauri-qa.json')], root / 'frontend'),
    ('native-v22-signature', ['codesign', '--verify', '--deep', '--strict', str(bundle)], root),
    ('frozen-v22-bundled', [str(root / 'backend/.venv/bin/python'), '-m', 'pytest', '-q', 'app/tests/test_desktop.py', 'app/tests/test_native_folder_protocol.py'], root / 'backend'),
]
report = {'method': __doc__, 'stages': []}
for name, argv, cwd in stages:
    log = qa / 'outputs' / f'{name}.log'
    print(json.dumps({'starting': name}), flush=True)
    began = time.monotonic()
    with log.open('x') as output:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT, check=False)
    row = {'name': name, 'argv': argv, 'seconds': round(time.monotonic() - began, 3), 'exit_code': result.returncode, 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
    report['stages'].append(row)
    print(json.dumps(row), flush=True)
    (qa / 'native-v22-build-review.json').write_text(json.dumps(report, indent=2) + '\n')
    if result.returncode:
        raise SystemExit(result.returncode)
report['files'] = {str(p.relative_to(bundle)): {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [sidecar, bundle / 'Contents/MacOS/noye-desktop']}
(qa / 'native-v22-build-review.json').write_text(json.dumps(report, indent=2) + '\n')
