"""Real invented PDF files through production scanner/ingestion/SourceSession.

This is not a native picker, live REST Qdrant or representative long-PDF/model
quality test. Scanner stability uses its controlled clock; actual extraction,
SQLite, local embedding HTTP requests and in-memory Qdrant are used.
"""
import hashlib
import json
import os
import shutil
import time
from contextlib import closing
from pathlib import Path

import pymupdf

ROOT = Path('/private/tmp/noye-phase8-20261014/pdf-input-controls')
ROOT.mkdir(exist_ok=False)
SAVED = Path('/Users/gavinpark/Projects/Noye/docs/phase8/evidence/2026-10-15/native-pdf')
originals = ROOT / 'knowledge'
originals.mkdir()
shutil.copyfile(SAVED / 'fixed-native.pdf', originals / 'valid.pdf')
image_pdf = originals / 'image-only.pdf'
with pymupdf.open(SAVED / 'fixed-native.pdf') as layout, pymupdf.open() as output:
    for i, source in enumerate(layout):
        page = output.new_page(width=source.rect.width, height=source.rect.height)
        page.insert_image(page.rect, filename=str(SAVED / f'fixed-page-{i+1:02}.png'))
    output.save(image_pdf, deflate=True)
# This control is intentionally not a deliverable PDF: truncation is the test.
corrupt = originals / 'corrupt.pdf'
corrupt.write_bytes((originals / 'valid.pdf').read_bytes()[:48])

os.environ['NOYE_DATA_DIR'] = str(ROOT / 'app')
os.environ['DATABASE_URL'] = f'sqlite:///{ROOT}/app/app.db'
from app.config import get_settings
from app.db.database import connect, init_schema
from app.services import ingestion
from app.services.extraction import extract_pdf
from app.services.folder_scanner import FolderScanner
from app.services.folders import register_root, update_root
from app.services.source_catalog import SourceCatalog, SourceSession
from qdrant_client import QdrantClient

get_settings.cache_clear()
report = {'method': __doc__, 'rows': [], 'errors': {}, 'inputs': {}}
for p in sorted(originals.iterdir()):
    report['inputs'][p.name] = {'bytes': p.stat().st_size,
        'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    if p.name != 'corrupt.pdf':
        report['inputs'][p.name]['extracted_pages'] = [
            {'page': x.page_number, 'characters': len(x.content), 'empty': x.is_empty}
            for x in extract_pdf(p)]
for p in [corrupt, originals / 'missing.pdf']:
    try:
        extract_pdf(p)
        raise AssertionError('An invalid input unexpectedly extracted.')
    except Exception as exc:
        if isinstance(exc, AssertionError):
            raise
        report['errors'][p.name] = {'type': type(exc).__name__, 'message': str(exc)}
with closing(connect()) as db, closing(QdrantClient(':memory:')) as qdrant:
    init_schema(db)
    root = register_root(db, originals, 'connected')
    update_root(db, root, processing=True)
    now = [0.0]
    scanner = FolderScanner(clock=lambda: now[0])
    scanner.scan_root(db, root)
    now[0] = 3.0
    pending = scanner.scan_root(db, root)
    for identifier in pending:
        start = time.monotonic()
        record = ingestion.ingest_file(db, identifier, qdrant_client=qdrant, reserved=True)
        row = {'id': record.id, 'name': record.name, 'state': record.status.value,
               'error': record.error, 'seconds': round(time.monotonic() - start, 3)}
        report['rows'].append(row)
    session = SourceSession(db)
    for source in SourceCatalog(db).list_sources():
        try:
            passages = session.read(source['source_id'], limit=100)
            text = '\n'.join(p.text for p in passages)
            report.setdefault('source_reads', {})[source['relative_path']] = {
                'pages': sorted(set(p.page_number for p in passages)), 'passages': len(passages),
                'final_sentinel_retained': 'FINAL-PDF-ALL-CONTENT-20261015' in text,
                'characters': len(text)}
        except Exception as exc:
            report.setdefault('source_reads', {})[source['relative_path']] = {
                'error': type(exc).__name__, 'code': getattr(exc, 'code', None)}
    settings = get_settings()
    points = qdrant.scroll(settings.qdrant_collection, limit=100, with_payload=True)[0]
    report['point_file_ids'] = sorted(set(p.payload['file_id'] for p in points))
    report['point_count'] = len(points)
    rows = {r['name']: r for r in report['rows']}
    assert rows['valid.pdf']['state'] == 'READY'
    assert rows['image-only.pdf']['state'] == rows['corrupt.pdf']['state'] == 'FAILED'
    assert report['point_file_ids'] == [rows['valid.pdf']['id']]
    assert report['source_reads']['valid.pdf']['final_sentinel_retained']
    assert report['source_reads']['valid.pdf']['pages'] == list(range(1, 8))
    assert all(x['empty'] for x in report['inputs']['image-only.pdf']['extracted_pages'])
with pymupdf.open(image_pdf) as pdf:
    for i, page in enumerate(pdf):
        page.get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(ROOT / f'image-only-page-{i+1:02}.png')
(ROOT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False), flush=True)
