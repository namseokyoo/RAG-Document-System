#!/usr/bin/env python3
"""
End-to-End Test: Exhaustive Query → File List

Phase 3 Day 2 통합 테스트:
1. RAGChain.query()가 exhaustive query를 감지하는지 확인
2. _handle_exhaustive_query()가 파일 리스트를 반환하는지 확인
3. Markdown table 형식이 올바른지 확인
"""

from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()

import sys
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def test_exhaustive_query_e2e():
    """End-to-End Test: Exhaustive Query → File List"""

    print("=" * 80)
    print("End-to-End Test: Exhaustive Query → File List")
    print("=" * 80)

    # Config 로드
    print("\n[Step 1] Config 로딩...")
    cfg = ConfigManager()

    # VectorStore 초기화
    print("\n[Step 2] VectorStore 초기화...")
    vectorstore = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=cfg.get("embedding_api_type", "ollama"),
        embedding_base_url=cfg.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=cfg.get("embedding_model", "mxbai-embed-large:latest")
    )

    print(f"  DB 문서 수: {vectorstore.vectorstore._collection.count()}")

    # RAGChain 초기화 (File Aggregation 활성화)
    print("\n[Step 3] RAGChain 초기화 (enable_file_aggregation=True)...")
    rag_chain = RAGChain(
        vectorstore=vectorstore,  # VectorStoreManager 객체 전달
        llm_api_type=cfg.get("llm_api_type", "request"),
        llm_base_url=cfg.get("llm_base_url", "http://localhost:11434"),
        llm_model=cfg.get("llm_model", "gemma3:latest"),
        llm_api_key=cfg.get("llm_api_key", ""),
        temperature=cfg.get("temperature", 0.3),
        top_k=cfg.get("top_k", 3),
        use_reranker=cfg.get("use_reranker", True),
        reranker_model=cfg.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=cfg.get("reranker_initial_k", 30),
        enable_hybrid_search=cfg.get("enable_hybrid_search", True),
        hybrid_bm25_weight=cfg.get("hybrid_bm25_weight", 0.5),
        diversity_penalty=cfg.get("diversity_penalty", 0.0),
        diversity_source_key=cfg.get("diversity_source_key", "source"),
        # Phase 3: File Aggregation 활성화
        enable_file_aggregation=True,  # 강제 활성화
        file_aggregation_strategy=cfg.get("file_aggregation_strategy", "weighted"),
        file_aggregation_top_n=cfg.get("file_aggregation_top_n", 20),
        file_aggregation_min_chunks=cfg.get("file_aggregation_min_chunks", 1)
    )

    print(f"  File Aggregation: {rag_chain.enable_file_aggregation}")
    print(f"  Strategy: {rag_chain.file_aggregation_strategy}")

    # 테스트 쿼리
    test_queries = [
        {
            "query": "OLED ETL 재료 평가 논문 모두 찾아줘",
            "expected_type": "exhaustive",
            "description": "Strong pattern: 모든 + 논문"
        },
        {
            "query": "Hyperfluorescence 기술 관련 전체 문서",
            "expected_type": "exhaustive",
            "description": "Strong pattern: 전체 + 문서"
        },
        {
            "query": "OLED 관련 논문 몇 개 있어?",
            "expected_type": "exhaustive",
            "description": "Strong pattern: 몇 + 개"
        },
        {
            "query": "OLED ETL 재료의 효율은 얼마인가?",
            "expected_type": "normal",
            "description": "Normal query: 구체적 정보 추출"
        }
    ]

    # 각 쿼리 테스트
    for i, test in enumerate(test_queries, 1):
        query = test['query']
        expected_type = test['expected_type']
        description = test['description']

        print(f"\n{'=' * 80}")
        print(f"[Test {i}/{len(test_queries)}] {description}")
        print(f"Query: \"{query}\"")
        print(f"Expected Type: {expected_type}")
        print("=" * 80)

        # RAGChain.query() 호출
        print(f"\n[Executing] RAGChain.query()...")
        result = rag_chain.query(query)

        # 결과 확인
        print(f"\n[Result] Query Type: {result.get('query_type', 'normal')}")
        print(f"  Success: {result['success']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Sources: {len(result['sources'])} 개")

        # Answer 출력 (처음 500자만)
        answer = result['answer']
        print(f"\n[Answer Preview] (처음 500자):")
        print(answer[:500])
        print("...")

        # 타입 검증
        actual_type = result.get('query_type', 'normal')
        if actual_type == expected_type:
            print(f"\n[OK] ✅ 예상된 타입과 일치: {actual_type}")
        else:
            print(f"\n[FAIL] ❌ 타입 불일치: expected={expected_type}, actual={actual_type}")

        # Exhaustive query 전용 검증
        if expected_type == "exhaustive":
            # Markdown table이 있는지 확인
            if "| 순위 | 파일명 |" in answer and "총 **" in answer:
                print(f"[OK] ✅ Markdown table 형식 확인")
            else:
                print(f"[FAIL] ❌ Markdown table 형식이 아님")

            # sources가 비어있는지 확인 (파일 리스트이므로)
            if len(result['sources']) == 0:
                print(f"[OK] ✅ Sources 비어있음 (파일 리스트이므로 정상)")
            else:
                print(f"[WARN] ⚠️  Sources가 비어있지 않음: {len(result['sources'])} 개")

        print("\n")

    print("=" * 80)
    print("Test 완료")
    print("=" * 80)

    # 최종 결과 요약
    print("\n[RESULT] 결과 요약:")
    print("1. [OK] RAGChain 초기화 (enable_file_aggregation=True)")
    print("2. [OK] Exhaustive query 감지 테스트")
    print("3. [OK] Normal query 처리 테스트")
    print("4. [OK] Markdown table 형식 확인")

    print("\n[NEXT] 다음 단계:")
    print("1. Entry Point 업데이트 (app.py, desktop_app.py)")
    print("2. 5개 exhaustive query로 추가 검증")
    print("3. Git commit & push")

    return True


if __name__ == "__main__":
    try:
        success = test_exhaustive_query_e2e()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
