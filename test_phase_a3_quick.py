#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase A-3 빠른 테스트"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def main():
    print("="*80)
    print("Phase A-3 빠른 테스트 (Self-Consistency Check)")
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

    # RAGChain 초기화 (Self-Consistency 활성화)
    print("RAGChain 초기화 중 (Self-Consistency 활성화)...")
    rag = RAGChain(
        vectorstore=vectorstore,
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
    print()

    # 테스트 질문
    question = "TADF란 무엇인가?"

    print("="*80)
    print(f"질문: {question}")
    print("="*80)
    print()

    # 답변 생성
    start_time = time.time()
    result = rag.query(question)
    elapsed_time = time.time() - start_time

    if result["success"]:
        answer = result["answer"]
        sources = result["sources"]

        print("\n답변:")
        print("-"*80)
        print(answer)
        print()

        print("="*80)
        print("테스트 결과:")
        print(f"  - 소요 시간: {elapsed_time:.2f}초")
        print(f"  - 답변 길이: {len(answer)} chars")
        print(f"  - 사용된 출처: {len(sources)}개")

        # 금지 표현 체크
        forbidden_phrases = [
            "정보를 찾을 수 없습니다",
            "문서에 없습니다",
            "확인할 수 없습니다"
        ]

        has_forbidden = any(phrase in answer for phrase in forbidden_phrases)

        if has_forbidden:
            print("  - 금지 표현: [WARN] 사용됨")
        else:
            print("  - 금지 표현: [OK] 없음")

        # Citation 체크
        citation_count = answer.count("[")
        print(f"  - Citation 개수: {citation_count}개")

        print()
        print("="*80)
        print("Phase A-3 테스트 완료!")
        print("="*80)
    else:
        print(f"오류: {result['answer']}")

if __name__ == "__main__":
    main()
