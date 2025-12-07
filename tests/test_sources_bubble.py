"""
참고문서 버블 표시 테스트
- SessionContext 우선 검색 시 _last_retrieved_docs가 제대로 설정되는지 확인
"""
from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()

import sys
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
from utils.session_context import SessionContext

print("=" * 80)
print("참고문서 버블 테스트")
print("=" * 80)

# 설정 로드
config_manager = ConfigManager()
config = config_manager.get_all()

# VectorStore 초기화
print("\n[1] VectorStore 초기화...")
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "ollama"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "nomic-embed-text"),
    embedding_api_key=config.get("embedding_api_key", ""),
    distance_function=config.get("chroma_distance_function", "l2"),
)
print("  ✓ VectorStore 초기화 완료")

# SessionContext 초기화
print("\n[2] SessionContext 초기화...")
session_context = SessionContext(timeout_seconds=300)
print("  ✓ SessionContext 생성 완료")

# RAGChain 초기화
print("\n[3] RAGChain 초기화...")
rag_chain = RAGChain(
    vectorstore=vector_manager,
    llm_api_type=config.get("llm_api_type", "request"),
    llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
    llm_model=config.get("llm_model", "gemma3:4b"),
    llm_api_key=config.get("llm_api_key", ""),
    temperature=config.get("temperature", 0.7),
    top_k=config.get("top_k", 3),
    use_reranker=config.get("use_reranker", True),
    reranker_model=config.get("reranker_model", "multilingual-mini"),
    reranker_initial_k=config.get("reranker_initial_k", 20),
    enable_hybrid_search=config.get("enable_hybrid_search", True),
    hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5),
    # Phase 3.5
    session_context=session_context,
    enable_session_priority=True,
    session_relevance_threshold=0.7,
)
print("  ✓ RAGChain 초기화 완료")

# 테스트용 문서 추가 (DB에서 실제 document_id 가져오기)
print("\n[4] DB에서 document_id 샘플 가져오기...")
try:
    # 임의 검색으로 document_id 하나 가져오기
    sample_docs = vector_manager.vectorstore.similarity_search("test", k=1)
    if sample_docs:
        sample_doc_id = sample_docs[0].metadata.get('document_id', 'unknown')
        sample_filename = sample_docs[0].metadata.get('file_name', 'unknown')
        print(f"  ✓ 샘플 document_id: {sample_doc_id}")
        print(f"  ✓ 샘플 file_name: {sample_filename}")
    else:
        print("  ✗ DB에 문서가 없습니다.")
        sys.exit(1)
except Exception as e:
    print(f"  ✗ 오류: {e}")
    sys.exit(1)

# SessionContext에 문서 추가
print("\n[5] SessionContext에 문서 추가...")
session_context.add_upload(
    document_id=sample_doc_id,
    file_name=sample_filename,
    num_chunks=10
)
print(f"  ✓ 추가 완료: {sample_filename}")
print(f"  ✓ 활성 문서 수: {len(session_context.get_active_documents())}")

# Intent Detection 트리거 질문
print("\n[6] Intent Detection 질문으로 검색...")
test_question = "이 문서에서 뭐라고 했어?"
print(f"  질문: \"{test_question}\"")

# _last_retrieved_docs 초기 상태 확인
print(f"\n  [검색 전] _last_retrieved_docs: {len(rag_chain._last_retrieved_docs)}개")

# 검색 수행 (_get_context만 호출)
try:
    context = rag_chain._get_context(test_question)
    print(f"  ✓ 검색 완료")
    print(f"  ✓ Context 길이: {len(context)} chars")
except Exception as e:
    print(f"  ✗ 검색 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# _last_retrieved_docs 설정 확인
print(f"\n  [검색 후] _last_retrieved_docs: {len(rag_chain._last_retrieved_docs)}개")
if rag_chain._last_retrieved_docs:
    print(f"  ✓ _last_retrieved_docs가 설정되어 있음!")
    for i, (doc, score) in enumerate(rag_chain._last_retrieved_docs[:3], 1):
        file_name = doc.metadata.get('file_name', 'Unknown')
        page = doc.metadata.get('page_number', '?')
        print(f"    [{i}] {file_name} (p.{page}), score={score:.4f}")
else:
    print(f"  ✗ _last_retrieved_docs가 비어있음! (버그 확인)")

# get_source_documents() 호출
print("\n[7] get_source_documents() 호출...")
sources = rag_chain.get_source_documents(test_question)
print(f"  ✓ Sources 개수: {len(sources)}")
if sources:
    print(f"  ✓ Sources 버블이 정상적으로 생성될 것입니다!")
    for i, src in enumerate(sources[:3], 1):
        print(f"    [{i}] {src['file_name']} (p.{src['page_number']}), "
              f"similarity={src['similarity_score']}")
else:
    print(f"  ✗ Sources가 비어있음! (버그 확인)")
    print(f"     _last_retrieved_docs 상태를 확인하세요.")

print("\n" + "=" * 80)
print("테스트 완료")
print("=" * 80)

# 결과 요약
print("\n[결과 요약]")
if rag_chain._last_retrieved_docs and sources:
    print("  ✅ PASS - _last_retrieved_docs와 sources 모두 정상")
    print("  → 참고문서 버블이 표시되어야 합니다.")
elif rag_chain._last_retrieved_docs and not sources:
    print("  ⚠️ PARTIAL - _last_retrieved_docs는 있지만 sources가 비어있음")
    print("  → get_source_documents() 로직 확인 필요")
else:
    print("  ❌ FAIL - _last_retrieved_docs가 설정되지 않음")
    print("  → _get_context_from_document_ids() 확인 필요")
