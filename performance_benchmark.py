#!/usr/bin/env python3
"""
Phase 3 성능 벤치마킹
Normal Query vs Exhaustive Query 성능 비교
"""

import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json
import time
from datetime import datetime
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def load_config():
    """Config 로드"""
    with open('config_test.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def initialize_rag(config):
    """RAG Chain 초기화"""
    print(f"\n[초기화] VectorStore 로드 중...")
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "request"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
        distance_function=config.get("chroma_distance_function", "cosine")
    )

    print(f"[초기화] RAG Chain 로드 중...")
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
        enable_file_aggregation=config.get("enable_file_aggregation", False),
        file_aggregation_strategy=config.get("file_aggregation_strategy", "weighted"),
        file_aggregation_top_n=config.get("file_aggregation_top_n", 20),
        file_aggregation_min_chunks=config.get("file_aggregation_min_chunks", 1),
        enable_hybrid_search=config.get("enable_hybrid_search", True),
        hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5)
    )

    return rag


def run_benchmark_test(rag, query, query_type, iterations=3):
    """개별 쿼리 벤치마크"""
    elapsed_times = []
    results_list = []

    for i in range(iterations):
        start = time.time()
        result = rag.query(query)
        elapsed = time.time() - start

        elapsed_times.append(elapsed)
        results_list.append(result)

    avg_time = sum(elapsed_times) / len(elapsed_times)
    min_time = min(elapsed_times)
    max_time = max(elapsed_times)

    # 첫 번째 결과로 통계 수집
    first_result = results_list[0]

    return {
        "query": query,
        "query_type": query_type,
        "iterations": iterations,
        "avg_time": avg_time,
        "min_time": min_time,
        "max_time": max_time,
        "times": elapsed_times,
        "success": first_result.get("success", False),
        "sources_count": len(first_result.get("sources", [])),
        "answer_length": len(first_result.get("answer", "")),
        "is_file_list": "|" in first_result.get("answer", "") and "순위" in first_result.get("answer", "")
    }


def main():
    """메인 벤치마크 함수"""
    print("="*80)
    print("Phase 3 성능 벤치마킹")
    print("="*80)
    print(f"\n실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Config 로드
    config = load_config()
    print(f"\n[Config]")
    print(f"  diversity_penalty: {config.get('diversity_penalty')}")
    print(f"  enable_file_aggregation: {config.get('enable_file_aggregation')}")
    print(f"  LLM: {config.get('llm_model')}")
    print(f"  Reranker: {config.get('reranker_model')}")

    # RAG 초기화
    rag = initialize_rag(config)
    print(f"✓ 초기화 완료\n")

    # 테스트 쿼리 정의
    test_queries = [
        # Normal Queries (일반 RAG)
        {
            "query": "OLED란 무엇인가?",
            "type": "normal",
            "description": "Simple 정의 질문"
        },
        {
            "query": "TADF의 효율은?",
            "type": "normal",
            "description": "Simple 수치 질문"
        },
        {
            "query": "OLED의 발광 원리는?",
            "type": "normal",
            "description": "Normal 원리 설명"
        },
        {
            "query": "Hyperfluorescence 기술이란?",
            "type": "normal",
            "description": "Normal 기술 개념"
        },
        {
            "query": "OLED와 QLED의 차이는?",
            "type": "normal",
            "description": "Complex 비교 질문"
        },

        # Exhaustive Queries (파일 리스트)
        {
            "query": "모든 OLED 논문을 찾아줘",
            "type": "exhaustive",
            "description": "Exhaustive 파일 검색"
        },
        {
            "query": "전체 OLED 관련 문서 리스트",
            "type": "exhaustive",
            "description": "Exhaustive 문서 리스트"
        },
        {
            "query": "Hyperfluorescence에 대한 모든 자료",
            "type": "exhaustive",
            "description": "Exhaustive 특정 주제"
        }
    ]

    # 벤치마크 실행
    print("="*80)
    print("벤치마크 실행 (각 쿼리당 3회 반복)")
    print("="*80)

    results = []

    for idx, test in enumerate(test_queries, 1):
        print(f"\n[{idx}/{len(test_queries)}] {test['description']}")
        print(f"  쿼리: {test['query']}")
        print(f"  타입: {test['type']}")

        result = run_benchmark_test(rag, test['query'], test['type'], iterations=3)
        results.append(result)

        print(f"  평균 시간: {result['avg_time']:.2f}초")
        print(f"  범위: {result['min_time']:.2f}초 ~ {result['max_time']:.2f}초")
        print(f"  출처 수: {result['sources_count']}개")
        if result['is_file_list']:
            print(f"  응답 형식: 파일 리스트 ✓")
        else:
            print(f"  응답 형식: 일반 답변")

    # 결과 분석
    print("\n" + "="*80)
    print("결과 분석")
    print("="*80)

    normal_results = [r for r in results if r['query_type'] == 'normal']
    exhaustive_results = [r for r in results if r['query_type'] == 'exhaustive']

    if normal_results:
        avg_normal_time = sum(r['avg_time'] for r in normal_results) / len(normal_results)
        print(f"\n[Normal Query 평균]")
        print(f"  평균 응답 시간: {avg_normal_time:.2f}초")
        print(f"  평균 출처 수: {sum(r['sources_count'] for r in normal_results) / len(normal_results):.1f}개")
        print(f"  평균 답변 길이: {sum(r['answer_length'] for r in normal_results) / len(normal_results):.0f}자")

    if exhaustive_results:
        avg_exhaustive_time = sum(r['avg_time'] for r in exhaustive_results) / len(exhaustive_results)
        file_list_count = sum(1 for r in exhaustive_results if r['is_file_list'])
        print(f"\n[Exhaustive Query 평균]")
        print(f"  평균 응답 시간: {avg_exhaustive_time:.2f}초")
        print(f"  파일 리스트 형식: {file_list_count}/{len(exhaustive_results)}개")
        print(f"  평균 답변 길이: {sum(r['answer_length'] for r in exhaustive_results) / len(exhaustive_results):.0f}자")

        if normal_results:
            speedup = avg_exhaustive_time / avg_normal_time
            print(f"\n[비교]")
            print(f"  Exhaustive vs Normal: {speedup:.2f}배 ({avg_exhaustive_time - avg_normal_time:+.2f}초)")

    # 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "diversity_penalty": config.get('diversity_penalty'),
            "enable_file_aggregation": config.get('enable_file_aggregation'),
            "llm_model": config.get('llm_model'),
            "reranker_model": config.get('reranker_model')
        },
        "summary": {
            "total_queries": len(results),
            "normal_queries": len(normal_results),
            "exhaustive_queries": len(exhaustive_results),
            "avg_normal_time": avg_normal_time if normal_results else None,
            "avg_exhaustive_time": avg_exhaustive_time if exhaustive_results else None
        },
        "detailed_results": results
    }

    output_file = f"performance_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_file}")
    print("\n" + "="*80)
    print("벤치마크 완료")
    print("="*80)


if __name__ == "__main__":
    main()
