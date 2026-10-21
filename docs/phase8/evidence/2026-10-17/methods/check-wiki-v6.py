"""One fresh whole Wiki attempt on the known invented corpus using production v6; no retry. Wait for packaging to avoid overlapping heavy work."""
import json,os,subprocess,sys,time
from pathlib import Path
import httpx
root=Path('/private/tmp/noye-phase8-20261017');start=time.monotonic()
while True:
 try:
  d=json.loads((root/'final-checks.json').read_text());ready=len(d['stages'])==4 and all(x['exit_code']==0 for x in d['stages'])
 except (FileNotFoundError,ValueError):ready=False
 if ready:break
 if time.monotonic()-start>900:raise TimeoutError('Packaging unfinished; Wiki generation not started')
 time.sleep(3)
env={**os.environ,'OLLAMA_BASE_URL':'http://127.0.0.1:11439','OLLAMA_MODEL':'qwen3.5:4b','OLLAMA_EMBEDDING_MODEL':'embeddinggemma','GENERATION_CONTEXT_TOKENS':'8192','GENERATION_OUTPUT_TOKENS':'2048','OLLAMA_THINKING':'false','LOG_TO_FILE':'false','PYTHONPATH':'/Users/gavinpark/Projects/Noye/backend','OPENAI_API_KEY':'','ANTHROPIC_API_KEY':'','GEMINI_API_KEY':''}
report={'method':__doc__};one=time.monotonic()
with httpx.Client(timeout=30,trust_env=False) as c:
 assert not c.get(env['OLLAMA_BASE_URL']+'/api/ps').json()['models']
argv=[sys.executable,'/private/tmp/noye-phase8-20261016/recorded-documents-current.py','--workspace',str(root/'v6-wiki'),'--scenario','wiki']
with (root/'wiki-v6-whole.log').open('x') as out:
 p=subprocess.run(argv,env=env,stdout=out,stderr=subprocess.STDOUT)
report.update(argv=argv,exit_code=p.returncode,wall_seconds=round(time.monotonic()-one,3))
with httpx.Client(timeout=60,trust_env=False) as c:
 report['unload_status']={m:c.post(env['OLLAMA_BASE_URL']+'/api/generate',json={'model':m,'keep_alive':0}).status_code for m in ['qwen3.5:4b','embeddinggemma']}
 report['loaded_after']=c.get(env['OLLAMA_BASE_URL']+'/api/ps').json()
(root/'wiki-v6-whole-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
raise SystemExit(p.returncode)
