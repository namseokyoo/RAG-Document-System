#!/usr/bin/env python3
"""Run benchmark questions and log retrieval/answer metrics."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

QUESTIONS_PATH = ROOT_DIR / "tests" / "data" / "benchmark_questions.json"
OUTPUT_PATH = ROOT_DIR / "test_logs" / "benchmark_round0.json"
TOP_K_VECTOR_LOG = 10


def load_questions(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def init_rag(config_path: Path = ROOT_DIR / "config_test.json") -> RAGChain:
    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "request"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
        embedding_api_key=config.get("embedding_api_key", ""),
        distance_function=config.get("chroma_distance_function", "cosine")
    )

    multi_query_num = int(config.get("multi_query_num", 3))
    enable_multi_query = config.get("enable_multi_query", True) and multi_query_num > 0

    rag = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "openai"),
        llm_base_url=config.get("llm_base_url", "https://api.openai.com/v1"),
        llm_model=config.get("llm_model", "gpt-4o-mini"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.3),
        top_k=config.get("top_k", 5),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=config.get("reranker_initial_k", 30),
        enable_synonym_expansion=config.get("enable_synonym_expansion", False),
        enable_multi_query=enable_multi_query,
        multi_query_num=multi_query_num,
        diversity_penalty=config.get("diversity_penalty", 0.3),
        diversity_source_key=config.get("diversity_source_key", "source"),
        enable_file_aggregation=config.get("enable_file_aggregation", True),
        file_aggregation_strategy=config.get("file_aggregation_strategy", "weighted"),
        file_aggregation_top_n=config.get("file_aggregation_top_n", 20),
        file_aggregation_min_chunks=config.get("file_aggregation_min_chunks", 1),
        enable_hybrid_search=config.get("enable_hybrid_search", True),
        hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5)
    )
    return rag


def log_top_vector_results(vector_manager: VectorStoreManager, query: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    results = vector_manager.vectorstore.similarity_search_with_score(query, k=TOP_K_VECTOR_LOG)
    for doc, score in results:
        meta = doc.metadata or {}
        entries.append({
            "source": meta.get("source", ""),
            "page": meta.get("page", meta.get("page_number", "")),
            "score": float(score)
        })
    return entries


def run_benchmark() -> None:
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", "./tiktoken_cache")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    os.environ.setdefault("CHROMA_TELEMETRY", "False")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    questions = load_questions(QUESTIONS_PATH)
    rag = init_rag()
    vector_manager = rag.vectorstore_manager

    results: List[Dict[str, Any]] = []

    print("=" * 100)
    print("Benchmark Run")
    print("=" * 100)

    for idx, q in enumerate(questions, 1):
        question = q["question"]
        print(f"\n[{idx}/{len(questions)}] {question}")
        start = time.time()
        validation = q.get("validation", {})
        constraints = {
            "must_include": validation.get("must_include", []),
            "expected_format": validation.get("format"),
            "category": q.get("category")
        }
        answer = rag.query(question, constraints=constraints)
        elapsed = time.time() - start

        sources = answer.get("sources", [])
        unique_files = len({s.get("file_name", "") for s in sources})
        diversity_ratio = (unique_files / len(sources)) if sources else 0.0

        entry: Dict[str, Any] = {
            "id": q.get("id"),
            "category": q.get("category"),
            "question": question,
            "success": answer.get("success", False),
            "elapsed_sec": elapsed,
            "source_count": len(sources),
            "unique_files": unique_files,
            "diversity_ratio": diversity_ratio,
            "classification": answer.get("classification", {}).get("type", "N/A"),
            "answer_preview": answer.get("answer", "")[:400].replace("\n", " "),
            "vector_top": log_top_vector_results(vector_manager, question),
            "failure_reason": answer.get("failure_reason"),
            "failure_details": answer.get("failure_details"),
            "constraint_evaluation": answer.get("constraint_evaluation")
        }
        results.append(entry)

        print(f"  success={entry['success']} | elapsed={elapsed:.2f}s | sources={entry['source_count']} | diversity={diversity_ratio:.1%}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump({"timestamp": time.time(), "results": results}, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 100)
    print(f"Benchmark results saved to {OUTPUT_PATH}")
    print("=" * 100)


if __name__ == "__main__":
    run_benchmark()
