"""Unchanged production v24 verifier on a separate installed local model; fixed eight-case suite from the paired comparison, not new holdouts or whole-document acceptance. Temperature remains the production 0; inherited sampling parameters differ with the model."""
import hashlib,json,sqlite3,sys,time
from pathlib import Path
from types import SimpleNamespace
from contextlib import closing
import httpx
from app.config import Settings
from app.db import source_documents as store
from app.db.database import init_schema
from app.services.source_documents import pipeline
sys.path.insert(0,'/private/tmp/noye-phase8-20261016')
from production_holdout_client import RecordedClient
root=Path('/private/tmp/noye-phase8-20261019');target=root/'alternative-support.json'
assert not target.exists()
source=root/'support-v24-resumed.json';prior=json.loads(source.read_text());assert len(prior['rows'])==16
settings=Settings(_env_file=None,ollama_base_url='http://127.0.0.1:11459',ollama_model='gemma4:e2b-it-qat',generation_context_tokens=8192,generation_output_tokens=3072,ollama_thinking=False)
with httpx.Client(timeout=30,trust_env=False) as c:
 assert not c.get('http://127.0.0.1:11439/api/ps').json()['models']
 assert not c.get(settings.ollama_base_url+'/api/ps').json()['models']
 descriptor=c.post(settings.ollama_base_url+'/api/show',json={'model':settings.ollama_model}).json()
 tags=c.get(settings.ollama_base_url+'/api/tags').json()
report={'method':__doc__,'prior_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'cases':prior['cases'],'model_info':descriptor['model_info'],'parameters':descriptor.get('parameters'),'model_tags':tags,'rows':[],'model_calls':[]}
with closing(sqlite3.connect(':memory:')) as db,closing(RecordedClient()) as client:
 db.row_factory=sqlite3.Row;init_schema(db);db.execute("INSERT INTO source_document_requests(id,request_json,manifest_json,created_at,updated_at) VALUES ('probe','{}','[]','test','test')")
 req=store.request(db,'probe');context=SimpleNamespace(connection=db,checkpoint=lambda *a:None,report=lambda *a,**kw:None)
 report['model_calls']=client.calls;start=time.monotonic()
 for n,case in enumerate(prior['cases']):
  began=time.monotonic();row={'id':case['id'],'expected':case['expected'],'valid':False}
  try:
   verdict=pipeline.verify(context,req,f'alternative:{n}',[{'text':case['text'],'quotes':case['originals'],'original_passages':case['originals']}],settings,client,strict=False)[0]
   row.update(valid=True,actual=verdict,correct=verdict==case['expected'])
  except Exception as e:row['error']={'type':type(e).__name__,'message':str(e)}
  row['seconds']=round(time.monotonic()-began,3);report['rows'].append(row)
  target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(row),flush=True)
 report['seconds']=round(time.monotonic()-start,3)
with httpx.Client(timeout=60,trust_env=False) as c:
 report['unload_status']=c.post(settings.ollama_base_url+'/api/generate',json={'model':settings.ollama_model,'keep_alive':0}).status_code
 report['loaded_after']=c.get(settings.ollama_base_url+'/api/ps').json()
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
