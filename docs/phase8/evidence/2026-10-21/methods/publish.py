"""Publish a bounded whitelist of invented Oct21 QA records. Preserve exact requests/final responses and failures; omit separate reasoning/token context and repeated successful preflight metadata with hashes. Do not include runtime DBs, backups, model weights, environment files or credentials."""
import hashlib,json,re
from pathlib import Path
base=Path('/private/tmp/noye-phase8-20261021');root=Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-21')
assert not root.exists(), 'Never overwrite published evidence'
checks=json.loads((base/'final/checks.json').read_text());assert len(checks['stages'])==3 and all(s['exit_code']==0 for s in checks['stages'])
assert len(json.loads((base/'relations-candidate-resumed.json').read_text())['rows'])==17
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

reports=['scenarios','fresh-wiki','guard-replay','guard-replay-setup-error','relations-current','relations-candidate','relations-candidate-resumed','relations-manual','relation-wire-equivalence','wiki-current-manual','comparison-current-manual','collection-v25-manual','collection-v26-retry-manual','collection-v27-manual','fresh-wiki-manual','collection-v26-context','collection-v27-context']
for n in reports:put(n+'.json','model/'+n+'.json','report')
for folder in ['v9-wiki','v10-wiki','current-wiki','current-comparison','current-collection','collection-v26','collection-v27']:
 files=list((base/folder).glob('*.json'))
 for p in files:put(str(p.relative_to(base)),'model/'+folder+'/'+p.name,'report')
methods=['recorded-current.py','run-scenarios.py','fresh-wiki.py','fresh-wiki-controls.json','relation-fresh-controls.json','probe-relations-current.py','probe-relations-candidate.py','resume-relations-candidate.py','verify-relation-wire.py','replay-current-guards.py','replay-current-guards-initial.py','finish-checks.py','build-native.py','publish.py','cleanup.py','tauri-qa.json']
for n in methods:put(n,'methods/'+n)
for n in ['wiki','comparison','collection','fresh-wiki','collection-v26','collection-v26-retry','collection-v27','collection-v27-retry','relation-current','relation-candidate','relation-candidate-resume']:
 put(n+'-events.jsonl','events/'+n+'.jsonl')
logs=['wiki-focus','wiki-v10-focus','source-v25-focus','source-v25-focus-corrected','v25-v11-focus','v25-v11-focus-corrected','postfix-quantity','quantity-retry-focus','source-v27-focus','relation-v13-focus','relation-v13-focus-corrected','wiki-v9-whole','wiki-v10-whole','wiki-whole','comparison-whole','collection-whole','fresh-wiki','collection-v26-whole','collection-v26-retry','collection-v27-whole','collection-v27-retry','relations-current','relations-candidate','relations-candidate-resumed','scenarios']
for n in logs:put(n+'.log','logs/'+n+'.txt','log')
for n in ['checks.json','build-review.json','backend-product-coverage.json']:
 put('final/'+n,'final/'+n)
put('final/coverage.ini','methods/coverage.ini')
for n in ['checks','backend-final','backend-lint','packaging-checks','sidecar-build','native-bundle','native-signature','frozen-bundled']:
 put('final/'+n+'.log','logs/final/'+n+'.txt','log')
for n in ['01-한국어.md','02-English.txt']:
 put('current-wiki/knowledge/Course/'+n,'corpus/Course/'+n)
put('current-wiki/knowledge/Unrelated.txt','corpus/Unrelated.txt')
put('cleanup.json','cleanup.json')
record={'method':__doc__,'files':sorted(entries,key=lambda x:x['file'])}
(root/'publication.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
for item in entries:
 data=(root/item['file']).read_bytes();assert len(data)==item['published_bytes'] and sha(data)==item['published_sha256']
 if item['file'].endswith('.json'):json.loads(data,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
 if item['file'].endswith('.jsonl'):
  for line in data.splitlines():json.loads(line,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
 assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)',data)
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}=={e['file'] for e in entries}|{'publication.json'}
print(json.dumps({'files':len(entries),'published_bytes':sum(e['published_bytes'] for e in entries),'hashes_and_strict_json_valid':True,'common_credential_pattern_matches':0}))
