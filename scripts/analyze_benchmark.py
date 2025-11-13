#!/usr/bin/env python3
"""Analyze benchmark results and compute summary metrics."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ROUND = ROOT_DIR / "test_logs" / "benchmark_round0.json"
DEFAULT_QUESTIONS = ROOT_DIR / "tests" / "data" / "benchmark_questions.json"
OUTPUT_REPORT = ROOT_DIR / "test_logs" / "benchmark_round0_report.json"


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def must_include_pass(answer_preview: str, must_include: List[str]) -> bool:
    return all(term in answer_preview for term in must_include)


def analyze(results: Dict[str, Any], questions: Dict[str, Any]) -> Dict[str, Any]:
    question_lookup = {q["id"]: q for q in questions}
    categories: Dict[str, List[Dict[str, Any]]] = {}

    summary: Dict[str, Any] = {
        "total": len(results["results"]),
        "success_count": 0,
        "average_diversity": 0.0,
        "average_unique_files": 0.0,
        "category": {},
        "failures": []
    }

    total_diversity = 0.0
    total_unique_files = 0

    for item in results["results"]:
        cat = item.get("category", "unknown")
        categories.setdefault(cat, []).append(item)

        success = item.get("success", False)
        answer_preview = item.get("answer_preview", "")
        qid = item.get("id")
        q_meta = question_lookup.get(qid, {})
        validation = q_meta.get("validation", {}) if q_meta else {}

        must_terms = validation.get("must_include", [])
        format_expected = validation.get("format")

        must_ok = must_include_pass(answer_preview, must_terms) if must_terms else True
        format_ok = True
        if format_expected == "table":
            format_ok = "|" in answer_preview
        elif format_expected == "list":
            format_ok = answer_preview.startswith("-") or "\n-" in answer_preview
        elif format_expected == "safe":
            format_ok = "없" in answer_preview or "정보" in answer_preview

        item_result = success and must_ok and format_ok
        if item_result:
            summary["success_count"] += 1
        else:
            summary["failures"].append({
                "id": qid,
                "category": cat,
                "reason": {
                    "success": success,
                    "must_include": must_ok,
                    "format": format_ok
                },
                "answer_preview": answer_preview
            })

        total_diversity += item.get("diversity_ratio", 0.0)
        total_unique_files += item.get("unique_files", 0)

    count = summary["total"] or 1
    summary["average_diversity"] = total_diversity / count
    summary["average_unique_files"] = total_unique_files / count

    # Category stats
    for cat, items in categories.items():
        cat_success = 0
        for item in items:
            success = item.get("success", False)
            qid = item.get("id")
            q_meta = question_lookup.get(qid, {})
            validation = q_meta.get("validation", {}) if q_meta else {}
            must_terms = validation.get("must_include", [])
            format_expected = validation.get("format")
            answer_preview = item.get("answer_preview", "")

            must_ok = must_include_pass(answer_preview, must_terms) if must_terms else True
            format_ok = True
            if format_expected == "table":
                format_ok = "|" in answer_preview
            elif format_expected == "list":
                format_ok = answer_preview.startswith("-") or "\n-" in answer_preview
            elif format_expected == "safe":
                format_ok = "없" in answer_preview or "정보" in answer_preview

            if success and must_ok and format_ok:
                cat_success += 1
        summary["category"][cat] = {
            "total": len(items),
            "success": cat_success,
            "success_rate": cat_success / len(items) if items else 0.0
        }

    summary["success_rate"] = summary["success_count"] / count
    return summary


def main(round_path: Path, question_path: Path) -> None:
    results = load_json(round_path)
    questions = load_json(question_path)

    report = analyze(results, questions)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_REPORT.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print("Benchmark Analysis Report")
    print("=" * 80)
    print(f"Total questions: {report['total']}")
    print(f"Success count: {report['success_count']} ({report['success_rate']:.1%})")
    print(f"Avg diversity: {report['average_diversity']:.2f}")
    print(f"Avg unique files: {report['average_unique_files']:.2f}")
    for cat, stats in report["category"].items():
        print(f"  - {cat}: {stats['success']}/{stats['total']} ({stats['success_rate']:.1%})")
    if report["failures"]:
        print("\nFailures:")
        for fail in report["failures"]:
            print(f"  [{fail['id']}] category={fail['category']} reason={fail['reason']}")
    print("=" * 80)


if __name__ == "__main__":
    round_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ROUND
    question_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_QUESTIONS
    main(round_path, question_path)
