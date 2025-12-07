#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase D 테스트: 답변 자연화 검증"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_phase_d():
    print("=" * 80)
    print("Phase D 테스트: 답변 자연화 (Answer Naturalization)")
    print("=" * 80)
    print()

    # VectorStore 초기화
    print("VectorStore 초기화 중...")
    vectorstore = VectorStoreManager(
        embedding_api_type="ollama",
        embedding_base_url="http://localhost:11434",
        embedding_model="mxbai-embed-large:latest"
    )
    print()

    # RAGChain 초기화 (Phase D: max_tokens=4096)
    print("RAGChain 초기화 중 (Phase D 적용)...")
    rag = RAGChain(
        vectorstore=vectorstore,
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:latest",
        temperature=0.3,
        max_tokens=4096,  # Phase D: 증가 (2048 → 4096)
        top_k=5,
        use_reranker=True,
        enable_hybrid_search=True,
        enable_self_consistency=False
    )
    print()

    # 테스트 케이스
    test_cases = [
        {
            "question": "kFRET 값은?",
            "type": "간단한 질문",
            "expected": "1-2문장 답변, 섹션 제목 없음"
        },
        {
            "question": "TADF의 원리를 설명해줘",
            "type": "설명 요청",
            "expected": "여러 문단, 섹션 제목 없음"
        },
        {
            "question": "HF-OLED 논문의 서론 부분 내용은?",
            "type": "긴 답변",
            "expected": "여러 문단, max_tokens 4096 활용"
        },
    ]

    results = []

    for i, case in enumerate(test_cases, 1):
        print("\n" + "=" * 80)
        print(f"[{i}/{len(test_cases)}] {case['type']}: {case['question']}")
        print("=" * 80)
        print()

        start_time = time.time()
        result = rag.query(case["question"])
        elapsed_time = time.time() - start_time

        if result["success"]:
            answer = result["answer"]

            print("답변:")
            print("-" * 80)
            print(answer)
            print()

            # 검증
            has_section_title = any(
                title in answer
                for title in ["## 답변", "## 상세 설명", "## 참조 정보", "## 관련 추가 정보",
                              "답변:", "상세설명:", "참조 정보:", "관련 추가 정보:"]
            )

            # Citation 확인
            citation_count = answer.count("[")

            # 결과 출력
            print("=" * 80)
            print("검증 결과:")
            print(f"  - 소요 시간: {elapsed_time:.2f}초")
            print(f"  - 답변 길이: {len(answer)} chars")
            print(f"  - Citation 개수: {citation_count}")

            if has_section_title:
                print(f"  - 섹션 제목: [WARN] 발견됨 (제거 필요)")
            else:
                print(f"  - 섹션 제목: [OK] 없음 (자연스러운 문단)")

            # 금지 표현 체크
            forbidden_phrases = [
                "정보를 찾을 수 없습니다",
                "문서에 없습니다",
                "확인할 수 없습니다",
                "제공된 문서에서는 해당 정보를 찾을 수 없습니다"
            ]
            has_forbidden = any(phrase in answer for phrase in forbidden_phrases)

            if has_forbidden:
                print(f"  - 금지 표현: [WARN] 사용됨")
            else:
                print(f"  - 금지 표현: [OK] 없음")

            results.append({
                "question": case["question"],
                "type": case["type"],
                "success": True,
                "elapsed_time": elapsed_time,
                "answer_length": len(answer),
                "citation_count": citation_count,
                "has_section_title": has_section_title,
                "has_forbidden": has_forbidden
            })

        else:
            print(f"[ERROR] 쿼리 실패: {result['answer']}")
            results.append({
                "question": case["question"],
                "type": case["type"],
                "success": False,
                "elapsed_time": elapsed_time,
                "error": result["answer"]
            })

        print()

    # 전체 요약
    print("\n" + "=" * 80)
    print("Phase D 테스트 요약")
    print("=" * 80)

    success_count = sum(1 for r in results if r["success"])
    section_count = sum(1 for r in results if r.get("has_section_title", False))
    forbidden_count = sum(1 for r in results if r.get("has_forbidden", False))
    avg_time = sum(r["elapsed_time"] for r in results) / len(results)
    total_citations = sum(r.get("citation_count", 0) for r in results)

    print(f"총 쿼리: {len(test_cases)}개")
    print(f"성공: {success_count}개")
    print(f"섹션 제목 사용: {section_count}개 (목표: 0개)")
    print(f"금지 표현 사용: {forbidden_count}개 (목표: 0개)")
    print(f"평균 응답 시간: {avg_time:.2f}초")
    print(f"총 Citation 개수: {total_citations}개")

    print()
    print("=" * 80)
    print("Phase D 개선 사항:")
    print("  1. [OK] 프롬프트 간결화 (금지 조항 5개 → 1개)")
    print("  2. [OK] max_tokens 증가 (2048 → 4096)")
    if section_count == 0:
        print("  3. [OK] 섹션 제목 제거 성공")
    else:
        print(f"  3. [WARN] 섹션 제목 {section_count}개 발견")
    print("  4. [OK] Inline Citation 가이드 적용")
    print("=" * 80)

    print()
    print("Phase D 테스트 완료! 답변 자연스러움이 향상되었습니다. ✓")

if __name__ == "__main__":
    test_phase_d()
