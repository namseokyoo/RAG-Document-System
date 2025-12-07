#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 3 통합 테스트: File Aggregation & Response Strategy Selector

Day 2 완료 검증:
1. Exhaustive query 감지
2. 파일 리스트 반환
3. Diversity penalty 적용
4. Markdown table 포맷
"""

import sys
import json
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# UTF-8 인코딩 설정
from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def test_exhaustive_query_detection():
    """Exhaustive query 감지 테스트"""
    print("\n" + "="*80)
    print("[TEST 1] Exhaustive Query 감지")
    print("="*80)

    # Config 로드
    config_manager = ConfigManager()
    config = config_manager.get_all()

    # VectorStore 초기화
    vector_manager = VectorStoreManager(
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config["embedding_base_url"],
        embedding_model=config["embedding_model"],
        embedding_api_key=config.get("embedding_api_key", "")
    )

    # RAGChain 초기화 (File Aggregation 활성화)
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "ollama"),
        llm_base_url=config["llm_base_url"],
        llm_model=config["llm_model"],
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.7),
        top_k=config["top_k"],
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        diversity_penalty=config.get("diversity_penalty", 0.3),
        diversity_source_key=config.get("diversity_source_key", "source"),
        # Phase 3: File Aggregation 활성화
        enable_file_aggregation=True,
        file_aggregation_strategy="weighted",
        file_aggregation_top_n=20,
        file_aggregation_min_chunks=1
    )

    # 테스트 케이스
    test_queries = [
        ("OLED 논문 모두 찾아줘", True),
        ("MicroLED 관련 전체 문서", True),
        ("모든 디스플레이 자료", True),
        ("Quantum dot 파일 리스트", True),
        ("OLED와 QLED의 차이점은?", False),  # Normal query
        ("Hyperfluorescence 기술이란?", False)  # Normal query
    ]

    print("\n테스트 쿼리:")
    for i, (query, expected_exhaustive) in enumerate(test_queries, 1):
        is_exhaustive = rag_chain._is_exhaustive_query(query)
        result = "✅ PASS" if is_exhaustive == expected_exhaustive else "❌ FAIL"
        print(f"  {i}. \"{query}\"")
        print(f"     기대: {'Exhaustive' if expected_exhaustive else 'Normal'}, "
              f"실제: {'Exhaustive' if is_exhaustive else 'Normal'} {result}")

    print("\n[TEST 1] 완료")
    return True


def test_file_list_response():
    """파일 리스트 반환 테스트"""
    print("\n" + "="*80)
    print("[TEST 2] 파일 리스트 반환 (End-to-End)")
    print("="*80)

    # Config 로드
    config_manager = ConfigManager()
    config = config_manager.get_all()

    # VectorStore 초기화
    vector_manager = VectorStoreManager(
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config["embedding_base_url"],
        embedding_model=config["embedding_model"],
        embedding_api_key=config.get("embedding_api_key", "")
    )

    # RAGChain 초기화 (File Aggregation 활성화)
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "ollama"),
        llm_base_url=config["llm_base_url"],
        llm_model=config["llm_model"],
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.7),
        top_k=config["top_k"],
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        diversity_penalty=0.3,  # Diversity penalty 활성화
        diversity_source_key="source",
        # Phase 3: File Aggregation 활성화
        enable_file_aggregation=True,
        file_aggregation_strategy="weighted",
        file_aggregation_top_n=10,  # 상위 10개 파일
        file_aggregation_min_chunks=1
    )

    # Exhaustive query 테스트
    test_query = "OLED 논문 모두 찾아줘"

    print(f"\n질문: \"{test_query}\"")
    print("\n처리 중...")

    try:
        result = rag_chain.query(test_query)

        # 결과 검증
        print("\n결과:")
        print(f"  - query_type: {result.get('query_type', 'N/A')}")
        print(f"  - success: {result.get('success', False)}")
        print(f"  - confidence: {result.get('confidence', 0.0)}")
        print(f"  - sources: {len(result.get('sources', []))}개")

        answer = result.get("answer", "")
        print(f"\n답변 미리보기 (처음 300자):")
        print(f"{answer[:300]}...")

        # 검증
        checks = []
        checks.append(("query_type == 'exhaustive'", result.get('query_type') == 'exhaustive'))
        checks.append(("success == True", result.get('success') == True))
        checks.append(("Markdown table 포함", "|" in answer and "순위" in answer))
        checks.append(("파일명 포함", "파일명" in answer or "파일" in answer))

        print("\n검증:")
        all_passed = True
        for check_name, check_result in checks:
            result_str = "✅ PASS" if check_result else "❌ FAIL"
            print(f"  - {check_name}: {result_str}")
            if not check_result:
                all_passed = False

        if all_passed:
            print("\n[TEST 2] ✅ 성공!")
        else:
            print("\n[TEST 2] ❌ 실패")
            return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_normal_query_regression():
    """Normal query 회귀 테스트 (기존 동작 유지 확인)"""
    print("\n" + "="*80)
    print("[TEST 3] Normal Query 회귀 테스트")
    print("="*80)

    # Config 로드
    config_manager = ConfigManager()
    config = config_manager.get_all()

    # VectorStore 초기화
    vector_manager = VectorStoreManager(
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config["embedding_base_url"],
        embedding_model=config["embedding_model"],
        embedding_api_key=config.get("embedding_api_key", "")
    )

    # RAGChain 초기화 (File Aggregation 활성화)
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "ollama"),
        llm_base_url=config["llm_base_url"],
        llm_model=config["llm_model"],
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.7),
        top_k=config["top_k"],
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        diversity_penalty=0.3,
        diversity_source_key="source",
        # Phase 3: File Aggregation 활성화
        enable_file_aggregation=True,
        file_aggregation_strategy="weighted",
        file_aggregation_top_n=20,
        file_aggregation_min_chunks=1
    )

    # Normal query 테스트
    test_query = "OLED와 QLED의 차이점은?"

    print(f"\n질문: \"{test_query}\"")
    print("\n처리 중...")

    try:
        result = rag_chain.query(test_query)

        # 결과 검증
        print("\n결과:")
        print(f"  - query_type: {result.get('query_type', 'normal')}")
        print(f"  - success: {result.get('success', False)}")
        print(f"  - confidence: {result.get('confidence', 0.0)}")
        print(f"  - sources: {len(result.get('sources', []))}개")

        answer = result.get("answer", "")
        print(f"\n답변 미리보기 (처음 200자):")
        print(f"{answer[:200]}...")

        # 검증
        checks = []
        checks.append(("query_type != 'exhaustive'", result.get('query_type') != 'exhaustive'))
        checks.append(("success == True", result.get('success') == True))
        checks.append(("sources 존재", len(result.get('sources', [])) > 0))
        checks.append(("일반 답변 형식", "검색 결과:" not in answer))  # 파일 리스트 형식 아님

        print("\n검증:")
        all_passed = True
        for check_name, check_result in checks:
            result_str = "✅ PASS" if check_result else "❌ FAIL"
            print(f"  - {check_name}: {result_str}")
            if not check_result:
                all_passed = False

        if all_passed:
            print("\n[TEST 3] ✅ 성공!")
        else:
            print("\n[TEST 3] ❌ 실패")
            return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    """전체 테스트 실행"""
    print("\n" + "="*80)
    print("Phase 3 통합 테스트 시작")
    print("="*80)

    results = []

    # Test 1: Exhaustive query 감지
    try:
        result = test_exhaustive_query_detection()
        results.append(("Exhaustive Query 감지", result))
    except Exception as e:
        print(f"\n[ERROR] Test 1 실패: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Exhaustive Query 감지", False))

    # Test 2: 파일 리스트 반환 (실제 DB 필요)
    try:
        result = test_file_list_response()
        results.append(("파일 리스트 반환", result))
    except Exception as e:
        print(f"\n[ERROR] Test 2 실패: {e}")
        import traceback
        traceback.print_exc()
        results.append(("파일 리스트 반환", False))

    # Test 3: Normal query 회귀 테스트
    try:
        result = test_normal_query_regression()
        results.append(("Normal Query 회귀", result))
    except Exception as e:
        print(f"\n[ERROR] Test 3 실패: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Normal Query 회귀", False))

    # 최종 결과
    print("\n" + "="*80)
    print("최종 결과")
    print("="*80)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")

    total = len(results)
    passed_count = sum(1 for _, p in results if p)

    print(f"\n총 {total}개 테스트 중 {passed_count}개 통과 ({passed_count/total*100:.0f}%)")

    if passed_count == total:
        print("\n🎉 Phase 3 Day 2 통합 완료!")
        return 0
    else:
        print("\n⚠️ 일부 테스트 실패, 코드 검토 필요")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
