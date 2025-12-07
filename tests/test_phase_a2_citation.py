#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase A-2 Citation 시스템 테스트
NotebookLM 스타일 인라인 출처 표시 검증
"""

import sys
import os
import io

# UTF-8 인코딩 설정 (Windows 콘솔 호환)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_citation_system():
    """Citation 시스템 간단 테스트"""
    print("="*80)
    print("Phase A-2 Citation 시스템 테스트")
    print("="*80)
    print()

    # VectorStore 초기화
    print("VectorStore 초기화 중...")
    vector_manager = VectorStoreManager(
        embedding_api_type="ollama",
        embedding_base_url="http://localhost:11434",
        embedding_model="mxbai-embed-large:latest"
    )

    # RAGChain 초기화
    print("RAGChain 초기화 중...")
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:latest",
        temperature=0.3,
        top_k=5,
        use_reranker=True,
        enable_hybrid_search=True
    )

    print()
    print("="*80)
    print("테스트 쿼리 실행")
    print("="*80)

    # 테스트 쿼리
    test_queries = [
        "TADF란 무엇인가?",
        "FRET 에너지 전달 효율은?",
        "LG디스플레이는 어떤 회사인가?"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n[{i}/{ len(test_queries)}] 질문: {query}")
        print("-"*80)

        try:
            result = rag_chain.query(query)

            if result["success"]:
                answer = result["answer"]
                sources = result["sources"]

                print(f"\n✅ 답변:")
                print(answer)
                print()

                # Citation 개수 확인
                citation_count = answer.count("[")
                print(f"📎 Citation 개수: {citation_count}개")
                print(f"📚 출처 문서: {len(sources)}개")

                # 출처 표시
                print(f"\n📖 사용된 출처:")
                for j, src in enumerate(sources[:3], 1):
                    print(f"  {j}. {src['file_name']} (p.{src['page_number']}, 점수: {src['similarity_score']})")

            else:
                print(f"❌ 쿼리 실패: {result['answer']}")

        except Exception as e:
            print(f"❌ 테스트 중 오류: {e}")
            import traceback
            traceback.print_exc()

        print()

    print("="*80)
    print("테스트 완료")
    print("="*80)

if __name__ == "__main__":
    test_citation_system()
