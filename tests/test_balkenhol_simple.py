"""
Lennart Balkenhol 검색 간단 테스트
"""

import os
import sys

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

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
print("Lennart Balkenhol 검색 테스트")
print("=" * 80)

# Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

# VectorStore 초기화
print(f"\n[초기화]")
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    embedding_api_key=config.get("embedding_api_key", ""),
)
print(f"  ✓ VectorStore 초기화")

# RAGChain 초기화
rag_chain = RAGChain(
    vectorstore=vector_manager,
    llm_api_type=config.get("llm_api_type", "request"),
    llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
    llm_model=config.get("llm_model", "gemma3:latest"),
    llm_api_key=config.get("llm_api_key", ""),
    temperature=config.get("temperature", 0.3),
    top_k=config.get("top_k", 5),
    use_reranker=config.get("use_reranker", True),
    reranker_model=config.get("reranker_model", "multilingual-mini"),
    reranker_initial_k=config.get("reranker_initial_k", 30),
    enable_synonym_expansion=config.get("enable_synonym_expansion", False),
    enable_multi_query=config.get("enable_multi_query", True),
    multi_query_num=config.get("multi_query_num", 3),
    enable_hybrid_search=config.get("enable_hybrid_search", True),
    hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5),
    small_to_large_context_size=config.get("small_to_large_context_size", 800)
)
print(f"  ✓ RAGChain 초기화")

collection = vector_manager.vectorstore._collection
total_chunks = collection.count()
print(f"  ✓ DB 총 청크: {total_chunks:,}개\n")

# 테스트 1: 벡터 검색 (similarity_search)
print("=" * 80)
print("[테스트 1] 벡터 검색: 'Lennart Balkenhol'")
print("=" * 80)

try:
    docs = vector_manager.similarity_search("Lennart Balkenhol", k=10)
    print(f"\n벡터 검색 결과: {len(docs)}개")

    for i, doc in enumerate(docs[:5], 1):
        content = doc.page_content[:150].replace('\n', ' ')
        file_name = doc.metadata.get('file_name', 'N/A')
        page = doc.metadata.get('page_number', 'N/A')

        print(f"\n{i}. [{file_name}] Page {page}")
        print(f"   {content}...")

        # "Balkenhol" 포함 여부 체크
        if "Balkenhol" in doc.page_content or "balkenhol" in doc.page_content:
            print(f"   ✓ 'Balkenhol' 포함됨!")
        else:
            print(f"   ✗ 'Balkenhol' 없음")

except Exception as e:
    print(f"[오류] {e}")
    import traceback
    traceback.print_exc()

# 테스트 2: 키워드 검색 (DB 직접 조회)
print(f"\n{'=' * 80}")
print("[테스트 2] 키워드 검색: 'Balkenhol' 텍스트 매칭")
print("=" * 80)

try:
    all_data = collection.get(include=['metadatas', 'documents'])

    matching_chunks = []
    for doc_id, doc_content, metadata in zip(
        all_data['ids'],
        all_data['documents'],
        all_data['metadatas']
    ):
        if "Balkenhol" in doc_content or "balkenhol" in doc_content:
            matching_chunks.append({
                'content': doc_content,
                'metadata': metadata
            })

    print(f"\n키워드 매칭 결과: {len(matching_chunks)}개")

    for i, chunk in enumerate(matching_chunks[:3], 1):
        file_name = chunk['metadata'].get('file_name', 'N/A')
        page = chunk['metadata'].get('page_number', 'N/A')
        content = chunk['content'][:150].replace('\n', ' ')

        print(f"\n{i}. [{file_name}] Page {page}")
        print(f"   {content}...")

except Exception as e:
    print(f"[오류] {e}")

# 테스트 3: RAG Chain 전체 테스트
print(f"\n{'=' * 80}")
print("[테스트 3] RAG Chain 전체 테스트")
print("=" * 80)

question = "Lennart Balkenhol 의 논문을 찾아야 오늘의 숙제가 해결돼?"
print(f"\n질문: {question}\n")

try:
    result = rag_chain.query(question)

    print(f"[응답]")
    print(f"{result['answer'][:800]}\n")

    print(f"[검색된 문서] {len(result.get('source_documents', []))}개")
    for i, doc in enumerate(result.get('source_documents', [])[:3], 1):
        file_name = doc.metadata.get('file_name', 'N/A')
        page = doc.metadata.get('page_number', 'N/A')
        content = doc.page_content[:100].replace('\n', ' ')

        print(f"\n  {i}. [{file_name}] Page {page}")
        print(f"     {content}...")

        if "Balkenhol" in doc.page_content or "balkenhol" in doc.page_content:
            print(f"     ✓ 'Balkenhol' 포함!")

except Exception as e:
    print(f"[오류] {e}")
    import traceback
    traceback.print_exc()

# 테스트 4: 단순 이름 검색
print(f"\n{'=' * 80}")
print("[테스트 4] 단순 이름 검색: 'Balkenhol'")
print("=" * 80)

try:
    docs = vector_manager.similarity_search("Balkenhol", k=10)
    print(f"\n벡터 검색 결과: {len(docs)}개")

    balkenhol_found = 0
    for i, doc in enumerate(docs[:5], 1):
        file_name = doc.metadata.get('file_name', 'N/A')
        page = doc.metadata.get('page_number', 'N/A')

        if "Balkenhol" in doc.page_content or "balkenhol" in doc.page_content:
            balkenhol_found += 1
            content = doc.page_content[:150].replace('\n', ' ')
            print(f"\n{i}. [{file_name}] Page {page}")
            print(f"   {content}...")
            print(f"   ✓ 'Balkenhol' 포함!")

    print(f"\n→ Top 5 중 {balkenhol_found}개 문서에서 'Balkenhol' 발견")

except Exception as e:
    print(f"[오류] {e}")

print(f"\n{'=' * 80}")
print("테스트 완료!")
print("=" * 80)

print(f"\n[분석]")
print(f"1. 키워드 검색: {len(matching_chunks)}개 청크에 'Balkenhol' 포함")
print(f"2. 벡터 검색: Top-5 문서에서 'Balkenhol' 발견 여부 확인")
print(f"3. RAG Chain: 최종 답변에서 'Balkenhol' 관련 정보 제공 여부")
print(f"\n→ 벡터 검색이 관련 문서를 찾지 못한다면: 임베딩 모델 이슈")
print(f"→ 벡터 검색은 되지만 답변이 이상하다면: LLM 처리 이슈")
