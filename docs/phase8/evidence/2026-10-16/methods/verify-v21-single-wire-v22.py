"""No-inference replay to compare recorded v21 single-claim wire bodies with v22.

Recorded HTTP responses are supplied by an in-process MockTransport. This proves
wire equality and runtime audit/guard behavior on those responses, not a fresh
model result. Prior semantic failures therefore remain applicable to this path.
"""
import hashlib,json,pathlib,sqlite3,uuid
from contextlib import closing
from types import SimpleNamespace
import httpx
from app.config import get_settings
from app.db.database import init_schema
from app.db import source_documents as store
from app.services.source_documents import pipeline,local
r=pathlib.Path('/private/tmp/noye-phase8-20261016');source=r/'multiple-original-v21.json';d=json.loads(source.read_text());recorded=iter(d['model_calls']);seen=[]
def response(req):
    old=next(recorded);actual=json.loads(req.content)
    equal=actual==old['request'];seen.append({'task':old['task'],'exact_wire_body_equal':equal})
    if not equal:raise AssertionError('wire mismatch')
    return httpx.Response(old['http_status'],json=json.loads(old['raw_response']))
with closing(sqlite3.connect(':memory:')) as db,httpx.Client(transport=httpx.MockTransport(response)) as client:
    db.row_factory=sqlite3.Row;init_schema(db);identifier=str(uuid.uuid4());db.execute("INSERT INTO source_document_requests(id,request_json,manifest_json,created_at,updated_at) VALUES (?,'{}','[]','test','test')",(identifier,));req=store.request(db,identifier)
    context=SimpleNamespace(connection=db,checkpoint=lambda *a:None,report=lambda *a,**kw:None)
    verdicts=[]
    for i,(label,gold,text,originals) in enumerate(d['suite']['cases']):
        pipeline.check_numbers(context,req,text,originals)
        verdicts.extend(pipeline.verify(context,req,f'wire-{i}',[{'text':text,'quotes':originals,'original_passages':originals}],get_settings(),client,strict=False))
    try:next(recorded)
    except StopIteration:pass
    else:raise AssertionError('unreplayed calls')
report={'method':__doc__,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'current_prompt_version':local.PROMPT_VERSION,'calls':seen,'recorded_verdicts_reproduced':verdicts==[x['supported'] for x in d['rows']],'fresh_model_run':False}
(r/'v21-single-wire-v22-equality.json').write_text(json.dumps(report,indent=2)+'\n');print({'calls':len(seen),'all_equal':all(x['exact_wire_body_equal'] for x in seen),'verdicts_reproduced':report['recorded_verdicts_reproduced']})
