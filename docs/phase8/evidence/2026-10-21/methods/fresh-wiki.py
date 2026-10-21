"""Actual production Wiki summary stages on four controls fixed before these calls. Synthetic direct Passage inputs, no DB/filesystem publication, no catalogue/native or broad-quality claim. Normal v11 quantity revision/strict checks remain enabled."""
import hashlib,json,time
from pathlib import Path
from contextlib import closing
import httpx
from app.config import Settings
from app.models.wiki import Passage,SourceRef
from app.evaluation.source_documents import MeasuredClient
from app.services.wiki import pipeline,local
qa=Path('/private/tmp/noye-phase8-20261021');target=qa/'fresh-wiki.json';assert not target.exists()
assert len(json.loads((qa/'scenarios.json').read_text())['rows'])==3
cases=json.loads((qa/'fresh-wiki-controls.json').read_text());settings=Settings(_env_file=None,ollama_base_url='http://127.0.0.1:11439',ollama_model='qwen3.5:4b',generation_context_tokens=8192,generation_output_tokens=2048,ollama_thinking=False)
with httpx.Client(timeout=30,trust_env=False) as c:assert not c.get(settings.ollama_base_url+'/api/ps').json()['models']
class Recorded(MeasuredClient):
 def post(self,url,*,json):
  with (qa/'fresh-wiki-events.jsonl').open('a') as out:out.write(__import__('json').dumps({'state':'started','endpoint':url,'request':json,'at':time.time()},ensure_ascii=False)+'\n')
  before=len(self.calls)
  try:return super().post(url,json=json)
  finally:
   if len(self.calls)>before:self.calls[-1]['request']=json
report={'method':__doc__,'cases':cases,'controls_sha256':hashlib.sha256((qa/'fresh-wiki-controls.json').read_bytes()).hexdigest(),'prompt_version':local.PROMPT_VERSION,'rows':[],'model_calls':[]}
with closing(Recorded()) as client:
 report['model_calls']=client.calls;start=time.monotonic()
 for case in cases:
  text=case['text'];digest=hashlib.sha256(text.encode()).hexdigest();row={'id':case['id'],'valid':False};one=time.monotonic()
  source=SourceRef(source_id=case['id'],root_id=None,relative_path=case['id']+'.txt',name=case['id'],source_hash=digest,source_version=digest,availability='available',indexing_status='READY')
  original=Passage(id=case['id'],source=source,passage_index=0,start=0,end=len(text),text=text)
  try:
   result,evidence=pipeline.summarize([original],categories=[],settings=settings,client=client)
   row.update(valid=True,result=result,evidence=[p.model_dump() for p in evidence])
  except Exception as e:row['error']={'type':type(e).__name__,'message':str(e)}
  row['seconds']=round(time.monotonic()-one,3);report['rows'].append(row);target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in row.items() if k not in ['result','evidence']},ensure_ascii=False),flush=True)
 report['seconds']=round(time.monotonic()-start,3)
with httpx.Client(timeout=60,trust_env=False) as c:
 report['unload_status']=c.post(settings.ollama_base_url+'/api/generate',json={'model':settings.ollama_model,'keep_alive':0}).status_code
 report['loaded_after']=c.get(settings.ollama_base_url+'/api/ps').json()
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
