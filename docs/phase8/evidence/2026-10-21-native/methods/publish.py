"""Bounded synthetic native-interruption publication. Exact completed final answers/requests and interrupted events are retained. Separate reasoning/token context and repeated successful preflight details are omitted with hashes. No DB, backup, model weight, credential or environment file is included."""
import hashlib,json,re
from pathlib import Path
base=Path('/private/tmp/noye-phase8-20261021-native');root=Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-21-native')
assert not root.exists()
assert all(s['exit_code']==0 for s in json.loads((base/'final/checks.json').read_text())['stages'])
assert json.loads((base/'thinking-decision.json').read_text())['model_unloaded']
assert not any(json.loads((base/'cleanup-app.json').read_text())['alive_after'].values())
assert not json.loads((base/'cleanup-services.json').read_text())['qdrant']['running_after']
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


for name in ['native-analysis','cleanup-app','cleanup-services','thinking-decision','entry-verification','entry-verification-initial-error']:
 put(name+'.json','checks/'+name+'.json')
put('thinking-relations.json','model/thinking-relations.json','report')
put('thinking-events.jsonl','events/thinking-events.jsonl')
put('thinking-relations.log','logs/thinking-relations.txt','log')
put('diagnostic-server-excerpt.txt','logs/diagnostic-server-excerpt.txt')
for group in ['before','after']:
 for source in sorted((base/group).iterdir()):
  if source.is_file():
   relative=source.relative_to(base).as_posix()
   put(relative,relative,'log' if source.suffix=='.log' else 'copy')
for name in ['finish-checks.py','build-native.py','verify-desktop-entry.py','verify-desktop-entry-initial.py','probe-thinking-relations.py','publish.py','tauri-qa.json']:
 put(name,'methods/'+name)
for name in ['checks.json','build-review.json','coverage.ini']:
 put('final/'+name,'checks/'+name)
for source in sorted((base/'final').glob('*.log')):
 put('final/'+source.name,'logs/'+source.stem+'.txt','log')

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
