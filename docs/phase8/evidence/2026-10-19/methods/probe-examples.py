"""Candidate-only support prompt experiment. Balanced synthetic relationship/coreference examples are not product changes. Eight prior controls and eight fresh controls fixed before any candidate call; unchanged production validator/transport/schema/options. Prior-control comparison only; fresh controls have no paired baseline."""
import hashlib,json,sqlite3,sys,time
from pathlib import Path
from types import SimpleNamespace
from contextlib import closing
import httpx
from app.config import Settings
from app.db import source_documents as store
from app.db.database import init_schema
from app.models.source_documents import SupportVerification
from app.services.source_documents import pipeline,local
sys.path.insert(0,'/private/tmp/noye-phase8-20261016')
from production_holdout_client import RecordedClient
root=Path('/private/tmp/noye-phase8-20261019');model=sys.argv[1];port=int(sys.argv[2]);label=sys.argv[3];target=root/f'examples-{label}.json';assert not target.exists()
prior=json.loads((root/'support-v24-resumed.json').read_text())
fresh=[
 ['new-independent-means',False,'Dahlia supports 20 sessions using a ceramic housing.',['Dahlia supports 20 sessions. Dahlia uses a ceramic housing.']],
 ['new-explicit-means',True,'Juniper locates saved entries using an index.',['Juniper uses an index to locate saved entries.']],
 ['new-adjoining-subject',True,'Mistral creates snapshots every Thursday.',['Mistral pauses writes during inspection. Snapshots are created every Thursday.']],
 ['new-competing-subject',False,'Nacre creates daily backups.',['Nacre pauses writes on Saturdays. Sol creates daily backups.']],
 ['new-korean-independent',False,'하늘은 TLS를 사용하여 요청 처리 한도 34건을 달성합니다.',['하늘의 요청 처리 한도는 34건입니다. 하늘은 TLS를 사용합니다.']],
 ['new-korean-explicit',True,'모래는 색인을 사용하여 저장된 기록을 찾습니다.',['모래는 저장된 기록을 찾는 수단으로 색인을 사용합니다.']],
 ['new-exception-dropped',False,'Fennel permits writes every day.',['Fennel permits writes except on Sundays.']],
 ['new-conjunctive-facts',True,'Violet stores 18 records and uses a ring buffer.',['Violet stores 18 records. Violet uses a ring buffer.']]
]
casefile=root/'examples-fresh-controls.json';encoded=json.dumps(fresh,ensure_ascii=False,indent=2)+'\n'
if casefile.exists():assert casefile.read_text()==encoded
else:casefile.write_text(encoded)
cases=prior['cases']+[{'id':n,'expected':e,'text':t,'originals':o,'regression':False} for n,e,t,o in fresh]
addition="""\nSynthetic examples: 'Rook has six ports. Rook uses copper.' supports 'Rook has six
ports and uses copper', but not 'Rook has six ports using copper': the latter adds
an instrumental link. 'Rook pauses writes on Fridays. Backups run hourly.' supports
'Rook runs hourly backups': adjoining sentences retain the source subject unless
a competing entity is stated. Check connectors such as using/by/사용하여 separately."""
local.SUPPORT_SYSTEM+=addition
settings=Settings(_env_file=None,ollama_base_url=f'http://127.0.0.1:{port}',ollama_model=model,generation_context_tokens=8192,generation_output_tokens=3072,ollama_thinking=False)
report={'method':__doc__,'model':model,'addition':addition,'system':local.SUPPORT_SYSTEM,'fresh_controls_sha256':hashlib.sha256(casefile.read_bytes()).hexdigest(),'cases':cases,'rows':[],'model_calls':[]}
with httpx.Client(timeout=30,trust_env=False) as c:
 for p in [11439,11459]:assert not c.get(f'http://127.0.0.1:{p}/api/ps').json()['models']
with closing(sqlite3.connect(':memory:')) as db,closing(RecordedClient()) as client:
 db.row_factory=sqlite3.Row;init_schema(db);db.execute("INSERT INTO source_document_requests(id,request_json,manifest_json,created_at,updated_at) VALUES ('probe','{}','[]','test','test')")
 req=store.request(db,'probe');context=SimpleNamespace(connection=db,checkpoint=lambda *a:None,report=lambda *a,**kw:None)
 report['model_calls']=client.calls;start=time.monotonic()
 for n,case in enumerate(cases):
  began=time.monotonic();row={'id':case['id'],'expected':case['expected'],'valid':False,'fresh':n>=8}
  try:
   verdict=pipeline.verify(context,req,f'examples:{label}:{n}',[{'text':case['text'],'quotes':case['originals'],'original_passages':case['originals']}],settings,client,strict=False)[0]
   row.update(valid=True,actual=verdict,correct=verdict==case['expected'])
  except Exception as e:row['error']={'type':type(e).__name__,'message':str(e)}
  row['seconds']=round(time.monotonic()-began,3);report['rows'].append(row)
  target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(row,ensure_ascii=False),flush=True)
 report['seconds']=round(time.monotonic()-start,3)
with httpx.Client(timeout=60,trust_env=False) as c:
 report['unload_status']=c.post(settings.ollama_base_url+'/api/generate',json={'model':model,'keep_alive':0}).status_code
 report['loaded_after']=c.get(settings.ollama_base_url+'/api/ps').json()
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
