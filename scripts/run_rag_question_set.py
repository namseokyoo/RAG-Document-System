#!/usr/bin/env python3
"""Run curated RAG test questions and print summaries."""

import os
import sys
import time
import json
from pathlib import Path
from typing import List, Dict

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


QUESTION_SET: List[Dict[str, str]] = [
    {
        "category": "single_paper",
        "question": "OLED를 이용한 양자 자기장 이미징 연구를 요약해줘.",
        "expectation": "OLED 기반 양자 센싱, 스핀 기반 특징, 논문 중심 요약"
    },
    {
        "category": "single_paper",
        "question": "QLED에서 드룹(droop) 현상을 줄이기 위한 구조적 접근을 설명해줘.",
        "expectation": "콜로이드 양자점 구조 엔지니어링, 안정성 및 드룹 제어"
    },
    {
        "category": "topic_search",
        "question": "MicroLED 웨이퍼 스케일 전사 기술의 최신 동향은?",
        "expectation": "BLAST 등 최신 공정, 여러 문서 활용"
    },
    {
        "category": "topic_search",
        "question": "Perovskite 태양전지에서 시뮬레이션 활용 사례를 알려줘.",
        "expectation": "실험+시뮬레이션 결합 사례, 최소 두 문서 이상"
    },
    {
        "category": "insight",
        "question": "OLED, QLED, MicroLED의 제조 공정 차이를 비교해줘.",
        "expectation": "세 기술 공정 비교, 다문서 인용"
    },
    {
        "category": "exhaustive",
        "question": "MicroLED 웨이퍼 전사 공정을 다루는 모든 논문 목록을 알려줘.",
        "expectation": "파일 리스트 형식, 관련도/청크 수 포함"
    }
]


def init_rag_chain(config_path: str = "config_test.json") -> RAGChain:
    """Load config, initialize VectorStore and RAG chain."""
    with open(config_path, "r", encoding="utf-8") as f:
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
        diversity_penalty=config.get("diversity_penalty", 0.0),
        diversity_source_key=config.get("diversity_source_key", "source"),
        enable_file_aggregation=config.get("enable_file_aggregation", True),
        file_aggregation_strategy=config.get("file_aggregation_strategy", "weighted"),
        file_aggregation_top_n=config.get("file_aggregation_top_n", 20),
        file_aggregation_min_chunks=config.get("file_aggregation_min_chunks", 1),
        enable_hybrid_search=config.get("enable_hybrid_search", True),
        hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5)
    )
    return rag


def run_tests() -> None:
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", "./tiktoken_cache")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    os.environ.setdefault("CHROMA_TELEMETRY", "False")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    rag = init_rag_chain()

    print("=" * 100)
    print("Curated RAG Test Run")
    print("=" * 100)

    results = []
    for idx, item in enumerate(QUESTION_SET, 1):
        question = item["question"]
        print(f"\n[{idx}/{len(QUESTION_SET)}] {question}")
        print(f"  기대사항: {item['expectation']}")

        start = time.time()
        result = rag.query(question)
        elapsed = time.time() - start

        sources = result.get("sources", [])
        unique_files = len({s.get("file_name", "") for s in sources})
        diversity_ratio = (unique_files / len(sources)) if sources else 0.0

        answer_preview = result.get("answer", "")[:400].replace("\n", " ")

        print(f"  성공 여부: {result.get('success', False)}")
        print(f"  소요시간: {elapsed:.2f}s")
        print(f"  출처 수: {len(sources)} / 고유 파일: {unique_files} / 다양성: {diversity_ratio:.1%}")
        print(f"  분류: {result.get('classification', {}).get('type', 'N/A')}")
        print(f"  답변 미리보기: {answer_preview}")

        results.append({
            "question": question,
            "category": item["category"],
            "success": result.get("success", False),
            "elapsed_sec": elapsed,
            "source_count": len(sources),
            "unique_files": unique_files,
            "diversity_ratio": diversity_ratio,
            "classification": result.get("classification", {}).get("type", "N/A"),
            "answer_preview": answer_preview
        })

    output_path = "test_logs/rag_test_round1.json"
    os.makedirs("test_logs", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": time.time(), "results": results}, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 100)
    print(f"Test results saved to {output_path}")
    print("=" * 100)


if __name__ == "__main__":
    run_tests()
