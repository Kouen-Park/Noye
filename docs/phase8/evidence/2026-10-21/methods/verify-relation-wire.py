"""No-inference comparison of all retained candidate requests against the adopted production transport, schema, prompt and byte budget. Exact final JSON is replayed only for parsing; it is not another semantic judgment."""
import hashlib,json,subprocess
from pathlib import Path
import httpx
from app.config import Settings
from app.models.wiki import RelationsOutput
from app.services.wiki import local
base=Path('/private/tmp/noye-phase8-20261021'); source=base/'relations-candidate-resumed.json'; report=json.loads(source.read_text())
settings=Settings(_env_file=None,ollama_base_url='http://127.0.0.1:11439',ollama_model='qwen3.5:4b',generation_context_tokens=8192,generation_output_tokens=2048,ollama_thinking=False)
rows=[]
for call in report['model_calls']:
 if call['task']!='verify_relation': continue
 expected=call['request']; payload=json.loads(expected['prompt']); payload.pop('output_schema'); prompt=json.dumps(payload,ensure_ascii=False)
 fields=expected['format']['$defs']['RelationProposal']['properties']; constraints={k:v['enum'] for k,v in fields.items() if k.endswith('_id') and 'enum' in v}; sent=[]
 def reply(request):
  if request.url.path=='/api/show': return httpx.Response(200,json={'model_info':{'general.architecture':'synthetic'}})
  actual=json.loads(request.content); sent.append(actual)
  assert actual==expected
  assert json.dumps(actual['format'],ensure_ascii=False)==json.dumps(expected['format'],ensure_ascii=False)
  return httpx.Response(200,json=json.loads(call['raw_response']))
 with httpx.Client(transport=httpx.MockTransport(reply)) as client:
  local.structured(prompt,RelationsOutput,settings=settings,client=client,constraints=constraints)
 assert len(sent)==1
 assert local.request_size(prompt,RelationsOutput,constraints)==len((expected['system']+expected['prompt']).encode())
 rows.append({'request_sha256':hashlib.sha256(json.dumps(expected,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),'exact_wire_and_budget':True})
assert len(rows)==17
result={'method':__doc__,'candidate_report_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'production_prompt_version':local.PROMPT_VERSION,'source_commit':subprocess.check_output(['git','-c','core.fsmonitor=false','rev-parse','HEAD'],text=True).strip(),'working_tree_source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('backend/app/models/wiki.py'),Path('backend/app/services/wiki/local.py')]},'rows':rows}
(base/'relation-wire-equivalence.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'requests':len(rows),'exact_wire_and_budget':True}))
