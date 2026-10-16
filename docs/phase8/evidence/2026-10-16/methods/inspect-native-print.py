"""Read-only checks for a native-exported synthetic source-link PDF.

MuPDF Rect objects are serialized as strings. This inspector does not create or
edit PDFs. Rendering is for visual review, which is recorded separately.
"""
import hashlib
import json
import sys
from pathlib import Path

import httpx
import pymupdf

fixture_path, pdf_path, report_path, png_path = map(Path, sys.argv[1:])
fixture = json.loads(fixture_path.read_text())
with pymupdf.open(pdf_path) as pdf:
    text = '\n'.join(page.get_text() for page in pdf)
    links = [link for page in pdf for link in page.get_links()]
    checks = {
        'one_page': len(pdf) == 1,
        'korean': '한국어 원문 링크 인쇄 검증.' in text,
        'measured_values': '12 milliseconds' in text and '37 megabytes' in text,
        'label': 'Open AT-201 original' in text,
        'destination_text': fixture['original_url'] in ''.join(text.split()),
        'destination_annotation': any(link.get('uri') == fixture['original_url'] for link in links),
        'sent_status_hidden': 'Sent the original' not in text,
        'pending_status_hidden': 'Opening original' not in text,
        'sentinel': 'FINAL-ORIGINAL-PRINT-20261016' in text,
    }
    pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(png_path)
    pages = len(pdf)
with httpx.Client(timeout=10, trust_env=False) as client:
    saved = client.get(fixture['base_url'] + '/documents/' + fixture['document']['id']).json()
checks['markdown_unchanged'] = hashlib.sha256(saved['content'].encode()).hexdigest() == fixture['content_sha256']
report = {
    'method': __doc__, 'path': str(pdf_path), 'bytes': pdf_path.stat().st_size,
    'sha256': hashlib.sha256(pdf_path.read_bytes()).hexdigest(), 'pages': pages,
    'checks': checks, 'links': links, 'text': text, 'visual_accepted': None,
    'native_save_observation': 'Initial Save remained disabled, confirmed by screenshot and later full AX. Re-selecting the same existing QA directory enabled it; filename was unchanged. This save does not accept first-panel default destination activation.',
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n')
print(json.dumps({'pages': pages, 'bytes': report['bytes'], 'checks': checks}, ensure_ascii=False))
