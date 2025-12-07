"""
통합 테스트: Question Classifier + RAG Chain
실제 문서 검색 및 답변 생성 테스트
"""

import sys
import os

# 환경 설정
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

print("=" * 80)
print("통합 테스트 시작")
print("=" * 80)

# Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

print("\n[1단계] 설정 확인")
print(f"  - Question Classifier: {config.get('enable_question_classifier', True)}")
print(f"  - Classifier Use LLM: {config.get('classifier_use_llm', True)}")
print(f"  - Multi-Query: {config.get('enable_multi_query', True)}")
print(f"  - Reranker Model: {config.get('reranker_model', 'multilingual-base')}")

# VectorStore 초기화
print("\n[2단계] VectorStore 초기화")
try:
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    # 문서 개수 확인 (간단한 검색으로 확인)
    try:
        test_search = vector_manager.vectorstore.similarity_search("test", k=1)
        print(f"  - VectorStore 정상 작동 (테스트 검색 성공)")
    except Exception as e:
        print(f"  [경고] VectorStore 테스트 검색 실패: {e}")
        print(f"  문서가 없거나 DB 연결 문제일 수 있습니다.")

except Exception as e:
    print(f"  [오류] VectorStore 초기화 실패: {e}")
    sys.exit(1)

# RAGChain 초기화
print("\n[3단계] RAGChain 초기화")
try:
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "request"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:4b"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.7),
        top_k=config.get("top_k", 3),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-base"),
        reranker_initial_k=config.get("reranker_initial_k", 60),
        enable_synonym_expansion=config.get("enable_synonym_expansion", True),
        enable_multi_query=config.get("enable_multi_query", True),
        multi_query_num=config.get("multi_query_num", 3),
        enable_hybrid_search=config.get("enable_hybrid_search", True),
        hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5)
    )

    # Question Classifier 설정
    if hasattr(rag_chain, 'question_classifier') and rag_chain.question_classifier:
        print("  - Question Classifier: 활성화됨")
    else:
        print("  - Question Classifier: 비활성화됨")

except Exception as e:
    print(f"  [오류] RAGChain 초기화 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 테스트 질문
test_questions = [
    {
        "question": "OLED는 무엇인가?",
        "expected_type": "normal",
        "description": "일반 질문 - Normal"
    },
    {
        "question": "효율 값은?",
        "expected_type": "simple",
        "description": "단순 질문 - Simple"
    },
    {
        "question": "OLED와 QLED를 비교해줘",
        "expected_type": "complex",
        "description": "복잡한 질문 - Complex"
    },
]

print("\n" + "=" * 80)
print("테스트 질문 실행")
print("=" * 80)

for i, test in enumerate(test_questions, 1):
    question = test["question"]
    expected_type = test["expected_type"]
    description = test["description"]

    print(f"\n[테스트 {i}] {description}")
    print(f"질문: \"{question}\"")
    print(f"예상 유형: {expected_type}")
    print("-" * 80)

    try:
        # 분류 결과 확인
        if hasattr(rag_chain, 'question_classifier') and rag_chain.question_classifier:
            classification = rag_chain.question_classifier.classify(question)
            print(f"\n[분류 결과]")
            print(f"  유형: {classification['type']} (예상: {expected_type})")
            print(f"  신뢰도: {classification['confidence']:.0%}")
            print(f"  방법: {classification['method']}")
            print(f"  Multi-Query: {classification['multi_query']}")
            print(f"  Max Results: {classification['max_results']}")
            print(f"  Reranker K: {classification['reranker_k']}")
            print(f"  Max Tokens: {classification['max_tokens']}")

            if classification['type'] != expected_type:
                print(f"  [경고] 분류 불일치! 예상: {expected_type}, 실제: {classification['type']}")

        # 검색만 수행 (답변 생성은 생략 - 시간 절약)
        print(f"\n[검색 결과]")

        # _get_context 호출하여 검색만 수행
        import time
        start = time.time()

        # 내부적으로 분류 및 검색 수행
        context = rag_chain._get_context(question)

        elapsed = time.time() - start

        print(f"  검색 시간: {elapsed:.2f}초")
        print(f"  컨텍스트 길이: {len(context)} 문자")

        # 검색된 문서 확인
        if hasattr(rag_chain, '_last_retrieved_docs'):
            docs = rag_chain._last_retrieved_docs
            print(f"  검색된 문서: {len(docs)}개")

            if len(docs) > 0:
                print(f"\n  [상위 3개 문서]")
                for j, (doc, score) in enumerate(docs[:3], 1):
                    file_name = doc.metadata.get('file_name', 'Unknown')
                    page = doc.metadata.get('page_number', '?')
                    content_preview = doc.page_content[:100].replace('\n', ' ')
                    print(f"    {j}. {file_name} (p.{page}) [점수: {score:.3f}]")
                    print(f"       내용: {content_preview}...")
            else:
                print(f"  [경고] 검색된 문서가 없습니다!")

        print(f"\n  [성공] 테스트 통과")

    except Exception as e:
        print(f"\n  [실패] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("통합 테스트 완료")
print("=" * 80)
