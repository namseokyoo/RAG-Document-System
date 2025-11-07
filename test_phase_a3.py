#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase A-3 Answer Verification 테스트
Prompt Engineering + Self-Consistency Check
"""

import sys
import os
import io
import time
import json
from datetime import datetime

# UTF-8 인코딩 설정 (Windows 콘솔 호환)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_phase_a3():
    """Phase A-3 테스트: Prompt Engineering + Self-Consistency"""
    print("="*80)
    print("Phase A-3 Answer Verification 테스트")
    print("="*80)
    print()

    # VectorStore 초기화
    print("VectorStore 초기화 중...")
    vector_manager = VectorStoreManager(
        embedding_api_type="ollama",
        embedding_base_url="http://localhost:11434",
        embedding_model="mxbai-embed-large:latest"
    )
    print()

    # 테스트 쿼리 (재생성이 발생하기 쉬운 쿼리)
    test_queries = [
        "TADF란 무엇인가?",
        "FRET 에너지 전달 효율은?",
        "kFRET 값은?",  # 재생성 유발 가능
        "LG디스플레이는 어떤 회사인가?",
        "OLED 효율을 높이는 방법은?"  # 재생성 유발 가능
    ]

    # 테스트 1: Prompt Engineering만 적용 (Self-Consistency 비활성화)
    print("="*80)
    print("테스트 1: Prompt Engineering만 적용 (기존 방식)")
    print("="*80)
    print()

    rag_baseline = RAGChain(
        vectorstore=vector_manager,
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:latest",
        temperature=0.3,
        top_k=5,
        use_reranker=True,
        enable_hybrid_search=True,
        enable_self_consistency=False  # Self-Consistency 비활성화
    )

    baseline_results = []
    baseline_total_time = 0

    for i, query in enumerate(test_queries, 1):
        print(f"\n[{i}/{len(test_queries)}] 질문: {query}")
        print("-"*80)

        start_time = time.time()
        result = rag_baseline.query(query)
        elapsed_time = time.time() - start_time

        baseline_total_time += elapsed_time

        if result["success"]:
            answer = result["answer"]
            sources = result["sources"]

            print(f"\n[OK] 답변 (소요 시간: {elapsed_time:.2f}초):")
            print(answer[:200] + "..." if len(answer) > 200 else answer)
            print()

            # 금지 표현 체크
            forbidden_phrases = [
                "정보를 찾을 수 없습니다",
                "문서에 없습니다",
                "확인할 수 없습니다",
                "제공된 문서에서는 해당 정보를 찾을 수 없습니다"
            ]

            has_forbidden = any(phrase in answer for phrase in forbidden_phrases)

            baseline_results.append({
                "query": query,
                "answer_length": len(answer),
                "elapsed_time": elapsed_time,
                "sources_count": len(sources),
                "has_forbidden_phrase": has_forbidden
            })

            print(f"[INFO] 답변 길이: {len(answer)} chars, 출처: {len(sources)}개")
            if has_forbidden:
                print("[WARN] 금지 표현 사용됨!")

        else:
            print(f"[ERROR] 쿼리 실패: {result['answer']}")
            baseline_results.append({
                "query": query,
                "answer_length": 0,
                "elapsed_time": elapsed_time,
                "sources_count": 0,
                "has_forbidden_phrase": False,
                "error": True
            })

        print()

    # 테스트 2: Prompt Engineering + Self-Consistency 적용
    print("\n")
    print("="*80)
    print("테스트 2: Prompt Engineering + Self-Consistency Check")
    print("="*80)
    print()

    rag_with_sc = RAGChain(
        vectorstore=vector_manager,
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:latest",
        temperature=0.3,
        top_k=5,
        use_reranker=True,
        enable_hybrid_search=True,
        enable_self_consistency=True,  # Self-Consistency 활성화
        self_consistency_n=3  # 3회 생성
    )

    sc_results = []
    sc_total_time = 0

    for i, query in enumerate(test_queries, 1):
        print(f"\n[{i}/{len(test_queries)}] 질문: {query}")
        print("-"*80)

        start_time = time.time()
        result = rag_with_sc.query(query)
        elapsed_time = time.time() - start_time

        sc_total_time += elapsed_time

        if result["success"]:
            answer = result["answer"]
            sources = result["sources"]

            print(f"\n[OK] 답변 (소요 시간: {elapsed_time:.2f}초):")
            print(answer[:200] + "..." if len(answer) > 200 else answer)
            print()

            # 금지 표현 체크
            forbidden_phrases = [
                "정보를 찾을 수 없습니다",
                "문서에 없습니다",
                "확인할 수 없습니다",
                "제공된 문서에서는 해당 정보를 찾을 수 없습니다"
            ]

            has_forbidden = any(phrase in answer for phrase in forbidden_phrases)

            sc_results.append({
                "query": query,
                "answer_length": len(answer),
                "elapsed_time": elapsed_time,
                "sources_count": len(sources),
                "has_forbidden_phrase": has_forbidden
            })

            print(f"[INFO] 답변 길이: {len(answer)} chars, 출처: {len(sources)}개")
            if has_forbidden:
                print("[WARN] 금지 표현 사용됨!")

        else:
            print(f"[ERROR] 쿼리 실패: {result['answer']}")
            sc_results.append({
                "query": query,
                "answer_length": 0,
                "elapsed_time": elapsed_time,
                "sources_count": 0,
                "has_forbidden_phrase": False,
                "error": True
            })

        print()

    # 결과 비교
    print("\n")
    print("="*80)
    print("테스트 결과 비교")
    print("="*80)
    print()

    # 금지 표현 사용 횟수
    baseline_forbidden_count = sum(1 for r in baseline_results if r.get("has_forbidden_phrase", False))
    sc_forbidden_count = sum(1 for r in sc_results if r.get("has_forbidden_phrase", False))

    # 평균 응답 시간
    baseline_avg_time = baseline_total_time / len(test_queries)
    sc_avg_time = sc_total_time / len(test_queries)

    # 평균 답변 길이
    baseline_avg_length = sum(r["answer_length"] for r in baseline_results) / len(baseline_results)
    sc_avg_length = sum(r["answer_length"] for r in sc_results) / len(sc_results)

    print(f"{'지표':<30} | {'Baseline':<15} | {'Self-Consistency':<15} | {'개선':<15}")
    print("-"*80)
    print(f"{'금지 표현 사용 횟수':<30} | {baseline_forbidden_count:<15} | {sc_forbidden_count:<15} | {baseline_forbidden_count - sc_forbidden_count:<15}")
    print(f"{'평균 응답 시간 (초)':<30} | {baseline_avg_time:<15.2f} | {sc_avg_time:<15.2f} | {baseline_avg_time - sc_avg_time:<15.2f}")
    print(f"{'평균 답변 길이 (chars)':<30} | {baseline_avg_length:<15.0f} | {sc_avg_length:<15.0f} | {sc_avg_length - baseline_avg_length:<15.0f}")

    print()
    print("="*80)
    print("Phase A-3 개선 효과:")
    print("="*80)

    # 재생성 빈도 감소 추정
    regeneration_reduction = (baseline_forbidden_count - sc_forbidden_count) / len(test_queries) * 100

    print(f"1. 금지 표현 사용 감소: {baseline_forbidden_count} → {sc_forbidden_count} (-{regeneration_reduction:.1f}%)")
    print(f"2. 응답 시간 변화: {baseline_avg_time:.2f}초 → {sc_avg_time:.2f}초 ({sc_avg_time - baseline_avg_time:+.2f}초)")

    # Self-Consistency는 3회 생성하므로 시간이 증가할 수 있음
    if sc_avg_time > baseline_avg_time:
        overhead = sc_avg_time - baseline_avg_time
        print(f"   [INFO] Self-Consistency 오버헤드: +{overhead:.2f}초")
        print(f"   [INFO] 하지만 재생성 감소로 인한 실제 시간 절감 가능")
    else:
        saved_time = baseline_avg_time - sc_avg_time
        print(f"   [OK] 시간 절감: -{saved_time:.2f}초")

    print(f"3. 답변 품질 (길이 기준): {baseline_avg_length:.0f} → {sc_avg_length:.0f} chars ({sc_avg_length - baseline_avg_length:+.0f})")

    print()
    print("="*80)
    print("테스트 완료!")
    print("="*80)

    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"test_results/phase_a3_{timestamp}.json"

    os.makedirs("test_results", exist_ok=True)

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "baseline": {
                "results": baseline_results,
                "total_time": baseline_total_time,
                "avg_time": baseline_avg_time,
                "forbidden_count": baseline_forbidden_count,
                "avg_length": baseline_avg_length
            },
            "self_consistency": {
                "results": sc_results,
                "total_time": sc_total_time,
                "avg_time": sc_avg_time,
                "forbidden_count": sc_forbidden_count,
                "avg_length": sc_avg_length
            },
            "summary": {
                "regeneration_reduction_pct": regeneration_reduction,
                "time_diff": sc_avg_time - baseline_avg_time,
                "length_diff": sc_avg_length - baseline_avg_length
            }
        }, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {result_file}")

if __name__ == "__main__":
    test_phase_a3()
