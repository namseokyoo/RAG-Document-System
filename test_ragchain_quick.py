#!/usr/bin/env python3
"""
RAGChain 사용법 빠른 테스트
"""

import sys
sys.path.append('.')

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

# 1. Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

print("[1] VectorStore 초기화 중...")
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config["embedding_api_type"],
    embedding_base_url=config["embedding_base_url"],
    embedding_model=config["embedding_model"],
    embedding_api_key=config.get("embedding_api_key", ""),
    distance_function=config.get("chroma_distance_function", "l2")
)

print("[2] RAGChain 초기화 중...")
rag_chain = RAGChain(
    vectorstore=vector_manager,
    llm_api_type=config["llm_api_type"],
    llm_base_url=config["llm_base_url"],
    llm_model=config["llm_model"],
    llm_api_key=config.get("llm_api_key", ""),
    temperature=config["temperature"],
    max_tokens=4096,
    top_k=config["top_k"],
    use_reranker=config["use_reranker"],
    reranker_model=config["reranker_model"],
    reranker_initial_k=config["reranker_initial_k"],
    enable_synonym_expansion=config.get("enable_synonym_expansion", True),
    enable_multi_query=config.get("enable_multi_query", True),
    multi_query_num=config.get("multi_query_num", 3),
    enable_hybrid_search=config.get("enable_hybrid_search", True),
    hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5),
    small_to_large_context_size=config.get("small_to_large_context_size", 800),
)

print("[3] 테스트 질문...")
question = "OLED의 정의는?"

# RAGChain의 메서드들을 확인
print("\nRAGChain 메서드 목록:")
methods = [m for m in dir(rag_chain) if not m.startswith('_') and callable(getattr(rag_chain, m))]
for m in methods[:20]:
    print(f"  - {m}")

print("\n... (더 많은 메서드)")

# 스트리밍 메서드 찾기
streaming_methods = [m for m in methods if 'stream' in m.lower()]
print(f"\n스트리밍 관련 메서드: {streaming_methods}")

# 질문 관련 메서드 찾기
query_methods = [m for m in methods if 'query' in m.lower() or 'ask' in m.lower() or 'answer' in m.lower()]
print(f"질문 관련 메서드: {query_methods}")

print("\n[완료]")
