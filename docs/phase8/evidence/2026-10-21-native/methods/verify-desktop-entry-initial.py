"""Check the actual frozen entry point against current source instructions/constants, ignoring source locations only. This is archive verification, not a native runtime observation."""
import hashlib,json,marshal,types
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader
root=Path('/Users/gavinpark/Projects/Noye');base=Path('/private/tmp/noye-phase8-20261021-native');sidecar=root/'frontend/src-tauri/target/release/bundle/macos/Noye Phase8 QA.app/Contents/MacOS/noye-backend'
def signature(code):
 def constant(value):return signature(value) if isinstance(value,types.CodeType) else value
 return (code.co_code,code.co_names,code.co_varnames,code.co_freevars,code.co_cellvars,code.co_flags,code.co_argcount,code.co_posonlyargcount,code.co_kwonlyargcount,code.co_exceptiontable,tuple(constant(c) for c in code.co_consts))
source=(root/'backend/desktop.py').read_bytes();expected=compile(source,str(root/'backend/desktop.py'),'exec',dont_inherit=True);entry=marshal.loads(CArchiveReader(str(sidecar)).extract('desktop'))
assert signature(expected)==signature(entry)
assert 'PARENT_SHUTDOWN_SECONDS' in entry.co_names and 15 in entry.co_consts
result={'method':__doc__,'source_sha256':hashlib.sha256(source).hexdigest(),'sidecar_sha256':hashlib.sha256(sidecar.read_bytes()).hexdigest(),'compiled_code_matches_source':True,'parent_shutdown_seconds':15}
(base/'entry-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
