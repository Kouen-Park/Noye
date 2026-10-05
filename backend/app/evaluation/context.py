"""Opt-in local comparison of the production bounded follow-up context."""

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import httpx

from app.config import get_settings
from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import ranking_metrics
from app.evaluation.run import DenseRanker
from app.models.conversations import Message, Role
from app.services.conversation_context import recent_context, retrieval_question
from app.services.embeddings import embed_query, input_format_version
from app.services.generation import build_prompt, generate
from app.services.retrieval import SearchResult


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path(__file__).resolve().parents[2]
                        / "evaluation" / "followups-v1.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    fixture = json.loads(args.cases.read_text())
    corpus_path = args.cases.parent / fixture["corpus"]
    if args.output.resolve() in (args.cases.resolve(), corpus_path.resolve()):
        parser.error("Output must preserve evaluation fixtures")
    corpus = load_dataset(corpus_path)
    settings = get_settings()
    # Unload only on the explicitly configured evaluation runner. No model download.
    response = httpx.post(f"{settings.ollama_base_url}/api/embed", timeout=60,
                          json={"model": settings.ollama_embedding_model,
                                "input": "", "keep_alive": 0})
    response.raise_for_status()
    started = time.perf_counter()
    embed_query(fixture["cases"][0]["question"])
    cold_ms = (time.perf_counter() - started) * 1000
    ranker = DenseRanker(corpus["passages"])
    rows = []
    try:
        for case in fixture["cases"]:
            messages = [Message(str(i), "synthetic", Role(item["role"]), item["content"])
                        for i, item in enumerate(case["history"])]
            for bounded in (False, True):
                started = time.perf_counter()
                query = retrieval_question(case["question"], messages) if bounded \
                    else case["question"]
                history = recent_context(messages) if bounded else ""
                ranking = ranker.rank(query)
                rows.append({"id": case["id"], "bounded": bounded,
                             "question": case["question"], "retrieval_query": query,
                             "history_chars": len(history), "ranking": ranking[:5],
                             "metrics_at_5": ranking_metrics(ranking, case["relevance"], 5),
                             "retrieval_ms": (time.perf_counter() - started) * 1000,
                             "expected_answer": case["expected_answer"],
                             "answer": None, "answer_ms": None, "review": None})
        digest = ranker.digest
    finally:
        ranker.close()
    if args.generate:
        by_id = {p["id"]: p for p in corpus["passages"]}
        for row in rows:
            case = next(case for case in fixture["cases"] if case["id"] == row["id"])
            messages = [Message(str(i), "synthetic", Role(item["role"]), item["content"])
                        for i, item in enumerate(case["history"])]
            context = [SearchResult(by_id[p]["text"], by_id[p]["document_id"], None, i, 0)
                       for i, p in enumerate(row["ranking"])]
            started = time.perf_counter()
            row["answer"] = generate(build_prompt(row["question"], context,
                                      history=recent_context(messages) if row["bounded"] else ""))
            row["answer_ms"] = (time.perf_counter() - started) * 1000
    result = {"name": fixture["name"], "input_format": input_format_version(),
              "context_policy": "recent-user-questions-v1",
              "model_digest": digest, "generation_model": settings.ollama_model,
              "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
              "cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
              "context_sha256": hashlib.sha256(
                  (Path(__file__).parents[1] / "services" / "conversation_context.py").read_bytes()
              ).hexdigest(), "system": platform.platform(),
              "cold_embedding_ms": cold_ms,
              "note": "One explicitly unloaded embedding query. Subsequent queries are warm; "
                      "in-memory Qdrant, not complete API/desktop latency. "
                      "Answer judgments require an explicit reviewer.", "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"cold_embedding_ms": cold_ms,
                      "rows": [{k: row[k] for k in ("id", "bounded", "metrics_at_5",
                                                    "retrieval_ms", "answer_ms")}
                               for row in rows]}))


if __name__ == "__main__":
    main()
