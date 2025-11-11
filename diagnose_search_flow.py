"""
전체 검색 흐름 진단 스크립트
RAG Chain의 실제 검색 경로 추적
"""

import os
import sys

if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

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
print("검색 흐름 진단")
print("=" * 80)

config_manager = ConfigManager()
config = config_manager.get_all()

print(f"\n[Config 설정]")
print(f"  - enable_hybrid_search: {config.get('enable_hybrid_search')}")
print(f"  - hybrid_bm25_weight: {config.get('hybrid_bm25_weight')}")
print(f"  - use_reranker: {config.get('use_reranker')}")
print(f"  - enable_multi_query: {config.get('enable_multi_query')}")
print(f"  - top_k: {config.get('top_k')}")

# VectorStore 초기화
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    embedding_api_key=config.get("embedding_api_key", ""),
)

# RAG Chain 초기화
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

print(f"\n[RAG Chain 설정 확인]")
print(f"  - enable_hybrid_search: {rag_chain.enable_hybrid_search}")
print(f"  - hybrid_retriever: {rag_chain.hybrid_retriever is not None}")
print(f"  - use_reranker: {rag_chain.use_reranker}")
print(f"  - enable_multi_query: {rag_chain.enable_multi_query}")

# VectorStore 기능 확인
print(f"\n[VectorStore 기능 확인]")
print(f"  - search_with_mode: {hasattr(vector_manager, 'search_with_mode')}")
print(f"  - similarity_search_hybrid: {hasattr(vector_manager, 'similarity_search_hybrid')}")
print(f"  - similarity_search_with_rerank: {hasattr(vector_manager, 'similarity_search_with_rerank')}")
print(f"  - shared_db_enabled: {vector_manager.shared_db_enabled}")

# 검색 경로 예측
print(f"\n[예상 검색 경로]")

# _search_candidates의 분기 로직
if hasattr(vector_manager, 'search_with_mode'):
    print(f"  1순위: search_with_mode() 호출됨 ✓")
    print(f"     └─ search_mode='integrated'")
    if not vector_manager.shared_db_enabled:
        print(f"        └─ 공유 DB 없음")
        if config.get("use_reranker", True):
            print(f"           └─ similarity_search_with_rerank() 호출 ✓")
            print(f"              └─ similarity_search_with_score() (순수 벡터!) ✗")
        else:
            print(f"           └─ similarity_search_hybrid() 호출 ✓")
elif rag_chain.enable_hybrid_search and rag_chain.hybrid_retriever:
    print(f"  2순위: HybridRetriever.search() 호출")
else:
    print(f"  3순위: similarity_search_hybrid() 호출")

print(f"\n{'=' * 80}")
print(f"핵심 문제 진단")
print(f"{'=' * 80}")

print(f"""
[현재 상황]
1. Config: enable_hybrid_search=True, use_reranker=True
2. VectorStore: search_with_mode 존재
3. 공유 DB: 비활성화

[실제 실행 경로]
RAG Chain
  └─ _search_candidates()
     └─ search_with_mode(search_mode='integrated')  ← 1순위
        └─ 공유 DB 없음 + use_reranker=True
           └─ similarity_search_with_rerank()  ← 749라인
              └─ similarity_search_with_score()  ← 순수 벡터!

[문제]
similarity_search_with_rerank()가:
- 순수 벡터 검색(similarity_search_with_score)만 사용
- hybrid_bm25_weight 설정을 무시함

[해결 방법]
utils/vector_store.py:749 수정
  기존: candidates = self.vectorstore.similarity_search_with_score(query, k=initial_k)
  수정: candidates = self.similarity_search_hybrid(query, initial_k=initial_k*2, top_k=initial_k)
""")

print(f"\n{'=' * 80}")
print(f"검증: 실제 RAG Chain 실행")
print(f"{'=' * 80}")

question = "Balkenhol"

print(f"\n질문: {question}")
print(f"\n검색 시작... (로그 주의 깊게 확인)")
print(f"-" * 80)

try:
    # _search_candidates를 직접 호출해서 경로 확인
    candidates = rag_chain._search_candidates(question, search_mode="integrated")

    print(f"\n[결과]")
    print(f"  - 후보 문서 수: {len(candidates)}")

    balkenhol_count = 0
    for i, (doc, score) in enumerate(candidates[:10], 1):
        file_name = doc.metadata.get('file_name', 'N/A')
        page = doc.metadata.get('page_number', 'N/A')

        if "Balkenhol" in doc.page_content or "balkenhol" in doc.page_content:
            balkenhol_count += 1
            print(f"  {i}. [{file_name}] p.{page} ✓ Balkenhol 포함 (score: {score:.4f})")
        else:
            print(f"  {i}. [{file_name}] p.{page} ✗ Balkenhol 없음 (score: {score:.4f})")

    print(f"\n→ Top-10 중 {balkenhol_count}개에서 'Balkenhol' 발견")

    if balkenhol_count == 0:
        print(f"\n✗ 문제 확인: 순수 벡터 검색만 수행됨")
        print(f"   해결 필요: similarity_search_with_rerank()가 하이브리드 검색 사용하도록 수정")
    else:
        print(f"\n✓ 하이브리드 검색 작동 중")

except Exception as e:
    print(f"\n[오류] {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'=' * 80}")
print(f"진단 완료")
print(f"={'=' * 80}")
