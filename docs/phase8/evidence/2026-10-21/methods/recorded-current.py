"""Current production acceptance CLI; synthetic corpus only. Retain exact requests/responses and durable request-start events so interruption is not mistaken for a completed judgment."""
import hashlib,json,os,time
from pathlib import Path
from app.evaluation import source_documents as evaluation
class RecordedClient(evaluation.MeasuredClient):
 def post(self,url,*,json):
  events=Path(os.environ['NOYE_QA_EVENTS'])
  with events.open('a') as out:out.write(__import__('json').dumps({'state':'started','endpoint':url,'request':json,'at':time.time()},ensure_ascii=False)+'\n')
  before=len(self.calls)
  try:
   response=super().post(url,json=json)
   with events.open('a') as out:out.write(__import__('json').dumps({'state':'returned','endpoint':url,'status':response.status_code,'body_sha256':hashlib.sha256(response.content).hexdigest(),'at':time.time()})+'\n')
   return response
  finally:
   if len(self.calls)>before:self.calls[-1]['request']=json
evaluation.MeasuredClient=RecordedClient
evaluation.main()
