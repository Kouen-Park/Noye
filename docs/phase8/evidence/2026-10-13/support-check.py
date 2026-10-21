import hashlib,json,platform,sqlite3,sys,time,uuid
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from app.config import get_settings
from app.db import source_documents as store
from app.db.database import init_schema
from app.evaluation.source_documents import MeasuredClient,save_report
from app.services.source_documents import pipeline,local
root=Path('/private/tmp/noye-phase8-20261012/source-comparison/knowledge')
alpha=(root/'Course/01-한국어.md').read_text().strip()
beta=(root/'Course/02-English.txt').read_text().strip()
cases=[
 ('translated-capacity',True,{'text':'Project Alpha has a storage capacity of 37 litres.','quotes':['Alpha 프로젝트의 저장 용량은 37리터입니다.'],'original_passages':[alpha]}),
 ('translated-sunday',True,{'text':'Project Alpha stops writes on Sundays.','quotes':['Alpha는 SQLite를 사용하며 일요일에는 쓰기를 중지합니다.'],'original_passages':[alpha]}),
 ('translated-backup',True,{'text':'Project Alpha performs backups once per day.','quotes':['백업은 하루에 한 번 실행됩니다.'],'original_passages':[alpha]}),
 ('recorded-volume',True,{'text':'Project Beta stores 92 litres.','quotes':['Project Beta stores 92 litres.'],'original_passages':[beta]}),
 ('capacity-strengthening',False,{'text':'Project Beta has a maximum storage capacity of 92 litres.','quotes':['Project Beta stores 92 litres.'],'original_passages':[beta]}),
 ('invented-condition',False,{'text':'Project Alpha is read-only on Saturdays.','quotes':['Alpha는 SQLite를 사용하며 일요일에는 쓰기를 중지합니다.'],'original_passages':[alpha]}),
 ('cross-language-comparison',True,{'text':'Alpha runs backups once per day, whereas Beta runs them twice per day.','quotes':['백업은 하루에 한 번 실행됩니다.','Backups run twice a day.'],'original_passages':[alpha,beta]}),
 ('wrong-frequency',False,{'text':'Project Alpha performs backups twice per day.','quotes':['백업은 하루에 한 번 실행됩니다.'],'original_passages':[alpha]})]
settings=get_settings()
with closing(sqlite3.connect(':memory:')) as db, closing(MeasuredClient()) as client:
 db.row_factory=sqlite3.Row
 init_schema(db)
 identifier=str(uuid.uuid4())
 db.execute("INSERT INTO source_document_requests(id,request_json,manifest_json,created_at,updated_at) VALUES (?,'{}','[]','test','test')",(identifier,))
 req=store.request(db,identifier)
 events=[]
 context=SimpleNamespace(connection=db,checkpoint=lambda *args:None,report=lambda *args,**kw:events.append({'stage':args[0],'state':args[1],**kw}))
 report={'prompt_version':local.PROMPT_VERSION,'system_sha256':hashlib.sha256(local.SYSTEM.encode()).hexdigest(),'support_system_sha256':hashlib.sha256(local.system({'task':'verify_support'}).encode()).hexdigest(),'local_source_sha256':hashlib.sha256(Path(local.__file__).read_bytes()).hexdigest(),'pipeline_sha256':hashlib.sha256(Path(pipeline.__file__).read_bytes()).hexdigest(),'model':settings.ollama_model,'context_tokens':settings.generation_context_tokens,'output_tokens':settings.generation_output_tokens,'thinking':settings.ollama_thinking,'platform':platform.platform(),'corpus':{'alpha':alpha,'beta':beta},'cases':[{'id':i,'expected':e,'input':c} for i,e,c in cases],'model_calls':client.calls,'note':'Eight synthetic bilingual support judgments using production verify and its exact input; isolated in-memory request/cache. This is not full document quality or a semantic guarantee.'}
 if Path(sys.argv[1]).exists(): raise FileExistsError(sys.argv[1])
 print(json.dumps({'started':local.PROMPT_VERSION,'cases':len(cases),'batching':'one claim per judgment'}),flush=True)
 began=time.monotonic()
 report['rows']=[]
 target=Path(sys.argv[1])
 try:
  for i,expected,claim in cases:
   one=time.monotonic()
   actual=pipeline.verify(context,req,'phase8-support-clinic:'+i,[claim],settings,client,strict=False)[0]
   row={'id':i,'expected':expected,'supported':actual,'matches_rubric':expected==actual,'seconds':round(time.monotonic()-one,3)}
   report['rows'].append(row)
   print(json.dumps(row),flush=True)
   target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 except Exception as exc:
  report['error']={'type':type(exc).__name__,'message':str(exc)}
 finally:
  report['seconds']=round(time.monotonic()-began,3)
  report['events']=events
  target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'rows':report['rows'],'error':report.get('error'),'seconds':report['seconds'],'report':str(target)}),flush=True)
