"""Actual exported PDF extraction + existing Atlas originals, existing rank harness.

Synthetic calibration only. No generation, personal library, production threshold
change or replacement evaluation harness. Full source paragraphs are the Atlas
gold evidence; the PDF rows require all specified markers in one real chunk.
"""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from app.config import get_settings
from app.evaluation.dataset import load_dataset
from app.evaluation.run import DenseRanker, evaluate
from app.models.files import FileType
from app.services.chunking import chunk_pages
from app.services.embeddings import embed_query
from app.services.extraction import extract_file

REPO = Path('/Users/gavinpark/Projects/Noye')
ROOT = Path('/private/tmp/noye-phase8-20261014/pdf-chunk-comparison')
PDF = REPO / 'docs/phase8/evidence/2026-10-15/native-pdf/fixed-native.pdf'
ROOT.mkdir(exist_ok=False)
atlas = load_dataset(REPO / 'backend/evaluation/atlas-v1.json')
by_id = {p['id']: p for p in atlas['passages']}
groups = defaultdict(list)
for passage in atlas['passages']:
    groups[passage['document_id']].append(passage['text'])
originals = {}
for identifier, paragraphs in groups.items():
    path = ROOT / f'{identifier}.txt'
    path.write_text('\n\n'.join(paragraphs) + '\n')
    originals[identifier] = (path, FileType.TEXT)
originals['native-complex-pdf'] = (PDF, FileType.PDF)
normalize = lambda text: re.sub(r'\s+', '', text)
selected = ['AT-201-en', 'AT-201-ko', 'DB-318-en', 'RS-044-en',
            'compare-graphs', 'compare-pdf', 'identifier-negative', 'fees-negative']
questions = [q for q in atlas['questions'] if q['id'] in selected]
if len(questions) != len(selected):
    raise ValueError('A selected Atlas question is missing; do not silently reduce the run.')
extra = [
    ('table-038', 'What measure, condition and exact token are recorded in PDF row T038?',
     ['T038', '38ms', 'Sundayexception', 'TOKEN-038-END'], '38 ms, Sunday exception, TOKEN-038-END.'),
    ('table-040-ko', 'PDF 표 T040의 수치와 정확한 토큰은?',
     ['T040', '40ms', 'TOKEN-040-END'], '40 ms, TOKEN-040-END.'),
    ('final-sentinel', 'What final sentinel appears at the end of the complex PDF?',
     ['FINAL-PDF-ALL-CONTENT-20261015', '끝까지보존.'], 'FINAL-PDF-ALL-CONTENT-20261015 / 끝까지 보존.'),
]
extracted = {identifier: extract_file(path, kind)
             for identifier, (path, kind) in originals.items()}
source_record = {
    identifier: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'physical_pages': len(extracted[identifier]) if kind.has_pages else None,
                 'pages': [{'page': p.page_number, 'characters': len(p.content), 'empty': p.is_empty}
                           for p in extracted[identifier]]}
    for identifier, (path, kind) in originals.items()
}
report = {
    'method': __doc__, 'source_records': source_record,
    'sizes': [], 'production_defaults_changed': False,
    'limitations': 'Eleven invented documents and eleven hand-selected questions, '
    'including two negatives. Source paragraphs, PDF text and ranking are actually '
    'processed; this is not representative personal-document calibration or an answer-quality test. '
    'Overlap is fixed at 150 characters, sizes are 500/1000/1500. Atlas files are short '
    'and may not change shape across sizes. All three variants are reported, no winner '
    'or threshold is installed from this sample.',
}
for size in [500, 1000, 1500]:
    passages = []
    for identifier, pages in extracted.items():
        for c in chunk_pages(pages, file_id=identifier, chunk_size=size, overlap=150):
            passages.append({'id': f'{identifier}-{c.chunk_index}', 'document_id': identifier,
                             'page_number': c.page_number if originals[identifier][1].has_pages else None,
                             'text': c.content})
    rows = []
    for q in questions:
        gold = {}
        for old_id, grade in q['relevance'].items():
            old = by_id[old_id]
            matches = [p for p in passages if p['document_id'] == old['document_id']
                       and normalize(old['text']) in normalize(p['text'])]
            if not matches:
                raise ValueError(f'Full gold evidence not in any chunk: {size}/{old_id}')
            for p in matches:
                gold[p['id']] = max(gold.get(p['id'], 0), grade)
        rows.append({**q, 'relevance': gold})
    for identifier, question, needles, answer in extra:
        gold = {p['id']: 2 for p in passages if p['document_id'] == 'native-complex-pdf'
                and all(n in normalize(p['text']) for n in needles)}
        if not gold:
            raise ValueError(f'PDF gold evidence not in one chunk: {size}/{identifier}')
        rows.append({'id': identifier, 'text': question, 'categories': ['actual-pdf'],
                     'relevance': gold, 'unanswerable': False, 'expected_answer': answer})
    dataset = {'version': 1, 'name': f'actual-native-pdf-atlas-chunk-{size}',
               'passages': passages, 'questions': rows}
    file = ROOT / f'dataset-{size}.json'
    file.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + '\n')
    load_dataset(file)
    metrics = evaluate(dataset, mode='dense', ks=[1, 3, 5], repeats=2)
    (ROOT / f'dense-{size}.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + '\n')
    # Additional score probe on the same corpus/model, leaving the rank harness intact.
    ranker = DenseRanker(passages)
    score_rows = []
    try:
        for q in rows:
            points = ranker.client.query_points(get_settings().qdrant_collection,
                query=embed_query(q['text']), limit=len(passages), with_payload=True).points
            ranking = [{'id': ranker.positions[(p.payload['file_id'], p.payload['chunk_index'])],
                        'score': p.score} for p in points]
            score_rows.append({'id': q['id'], 'unanswerable': q['unanswerable'],
                               'gold': q['relevance'], 'ranking': ranking})
    finally:
        ranker.close()
    cutoffs = []
    for cutoff in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        cutoffs.append({'cutoff': cutoff,
            'negative_questions_with_any_result': sum(r['unanswerable'] and r['ranking'][0]['score'] >= cutoff for r in score_rows),
            'answerable_questions_with_no_gold_retained': sum(not r['unanswerable'] and not any(p['id'] in r['gold'] and p['score'] >= cutoff for p in r['ranking']) for r in score_rows)})
    one = {'size': size, 'overlap': 150, 'chunks': len(passages),
           'summary': metrics['summary'], 'latency': metrics['latency'],
           'threshold_probes': cutoffs, 'score_rows': score_rows}
    report['sizes'].append(one)
    (ROOT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: one[k] for k in ['size', 'chunks', 'summary', 'threshold_probes']}, ensure_ascii=False), flush=True)
