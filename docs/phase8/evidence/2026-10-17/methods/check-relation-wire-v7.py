"""No-inference comparison: v7 quantity guard/version does not alter the twelve recorded v6 relation requests. This is compatibility evidence, not new semantic evaluation."""
import hashlib,json
from pathlib import Path
from app.models.wiki import RelationsOutput
from app.services.wiki import local
root=Path('/private/tmp/noye-phase8-20261017');p=root/'relations-v6.json';d=json.loads(p.read_text());rows=[]
for c in d['model_calls']:
 if c.get('task')!='verify_relation':continue
 req=c['request'];payload=json.loads(req['prompt']);payload.pop('output_schema')
 props=req['format']['$defs']['RelationProposal']['properties']
 constraints={k:props[k]['enum'] for k in ['target_id','origin_evidence_id','target_evidence_id']}
 actual={'system':local.SYSTEM,'prompt':local.model_prompt(json.dumps(payload,ensure_ascii=False),RelationsOutput,constraints),'format':local.response_schema(RelationsOutput,constraints)}
 rows.append({'same_system_prompt_and_format':all(actual[k]==req[k] for k in actual)})
assert len(rows)==12 and all(r['same_system_prompt_and_format'] for r in rows)
report={'method':__doc__,'prompt_version':local.PROMPT_VERSION,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'requests':len(rows),'identical':len(rows)}
(root/'relation-wire-v7.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
