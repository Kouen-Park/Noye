"""No-model replay of exact v6 Wiki claims through the v7 production claim guard. This establishes a narrow rejection, not fresh generation or full semantic acceptance."""
import hashlib,json
from pathlib import Path
from app.models.wiki import Claim,Passage
from app.services.wiki import pipeline
from app.services.wiki.local import WikiError,PROMPT_VERSION
from app.services import quantity_properties
root=Path('/private/tmp/noye-phase8-20261017');source=next((root/'v6-wiki').glob('wiki-*.json'));d=json.loads(source.read_text())
report={'method':__doc__,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'prompt_version':PROMPT_VERSION,'runtime_hashes':{Path(m.__file__).name:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in [pipeline,quantity_properties]},'rows':[]}
for r in d['revisions']:
 rev=r['revision'];evidence={p['id']:Passage.model_validate(p) for p in rev['evidence']}
 for s in rev['metadata']['sections']:
  for c in [s['summary'],*s['key_points']]:
   row={'text':c['text'],'blocked':False}
   try:pipeline.verify_claim(Claim.model_validate(c),evidence)
   except WikiError as e:row.update(blocked=True,error=str(e))
   report['rows'].append(row)
assert len(report['rows'])==10
blocked=[r for r in report['rows'] if r['blocked']]
assert len(blocked)==1 and blocked[0]['text']=='The system has a storage capacity of 92 litres.'
(root/'wiki-v7-quantity-replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'claims':10,'blocked':1,'others_do_not_establish_semantic_acceptance':True}))
