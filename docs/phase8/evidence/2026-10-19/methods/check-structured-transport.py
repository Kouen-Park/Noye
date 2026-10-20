"""Actual local structured-output compatibility matrix. Same known positive control, exact system/user/schema and options; endpoint and thinking only vary. Not generation-quality acceptance."""
import hashlib,json,time
from pathlib import Path
import httpx
from app.models.source_documents import SupportVerification
root=Path('/private/tmp/noye-phase8-20261019');target=root/'structured-transport.json';assert not target.exists()
old=json.loads(Path('/private/tmp/noye-phase8-reasoning-20261017/thinking-comparison.json').read_text())
original=next(c['request'] for c in old['model_calls'] if c.get('task')=='verify_support')
report={'method':__doc__,'baseline_request_sha256':hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest(),'rows':[]}
with httpx.Client(timeout=300,trust_env=False,follow_redirects=False) as client:
 report['ollama_version']=client.get('http://127.0.0.1:11439/api/version').json()
 for endpoint,thinking in [('generate',False),('chat',False),('chat',True),('generate',True)]:
  request={**original,'think':thinking}
  if endpoint=='chat':
   request.pop('system');request.pop('prompt')
   request['messages']=[{'role':'system','content':original['system']},{'role':'user','content':original['prompt']}]
  one=time.monotonic();row={'endpoint':endpoint,'thinking':thinking,'request':request,'valid':False}
  try:
   response=client.post('http://127.0.0.1:11439/api/'+endpoint,json=request);row['http_status']=response.status_code
   body=response.json();row['raw_response']=body
   final=body.get('response','') if endpoint=='generate' else body.get('message',{}).get('content','')
   trace=body.get('thinking','') if endpoint=='generate' else body.get('message',{}).get('thinking','')
   row.update(final_characters=len(final),thinking_characters=len(trace),done_reason=body.get('done_reason'),eval_count=body.get('eval_count'))
   if response.status_code!=200 or body.get('done') is not True or body.get('done_reason')=='length':raise ValueError('Unfinished request')
   parsed=SupportVerification.model_validate_json(final,strict=True)
   row.update(valid=True,verdicts=[a.supported for a in parsed.audits])
  except Exception as e:row['error']={'type':type(e).__name__,'message':str(e)}
  row['seconds']=round(time.monotonic()-one,3);report['rows'].append(row)
  target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({k:v for k,v in row.items() if k not in ['request','raw_response','error']},ensure_ascii=False),flush=True)
 report['unload_status']=client.post('http://127.0.0.1:11439/api/generate',json={'model':original['model'],'keep_alive':0}).status_code
 report['loaded_after']=client.get('http://127.0.0.1:11439/api/ps').json()
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
