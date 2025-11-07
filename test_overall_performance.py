#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""전체 성능 테스트 - Phase D 검증"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_overall_performance():
    print("=" * 80)
    print("전체 성능 테스트 - Phase D (v3.3.0)")
    print("=" * 80)
    print()

    # VectorStore 초기화
    print("[INIT] VectorStore 초기화 중...")
    vectorstore = VectorStoreManager(
        embedding_api_type="ollama",
        embedding_base_url="http://localhost:11434",
        embedding_model="mxbai-embed-large:latest"
    )

    # RAGChain 초기화 (Phase D 설정)
    print("[INIT] RAGChain 초기화 중 (max_tokens=4096)...")
    rag = RAGChain(
        vectorstore=vectorstore,
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:latest",
        temperature=0.3,
        max_tokens=4096,  # Phase D
        top_k=5,
        use_reranker=True,
        enable_hybrid_search=True
    )
    print()

    # 테스트 질문 (다양한 유형)
    test_cases = [
        {
            "category": "구체적 정보 (specific_info)",
            "question": "kFRET 값은?",
            "expected_type": "짧은 답변 (1-2문장)"
        },
        {
            "category": "설명 (general)",
            "question": "TADF의 원리를 설명해줘",
            "expected_type": "여러 문단 설명"
        },
        {
            "category": "번역/요약 (general)",
            "question": "HF-OLED 논문 서론 요약해줘",
            "expected_type": "긴 답변 (토큰 충분)"
        },
        {
            "category": "비교 (comparison)",
            "question": "ACRSA와 DMAC-TRZ 비교해줘",
            "expected_type": "비교 분석"
        },
        {
            "category": "관계 (relationship)",
            "question": "TADF 구조가 효율에 미치는 영향은?",
            "expected_type": "관계 설명"
        },
    ]

    results = []
    total_start = time.time()

    for i, case in enumerate(test_cases, 1):
        print("=" * 80)
        print(f"[{i}/{len(test_cases)}] {case['category']}")
        print("=" * 80)
        print(f"질문: {case['question']}")
        print("-" * 80)

        start_time = time.time()
        result = rag.query(case["question"])
        elapsed = time.time() - start_time

        if result["success"]:
            answer = result["answer"]
            print(answer)
            print()

            # 분석
            has_section = any(
                title in answer
                for title in ["## 답변", "## 상세", "답변:", "상세설명:"]
            )
            citation_count = answer.count("[")
            answer_length = len(answer)

            # 금지 표현 체크
            forbidden = [
                "정보를 찾을 수 없습니다",
                "문서에 없습니다",
                "확인할 수 없습니다",
                "제공된 문서에서는 해당 정보를 찾을 수 없습니다",
                "문서에 명시되어 있지 않습니다"
            ]
            has_forbidden = any(phrase in answer for phrase in forbidden)

            results.append({
                "category": case["category"],
                "question": case["question"],
                "success": True,
                "time": elapsed,
                "length": answer_length,
                "citations": citation_count,
                "has_section": has_section,
                "has_forbidden": has_forbidden
            })

            # 결과 요약
            print("분석:")
            print(f"  - 소요 시간: {elapsed:.2f}초")
            print(f"  - 답변 길이: {answer_length} chars")
            print(f"  - Citation 개수: {citation_count}")
            print(f"  - 섹션 제목: {'[WARN] 있음' if has_section else '[OK] 없음'}")
            print(f"  - 금지 표현: {'[WARN] 발견' if has_forbidden else '[OK] 없음'}")
        else:
            results.append({
                "category": case["category"],
                "question": case["question"],
                "success": False,
                "error": result["answer"]
            })
            print(f"[ERROR] 쿼리 실패: {result['answer']}")

        print()

    total_time = time.time() - total_start

    # 최종 요약
    print("=" * 80)
    print("전체 성능 테스트 결과 요약")
    print("=" * 80)
    print()

    success_count = sum(1 for r in results if r.get("success"))
    section_count = sum(1 for r in results if r.get("has_section", False))
    forbidden_count = sum(1 for r in results if r.get("has_forbidden", False))
    total_citations = sum(r.get("citations", 0) for r in results if r.get("success"))
    avg_time = sum(r.get("time", 0) for r in results if r.get("success")) / max(success_count, 1)

    print(f"총 테스트: {len(test_cases)}개")
    print(f"성공: {success_count}개 ({success_count/len(test_cases)*100:.1f}%)")
    print(f"평균 응답 시간: {avg_time:.2f}초")
    print(f"총 Citation: {total_citations}개")
    print()

    print("Phase D 목표 달성도:")
    print(f"  [OK] max_tokens=4096: 적용됨")
    print(f"  {'[OK]' if section_count == 0 else '[WARN]'} 섹션 제목 제거: {len(test_cases) - section_count}/{len(test_cases)} 성공")
    print(f"  {'[OK]' if forbidden_count == 0 else '[FAIL]'} 금지 표현 제거: {forbidden_count}개 발견")
    print(f"  {'[OK]' if total_citations > 0 else '[FAIL]'} Inline Citation: {total_citations}개")
    print()

    # 카테고리별 분석
    print("카테고리별 분석:")
    for cat in set(r["category"] for r in results):
        cat_results = [r for r in results if r["category"] == cat]
        cat_success = [r for r in cat_results if r.get("success")]
        if cat_success:
            avg_cat_time = sum(r["time"] for r in cat_success) / len(cat_success)
            has_sections = sum(1 for r in cat_success if r.get("has_section"))
            print(f"  - {cat}:")
            print(f"      응답 시간: {avg_cat_time:.2f}초")
            print(f"      섹션 제목: {has_sections}/{len(cat_success)}")

    print()
    print("=" * 80)
    print(f"전체 테스트 완료 (총 {total_time:.2f}초)")
    print("=" * 80)

if __name__ == "__main__":
    test_overall_performance()
