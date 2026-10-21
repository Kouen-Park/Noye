"""No-inference replay of current numeric/reference guards over retained final outputs. This checks compatibility and the recorded postfix refusal, not general semantic quality or a new generation attempt."""
import json,hashlib,subprocess
from pathlib import Path
from app.models.wiki import Passage,SectionSummary
from app.services.wiki import pipeline as wiki
from app.services.source_documents import presentation,pipeline
qa=Path('/private/tmp/noye-phase8-20261021');report={'method':__doc__,'source_commit':subprocess.check_output(['git','-c','core.fsmonitor=false','rev-parse','HEAD'],text=True).strip(),'rows':[]}
def row(name,text,originals,expected):
 accepted=True;error=None
 try:
  pipeline.verify_numbers(text,' '.join(originals));presentation.check_volume_properties(text,originals)
 except pipeline.local.DocumentError as e:accepted=False;error=str(e)
 assert accepted==expected,(name,text,error)
 report['rows'].append({'case':name,'text':text,'accepted':accepted,'expected':expected,'error':error})
source=next((qa/'current-comparison').glob('comparison-*.json'));r=json.loads(source.read_text())
for call in r['model_calls']:
 if call['task']!='process_original_sections':continue
 payload=json.loads(call['request']['prompt']);evidence={p['evidence_id']:p['text'] for p in payload['passages']}
 for claim in json.loads(call['response'])['claims']:row('accepted-v25-comparison-extraction',claim['text'],[evidence[i] for i in claim['evidence_ids']],True)
source=next((qa/'current-wiki').glob('wiki-*.json'));r=json.loads(source.read_text())
for item in r['revisions']:
 rev=item['revision'];evidence={p['id']:Passage.model_validate(p) for p in rev['evidence']}
 for section in rev['metadata']['sections']:
  s=SectionSummary.model_validate(section)
  for c in [s.summary,*s.key_points]:wiki.verify_claim(c,evidence);row('accepted-v11-wiki',c.text,[evidence[c.evidence_id].text],True)
r=json.loads((qa/'fresh-wiki.json').read_text())
for one in r['rows']:
 assert one['valid'];evidence={p['id']:Passage.model_validate(p) for p in one['evidence']}
 for section in one['result']['sections']:
  s=SectionSummary.model_validate(section)
  for c in [s.summary,*s.key_points]:wiki.verify_claim(c,evidence);row(one['id'],c.text,[evidence[c.evidence_id].text],True)
r=json.loads(next((qa/'current-collection').glob('collection-*.json')).read_text());rejected=0
for call in r['model_calls']:
 if call['task']!='cross_source_synthesis':continue
 p=json.loads(call['request']['prompt']);known={c['id']:c for c in p['claims']}
 for c in json.loads(call['response'])['claims']:
  originals=[s['quote'] for identifier in c['claim_ids'] for s in known[identifier]['supports']]
  bad='92 리터의 용량을 저장' in c['text']
  row('unaccepted-v25-korean-synthesis',c['text'],originals,not bad);rejected+=bad
assert rejected>=1
report['recorded_bad_korean_claims_refused']=rejected;report['loaded_model_calls']=0
(qa/'guard-replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'rows':len(report['rows']),'bad_claims_refused':rejected,'inference_calls':0}))
