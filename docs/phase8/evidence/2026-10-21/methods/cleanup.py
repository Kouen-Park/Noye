"""Stop only the owned, unloaded QA Ollama listener on 127.0.0.1:11439. Existing weights are never modified; personal services are outside this check."""
import json,os,signal,subprocess,time
from pathlib import Path
import httpx
base=Path('/private/tmp/noye-phase8-20261021');target=base/'cleanup.json';assert not target.exists()
with httpx.Client(timeout=30,trust_env=False) as c:
 version=c.get('http://127.0.0.1:11439/api/version').json();loaded=c.get('http://127.0.0.1:11439/api/ps').json();assert loaded['models']==[]
pids=subprocess.check_output(['lsof','-t','-nP','-iTCP:11439','-sTCP:LISTEN'],text=True).split();assert pids==['68260'],pids
command=subprocess.check_output(['ps','-p',pids[0],'-o','command='],text=True).strip();assert command=='/opt/homebrew/bin/ollama serve',command
report={'method':__doc__,'version':version,'loaded_before':loaded,'owned_pid':int(pids[0]),'command':command,'no_weights_pulled_or_deleted':True}
os.kill(int(pids[0]),signal.SIGTERM)
for _ in range(20):
 result=subprocess.run(['lsof','-t','-nP','-iTCP:11439','-sTCP:LISTEN'],capture_output=True,text=True)
 if not result.stdout.strip():break
 time.sleep(.2)
report['listener_absent']=not result.stdout.strip();target.write_text(json.dumps(report,indent=2)+'\n');assert report['listener_absent'];print(json.dumps(report))
