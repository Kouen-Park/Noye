"""QA-only byte-preserving loopback Ollama relay, used to observe a real first final-content token before an OS-native force quit. Never substitutes model output, changes options, retries, or forwards to cloud. Headers/credentials are not logged."""
import hashlib,json,time,uuid,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import httpx
base=Path('/private/tmp/noye-phase8-20261021-followup');lock=threading.Lock()
def event(value):
 with lock,(base/'native-stream-events.jsonl').open('a') as out: out.write(json.dumps({'at':time.time(),**value},ensure_ascii=False)+'\n')
class Handler(BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def log_message(self,*args): pass
 def do_GET(self): self.relay()
 def do_POST(self): self.relay()
 def relay(self):
  raw=self.rfile.read(int(self.headers.get('Content-Length',0)))
  try: body=json.loads(raw) if raw else {}
  except ValueError: body={}
  observed=self.command=='POST' and body.get('stream') is True and body.get('model')=='qwen3.5:4b'
  identifier=str(uuid.uuid4());first=False;done=False;pending=b''
  if observed:event({'state':'request_started','stream_id':identifier,'path':self.path,'request':body})
  try:
   with httpx.Client(timeout=300,trust_env=False,follow_redirects=False) as client:
    with client.stream(self.command,'http://127.0.0.1:11440'+self.path,content=raw,headers={'Content-Type':'application/json'}) as response:
     self.send_response(response.status_code)
     self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
     self.send_header('Connection','close');self.end_headers();self.close_connection=True
     for chunk in response.iter_raw():
      self.wfile.write(chunk);self.wfile.flush()
      if not observed:continue
      pending+=chunk
      while b'\n' in pending:
       line,pending=pending.split(b'\n',1)
       if not line:continue
       frame=json.loads(line);text=frame.get('response') or frame.get('message',{}).get('content')
       if text and not first:
        first=True;mark={'at':time.time(),'stream_id':identifier,'path':self.path,'done':frame.get('done'),'token':text,'token_sha256':hashlib.sha256(text.encode()).hexdigest()}
        assert frame.get('done') is False
        marker=base/'native-first-token.json';assert not marker.exists();marker.write_text(json.dumps(mark,ensure_ascii=False,indent=2)+'\n');event({'state':'first_token_forwarded',**mark})
       if frame.get('done'):
        done=True;event({'state':'model_done','stream_id':identifier,'eval_count':frame.get('eval_count')})
   if observed:event({'state':'request_ended','stream_id':identifier,'first_token':first,'model_done':done})
  except (BrokenPipeError,ConnectionResetError):
   if observed:event({'state':'native_client_disconnected','stream_id':identifier,'first_token':first,'model_done':done})
  except Exception as error:
   if observed:event({'state':'relay_error','stream_id':identifier,'type':type(error).__name__,'message':str(error),'model_done':done})
   self.close_connection=True
ThreadingHTTPServer(('127.0.0.1',11439),Handler).serve_forever()
