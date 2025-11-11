"""
빠른 성능 체크 스크립트
"""

import json
import sys
import os

# 환경 변수 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_question(question, rag_chain, vector_store_manager):
    """단일 질문 테스트"""
    print(f"\n{'='*80}")
    print(f"질문: {question}")
    print(f"{'='*80}")

    # 1. 직접 검색 테스트
    print("\n[1단계] 초기 유사도 검색...")
    try:
        docs = vector_store_manager.vectorstore.similarity_search_with_score(
            question, k=10
        )
        print(f"검색된 문서: {len(docs)}개")

        if docs:
            print("\n상위 3개 문서:")
            for i, (doc, score) in enumerate(docs[:3], 1):
                print(f"  [{i}] 점수: {score:.4f} | {doc.metadata.get('source', 'N/A')} p.{doc.metadata.get('page_number', 'N/A')}")
                print(f"      내용: {doc.page_content[:80]}...")
    except Exception as e:
        print(f"검색 오류: {e}")

    # 2. RAG 체인 실행
    print("\n[2단계] RAG 체인 실행...")
    try:
        # question_classifier 사용 확인
        if hasattr(rag_chain, 'question_classifier') and rag_chain.question_classifier:
            classification = rag_chain.question_classifier.classify(question)
            print(f"\n질문 분류:")
            print(f"  유형: {classification['type']}")
            print(f"  신뢰도: {classification['confidence']:.0%}")
            print(f"  방법: {classification['method']}")
            print(f"  Multi-Query: {classification['multi_query']}")
            print(f"  Max Results: {classification['max_results']}")

        # RAGChain의 query 메서드 사용
        response = rag_chain.query(
            question=question,
            chat_history=[]
        )

        answer = response.get('answer', '')
        context_docs = rag_chain._last_retrieved_docs  # 검색된 문서들

        print(f"\n답변 길이: {len(answer)} 글자")
        print(f"사용된 컨텍스트: {len(context_docs)}개 문서")

        print(f"\n답변:\n{answer}")

        if context_docs:
            print(f"\n사용된 컨텍스트 문서:")
            for i, doc in enumerate(context_docs[:5], 1):
                score = doc.metadata.get('reranker_score', 'N/A')
                print(f"  [{i}] {doc.metadata.get('source', 'N/A')} p.{doc.metadata.get('page_number', 'N/A')} | Score: {score}")

    except Exception as e:
        print(f"RAG 체인 오류: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("빠른 성능 체크 시작...\n")

    # 설정 로드
    config = ConfigManager().get_all()
    print(f"Chunk Size: {config.get('chunk_size')}")
    print(f"Reranker: {config.get('use_reranker')}")
    print(f"Question Classifier: {config.get('enable_question_classifier')}")

    # 초기화
    print("\n초기화 중...")
    vector_store = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    rag_chain = RAGChain(
        vectorstore=vector_store,
        llm_api_type=config.get("llm_api_type", "request"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:4b"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.7),
        top_k=config.get("top_k", 3),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=config.get("reranker_initial_k", 60),
        enable_synonym_expansion=config.get("enable_synonym_expansion", True),
        enable_multi_query=config.get("enable_multi_query", True),
        multi_query_num=config.get("multi_query_num", 3),
    )
    print("[OK] 초기화 완료")

    # Question Classifier 확인
    if hasattr(rag_chain, 'question_classifier'):
        print(f"Question Classifier: {rag_chain.question_classifier}")
    else:
        print("Question Classifier: 속성 없음")

    # 테스트 질문들
    questions = [
        "OLED는 무엇인가?",
        "TADF의 효율은?",
        "kFRET 값은?",
    ]

    for q in questions:
        test_question(q, rag_chain, vector_store)
        print("\n" + "="*80)

    print("\n완료!")

if __name__ == "__main__":
    main()
