"""Invented copied workspace + real Ollama; no native UI acceptance is claimed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import closing

BASE = Path('/private/tmp/noye-phase8-20261012/source-comparison')
OUT = Path('/private/tmp/noye-phase8-20261014')

def digest(rows):
    return hashlib.sha256(json.dumps([dict(r) for r in rows], sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def work(dbfile, workspace, case):
    os.environ['NOYE_DATA_DIR'] = str(workspace/'app')
    os.environ['DATABASE_URL'] = f'sqlite:///{dbfile}'
    from app.config import get_settings
    from app.db.database import connect, init_schema
    from app.evaluation.source_documents import MeasuredClient, measured_document, save_report
    from app.models.source_documents import GenerateRequest
    from app.models.wiki import WikiScope
    from app.services import knowledge_jobs
    from app.services.folders import register_root
    from app.services.source_catalog import SourceCatalog, SourceSession
    from app.services.source_documents import jobs
    get_settings.cache_clear()
    settings = get_settings()
    with closing(connect()) as db:
        init_schema(db)
        root = db.execute('SELECT id FROM source_roots').fetchone()[0]
        register_root(db, workspace/'knowledge', 'connected', reconnect_id=root)
        beta = next(s['source_id'] for s in SourceCatalog(db).list_sources() if s['relative_path']=='Course/02-English.txt')
        existing = {t: [dict(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY id')] for t in ('documents','messages','conversations')}
        hashes = {t:digest(rows) for t,rows in existing.items()}
        job = jobs.enqueue(db, GenerateRequest(request_id=str(uuid.uuid4()), instruction='Write a short English note about Project Beta. Preserve the exact storage amount, write permissions and backup schedule.', scope=WikiScope(mode='chosen', source_ids=[beta]), inventory_mode='collection'))
        jobs.register()
        action = {}
        target = 'process_original_sections' if case=='edit' else 'interpret_intent'
        original = (workspace/'knowledge/Course/02-English.txt').read_bytes()
        class Client(MeasuredClient):
            def post(self, url, *, json):
                task = __import__('json').loads(json.get('prompt', '{}')).get('task')
                if task==target and case=='crash':
                    # Measurement-only change: stream the identical production
                    # request so the parent can prove a real output token arrived.
                    # The normal application still uses stream=False.
                    action.update(task=task, post_started=time.monotonic())
                    with self.client.stream('POST', url, json={**json, 'stream':True}) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            token = __import__('json').loads(line).get('response', '')
                            if token and not (workspace/'active.json').exists():
                                (workspace/'active.json').write_text(__import__('json').dumps({
                                    'job_id':job['id'], 'task':task,
                                    'first_token_received':time.monotonic(),
                                    'first_token_utf8_bytes':len(token.encode()),
                                    'first_token_sha256':hashlib.sha256(token.encode()).hexdigest(),
                                    'measurement_change':'Only this QA transport uses stream=True to observe actual output tokens.'}))
                    raise RuntimeError('Owned worker unexpectedly finished before parent termination.')
                if task==target and not action:
                    action.update(task=task, post_started=time.monotonic())
                    (workspace/'active.json').write_text(__import__('json').dumps({'job_id':job['id'],'task':task,'started':action['post_started']}))
                    def alter():
                        time.sleep(0.4)
                        if case=='cancel':
                            with closing(connect()) as another:
                                result = knowledge_jobs.cancel(another, job['id'])
                            action.update(at=time.monotonic(), state=result['state'])
                        elif case=='edit':
                            (workspace/'knowledge/Course/02-English.txt').write_bytes(original+b'\nQA edit during actual inference.\n')
                            action.update(at=time.monotonic(), changed_sha256=hashlib.sha256((workspace/'knowledge/Course/02-English.txt').read_bytes()).hexdigest())
                    if case!='crash':
                        threading.Thread(target=alter).start()
                response = super().post(url,json=json)
                if task==target:
                    action['post_finished']=time.monotonic()
                return response
        with closing(Client()) as client:
            report = measured_document(db,job,settings,client)
        changed_rejected = None
        if case=='edit':
            try:
                SourceSession(db, job['scope'], job['manifest']).read(beta)
                changed_rejected = False
            except Exception as exc:
                changed_rejected = {'type':type(exc).__name__, 'code':getattr(exc,'code',None), 'message':str(exc)}
            (workspace/'knowledge/Course/02-English.txt').write_bytes(original)
        preserved = {}
        for table, rows in existing.items():
            oldids = [r['id'] for r in rows]
            after = [dict(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY id') if r['id'] in oldids]
            preserved[table] = digest(after)==hashes[table]
        report.update(case=case, prompt_version=jobs.pipeline.local.PROMPT_VERSION, action=action, previous_writing_preserved=preserved, changed_original_read_rejection=changed_rejected, method='Copied invented corpus; actual production handler, durable jobs, HTTP model responses. Not a native UI, physical power-loss or OS force-quit test.')
        print(save_report(workspace/'report.json',report),flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('case',choices=['cancel','edit','crash'])
    parser.add_argument('--child',type=Path)
    args=parser.parse_args()
    if args.child:
        work(args.child/'app/app.db',args.child,args.case)
        return
    workspace=OUT/f'actual-inference-{args.case}-{uuid.uuid4()}'
    workspace.mkdir()
    shutil.copytree(BASE/'knowledge',workspace/'knowledge')
    (workspace/'app').mkdir()
    with closing(sqlite3.connect(f'file:{BASE}/app/app.db?mode=ro',uri=True)) as source, closing(sqlite3.connect(workspace/'app/app.db')) as target:
        source.backup(target)
    process=subprocess.Popen([sys.executable,__file__,args.case,'--child',str(workspace)])
    print(json.dumps({'case':args.case,'workspace':str(workspace),'owned_pid':process.pid}),flush=True)
    if args.case!='crash':
        raise SystemExit(process.wait())
    deadline=time.monotonic()+120
    while not (workspace/'active.json').exists():
        if process.poll() is not None or time.monotonic()>deadline:
            raise RuntimeError('Owned worker did not enter actual inference.')
        time.sleep(0.1)
    time.sleep(0.5)
    killed_at=time.monotonic()
    process.send_signal(signal.SIGKILL)
    process.wait(timeout=10)
    os.environ['NOYE_DATA_DIR']=str(workspace/'app')
    os.environ['DATABASE_URL']=f'sqlite:///{workspace}/app/app.db'
    from app.db.database import connect
    from app.services import knowledge_jobs
    from app.evaluation.source_documents import save_report
    with closing(connect()) as db:
        marker=json.loads((workspace/'active.json').read_text())
        before=knowledge_jobs.get(db,marker['job_id'])
        count=db.execute('SELECT count(*) FROM knowledge_jobs').fetchone()[0]
        writing={table:digest(db.execute(f'SELECT * FROM {table} ORDER BY id')) for table in ('documents','messages','conversations')}
        knowledge_jobs.recover_interrupted(db)
        recovered=knowledge_jobs.get(db,marker['job_id'])
        replayed=db.execute('SELECT count(*) FROM knowledge_jobs').fetchone()[0]!=count
        preserved={table:digest(db.execute(f'SELECT * FROM {table} ORDER BY id'))==sha for table,sha in writing.items()}
        retry=knowledge_jobs.resume(db,marker['job_id'])
        retry=knowledge_jobs.cancel(db,retry['id'])
        report={'case':'crash','marker':marker,'killed_at':killed_at,'returncode':process.returncode,'before':before,'recovered':recovered,'automatic_replay':replayed,'writing_preserved_across_recovery':preserved,'explicit_retry_state':retry['state'],'explicit_retry_attempt':retry['attempt'],'frozen_scope_and_manifest_retained':retry['scope']==before['scope'] and retry['manifest']==before['manifest'],'note':'SIGKILL of only the owned QA Python worker 0.5 seconds after a real nonempty response token arrived. Only this QA request uses stream=True as instrumentation; production uses stream=False. Remaining request fields/production job handler are unchanged. Not native OS force-quit or physical power-loss acceptance.'}
        print(save_report(workspace/'report.json',report),flush=True)
if __name__=='__main__':main()
