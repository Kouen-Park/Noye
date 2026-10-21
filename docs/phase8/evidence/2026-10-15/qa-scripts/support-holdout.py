"""Production mechanical guards + semantic verifier on unseen invented controls."""
import hashlib,json,platform,sqlite3,sys,time,uuid
from pathlib import Path
from types import SimpleNamespace
from contextlib import closing
from app.config import get_settings
from app.db.database import init_schema
from app.db import source_documents as store
from app.evaluation.source_documents import MeasuredClient,save_report
from app.services.source_documents import local,pipeline
A='Cedar의 용량은 18리터이다. Cedar는 일요일에 쓰기를 중지한다. 평일에는 쓰기가 허용된다.'
B='Oak stores 41 litres. Oak uses log files. The backup runs daily except Tuesdays.'
cases=[
 ('capacity-translation',True,'Cedar has a capacity of 18 litres.',[A]),
 ('capacity-is-not-content',False,'Cedar stores 18 litres.',[A]),
 ('content-is-not-capacity',False,'Oak has a capacity of 41 litres.',[B]),
 ('direct-storage',True,'Oak stores 41 litres.',[B]),
 ('swapped-subject',False,'Cedar stores 41 litres.',[A,B]),
 ('wrong-unit',False,'Oak stores 41 kilograms.',[B]),
 ('unsupported-purpose',False,'Oak stores 41 litres using log files.',[B]),
 ('independent-conjunction',True,'Oak stores 41 litres and uses log files.',[B]),
 ('lost-exception',False,'Oak runs its backup every day.',[B]),
 ('preserved-exception',True,'Oak runs its backup daily except on Tuesdays.',[B]),
 ('wrong-day',False,'Cedar stops writes on Saturdays.',[A]),
 ('unverified-absence',False,'No evidence was supplied for Cedar storage.',[B]),
 ('faithful-korean',True,'Oak는 41리터를 저장하고 로그 파일을 사용한다.',[B]),
 ('recorded-condition',True,'Cedar permits writes on weekdays and stops them on Sundays.',[A]),
]
with closing(sqlite3.connect(':memory:')) as db,closing(MeasuredClient()) as client:
 db.row_factory=sqlite3.Row;init_schema(db)
 identifier=str(uuid.uuid4())
 db.execute("INSERT INTO source_document_requests(id,request_json,manifest_json,created_at,updated_at) VALUES (?,'{}','[]','test','test')",(identifier,))
 req=store.request(db,identifier);events=[]
 context=SimpleNamespace(connection=db,checkpoint=lambda *a:None,report=lambda *a,**kw:events.append({'stage':a[0],'state':a[1],**kw}))
 settings=get_settings();out=Path(sys.argv[1])
 if out.exists():raise FileExistsError(out)
 report={'prompt_version':local.PROMPT_VERSION,'model':settings.ollama_model,'context_tokens':settings.generation_context_tokens,'output_tokens':settings.generation_output_tokens,'thinking':settings.ollama_thinking,'platform':platform.platform(),'cases':cases,'rows':[],'model_calls':client.calls,'pipeline_sha256':hashlib.sha256(Path(pipeline.__file__).read_bytes()).hexdigest(),'local_sha256':hashlib.sha256(Path(local.__file__).read_bytes()).hexdigest(),'method':'Unseen invented subjects/values/conditions. First production check_numbers (numeric/property/absence guards), then production verify(strict=False), one claim per call. Mechanical rejection is reported separately; matching this rubric is not full document quality.'}
 began=time.monotonic()
 try:
  for label,expected,text,originals in cases:
   one=time.monotonic();reason=None;stage='semantic';calls_before=len(client.calls)
   try:
    pipeline.check_numbers(context,req,text,originals)
    actual=pipeline.verify(context,req,label,[{'text':text,'quotes':originals,'original_passages':originals}],settings,client,strict=False)[0]
   except local.DocumentError as exc:
    actual=False;reason=str(exc);stage='mechanical'
   row={'id':label,'expected':expected,'supported':actual,'matches_rubric':actual==expected,'decision_stage':stage,'reason':reason,'model_calls':len(client.calls)-calls_before,'seconds':round(time.monotonic()-one,3)}
   report['rows'].append(row);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(row),flush=True)
 except Exception as exc:
  report['error']={'type':type(exc).__name__,'message':str(exc)}
 finally:
  report['seconds']=round(time.monotonic()-began,3);report['events']=events
  out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'matches':sum(r['matches_rubric'] for r in report['rows']),'count':len(report['rows']),'seconds':report['seconds'],'error':report.get('error')}),flush=True)
