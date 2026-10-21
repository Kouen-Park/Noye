"""Remove only the newly downloaded QA model and stop the two dedicated services created for this run. Personal 11434 and personal weights are untouched."""
import httpx,json,os,signal,subprocess,time
from pathlib import Path
root=Path('/private/tmp/noye-phase8-20261019');report={'method':__doc__,'services':[]}
with httpx.Client(timeout=60,trust_env=False) as client:
 for port,pid in [(11439,54538),(11459,55202)]:
  base=f'http://127.0.0.1:{port}';loaded=client.get(base+'/api/ps').json();assert not loaded['models']
  listener=subprocess.check_output(['lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN','-Fp'],text=True)
  assert [x for x in listener.splitlines() if x.startswith('p')]==[f'p{pid}']
  comm=subprocess.check_output(['ps','-p',str(pid),'-o','comm='],text=True).strip();assert comm.endswith('/ollama') or comm=='ollama',comm
  row={'port':port,'pid':pid,'loaded_before':loaded,'comm':comm}
  if port==11459:
   tags=client.get(base+'/api/tags').json();assert [m['name'] for m in tags['models']]==['gemma4:e2b-it-qat']
   response=client.delete(base+'/api/delete',json={'model':'gemma4:e2b-it-qat'}) if False else client.request('DELETE',base+'/api/delete',json={'model':'gemma4:e2b-it-qat'})
   row['qa_model_delete_http_status']=response.status_code;assert response.status_code==200
   row['models_after_delete']=client.get(base+'/api/tags').json();assert not row['models_after_delete']['models']
  os.kill(pid,signal.SIGTERM);row['sigterm_sent']=True;report['services'].append(row)
for row in report['services']:
 for _ in range(20):
  result=subprocess.run(['lsof','-nP',f"-iTCP:{row['port']}",'-sTCP:LISTEN','-Fp'],text=True,capture_output=True)
  if not result.stdout.strip():break
  time.sleep(.1)
 row['no_listener_after']=not result.stdout.strip();assert row['no_listener_after']
(root/'cleanup.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
