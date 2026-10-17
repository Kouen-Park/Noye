"""Actual production v23 support audit on the two saved unsafe Wiki summaries and their faithful key points. Known regressions, not fresh holdout or end-to-end Wiki acceptance."""
import hashlib, json, sqlite3, sys, time
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
import httpx
from app.config import Settings
from app.db import source_documents as store
from app.db.database import init_schema
from app.services.source_documents import local,pipeline
sys.path.insert(0,'/private/tmp/noye-phase8-20261016')
from production_holdout_client import RecordedClient
root=Path('/private/tmp/noye-phase8-20261017'); target=root/'wiki-support-probe.json'
assert not target.exists()
source=next((root/'v23-documents').glob('wiki-*.json'))
wiki=json.loads(source.read_text());batches=[]
for row in wiki['revisions']:
 revision=row['revision'];evidence={p['id']:p['text'] for p in revision['evidence']}
 for i,s in enumerate(revision['metadata']['sections']):
  claims=[s['summary'],s['key_points'][0]]
  batches.append((row['source_id']+':'+str(i),[False,True],[{'text':c['text'],'quotes':[evidence[c['evidence_id']]],'original_passages':[evidence[c['evidence_id']]]} for c in claims]))
report={'method':__doc__,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'prompt_version':local.PROMPT_VERSION,'batches':batches,'rows':[]}
settings=Settings(_env_file=None,ollama_base_url='http://127.0.0.1:11439',ollama_model='qwen3.5:4b',generation_context_tokens=8192,generation_output_tokens=2048,ollama_thinking=False)
with closing(sqlite3.connect(':memory:')) as db, closing(RecordedClient()) as client:
 db.row_factory=sqlite3.Row;init_schema(db)
 db.execute("INSERT INTO source_document_requests(id,request_json,manifest_json,created_at,updated_at) VALUES ('probe','{}','[]','test','test')")
 req=store.request(db,'probe');context=SimpleNamespace(connection=db,checkpoint=lambda *a:None,report=lambda *a,**kw:None)
 report['model_calls']=client.calls;began=time.monotonic()
 for n,(name,expected,claims) in enumerate(batches):
  one=time.monotonic();row={'id':name,'valid':False,'expected':expected}
  try:
   actual=pipeline.verify(context,req,f'wiki-probe:{n}',claims,settings,client,strict=False)
   row.update(valid=True,actual=actual,matches=[a==e for a,e in zip(actual,expected,strict=True)])
  except Exception as e:row['error']={'type':type(e).__name__,'message':str(e)}
  row['seconds']=round(time.monotonic()-one,3);report['rows'].append(row)
  target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(row),flush=True)
 report['seconds']=round(time.monotonic()-began,3)
with httpx.Client(timeout=30,trust_env=False) as client:
 report['unload_status']=client.post(settings.ollama_base_url+'/api/generate',json={'model':settings.ollama_model,'keep_alive':0}).status_code
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
