# Phase 7 item 10: retrieval evaluation foundation

Started independently from `main` on 2026-10-05 while Phase 6 continues in a
separate checkout. This supplies a pilot dataset and reproducible comparisons;
it did not close item 10 at that checkpoint. The later comparisons and actual
answer/abstention reviews below complete its implementation measurements;
independent human review and larger real-document studies remain Phase 8 work.

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

## Final integration — 2026-10-05

`feat/retrieval-evaluation` retains closed #40's feature head `f550315` and normally
merges main `9334d56` after Phase 6, local exposure, maintenance and identity landed.
The final implementation `f1cdc8b` merged cleanly. Fresh full backend: **734 passed,
19 skipped, 8 warnings**; frontend: **199 passed**. Ruff, ESLint, TypeScript,
unsigned macOS packaging/static export (**67.53 MiB**), Rust format/Clippy and final
frozen-backend checks (**10 passed**) passed. The prior merged source also passed
route types/web build and unchanged native Rust tests (**3 passed**).

A fresh lexical-only CLI run reproduced Recall@5 **0.7143**, nDCG@5 **0.7656**,
and all three negatives returning some context; p50/p95 was **0.0467/0.0749 ms**.
Its report was temporary, not a replacement for the historical committed model
comparisons. No model/Qdrant call or generation was made by that lexical run.
Dense/hybrid reports above retain their original environment/hashes and were not
regenerated. Production ranking remains unchanged. Item 10 is still partial.

## Workflow and input comparison — 2026-10-05

`feat/knowledge-workflow-completion` adds `atlas-v1.json`: 30 pre-chunked passages,
10 fictional lecture/lab/research/meeting/PDF-log documents and 26 questions
(22 answerable, four negatives). Close identifiers include AT-201/210,
DB-318/381, RS-044/040, SM-812/821 and PX-606/660. This represents study-workflow
types, not personal documents or a representative sample of all real PDFs.
The corpus remains intentionally small. It does not measure extraction or chunking.

The [EmbeddingGemma model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card)
describes distinct retrieval query/document prefixes. The installed Ollama 0.34.2
model's `/api/show` template was `{{ .Prompt }}`, with a 2048-token context.
The [versioned embed handler](https://github.com/ollama/ollama/blob/v0.34.2/server/routes.go)
passes supplied text to embedding and rejects over-context inputs when truncation
is disabled. Noye can now explicitly supply `task: search result | query: ` or
`title: none | text: `, retaining the original passage separately. Tests capture
these payloads; an actual 8000-character Korean input was rejected with a useful
error and no silent truncation. A short raw input returned 768 dimensions.
`runner-validation.json` records the observation. Character limits include prefixes
and are request-size guards, not token estimates.

Fresh reports use the installed embedding digest listed above, raw-v1 or
embeddinggemma-v1 consistently for both corpus and questions. They were generated
from the working tree at the commits recorded in each report, before subsequent
workflow commits; retained harness/production hashes identify the measured source.
No saved library was re-indexed and no model was downloaded.

| Corpus / variant | Recall@5 | nDCG@5 | MRR@5 | Warm p50 / p95 ms |
| --- | --- | --- | --- | --- |
| Lumen, raw input | 0.9762 | 0.9485 | 0.9762 | 24.05 / 29.58 |
| Lumen, task prefixes | 0.9524 | 0.9368 | 0.9762 | 22.84 / 32.15 |
| Atlas, raw input | 1.0000 | 0.9788 | 0.9773 | 24.45 / 32.75 |
| Atlas, task prefixes | 1.0000 | 0.9927 | 1.0000 | 26.85 / 47.43 |
| Atlas, raw dense + BM25/RRF60 | 0.8182 | 0.8355 | 1.0000 | 24.32 / 36.34 |

Raw input remains the default: task prefixes improved Atlas ranking but worsened
Lumen recall/ranking. An explicit format change is available and invalidates the
index fingerprint; it requires a deliberate rebuild. Hybrid remains declined:
simple Unicode-word tokenization misses Korean suffix/cross-language matches and
fusion loses required bilingual facts. The earlier diversity comparison also
reduced recall. These results do not rule out better tokenization or fusion.

Conditional reranking is **declined for this baseline**. Atlas retrieves every
relevant passage/document by K=5, and Lumen's observed factual failures below occur
with the needed excerpts already present. There is no demonstrated retrieval
bottleneck justifying another local model and its loading/context cost on this
8-GiB machine. No cross-encoder was installed or benchmarked; this is a measured
adoption decision, not a claim that all rerankers were compared. Larger-corpus and
production chunking comparisons remain Phase 8 evaluation work.

## Actual generated answers and explicit rubric review

`answer-baseline.json` retains 24 actual Lumen answers from local `qwen3.5:4b`
(installed Q4_K_M, digest
`2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`).
All retrieval runs finish before generation to avoid swapping embedding and
generation models for each question. This eliminated a failed alternating-model
attempt's load timeout. Ranking and generation still use the production functions.

`answer-reviews.json` records **Codex's explicit rubric inspection**, with per-answer
SHA-256 and rationale. It is not an independent human review or an automatic LLM
judge. Core factual correctness is 22/24 (0.9167), faithfulness 21/24 (0.875), and
all three negatives abstained (3/3). Three Korean questions were answered in English
(language match 21/24). These are distinct outcomes: retrieval alone cannot prove
that the model used its evidence correctly or answered in the requested language.

The digest-change answer confused generation and embedding models; the SQLite
preservation answer incorrectly included vectors and declined a reason present in
the excerpts. One otherwise correct answer added an unsupported condition. The
reviews preserve those failures rather than converting retrieved context into a
pass. Median generation was 45.53 s and p95 84.87 s in this memory-constrained run,
including model-load effects. This is neither cold/warm separation nor API/native
end-to-end latency, and model sampling was not fixed to a deterministic seed.

Reproduce aggregation without overwriting the originals:

```bash
python -m app.evaluation.review \
  --report ../docs/phase7/answer-baseline.json \
  --reviews ../docs/phase7/answer-reviews.json \
  --output /tmp/noye-reviewed.json
```

The review tool rejects a mismatched dataset, unknown question, changed answer,
missing reviewer/rationale or non-boolean judgment. Unreviewed answers remain
unknown. Its abstention denominator includes reviewed negatives only.

## Follow-up context comparison

`followups-v1.json` and `app.evaluation.context` compare two fixed English/Korean
follow-ups with the same isolated Atlas corpus and production context functions.
Run `python -m app.evaluation.context --generate --output /tmp/followups.json`.
The runner explicitly unloads the configured embedding model for one cold query;
use an isolated evaluation Ollama service. It never opens SQLite or a personal
Qdrant collection. Reports retain questions, rankings, expected answers, context
hashes, actual answers and timing.

English “Which was faster?” improves Recall@5 from 0.75 to 1.0 and nDCG@5 from
0.5143 to 1.0 after adding the recent user's AT-201/AT-210 topic. Both final answers
correctly give the 27-ms difference. Korean “그럼 두 결과의 대화 수 차이는 얼마야?”
retrieves all relevant passages with both variants, but the bounded answer treats
an unrecorded count as zero and incorrectly answers 87; the standalone answer
correctly says the difference is unknown. This remains a recorded generation
failure, not a successful quality gate.

A prior comparison containing previous assistant prose (`followup-with-assistant.json`)
also produced this false inference. Production now sends only bounded recent user
questions, excluding generated claims entirely. The stricter boundary prevents
propagating prior assistant prose, but the final Korean result shows that the
boundary alone does not solve numerical faithfulness.

In `followup-comparison.json`, the explicitly unloaded embedding query took
809.81 ms; warm retrieval took 21.19/21.30 ms (English standalone/bounded) and
21.88/29.22 ms (Korean). Generation took 17.97/4.99 s and 8.25/6.78 s respectively.
The first answer includes a model-load cost, and order/cache/memory effects are
uncontrolled. Two cases and one timing per case are insufficient to claim a
general speed or answer-quality improvement. Independent human review, larger
workloads, actual PDF/chunking comparisons and final Phase 8 acceptance remain open.
