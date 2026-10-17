"""Rerun the four affected integration cases after correcting embedding-identity fixtures. The first failed/vacuous outcomes remain recorded; the other fifteen passing checks are not repeated.

Each test gets a unique SQLite/files root and Qdrant collection. This also keeps
arbitrary-vector server tests separate from genuine embedding-identity tests.
No cloud credentials, personal collections, model pulls or model deletion.
"""
import hashlib,json,os,pathlib,subprocess,time
import httpx
root=pathlib.Path('/Users/gavinpark/Projects/Noye');qa=pathlib.Path('/private/tmp/noye-phase8-20261016');out=qa/'live-integration-corrected'
out.mkdir(exist_ok=False)
settings={'OLLAMA_BASE_URL':'http://127.0.0.1:11439','OLLAMA_MODEL':'qwen3.5:4b','OLLAMA_EMBEDDING_MODEL':'embeddinggemma','QDRANT_URL':'http://127.0.0.1:16339','QDRANT_VECTOR_SIZE':'768','GENERATION_CONTEXT_TOKENS':'8192','GENERATION_OUTPUT_TOKENS':'2048','OLLAMA_THINKING':'false','LOG_TO_FILE':'false','GEMINI_API_KEY':'','OPENAI_API_KEY':'','ANTHROPIC_API_KEY':'','NO_PROXY':'127.0.0.1,localhost'}
report={'method':__doc__,'service_settings':{k:v for k,v in settings.items() if 'KEY' not in k},'rows':[]}
with httpx.Client(trust_env=False,timeout=30) as client:
    for url in [settings['OLLAMA_BASE_URL']+'/api/version',settings['QDRANT_URL']+'/']:
        response=client.get(url);response.raise_for_status()
        report.setdefault('preflight',[]).append({'url':url,'status':response.status_code,'body':response.json()})
    for number,nodeid in [(i, nodeid) for i, nodeid in enumerate(json.loads((qa/'live-integration-nodeids.json').read_text()),1) if i in [15,17,18,19]]:
        case=out/f'case-{number:02}';case.mkdir();collection=f'noye_phase8_live_corrected_20261016_{number:02}'
        env={**os.environ,**settings,'NOYE_DATA_DIR':str(case),'DATABASE_URL':'sqlite:///'+str(case/'app.db'),'QDRANT_COLLECTION':collection}
        log=out/f'case-{number:02}.log';xml=out/f'case-{number:02}.xml';began=time.monotonic()
        print(json.dumps({'starting':number,'nodeid':nodeid}),flush=True)
        with log.open('x') as output:
            result=subprocess.run([str(root/'backend/.venv/bin/python'),'-m','pytest','-q','-rA',nodeid,'--junitxml='+str(xml)],cwd=root/'backend',env=env,stdout=output,stderr=subprocess.STDOUT,check=False)
        row={'number':number,'nodeid':nodeid,'exit_code':result.returncode,'seconds':round(time.monotonic()-began,3),'collection':collection,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
        # Keep failed collections available for diagnosis; passing synthetic data is disposable.
        if result.returncode==0:
            response=client.delete(settings['QDRANT_URL']+'/collections/'+collection)
            row['cleanup_http_status']=response.status_code
        report['rows'].append(row);(qa/'live-integration-corrected.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(row),flush=True)
    report['unload_http_status']=client.post(settings['OLLAMA_BASE_URL']+'/api/generate',json={'model':settings['OLLAMA_MODEL'],'keep_alive':0}).status_code
    report['unload_embedding_http_status']=client.post(settings['OLLAMA_BASE_URL']+'/api/generate',json={'model':settings['OLLAMA_EMBEDDING_MODEL'],'keep_alive':0}).status_code
    report['remaining_loaded_models']=client.get(settings['OLLAMA_BASE_URL']+'/api/ps').json()
(qa/'live-integration-corrected.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'finished':len(report['rows']),'process_successes':sum(x['exit_code']==0 for x in report['rows'])}),flush=True)
