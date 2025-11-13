#!/usr/bin/env python3
"""Diagnose retrieval results for representative queries."""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.vector_store import VectorStoreManager

DIAG_QUERIES: List[str] = [
    "OLED를 이용한 양자 자기장 이미징 연구를 요약해줘.",
    "QLED에서 드룹(droop) 현상을 줄이기 위한 구조적 접근을 설명해줘.",
    "MicroLED 웨이퍼 스케일 전사 기술의 최신 동향은?",
    "Perovskite 태양전지에서 시뮬레이션 활용 사례를 알려줘.",
    "Graphene 기반 THz 안테나 설계 방법을 정리해줘.",
    "VR/AR 디스플레이용 스테레오 데이터베이스의 특징을 알려줘."
]


def load_vector_manager(config_path: str = "config_test.json") -> VectorStoreManager:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "request"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
        embedding_api_key=config.get("embedding_api_key", ""),
        distance_function=config.get("chroma_distance_function", "cosine")
    )
    return manager


def summarize_results(label: str, tuples: List[tuple], limit: int = 5) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for doc, score in tuples[:limit]:
        meta = doc.metadata or {}
        summary.append({
            "label": label,
            "source": meta.get("source", ""),
            "file_name": meta.get("file_name", meta.get("source", "")),
            "page": meta.get("page", meta.get("page_number", "")),
            "category": meta.get("category", ""),
            "score": float(score),
            "preview": doc.page_content[:180].replace("\n", " ")
        })
    return summary


def run_diagnosis() -> None:
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", "./tiktoken_cache")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    os.environ.setdefault("CHROMA_TELEMETRY", "False")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    manager = load_vector_manager()

    results: Dict[str, Any] = {
        "timestamp": time.time(),
        "queries": []
    }

    for query in DIAG_QUERIES:
        print("\n" + "=" * 100)
        print(f"Query: {query}")
        print("=" * 100)

        vector_only = manager.vectorstore.similarity_search_with_score(query, k=10)
        print("[Vector Top 5]")
        for idx, (doc, score) in enumerate(vector_only[:5], 1):
            meta = doc.metadata or {}
            print(f" {idx}. {meta.get('source', '')} | score={score:.4f} | page={meta.get('page_number', meta.get('page', ''))}")

        bm25_only = []
        if hasattr(manager, "_bm25_only_search"):
            try:
                bm25_only = manager._bm25_only_search(query, top_k=5)  # type: ignore[attr-defined]
                print("[BM25 Top 5]")
                for idx, (doc, score) in enumerate(bm25_only[:5], 1):
                    meta = doc.metadata or {}
                    print(f" {idx}. {meta.get('source', '')} | score={score:.4f} | page={meta.get('page_number', meta.get('page', ''))}")
            except Exception as exc:  # pragma: no cover - diagnostic output
                print(f"[WARN] BM25 diagnostic failed: {exc}")

        hybrid = manager.similarity_search_hybrid(query, initial_k=40, top_k=5)
        print("[Hybrid Top 5]")
        for idx, (doc, score) in enumerate(hybrid[:5], 1):
            meta = doc.metadata or {}
            print(f" {idx}. {meta.get('source', '')} | score={score:.4f} | page={meta.get('page_number', meta.get('page', ''))}")

        entry = {
            "query": query,
            "vector_top": summarize_results("vector", vector_only),
            "bm25_top": summarize_results("bm25", bm25_only) if bm25_only else [],
            "hybrid_top": summarize_results("hybrid", hybrid)
        }
        results["queries"].append(entry)

    os.makedirs("test_logs", exist_ok=True)
    output_path = Path("test_logs") / "retrieval_diagnosis.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 100)
    print(f"Diagnosis results saved to {output_path}")
    print("=" * 100)


if __name__ == "__main__":
    run_diagnosis()

