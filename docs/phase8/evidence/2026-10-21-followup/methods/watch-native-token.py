"""Wait for a new real runner n_gen progress line after this invocation's log offset. No UI or model payload changes. Native generation remains non-streaming."""
import hashlib,json,re,time
from pathlib import Path
base=Path('/private/tmp/noye-phase8-20261021-followup');log=base/'ollama-native.log';marker=base/'native-token-progress.json';assert not marker.exists();offset=log.stat().st_size
(base/'native-token-watch-start.json').write_text(json.dumps({'offset':offset,'at':time.time(),'method':__doc__},indent=2)+'\n')
for _ in range(480):
 data=log.read_bytes()[offset:]
 match=re.search(rb'^.*n_gen =\s*(\d+).*$',data,re.M)
 if match:
  row={'at':time.time(),'new_log_offset':offset,'generated_tokens':int(match[1]),'runner_line':match[0].decode(),'new_log_prefix_sha256':hashlib.sha256(data).hexdigest()};assert row['generated_tokens']>0
  marker.write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True);break
 time.sleep(.25)
else:raise TimeoutError('No new actual runner token progress')
