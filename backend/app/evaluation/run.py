"""Run an opt-in synthetic retrieval comparison without opening the user's DB.

python -m app.evaluation.run --mode lexical --output /tmp/lexical.json
python -m app.evaluation.run --mode dense --output /tmp/dense.json
python -m app.evaluation.run --mode hybrid --diversify --output /tmp/hybrid.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import subprocess
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from statistics import median

import httpx
from qdrant_client import QdrantClient

from app.config import get_settings
from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import diversify, ranking_metrics, reciprocal_rank_fusion, summarize
from app.services.chunking import Chunk
from app.services.embeddings import (
    EmbeddingError,
    input_format_version,
)
from app.services.embeddings import (
    embed_documents as embed_texts,
)
from app.services.embeddings import (
    embed_query as embed_text,
)
from app.services.generation import NO_CONTEXT_ANSWER, GenerationError, build_prompt, generate
from app.services.indexing import index_chunks
from app.services.retrieval import SearchResult

DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "evaluation" / "lumen-v1.json"


def tokenize(text: str) -> list[str]:
    """Unicode words with hyphenated IDs intact; Korean morphology is not solved."""
    return re.findall(r"[^\W_]+(?:-[^\W_]+)*", text.casefold(), flags=re.UNICODE)


class LexicalRanker:
    """Small BM25 baseline, not a new production search backend."""

    def __init__(self, passages: list[dict]):
        self.counts = {p["id"]: Counter(tokenize(p["text"])) for p in passages}
        self.lengths = {key: sum(counts.values()) for key, counts in self.counts.items()}
        self.average = max(1.0, sum(self.lengths.values()) / len(passages))
        self.document_frequency = Counter(
            token for counts in self.counts.values() for token in counts
        )

    def rank(self, query: str) -> list[str]:
        scores = {}
        for passage_id, counts in self.counts.items():
            score = 0.0
            for token in set(tokenize(query)):
                frequency = counts[token]
                if not frequency:
                    continue
                df = self.document_frequency[token]
                idf = math.log(1 + (len(self.counts) - df + 0.5) / (df + 0.5))
                denominator = frequency + 1.2 * (1 - 0.75 + 0.75 * self.lengths[passage_id]
                                                 / self.average)
                score += idf * frequency * 2.2 / denominator
            if score > 0:
                scores[passage_id] = score
        return sorted(scores, key=lambda key: (-scores[key], key))


def installed_digest() -> str:
    settings = get_settings()
    response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
    response.raise_for_status()
    wanted = settings.ollama_embedding_model
    wanted = wanted if ":" in wanted.rsplit("/", 1)[-1] else wanted + ":latest"
    for model in response.json()["models"]:
        name = model.get("name") or model.get("model") or ""
        name = name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"
        if name == wanted and model.get("digest"):
            return model["digest"]
    raise EmbeddingError(
        "The configured embedding model is not installed; no model was downloaded."
    )


class DenseRanker:
    """The current raw-input embedding/cosine baseline in isolated Qdrant memory."""

    def __init__(self, passages: list[dict]):
        self.digest = installed_digest()
        self.client = QdrantClient(":memory:")
        self.passages = passages
        self.positions = {(p["document_id"], index): p["id"]
                          for index, p in enumerate(passages)}
        chunks = [Chunk(p["document_id"], None, index, p["text"])
                  for index, p in enumerate(passages)]
        try:
            vectors = embed_texts([p["text"] for p in passages])
            if installed_digest() != self.digest:
                raise EmbeddingError("Model changed while embedding the evaluation corpus.")
            index_chunks(chunks, vectors, client=self.client)
        except BaseException:
            self.client.close()
            raise

    def rank(self, query: str) -> list[str]:
        vector = embed_text(query)
        points = self.client.query_points(get_settings().qdrant_collection, query=vector,
                                          limit=len(self.passages), with_payload=True).points
        return [self.positions[(point.payload["file_id"], point.payload["chunk_index"])]
                for point in points]

    def close(self):
        self.client.close()


def evaluate(dataset: dict, *, mode: str, ks: list[int], repeats: int,
             diversity: bool = False, generation: bool = False) -> dict:
    if mode not in ("lexical", "dense", "hybrid") or repeats < 2 or not ks or min(ks) < 1:
        raise ValueError("Choose lexical/dense/hybrid, positive K values and at least two repeats")
    passages = dataset["passages"]
    by_id = {p["id"]: p for p in passages}
    documents = {p["id"]: p["document_id"] for p in passages}
    lexical = LexicalRanker(passages)
    started = time.perf_counter()
    dense = DenseRanker(passages) if mode != "lexical" else None
    indexing_ms = (time.perf_counter() - started) * 1000
    rows = []
    warm_times = []
    try:
        for question in dataset["questions"]:
            ranking = []
            timings = []
            consistent = True
            for repeat in range(repeats):
                started = time.perf_counter()
                if mode == "lexical":
                    result = lexical.rank(question["text"])
                elif mode == "dense":
                    result = dense.rank(question["text"])
                else:
                    result = reciprocal_rank_fusion([
                        dense.rank(question["text"]), lexical.rank(question["text"])
                    ])
                if diversity:
                    result = diversify(result, documents)
                timings.append((time.perf_counter() - started) * 1000)
                if repeat == 0:
                    ranking = result
                else:
                    consistent = consistent and result == ranking
                    warm_times.append(timings[-1])
            metrics = {str(k): ranking_metrics(ranking, question["relevance"], k) for k in ks}
            gold_documents = {documents[p] for p in question["relevance"]}
            for k in ks:
                relevant_documents = {documents[p] for p in ranking[:k]
                                      if p in question["relevance"]}
                metrics[str(k)]["document_recall"] = (
                    len(relevant_documents) / len(gold_documents) if gold_documents else None
                )
            row = {"question_id": question["id"], "question": question["text"],
                   "categories": question["categories"], "ranking": ranking,
                   "metrics": metrics, "first_pass_ms": timings[0],
                   "repeat_ms": timings[1:], "ranking_consistent": consistent,
                   "expected_answer": question["expected_answer"], "answer": None,
                   "answer_ms": None, "review": None}
            if generation:
                context = [SearchResult(by_id[p]["text"], documents[p], None,
                                        passages.index(by_id[p]), 0.0) for p in ranking[:max(ks)]]
                started = time.perf_counter()
                row["answer"] = generate(build_prompt(question["text"], context)) if context \
                    else NO_CONTEXT_ANSWER
                row["answer_ms"] = (time.perf_counter() - started) * 1000
            rows.append(row)
        if dense and installed_digest() != dense.digest:
            raise EmbeddingError("Model changed during evaluation; discard this run.")
        categories = sorted({c for q in dataset["questions"] for c in q["categories"]})
        summaries = {}
        for k in ks:
            summaries[str(k)] = summarize([r["metrics"][str(k)] for r in rows])
            document_values = [r["metrics"][str(k)]["document_recall"] for r in rows
                               if r["metrics"][str(k)]["document_recall"] is not None]
            summaries[str(k)]["document_recall"] = (
                sum(document_values) / len(document_values) if document_values else None
            )
        ordered_times = sorted(warm_times)
        return {"dataset": dataset["name"], "mode": mode, "diversity": diversity,
                "k": ks, "vector_size": get_settings().qdrant_vector_size,
                "input_format": input_format_version(),
                "lexical_tokenizer": "unicode-words-preserving-ids",
                "model": get_settings().ollama_embedding_model if dense else None,
                "model_digest": dense.digest if dense else None,
                "generation_model": get_settings().ollama_model if generation else None,
                "repeats": repeats, "passages": len(passages), "indexing_ms": indexing_ms,
                "documents": len(set(documents.values())),
                "latency": {"first_query_ms": rows[0]["first_pass_ms"],
                            "warm_p50_ms": median(warm_times),
                            "warm_p95_ms": ordered_times[math.ceil(len(ordered_times) * .95) - 1],
                            "cold_model_ms": None,
                            "note": (
                                "Corpus embedding warms the model before queries; "
                                "Qdrant is in memory, not a REST server."
                                if dense else "Lexical ranking only; no model or Qdrant calls."
                            )},
                "summary": summaries,
                "by_category": {c: {str(k): summarize([r["metrics"][str(k)] for r in rows
                                                       if c in r["categories"]]) for k in ks}
                                for c in categories},
                "answer_review": {"completed": 0, "accuracy": None,
                                  "abstention_accuracy": None,
                                  "note": "Human review against the rubric is required. "
                                          "Returned context is not proof of answer support."},
                "rows": rows}
    finally:
        if dense:
            dense.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mode", choices=("lexical", "dense", "hybrid"), default="dense")
    parser.add_argument("--k", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--diversify", action="store_true")
    parser.add_argument("--generate", action="store_true",
                        help="Explicitly run local generation and save answers for human review")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.resolve() == args.dataset.resolve():
            raise ValueError("Output must not overwrite the dataset")
        dataset = load_dataset(args.dataset)
        result = evaluate(dataset, mode=args.mode, ks=args.k, repeats=args.repeats,
                          diversity=args.diversify, generation=args.generate)
        result["dataset_sha256"] = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
        result["environment"] = {
            "python": platform.python_version(), "system": platform.system(),
            "architecture": platform.machine(),
            "packages": {name: version(name) for name in ("qdrant-client", "httpx")},
            "git_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "harness_sha256": hashlib.sha256(b"".join(
                (Path(__file__).parent / name).read_bytes()
                for name in ("dataset.py", "metrics.py", "run.py")
            )).hexdigest(),
            "embedding_and_indexing_sha256": hashlib.sha256(b"".join(
                (Path(__file__).parents[1] / "services" / name).read_bytes()
                for name in ("embeddings.py", "indexing.py")
            )).hexdigest(),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"mode": args.mode, "summary": result["summary"],
                          "latency": result["latency"]}, ensure_ascii=False))
    except (ValueError, KeyError, OSError, EmbeddingError, GenerationError, httpx.HTTPError) as exc:
        parser.exit(1, f"Evaluation failed: {exc}\nNo model was downloaded.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
