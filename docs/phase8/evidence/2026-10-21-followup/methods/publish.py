"""Bounded synthetic follow-up publication. Exact completed final answers/requests and interrupted events are retained. Separate reasoning/token context and repeated successful preflight details are omitted with hashes. No DB, backup, model weight, credential or environment file is included."""
import hashlib,json,re
from pathlib import Path
base=Path('/private/tmp/noye-phase8-20261021-followup');root=Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-21-followup')
assert not root.exists()
assert all(s['exit_code']==0 for s in json.loads((base/'frontend-checks-corrected.json').read_text())['stages'])
assert all(s['exit_code']==0 for s in json.loads((base/'native-ui-build.json').read_text())['stages'])
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


for name in ['baseline','candidate','candidate-decision']:
 put(name+'.json','model/'+name+'.json','report')
for name in ['baseline','candidate']:
 put(name+'-events.jsonl','events/'+name+'.jsonl')
for name in ['probe-relations.py','relation-fresh-controls.json','check-frontend.py','check-frontend-corrected.py','build-native-ui.py','native-proxy.py','native-proxy-observed.py','watch-native-token.py','publish.py']:
 put(name,'methods/'+name)
for name in ['frontend-checks','frontend-checks-corrected','native-ui-build','saved-doc-before','native-first-attempt','native-recovery-review','relay-transition','approval-block']:
 put(name+'.json','checks/'+name+'.json')
for name in ['baseline','candidate','documents-focus','documents-focus-corrected','frontend-checks','frontend-checks-corrected','frontend-tests','frontend-tests-corrected','frontend-types','frontend-types-corrected','frontend-lint','frontend-lint-corrected','desktop-ui-build-corrected','build-native-ui','native-ui-bundle','native-ui-signature']:
 put(name+'.log','logs/'+name+'.txt','log')
put('native-token-excerpt.txt','logs/native-token-excerpt.txt')
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
