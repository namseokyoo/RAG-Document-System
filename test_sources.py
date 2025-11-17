"""출처 표시 기능 테스트"""
from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()

import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TORCH_HOME"] = "./torch_cache"
os.environ["HF_HOME"] = "./huggingface_cache"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"

from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

try:
    print("=" * 60)
    print("출처 표시 기능 테스트")
    print("=" * 60)

    # Config 로드
    config_manager = ConfigManager()
    config = config_manager.get_all()

    # VectorStore 초기화
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
        shared_db_path=None,
        shared_db_enabled=False,
        distance_function=config.get("chroma_distance_function", "l2"),
    )

    # RAGChain 초기화
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "request"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:4b"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.7),
        top_k=config.get("top_k", 3),
        use_reranker=config.get("use_reranker", True),
        reranker_model="multilingual-mini",
        reranker_initial_k=config.get("reranker_initial_k", 20),
    )

    print("\n1. DB 문서 개수 확인")
    docs_list = vector_manager.get_documents_list()
    print(f"   총 문서 수: {len(docs_list)}")

    if len(docs_list) == 0:
        print("\n⚠️ DB에 문서가 없습니다. 문서를 업로드한 후 다시 테스트하세요.")
        print("   프로그램 실행 후 '업로드' 탭에서 PDF/PPTX 파일을 업로드하세요.")
    else:
        print(f"\n2. 업로드된 파일 목록 (처음 5개):")
        unique_files = list(set([doc['file_name'] for doc in docs_list]))[:5]
        for f in unique_files:
            print(f"   - {f}")

        print(f"\n3. 테스트 질문 실행")
        test_question = "이 문서의 내용이 뭐야?"
        print(f"   질문: {test_question}")

        # query 실행 (스트리밍 없이)
        try:
            result = rag_chain.query(test_question)
            print(f"\n4. 응답:")
            print(f"   {result[:200]}..." if len(result) > 200 else f"   {result}")

            # get_source_documents 호출
            print(f"\n5. 출처 확인:")
            sources = rag_chain.get_source_documents(test_question)

            if sources:
                print(f"   총 {len(sources)}개 출처 발견:")
                for i, src in enumerate(sources[:3], 1):
                    print(f"   {i}. {src.get('file_name', '?')} (p.{src.get('page_number', '?')}) - Score: {src.get('similarity_score', 0):.2f}%")
            else:
                print("   ⚠️ 출처가 없습니다!")
                print(f"   sources 타입: {type(sources)}")
                print(f"   sources 값: {sources}")

        except Exception as e:
            print(f"\n❌ 쿼리 실행 실패: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
