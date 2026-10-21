"""One fresh whole Wiki, English comparison and Korean collection attempt under production v11/v25. Sequential inference; no failed job retry, no provider fallback and no simultaneous heavy tests/builds. Semantic acceptance is reviewed separately from job completion."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
import httpx
repo=Path('/Users/gavinpark/Projects/Noye');qa=Path('/private/tmp/noye-phase8-20261021');target=qa/'scenarios.json';assert not target.exists()
env={**os.environ,'PYTHONPATH':str(repo/'backend'),'OLLAMA_BASE_URL':'http://127.0.0.1:11439','OLLAMA_MODEL':'qwen3.5:4b','OLLAMA_EMBEDDING_MODEL':'embeddinggemma','GENERATION_CONTEXT_TOKENS':'8192','GENERATION_OUTPUT_TOKENS':'2048','OLLAMA_THINKING':'false','LOG_TO_FILE':'false','OPENAI_API_KEY':'','ANTHROPIC_API_KEY':'','GEMINI_API_KEY':''}
report={'method':__doc__,'source_commit':subprocess.check_output(['git','-c','core.fsmonitor=false','rev-parse','HEAD'],cwd=repo,text=True).strip(),'runtime_sha256':{n:hashlib.sha256((repo/'backend'/n).read_bytes()).hexdigest() for n in ['app/models/wiki.py','app/services/wiki/local.py','app/services/wiki/pipeline.py','app/services/source_documents/local.py','app/services/source_documents/pipeline.py','app/services/source_documents/presentation.py']},'rows':[]}
for scenario in ['wiki','comparison','collection']:
 with httpx.Client(timeout=30,trust_env=False) as c:assert not c.get(env['OLLAMA_BASE_URL']+'/api/ps').json()['models']
 workspace=qa/('current-'+scenario);assert not workspace.exists()
 argv=[sys.executable,str(qa/'recorded-current.py'),'--workspace',str(workspace),'--scenario',scenario]
 print(json.dumps({'starting':scenario}),flush=True);started=time.monotonic()
 one_env={**env,'NOYE_QA_EVENTS':str(qa/(scenario+'-events.jsonl'))}
 with (qa/(scenario+'-whole.log')).open('x') as out:p=subprocess.run(argv,cwd=repo,env=one_env,stdout=out,stderr=subprocess.STDOUT)
 row={'scenario':scenario,'argv':argv,'exit_code':p.returncode,'seconds':round(time.monotonic()-started,3)}
 reports=list(workspace.glob(scenario+'-*.json'))
 if reports:
  assert len(reports)==1;body=json.loads(reports[0].read_text());row.update(report=str(reports[0]),state=body.get('state',body.get('job',{}).get('state')),error=body.get('error',body.get('job',{}).get('error')))
 with httpx.Client(timeout=60,trust_env=False) as c:
  row['unload_status']={m:c.post(env['OLLAMA_BASE_URL']+'/api/generate',json={'model':m,'keep_alive':0}).status_code for m in ['qwen3.5:4b','embeddinggemma']}
  row['loaded_after']=c.get(env['OLLAMA_BASE_URL']+'/api/ps').json()
 report['rows'].append(row);target.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(row),flush=True)
