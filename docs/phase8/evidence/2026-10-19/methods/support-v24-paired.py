"""Paired production v24 configurations: non-thinking generate versus thinking chat, same original/system/schema/options (8192 context/3072 output). Four fresh Oct19 controls fixed before calls, then four known regressions. Not default-setting changes, whole-document acceptance or a controlled latency benchmark."""
import hashlib,json,sqlite3,sys,time
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
root=Path('/private/tmp/noye-phase8-20261019');old=Path('/private/tmp/noye-phase8-20261017');target=root/'support-v24-paired.json'
assert not target.exists()
fresh=[
 ['fresh-explicit-means',True,'Nightingale retains 45 records using a queue.',['A queue is the mechanism Nightingale uses to retain 45 records.']],
 ['fresh-independent-purpose',False,'Tern uses SQLite to achieve resilience.',['Tern is resilient. Tern uses SQLite.']],
 ['fresh-translated-interval',True,'Ginkgo backups run every six days.',['Ginkgo의 백업은 엿새마다 실행됩니다.']],
 ['fresh-observed-budget',False,'Lark currently caches 41 items.',['Lark has a cache budget of 41 items. It currently caches 5 items.']]
]
casefile=root/'support-v24-fresh-controls.json';casefile.write_text(json.dumps({'cases':fresh},indent=2)+'\n')
cases=[{'id':n,'expected':e,'text':t,'originals':o,'regression':False} for n,e,t,o in fresh]
comparison=json.loads(next((old/'v23-documents').glob('comparison-*.json')).read_text())
for c in comparison['model_calls']:
 if c.get('task')=='verify_support' and 'stores 92 litres using' in c['request']['prompt']:
  payload=json.loads(c['request']['prompt']);originals={p['original_index']:p['text'] for p in payload['original_passages']}
  for claim in payload['claims']:
   cases.append({'id':'known-unsafe-comparison','expected':False,'text':claim['text'],'originals':[originals[i] for i in claim['original_indexes']],'regression':True})
wiki=json.loads(next((old/'v7-final/wiki').glob('wiki-*.json')).read_text())
rev=wiki['revisions'][0]['revision'];c=rev['metadata']['sections'][0]['summary'];ev={p['id']:p['text'] for p in rev['evidence']}
cases.append({'id':'known-unsafe-wiki-summary','expected':False,'text':c['text'],'originals':[ev[c['evidence_id']]],'regression':True})
prior=json.loads((old/'support-v23.json').read_text())
for name,_,batch in prior['input_batches']:
 if name=='translated-adjoining-true':
  e,t,o=batch[0];cases.append({'id':'known-four-day-translation','expected':e,'text':t,'originals':o,'regression':True})
 if name=='shared-duplicate':
  e,t,o=batch[-1];cases.append({'id':'known-adjoining-backups','expected':e,'text':t,'originals':o,'regression':True})
assert len(cases)==8,len(cases)
report={'method':__doc__,'cases':cases,'fresh_sha256':hashlib.sha256(casefile.read_bytes()).hexdigest(),'source_commit':'c714e79','prompt_version':local.PROMPT_VERSION,'settings':{'context':8192,'output':3072,'temperature':0,'presence_penalty':'inherited model default 1.5'},'runtime_hashes':{Path(m.__file__).name:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in [local,pipeline]},'rows':[]}
settings=Settings(_env_file=None,ollama_base_url='http://127.0.0.1:11439',ollama_model='qwen3.5:4b',generation_context_tokens=8192,generation_output_tokens=3072,ollama_thinking=False)
with closing(sqlite3.connect(':memory:')) as db,closing(RecordedClient()) as client:
 db.row_factory=sqlite3.Row;init_schema(db);db.execute("INSERT INTO source_document_requests(id,request_json,manifest_json,created_at,updated_at) VALUES ('probe','{}','[]','test','test')")
 req=store.request(db,'probe');context=SimpleNamespace(connection=db,checkpoint=lambda *a:None,report=lambda *a,**kw:None)
 report['model_calls']=client.calls;started=time.monotonic()
 for n,c in enumerate(cases):
  # Counterbalance pair order; cache/load effects still prevent a controlled latency claim.
  for thinking in ([False,True] if n%2==0 else [True,False]):
   one=time.monotonic();row={'id':c['id'],'thinking':thinking,'expected':c['expected'],'regression':c['regression'],'valid':False};before=len(client.calls)
   try:
    claim={'text':c['text'],'quotes':c['originals'],'original_passages':c['originals']}
    actual=pipeline.verify(context,req,f'thinking:{n}:{thinking}',[claim],settings.model_copy(update={'ollama_thinking':thinking}),client,strict=False)
    row.update(valid=True,actual=actual[0],correct=actual[0]==c['expected'])
   except Exception as e:row['error']={'type':type(e).__name__,'message':str(e)}
   for call in client.calls[before:]:
    if call.get('task')=='verify_support' and call.get('raw_response'):
     try:
      raw=json.loads(call['raw_response']);trace=raw.get('thinking',raw.get('message',{}).get('thinking',''));row.update(thinking_characters=len(trace),thinking_sha256=hashlib.sha256(trace.encode()).hexdigest(),eval_count=raw.get('eval_count'),done_reason=raw.get('done_reason'))
     except ValueError:pass
   row['seconds']=round(time.monotonic()-one,3);report['rows'].append(row)
   target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(row,ensure_ascii=False),flush=True)
 report['seconds']=round(time.monotonic()-started,3)
with httpx.Client(timeout=30,trust_env=False) as c:
 report['unload_status']=c.post(settings.ollama_base_url+'/api/generate',json={'model':settings.ollama_model,'keep_alive':0}).status_code
 report['loaded_after']=c.get(settings.ollama_base_url+'/api/ps').json()
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
