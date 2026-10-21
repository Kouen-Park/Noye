"""Sequential frontend tests, types, lint and actual desktop static build after QA model unload. Native bundling is separate so the running QA app is not overwritten."""
import json,os,subprocess,time,hashlib
from pathlib import Path
import httpx
base=Path('/private/tmp/noye-phase8-20261021-followup');root=Path('/Users/gavinpark/Projects/Noye');target=base/'frontend-checks.json';assert not target.exists()
with httpx.Client(timeout=20,trust_env=False) as c:
 for model in ['qwen3.5:4b','embeddinggemma']: c.post('http://127.0.0.1:11439/api/generate',json={'model':model,'keep_alive':0}).raise_for_status()
 assert c.get('http://127.0.0.1:11439/api/ps').json()['models']==[]
report={'method':__doc__,'source_commit':subprocess.check_output(['git','-c','core.fsmonitor=false','rev-parse','HEAD'],cwd=root,text=True).strip(),'stages':[]}
for name,argv in [('frontend-tests',['npm','test']),('frontend-types',['npx','tsc','--noEmit']),('frontend-lint',['npm','run','lint']),('desktop-ui-build',['npm','run','desktop:ui'])]:
 start=time.monotonic();log=base/(name+'.log')
 with log.open('x') as out: run=subprocess.run(argv,cwd=root/'frontend',stdout=out,stderr=subprocess.STDOUT)
 row={'name':name,'argv':argv,'exit_code':run.returncode,'seconds':round(time.monotonic()-start,3),'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()};report['stages'].append(row);target.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(row),flush=True)
 if run.returncode:raise SystemExit(run.returncode)
