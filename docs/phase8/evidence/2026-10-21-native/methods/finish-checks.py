"""Current v27/v13 full backend, lint and frozen/native rebuild after dedicated inference unload. No new whole-generation acceptance is implied."""
import json,os,subprocess,sys,time
from pathlib import Path
import httpx
repo=Path('/Users/gavinpark/Projects/Noye');base=Path('/private/tmp/noye-phase8-20261021-native');qa=base/'final'
model_env={**os.environ,'PYTHONPATH':str(repo/'backend'),'COVERAGE_FILE':str(qa/'.coverage'),'LOG_TO_FILE':'false',
'OLLAMA_BASE_URL':'http://127.0.0.1:11439','OLLAMA_MODEL':'qwen3.5:4b','OLLAMA_EMBEDDING_MODEL':'embeddinggemma','GENERATION_CONTEXT_TOKENS':'8192','GENERATION_OUTPUT_TOKENS':'2048','OLLAMA_THINKING':'false','OPENAI_API_KEY':'','ANTHROPIC_API_KEY':'','GEMINI_API_KEY':''}
env={**os.environ,'PYTHONPATH':str(repo/'backend'),'COVERAGE_FILE':str(qa/'.coverage'),'LOG_TO_FILE':'false'}
stages=[
('backend-final',[sys.executable,'-m','pytest','-q','--cov=app','--cov-branch','--cov-config='+str(qa/'coverage.ini'),'--cov-report=json:'+str(qa/'backend-product-coverage.json'),'--cov-report=term'],repo/'backend'),
('backend-lint',[str(repo/'backend/.venv/bin/ruff'),'check','app'],repo/'backend'),
('packaging-checks',[sys.executable,str(base/'build-native.py')],repo)]
report={'method':__doc__,'stages':[]}
for name,argv,cwd in stages:
 with httpx.Client(timeout=30,trust_env=False) as c:
  assert not c.get(model_env['OLLAMA_BASE_URL']+'/api/ps').json()['models']
 print(json.dumps({'starting':name}),flush=True);one=time.monotonic()
 with (qa/(name+'.log')).open('x') as out:
  p=subprocess.run(argv,cwd=cwd,env=model_env if name=='wiki-whole' else env,stdout=out,stderr=subprocess.STDOUT)
 row={'name':name,'argv':argv,'seconds':round(time.monotonic()-one,3),'exit_code':p.returncode}
 if name=='wiki-whole':
  with httpx.Client(timeout=60,trust_env=False) as c:
   row['unload_status']={m:c.post(model_env['OLLAMA_BASE_URL']+'/api/generate',json={'model':m,'keep_alive':0}).status_code for m in ['qwen3.5:4b','embeddinggemma']}
   row['loaded_after']=c.get(model_env['OLLAMA_BASE_URL']+'/api/ps').json()
 report['stages'].append(row);(qa/'checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(row),flush=True)
 if p.returncode:raise SystemExit(p.returncode)
