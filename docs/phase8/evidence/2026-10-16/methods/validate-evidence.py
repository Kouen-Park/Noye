"""Validate the explicit publication inventory without printing possible secrets.

Checks SHA-256/byte lengths, strict JSON, allowed evidence formats and common
credential/private-key patterns. This is a bounded artifact hygiene check, not
an independent security audit or proof that all possible secrets are absent.
"""
import hashlib,json,pathlib,re
import xml.etree.ElementTree as ET
root=pathlib.Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-16')
record=json.loads((root/'publication.json').read_text());listed=set();json_count=0;hits=[]
patterns=[re.compile(r'(?<![A-Za-z])sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}'),re.compile(r'AIza[0-9A-Za-z_-]{35}'),re.compile(r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b'),re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
for e in record['files']:
    p=root/e['file'];assert p.is_file(),e['file'];data=p.read_bytes();listed.add(e['file'])
    assert len(data)==e['published_bytes'],e['file']
    assert hashlib.sha256(data).hexdigest()==e['published_sha256'],e['file']
    assert p.suffix in {'.json','.py','.txt','.xml','.pdf','.png'},e['file']
    if p.suffix=='.json':
        def reject(c):raise ValueError(c)
        json.loads(data,parse_constant=reject);json_count+=1
    if p.suffix=='.xml':ET.fromstring(data)
    if p.suffix=='.pdf':assert data.startswith(b'%PDF-'),e['file']
    elif p.suffix=='.png':assert data.startswith(b'\x89PNG\r\n\x1a\n'),e['file']
    elif any(pattern.search(data.decode()) for pattern in patterns):hits.append(e['file'])
actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}-{'publication.json'}
assert actual==listed,{'unlisted':sorted(actual-listed),'missing':sorted(listed-actual)}
assert not hits,{'credential_pattern_files_only':hits}
print(json.dumps({'published_records':len(listed),'strict_json_files':json_count,'hashes_and_lengths':'all match','unlisted_files':0,'common_credential_patterns':0,'methods_note':__doc__}))
