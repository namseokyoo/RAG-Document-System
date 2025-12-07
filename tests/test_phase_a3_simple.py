#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase A-3 간단한 테스트 (Self-Consistency 비활성화)"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def main():
    print("="*80)
    print("Phase A-3 테스트 (Prompt Engineering만 적용)")
    print("="*80)
    print()

    # VectorStore 초기화
    print("VectorStore 초기화 중...")
    vectorstore = VectorStoreManager(
        embedding_api_type="ollama",
        embedding_base_url="http://localhost:11434",
        embedding_model="mxbai-embed-large:latest"
    )
    print()

    # RAGChain 초기화 (Self-Consistency 비활성화 - 메모리 문제 회피)
    print("RAGChain 초기화 중 (Prompt Engineering만 적용)...")
    rag = RAGChain(
        vectorstore=vectorstore,
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:latest",
        temperature=0.3,
        top_k=5,
        use_reranker=True,
        enable_hybrid_search=True,
        enable_self_consistency=False  # Self-Consistency 비활성화
    )
    print()

    # 테스트 질문들
    test_questions = [
        "TADF란 무엇인가?",
        "kFRET 값은?",
        "OLED 효율을 높이는 방법은?"
    ]

    total_time = 0
    results = []

    for i, question in enumerate(test_questions, 1):
        print("="*80)
        print(f"[{i}/{len(test_questions)}] 질문: {question}")
        print("="*80)
        print()

        # 답변 생성
        start_time = time.time()
        result = rag.query(question)
        elapsed_time = time.time() - start_time
        total_time += elapsed_time

        if result["success"]:
            answer = result["answer"]
            sources = result["sources"]

            print("\n답변:")
            print("-"*80)
            print(answer)
            print()

            # 금지 표현 체크
            forbidden_phrases = [
                "정보를 찾을 수 없습니다",
                "문서에 없습니다",
                "확인할 수 없습니다",
                "제공된 문서에서는 해당 정보를 찾을 수 없습니다"
            ]

            has_forbidden = any(phrase in answer for phrase in forbidden_phrases)

            # Citation 체크
            citation_count = answer.count("[")

            print("="*80)
            print("결과:")
            print(f"  - 소요 시간: {elapsed_time:.2f}초")
            print(f"  - 답변 길이: {len(answer)} chars")
            print(f"  - 사용된 출처: {len(sources)}개")
            print(f"  - Citation 개수: {citation_count}개")

            if has_forbidden:
                print(f"  - 금지 표현: [WARN] 사용됨")
            else:
                print(f"  - 금지 표현: [OK] 없음")

            results.append({
                "question": question,
                "success": True,
                "elapsed_time": elapsed_time,
                "answer_length": len(answer),
                "sources_count": len(sources),
                "citation_count": citation_count,
                "has_forbidden": has_forbidden
            })

        else:
            print(f"[ERROR] 쿼리 실패: {result['answer']}")
            results.append({
                "question": question,
                "success": False,
                "elapsed_time": elapsed_time,
                "error": result["answer"]
            })

        print()

    # 전체 요약
    print("\n")
    print("="*80)
    print("테스트 요약")
    print("="*80)

    success_count = sum(1 for r in results if r["success"])
    forbidden_count = sum(1 for r in results if r.get("has_forbidden", False))
    avg_time = total_time / len(test_questions)
    total_citations = sum(r.get("citation_count", 0) for r in results)

    print(f"총 쿼리: {len(test_questions)}개")
    print(f"성공: {success_count}개")
    print(f"금지 표현 사용: {forbidden_count}개")
    print(f"평균 응답 시간: {avg_time:.2f}초")
    print(f"총 Citation 개수: {total_citations}개")

    print()
    print("="*80)
    print("Phase A-3 Prompt Engineering 테스트 완료!")
    print("="*80)

if __name__ == "__main__":
    main()
