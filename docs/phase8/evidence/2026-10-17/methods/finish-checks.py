"""Serialize the final diagnostic, full backend tests and QA packaging after inference unload."""
import json,os,subprocess,sys,time
from pathlib import Path
import httpx
root=Path('/Users/gavinpark/Projects/Noye');qa=Path('/private/tmp/noye-phase8-20261017')
began=time.monotonic()
while True:
 try:
  d=json.loads((qa/'stances-probe.json').read_text());ready=len(d['rows'])==15 and d.get('unload_status')==200 and 'seconds' in d
 except (FileNotFoundError,ValueError):ready=False
 if ready:break
 if time.monotonic()-began>900:raise TimeoutError('Stance experiment did not finish; no concurrent inference/build started')
 time.sleep(3)
env={**os.environ,'PYTHONPATH':str(root/'backend'),'COVERAGE_FILE':str(qa/'.coverage'),'LOG_TO_FILE':'false'}
commands=[
 ('wiki-support-probe',[sys.executable,str(qa/'probe-wiki-support.py')],root),
 ('backend-final',[sys.executable,'-m','pytest','-q','--cov=app','--cov-branch','--cov-config='+str(qa/'coverage.ini'),'--cov-report=json:'+str(qa/'backend-product-coverage.json'),'--cov-report=term'],root/'backend'),
 ('backend-lint',[str(root/'backend/.venv/bin/ruff'),'check','app'],root/'backend'),
 ('packaging-checks',[sys.executable,str(qa/'build-native.py')],root)]
report={'method':__doc__,'stages':[]}
for name,argv,cwd in commands:
 with httpx.Client(timeout=10,trust_env=False) as c:
  assert not c.get('http://127.0.0.1:11439/api/ps').json()['models']
 print(json.dumps({'starting':name}),flush=True);one=time.monotonic()
 with (qa/(name+'.log')).open('x') as log:
  p=subprocess.run(argv,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
 report['stages'].append({'name':name,'argv':argv,'seconds':round(time.monotonic()-one,3),'exit_code':p.returncode})
 (qa/'final-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['stages'][-1]),flush=True)
 if p.returncode:raise SystemExit(p.returncode)
