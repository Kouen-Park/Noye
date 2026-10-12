"""Apply explicit rubric reviews bound to the exact generated answer text."""

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean


def answer_hash(answer: str) -> str:
    return hashlib.sha256(answer.encode()).hexdigest()


def apply_reviews(report: dict, reviews: dict) -> dict:
    if reviews["dataset_sha256"] != report["dataset_sha256"]:
        raise ValueError("Review dataset hash does not match")
    if not reviews.get("reviewer"):
        raise ValueError("An identified reviewer is required")
    by_id = {row["question_id"]: row for row in report["rows"]}
    if set(reviews["rows"]) - set(by_id):
        raise ValueError("Review names an unknown question")
    for question_id, review in reviews["rows"].items():
        row = by_id[question_id]
        if row["answer"] is None or review["answer_sha256"] != answer_hash(row["answer"]):
            raise ValueError("Review must match the exact generated answer")
        if not review.get("note") or any(type(review.get(key)) is not bool
                                        for key in ("correct", "faithful", "abstained")):
            raise ValueError("Review needs boolean judgments and a rationale")
        row["review"] = review
    completed = [row for row in report["rows"] if row["review"]]
    negatives = [row for row in completed if "negative" in row["categories"]]
    report["answer_review"] = {
        "reviewer": reviews["reviewer"], "completed": len(completed), "total": len(by_id),
        "accuracy": mean(row["review"]["correct"] for row in completed) if completed else None,
        "faithfulness": mean(row["review"]["faithful"] for row in completed) if completed else None,
        "abstention_accuracy": mean(row["review"]["abstained"] for row in negatives)
        if negatives else None,
        "note": "Explicit reviewer judgments against the dataset rubric; "
                "not an automatic LLM judge.",
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in (args.report.resolve(), args.reviews.resolve()):
        parser.error("Output must preserve the original report and reviews")
    result = apply_reviews(json.loads(args.report.read_text()),
                           json.loads(args.reviews.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["answer_review"]))


if __name__ == "__main__":
    main()
