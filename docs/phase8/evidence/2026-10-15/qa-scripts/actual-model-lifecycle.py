"""Only a new temporary Ollama model store; no personal model mutation."""
import asyncio,json,os,subprocess,time,uuid
from pathlib import Path
import httpx
from app.config import get_settings
from app.services.model_manager import ModelManager

root=Path('/private/tmp/noye-phase8-20261014')/('model-lifecycle-'+str(uuid.uuid4()))
root.mkdir()
(root/'models').mkdir()
os.environ['OLLAMA_BASE_URL']='http://127.0.0.1:11449'
os.environ['OLLAMA_MODEL']='qwen3.5:4b'
os.environ['NOYE_DATA_DIR']=str(root/'app')
get_settings.cache_clear()
report={'workspace':str(root),'model':'qwen3.5:0.8b','method':'Production ModelManager + actual isolated Ollama server and registry. Network failure uses an unreachable proxy only for the owned server; cancellation/retry uses a real pull. No UI acceptance or generation on this downloaded model is claimed.','steps':[]}
server=None
log=None

def save():
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

def stop():
 global server,log
 if server:
  server.terminate()
  server.wait(timeout=10)
  server=None
 if log:log.close();log=None

def start(broken):
 global server,log
 env={**os.environ,'OLLAMA_HOST':'127.0.0.1:11449','OLLAMA_MODELS':str(root/'models'),'OLLAMA_NO_CLOUD':'1','OLLAMA_MAX_LOADED_MODELS':'1'}
 for key in list(env):
  if key.upper().endswith('_PROXY'):env.pop(key)
 if broken:env['HTTPS_PROXY']='http://127.0.0.1:9'
 log=(root/('failed-server.log' if broken else 'normal-server.log')).open('w')
 server=subprocess.Popen(['/opt/homebrew/bin/ollama','serve'],env=env,stdout=log,stderr=subprocess.STDOUT)
 with httpx.Client(trust_env=False,timeout=1) as client:
  for _ in range(80):
   if server.poll() is not None:raise RuntimeError('Owned Ollama server failed to start.')
   try:
    if client.get('http://127.0.0.1:11449/api/tags').status_code==200:return
   except httpx.HTTPError:pass
   time.sleep(0.1)
 raise TimeoutError('Owned server readiness timed out.')

async def run():
 manager=ModelManager()
 start(True)
 began=time.monotonic()
 await manager.pull(report['model'],str(root))
 await asyncio.wait_for(manager.task,40)
 report['steps'].append({'case':'network_failure','seconds':round(time.monotonic()-began,3),'job':manager.job.copy()})
 save()
 if manager.job['state']!='failed':raise AssertionError('Registry access via the closed proxy did not fail.')
 stop()
 start(False)
 began=time.monotonic()
 await manager.pull(report['model'],str(root))
 deadline=time.monotonic()+60
 while manager.job['state']=='downloading' and manager.job['completed']==0 and time.monotonic()<deadline:
  await asyncio.sleep(0.1)
 before=manager.job.copy()
 await manager.cancel()
 report['steps'].append({'case':'actual_cancel','seconds':round(time.monotonic()-began,3),'before':before,'after':manager.job.copy()})
 save()
 if before['state']!='downloading' or manager.job['state']!='cancelled':raise AssertionError('Pull did not remain active until cancellation.')
 began=time.monotonic()
 await manager.pull(report['model'],str(root))
 await asyncio.wait_for(manager.task,600)
 report['steps'].append({'case':'explicit_retry','seconds':round(time.monotonic()-began,3),'job':manager.job.copy()})
 save()
 if manager.job['state']!='complete':raise AssertionError('Actual retry did not install the model.')
 with httpx.Client(trust_env=False,timeout=5) as client:
  tags=client.get('http://127.0.0.1:11449/api/tags').json()
 report['installed_tags']=tags
 await manager.delete(report['model'])
 with httpx.Client(trust_env=False,timeout=5) as client:
  report['tags_after_qa_model_deletion']=client.get('http://127.0.0.1:11449/api/tags').json()
 if report['tags_after_qa_model_deletion']['models']:raise AssertionError('QA model deletion did not clear the isolated inventory.')
 report['state']='passed'
 save()
try:
 asyncio.run(run())
except Exception as exc:
 report['state']='failed'
 report['error']={'type':type(exc).__name__,'message':str(exc)}
 save()
 raise
finally:
 stop()
 print(json.dumps({'state':report.get('state'),'report':str(root/'report.json'),'steps':report['steps']},ensure_ascii=False),flush=True)
