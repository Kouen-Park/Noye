"""Whitelist publication of synthetic Oct19 QA. Preserve exact requests and final answer strings; omit separate reasoning/token context and repeated successful preflight metadata with hashes. Runtime files, model weights and credentials are excluded."""
import hashlib,json,re
from pathlib import Path
base=Path('/private/tmp/noye-phase8-20261019');root=Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-19')
assert not root.exists(), 'Never overwrite a published evidence directory'
assert len(json.loads((base/'support-v24-resumed.json').read_text())['rows'])==16
checks=json.loads((base/'final/checks.json').read_text());assert len(checks['stages'])==3 and all(s['exit_code']==0 for s in checks['stages'])
root.mkdir(parents=True);entries=[]
def sha(data):return hashlib.sha256(data).hexdigest()
def note(text):
 data=text.encode();return {'omitted':True,'sha256':sha(data),'bytes':len(data),'characters':len(text)}
def body_clean(body):
 if isinstance(body,dict):
  out={}
  for k,v in body.items():
   if k=='thinking' and isinstance(v,str):out['publication_thinking']=note(v)
   elif k=='context' and isinstance(v,list):out['publication_context']=note(json.dumps(v,separators=(',',':')))
   else:out[k]=body_clean(v)
  return out
 if isinstance(body,list):return [body_clean(v) for v in body]
 return body
def clean(node):
 if isinstance(node,list):return [clean(x) for x in node]
 if not isinstance(node,dict):return node
 result={k:clean(v) for k,v in node.items()}
 raw=node.get('raw_response')
 if isinstance(raw,str):
  if node.get('task')=='model_preflight' and node.get('http_status')==200:
   result.pop('raw_response');result['publication_preflight']=note(raw)
  else:
   try:body=json.loads(raw)
   except ValueError:return result
   before=body.get('response'),body.get('message',{}).get('content')
   changed=body_clean(body)
   assert before==(changed.get('response'),changed.get('message',{}).get('content'))
   result['raw_response']=json.dumps(changed,ensure_ascii=False,separators=(',',':'))
   result['publication_raw_response']=note(raw)
 return result
def put(name,relative,kind='copy'):
 source=base/name;raw=source.read_bytes();data=raw;transformation='Byte-for-byte copy'
 if kind=='report':
  original=json.loads(raw);published=clean(original)
  data=(json.dumps(published,ensure_ascii=False,indent=2)+'\n').encode()
  transformation='Separate reasoning/token context and repeated successful preflight metadata omitted with hashes; exact requests and final answer strings preserved'
 elif kind=='log':
  value=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',raw.decode()).replace('\r','\n')
  data=('\n'.join(x.rstrip() for x in value.splitlines()).strip()+'\n').encode();transformation='ANSI, carriage returns and trailing whitespace normalized'
 target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 entries.append({'file':relative,'source':str(source),'source_bytes':len(raw),'source_sha256':sha(raw),'published_bytes':len(data),'published_sha256':sha(data),'transformation':transformation})
for n in ['structured-transport','support-v24-paired-interrupted','support-v24-resumed','alternative-support','examples-gemma','link-focus']:
 put(n+'.json','model/'+n+'.json','report')
for n in ['check-structured-transport.py','support-v24-paired.py','support-v24-resume.py','support-v24-fresh-controls.json','probe-alternative.py','finish-checks.py','build-native.py','publish.py','review-model-results.py','review-model-results.json','probe-examples.py','examples-fresh-controls.json','probe-link-focus.py','cleanup.py']:
 put(n,'methods/'+n)
put('support-v24-resume-events.jsonl','model/support-v24-resume-events.jsonl')
for n in ['structured-transport','support-v24-paired','support-v24-resumed','alternative-support','evaluation-unit','structured-unit','structured-unit-corrected','structured-unit-final','examples-gemma','link-focus']:
 put(n+'.log','logs/'+n+'.txt','log')
for n in ['checks.json','build-review.json','backend-product-coverage.json']:
 put('final/'+n,'final/'+n)
put('final/coverage.ini','methods/coverage.ini')
for n in ['checks','backend-final','backend-lint','packaging-checks','sidecar-build','native-bundle','native-signature','frozen-bundled']:
 put('final/'+n+'.log','logs/final/'+n+'.txt','log')
put('alternative-install.json','alternative-install.json')
put('cleanup.json','cleanup.json')
put('alternative-runtime-review.json','alternative-runtime-review.json')
put('/private/tmp/noye-phase8-20261016/production_holdout_client.py','methods/production_holdout_client.py')
record={'method':__doc__,'files':sorted(entries,key=lambda x:x['file'])}
(root/'publication.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
for item in entries:
 data=(root/item['file']).read_bytes();assert len(data)==item['published_bytes'] and sha(data)==item['published_sha256']
 if item['file'].endswith('.json'):json.loads(data,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
 assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)',data)
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}=={e['file'] for e in entries}|{'publication.json'}
print(json.dumps({'files':len(entries),'hashes_and_strict_json_valid':True,'common_credential_pattern_matches':0}))
