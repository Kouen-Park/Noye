# Phase 7 item 10: retrieval evaluation foundation

Started independently from `main` on 2026-10-05 while Phase 6 continues in a
separate checkout. This supplies a pilot dataset and reproducible comparisons;
it does not close the complete item 10 quality milestone.

The [parallel merge guide](parallel-merge-guide.md) records draft PR order,
observed conflicts and validation of a combined committed Phase 6 snapshot.

`backend/evaluation/lumen-v1.json` contains invented project facts: 18 pre-chunked
passages across 9 documents, 24 Korean/English questions, 21 answerable questions
and 3 negatives. It includes cross-language questions, close identifiers
NX-742/NX-724, missing NX-999, multi-document cases, graded relevance and manual
answer-review rubrics. It contains no personal documents or production database.

Run from `backend` using the project virtual environment:

```bash
python -m app.evaluation.run --mode lexical --output /tmp/lexical.json
python -m app.evaluation.run --mode dense --output /tmp/dense.json
python -m app.evaluation.run --mode hybrid --output /tmp/hybrid.json
python -m app.evaluation.run --mode hybrid --diversify --output /tmp/diverse.json
```

Dense/hybrid runs require the configured local Ollama embedding model to already
be installed. They use a fresh **in-memory Qdrant** and do not open SQLite, connect
to the user's Qdrant server or write personal library files. There is no model
download, cloud request or automatic search-algorithm change. `--generate` is a
separate explicit option to save local answers and timing for manual review;
answers are not automatically labelled accurate or supported.

The runner records Recall@K, Precision@K, MRR@K, graded nDCG@K, relevant-document
coverage, categories, negative-context returns, initial/repeated query timings,
model digest, dataset/harness/production-source hashes and package/platform
metadata. Negatives do not inflate positive recall and duplicate passage IDs
are rejected. K defaults to 1/3/5; each query repeats twice.

## Recorded pilot results

Reports were generated from harness commit
`e6b616b39218c2261684ffd2764091a77ebe2164`, against baseline production code from
`main` (`e8dfa91`). Local Ollama 0.34.2 ran on an owned temporary loopback port,
using already-installed EmbeddingGemma (307.58M, BF16, 768 dimensions), digest
`85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`.
All embedding inputs use the current raw-v1 baseline. No model was downloaded.

| Variant | Recall@5 | nDCG@5 | MRR@5 | Repeat p50 / p95 ms |
| --- | --- | --- | --- | --- |
| Dense cosine baseline | 0.9762 | 0.9485 | 0.9762 | 23.71 / 30.74 |
| Unicode-word BM25 | 0.7143 | 0.7656 | 0.8095 | 0.04 / 0.07 |
| Dense + BM25, RRF constant 60 | 0.8571 | 0.8765 | 0.9286 | 22.80 / 31.33 |
| Same fusion, first passage per document promoted | 0.8333 | 0.8714 | 0.9286 | 22.02 / 28.84 |

The JSON files beside this document retain all per-question rankings and category
results. The Korean lexical baseline uses Unicode words without morphological
analysis; it does not solve suffixes or cross-language matching. Default fusion
and unconditional diversity reduced recall on this pilot, so production retains
the existing dense search. These findings apply to these fixtures and parameters;
they do not rule out a measured alternative tokenizer, fusion weighting or reranker
on a larger corpus. No extra reranking model was introduced without that need.

All variants returned some context for all three negatives. This is a finding
about retrieval, **not proof that an answer hallucinated**: generation may decline
despite nearest-neighbor passages. No arbitrary relevance threshold was installed.

## Validation and limits

- Full backend: **520 passed, 19 skipped**;
  `python -m pytest app/tests -q -p no:cacheprovider`.
- Evaluation regressions: **14 passed**. Gold metric denominators, negative
  aggregation, duplicate rejection, fusion ties, document diversity, dataset
  errors, identifier tokenization and explicit generation behavior are covered.
- Ruff and `git diff --check` passed. Four real local embedding/lexical comparisons
  produced the committed reports; Qdrant used its real in-memory implementation.
- Corpus embedding warms the model before queries, so **cold-model latency is
  unmeasured**, represented by null. Timing is not desktop/API/REST latency and
  excludes production readiness and fingerprint checks. Tiny-run latency differences
  are not a performance conclusion.
- Model answer accuracy, faithfulness and abstention need actual generated answers
  plus human review; their report fields remain null. The optional generation path
  was unit-tested, but not run against the real generation model in these reports.
- PDF parsing, chunk-size/input-prefix comparisons, a representative larger corpus,
  conditional reranking and final packaged-app acceptance remain open. This item
  supplies the foundation for those later measurements rather than claiming them.
