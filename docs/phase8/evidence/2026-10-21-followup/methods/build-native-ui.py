"""Rebundle the changed frontend with the unchanged verified v27/v13 sidecar. Uses cached Rust dependencies offline, local ad-hoc QA signing, and no new model calls."""
import hashlib,json,os,subprocess,time
from pathlib import Path
root=Path('/Users/gavinpark/Projects/Noye');base=Path('/private/tmp/noye-phase8-20261021-followup');target=base/'native-ui-build.json';assert not target.exists()
bundle=root/'frontend/src-tauri/target/release/bundle/macos/Noye Phase8 QA.app';sidecar=bundle/'Contents/MacOS/noye-backend';before=hashlib.sha256(sidecar.read_bytes()).hexdigest();assert before=='dd6450e6a7ac9d3122612ae8ef0e4a0400de03fd3a477786d9f99fb295a597aa'
env={**os.environ,'CARGO_HOME':str(root/'.desktop-tools/cargo'),'RUSTUP_HOME':str(root/'.desktop-tools/rustup'),'PATH':str(root/'.desktop-tools/cargo/bin')+':'+os.environ['PATH'],'CARGO_NET_OFFLINE':'true','APPLE_SIGNING_IDENTITY':'-'}
report={'method':__doc__,'source_commit':subprocess.check_output(['git','-c','core.fsmonitor=false','rev-parse','HEAD'],cwd=root,text=True).strip(),'sidecar_before_sha256':before,'stages':[]}
for name,argv,cwd in [('native-ui-bundle',['npx','--no-install','tauri','build','--bundles','app','--config','/private/tmp/noye-phase8-20261021/tauri-qa.json'],root/'frontend'),('native-ui-signature',['codesign','--verify','--deep','--strict',str(bundle)],root)]:
 start=time.monotonic();log=base/(name+'.log')
 with log.open('x') as out:r=subprocess.run(argv,cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT)
 row={'name':name,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,3),'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()};report['stages'].append(row);target.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(row),flush=True)
 if r.returncode:raise SystemExit(r.returncode)
report['sidecar_after_sha256']=hashlib.sha256(sidecar.read_bytes()).hexdigest();assert report['sidecar_after_sha256']==before
report['native_sha256']=hashlib.sha256((bundle/'Contents/MacOS/noye-desktop').read_bytes()).hexdigest();target.write_text(json.dumps(report,indent=2)+'\n')
