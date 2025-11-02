#!/usr/bin/env python
"""빠른 성능 테스트"""
import sys
import os

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
import time

def quick_test():
    print("=" * 60)
    print("RAG 시스템 빠른 성능 테스트")
    print("=" * 60)
    
    # 설정 로드
    config = ConfigManager().get_all()
    
    # 먼저 임베딩된 문서 목록 확인
    print(f"\n[임베딩된 문서 확인]")
    try:
        vector_manager = VectorStoreManager(
            persist_directory="data/chroma_db",
            embedding_api_type=config.get("embedding_api_type", "ollama"),
            embedding_base_url=config.get("embedding_base_url"),
            embedding_model=config.get("embedding_model"),
        )
        
        docs = vector_manager.get_documents_list()
        if docs:
            print(f"  총 {len(docs)}개 문서 임베딩됨:")
            for i, doc in enumerate(docs, 1):
                print(f"  {i}. {doc['file_name']} ({doc['file_type']}) - {doc['chunk_count']}개 청크")
        else:
            print("  ⚠ 경고: 임베딩된 문서가 없습니다!")
            print("  데스크탑 앱에서 문서를 업로드한 후 테스트하세요.")
            return
    except Exception as e:
        print(f"  ✗ 문서 목록 조회 실패: {e}")
        return
    
    print("\n" + "=" * 60)
    
    print(f"\n[설정 확인]")
    print(f"  LLM: {config['llm_model']}")
    print(f"  임베딩: {config['embedding_model']}")
    print(f"  청크 크기: {config['chunk_size']}")
    print(f"  Top K: {config['top_k']}")
    print(f"  Reranker: {config['use_reranker']} ({config.get('reranker_model', 'N/A')})")
    
    # RAG Chain 초기화
    print(f"\n[RAG Chain 초기화 중...]")
    try:
        multi_query_num = int(config.get("multi_query_num", 3))
        enable_multi_query = config.get("enable_multi_query", True) and multi_query_num > 0
        rag_chain = RAGChain(
            vectorstore=vector_manager.get_vectorstore(),
            llm_api_type=config.get("llm_api_type", "ollama"),
            llm_base_url=config.get("llm_base_url"),
            llm_model=config.get("llm_model"),
            llm_api_key=config.get("llm_api_key", ""),
            temperature=config.get("temperature", 0.7),
            top_k=config.get("top_k", 3),
            use_reranker=config.get("use_reranker", True),
            reranker_model=config.get("reranker_model"),
            reranker_initial_k=config.get("reranker_initial_k", 20),
            enable_synonym_expansion=config.get("enable_synonym_expansion", True),
            enable_multi_query=enable_multi_query,
            multi_query_num=multi_query_num
        )
        print("  ✓ RAG Chain 초기화 완료")
    except Exception as e:
        print(f"  ✗ RAG Chain 초기화 실패: {e}")
        return
    
    # 테스트 질문 (reference_result.json 샘플)
    test_questions = [
        "MIPS(운동성 유도 상분리)란 무엇이며, 수동적 시스템의 상분리와의 주요 차이점은 무엇입니까?",
        "DC(직류) 마그노닉 결정(magnonic crystal)이 스핀파 스펙트럼에 미치는 영향은 무엇이며, 밴드 갭의 크기는 무엇에 비례합니까?",
        "X-ray 단층 촬영 재구성을 위한 베이지안(Bayesian) 방법에서 '프라이어(prior)'의 역할은 무엇입니까?",
    ]
    
    print(f"\n[테스트 시작 ({len(test_questions)}개 질문)]")
    print("=" * 60)
    
    results = []
    for i, question in enumerate(test_questions, 1):
        print(f"\n질문 {i}: {question}")
        print("-" * 60)
        
        start = time.time()
        try:
            # query_stream 사용 (스트리밍 방식)
            answer_parts = []
            for part in rag_chain.query_stream(question, chat_history=[]):
                answer_parts.append(part)
            answer = "".join(answer_parts)
            
            elapsed = time.time() - start
            
            print(f"응답 시간: {elapsed:.2f}초")
            print(f"검색 문서 수: {len(rag_chain._last_retrieved_docs)}개")
            print(f"\n답변:\n{answer[:200]}...")
            
            results.append({
                "question": question,
                "time": elapsed,
                "docs": len(rag_chain._last_retrieved_docs)
            })
        except Exception as e:
            print(f"오류 발생: {e}")
            results.append({
                "question": question,
                "error": str(e)
            })
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("[테스트 결과 요약]")
    print("=" * 60)
    
    if results:
        successful = [r for r in results if 'time' in r]
        if successful:
            avg_time = sum(r['time'] for r in successful) / len(successful)
            print(f"평균 응답 시간: {avg_time:.2f}초")
            print(f"성공한 질문: {len(successful)}/{len(results)}")

if __name__ == "__main__":
    quick_test()

