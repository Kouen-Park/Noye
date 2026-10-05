"""Gold metrics and fixture errors must fail independently of model quality."""

import copy
import json
import math

import pytest

from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import diversify, ranking_metrics, reciprocal_rank_fusion, summarize
from app.evaluation.run import DEFAULT_DATASET, LexicalRanker, evaluate, tokenize


def test_metric_values_have_known_denominators():
    metrics = ranking_metrics(["other", "a", "b"], {"a": 2, "b": 1, "c": 1}, 3)
    assert metrics["recall"] == pytest.approx(2 / 3)
    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["mrr"] == .5
    expected = (3 / math.log2(3) + 1 / math.log2(4)) / (
        3 + 1 / math.log2(3) + 1 / math.log2(4)
    )
    assert metrics["ndcg"] == pytest.approx(expected)


def test_precision_at_k_does_not_reward_returning_fewer_results():
    assert ranking_metrics(["a"], {"a": 2}, 5)["precision"] == .2


def test_negative_questions_do_not_inflate_positive_recall():
    negative = ranking_metrics(["wrong"], {}, 5)
    positive = ranking_metrics(["a"], {"a": 2}, 5)
    summary = summarize([negative, positive])
    assert negative["recall"] is None
    assert summary["recall"] == 1.0
    assert summary["negative_returned_context"] == 1.0
    assert ranking_metrics([], {}, 5)["negative_returned_context"] is False


def test_duplicate_predictions_are_rejected_instead_of_double_counted():
    with pytest.raises(ValueError, match="duplicate"):
        ranking_metrics(["a", "a"], {"a": 2}, 5)
    with pytest.raises(ValueError, match="duplicate"):
        reciprocal_rank_fusion([["a", "a"]])


def test_fusion_promotes_agreement_and_has_deterministic_ties():
    assert reciprocal_rank_fusion([["a", "b"], ["b", "c"]])[0] == "b"
    assert reciprocal_rank_fusion([["z"], ["a"]]) == ["a", "z"]


def test_diversity_keeps_one_passage_per_document_before_repeats():
    documents = {"a": "one", "b": "one", "c": "two"}
    assert diversify(["a", "b", "c"], documents) == ["a", "c", "b"]


def test_fixture_covers_all_required_categories_and_has_no_personal_data():
    dataset = load_dataset(DEFAULT_DATASET)
    assert len(dataset["passages"]) == 18
    assert len(dataset["questions"]) == 24
    categories = {c for q in dataset["questions"] for c in q["categories"]}
    assert {"english", "korean", "cross-language", "exact-identifier",
            "negative", "multi-document"} <= categories
    assert sum(q["unanswerable"] for q in dataset["questions"]) == 3


@pytest.mark.parametrize("mutation,match", [
    (lambda d: d["passages"].append(d["passages"][0]), "Duplicate passage"),
    (lambda d: d["questions"][0]["relevance"].update(ghost=2), "unknown passage"),
    (lambda d: d["questions"][0].update(unanswerable=True), "Unanswerable"),
    (lambda d: d["questions"][0]["relevance"].update({"backup-en": 3}), "grades"),
])
def test_invalid_gold_labels_are_rejected(tmp_path, mutation, match):
    dataset = copy.deepcopy(load_dataset(DEFAULT_DATASET))
    mutation(dataset)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(dataset))
    with pytest.raises(ValueError, match=match):
        load_dataset(path)


def test_identifiers_survive_tokenization_and_close_codes_do_not_match():
    assert tokenize("NX-742 와 NX-724") == ["nx-742", "와", "nx-724"]
    ranker = LexicalRanker([
        {"id": "one", "text": "NX-742 means a source change."},
        {"id": "two", "text": "NX-724 means a printer error."},
    ])
    assert ranker.rank("NX-742") == ["one"]


def test_offline_runner_has_no_fabricated_answer_or_cold_model_score(monkeypatch):
    from app.evaluation import run
    def forbidden(*args, **kwargs):
        raise AssertionError("offline mode must not call a model")
    monkeypatch.setattr(run, "embed_text", forbidden)
    monkeypatch.setattr(run, "generate", forbidden)
    result = evaluate(load_dataset(DEFAULT_DATASET), mode="lexical", ks=[1, 5], repeats=2)
    assert result["summary"]["5"]["negatives"] == 3
    assert result["latency"]["cold_model_ms"] is None
    assert result["answer_review"]["accuracy"] is None
    assert all(row["answer"] is None for row in result["rows"])


def test_optional_generation_saves_answers_for_manual_review(monkeypatch):
    from app.evaluation import run
    calls = []
    monkeypatch.setattr(run, "generate", lambda prompt: calls.append(prompt) or "Synthetic answer")
    dataset = load_dataset(DEFAULT_DATASET)
    dataset["questions"] = dataset["questions"][:1]
    result = evaluate(dataset, mode="lexical", ks=[5], repeats=2, generation=True)
    assert calls
    assert result["rows"][0]["answer"] == "Synthetic answer"
    assert result["rows"][0]["review"] is None
