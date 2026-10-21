"""Read-only liveness and runner-progress observation for a native OS force quit. Signal zero only; no process is killed by this observer, and model payloads are unchanged."""
import json,os,re,time
from pathlib import Path
base=Path('/private/tmp/noye-phase8-20261021-followup');log=base/'ollama-direct.log';target=base/'native-process-observation.json';assert not target.exists()
pids=[int(x) for x in os.environ['NOYE_QA_OBSERVE_PIDS'].split(',')]
for pid in pids:os.kill(pid,0)
report={'method':__doc__,'started_at':time.time(),'native_pid':pids[0],'sidecar_pids':pids[1:],'pid_gone_at':{},'events':[]};offset=log.stat().st_size;pending=b'';first=False
(base/'native-observer-started.json').write_text(json.dumps({'pids':pids,'offset':offset,'at':time.time()},indent=2)+'\n')
for _ in range(1500):
 now=time.time();data=log.read_bytes();new=data[offset:];offset=len(data);pending+=new
 while b'\n' in pending:
  line,pending=pending.split(b'\n',1)
  match=re.search(rb'n_gen =\s*(\d+)',line)
  if match and int(match[1])>0:
   event={'at':now,'state':'generated_tokens','count':int(match[1]),'line':line.decode()};report['events'].append(event)
   if not first:
    first=True;(base/'native-active-token-ready.json').write_text(json.dumps(event,indent=2)+'\n');print(json.dumps(event),flush=True)
  elif first and (b'all slots are idle' in line or b'POST' in line and b'/api/generate' in line):
   report['events'].append({'at':now,'state':'runner_complete_or_idle','line':line.decode()})
 for pid in pids:
  if str(pid) in report['pid_gone_at']:continue
  try:os.kill(pid,0)
  except ProcessLookupError:report['pid_gone_at'][str(pid)]=now;print(json.dumps({'at':now,'pid_gone':pid}),flush=True)
 target.write_text(json.dumps(report,indent=2)+'\n')
 if len(report['pid_gone_at'])==len(pids) and any(e['state']=='runner_complete_or_idle' for e in report['events']):break
 time.sleep(.1)
report['finished_at']=time.time();target.write_text(json.dumps(report,indent=2)+'\n')
