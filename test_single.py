#!/usr/bin/env python
"""단일 질문 테스트 - OpenAI API 키 검증"""
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

# ensure project root on sys.path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_single():
    """단일 질문으로 테스트"""
    print("=" * 80)
    print("단일 질문 테스트 - OpenAI API 검증")
    print("=" * 80)
    
    # 설정 로드
    print(f"\n[설정 로드 중...]")
    config = ConfigManager().get_all()
    print(f"  LLM API Type: {config.get('llm_api_type')}")
    print(f"  LLM Model: {config.get('llm_model')}")
    print(f"  LLM Base URL: {config.get('llm_base_url')}")
    print(f"  LLM API Key: {config.get('llm_api_key', '')[:20]}..." if config.get('llm_api_key') else "  LLM API Key: (없음)")
    print(f"  Temperature: {config.get('temperature')}")
    
    # RAG 초기화
    print(f"\n[RAG 초기화 중...]")
    try:
        vector_manager = VectorStoreManager(
            persist_directory="data/chroma_db",
            embedding_api_type=config.get("embedding_api_type", "ollama"),
            embedding_base_url=config.get("embedding_base_url"),
            embedding_model=config.get("embedding_model"),
            embedding_api_key=config.get("embedding_api_key", "")
        )
        multi_query_num = int(config.get("multi_query_num", 3))
        enable_multi_query = config.get("enable_multi_query", True) and multi_query_num > 0
        
        rag_chain = RAGChain(
            vectorstore=vector_manager.get_vectorstore(),
            llm_api_type=config.get("llm_api_type", "openai"),
            llm_base_url=config.get("llm_base_url"),
            llm_model=config.get("llm_model"),
            llm_api_key=config.get("llm_api_key", ""),
            temperature=config.get("temperature", 0.3),
            top_k=config.get("top_k", 5),
            use_reranker=config.get("use_reranker", True),
            reranker_model=config.get("reranker_model"),
            reranker_initial_k=config.get("reranker_initial_k", 40),
            enable_synonym_expansion=config.get("enable_synonym_expansion", True),
            enable_multi_query=enable_multi_query,
            multi_query_num=multi_query_num
        )
        print("  ✓ 초기화 완료")
    except Exception as e:
        print(f"  ✗ 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 단일 질문 테스트
    test_question = "MIPS(운동성 유도 상분리)란 무엇이며, 수동적 시스템의 상분리와의 주요 차이점은 무엇입니까?"
    
    print(f"\n[테스트 질문]")
    print(f"Q: {test_question}")
    print("-" * 80)
    
    try:
        import time
        start = time.time()
        
        # RAG 응답 생성
        answer_parts = []
        for part in rag_chain.query_stream(test_question, chat_history=[]):
            answer_parts.append(part)
        
        generated_answer = "".join(answer_parts)
        elapsed = time.time() - start
        
        num_docs = len(rag_chain._last_retrieved_docs) if hasattr(rag_chain, '_last_retrieved_docs') else 0
        
        print(f"\n[결과]")
        print(f"응답 시간: {elapsed:.2f}초")
        print(f"검색 문서 수: {num_docs}개")
        print(f"\n생성된 답변:")
        print(generated_answer)
        
        print("\n✓ 테스트 성공!")
        
    except Exception as e:
        print(f"\n✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_single()


