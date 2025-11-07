#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase A-2 Citation 빠른 테스트"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def main():
    print("="*80)
    print("Phase A-2 Citation 테스트")
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

    # RAGChain 초기화
    print("RAGChain 초기화 중...")
    rag = RAGChain(
        vectorstore=vectorstore,
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:latest",
        temperature=0.3,
        top_k=5,
        use_reranker=True,
        enable_hybrid_search=True
    )
    print()

    # 테스트 질문
    question = "TADF란 무엇인가?"

    print("="*80)
    print(f"질문: {question}")
    print("="*80)
    print()

    # 답변 생성
    result = rag.query(question)

    if result["success"]:
        answer = result["answer"]
        sources = result["sources"]

        print("답변:")
        print("-"*80)
        print(answer)
        print()

        # Citation 통계
        citation_count = answer.count("[")
        print("="*80)
        print("Citation 통계:")
        print(f"  - 인라인 Citation 개수: {citation_count}개")
        print(f"  - 사용된 출처: {len(sources)}개")
        print(f"  - Citation 비율: {citation_count}/{len(sources)} = {citation_count/len(sources)*100:.1f}%")
        print()

        # 출처 정보
        print("사용된 출처:")
        for i, src in enumerate(sources, 1):
            print(f"  {i}. {src['file_name']} (p.{src['page_number']}, 점수: {src['similarity_score']})")
        print()

        # Citation 예시 추출
        if citation_count > 0:
            print("Citation 예시:")
            lines = answer.split(". ")
            cited_lines = [line for line in lines if "[" in line]
            for i, line in enumerate(cited_lines[:3], 1):
                print(f"  {i}. {line.strip()}")

        print()
        print("="*80)
        print("테스트 완료!")
        print("="*80)
    else:
        print(f"오류: {result['answer']}")

if __name__ == "__main__":
    main()
