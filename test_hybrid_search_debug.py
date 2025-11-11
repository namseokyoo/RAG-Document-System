"""
하이브리드 검색 디버깅 테스트
BM25가 제대로 작동하는지 확인
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

print("=" * 80)
print("하이브리드 검색 디버깅")
print("=" * 80)

config_manager = ConfigManager()
config = config_manager.get_all()

vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    embedding_api_key=config.get("embedding_api_key", ""),
)

print(f"\n[설정 확인]")
print(f"  - enable_hybrid_search: {config.get('enable_hybrid_search')}")
print(f"  - hybrid_bm25_weight: {config.get('hybrid_bm25_weight')}")

# 테스트 1: 순수 벡터 검색
print(f"\n{'=' * 80}")
print("[테스트 1] 순수 벡터 검색: 'Balkenhol'")
print("=" * 80)

docs = vector_manager.similarity_search("Balkenhol", k=5)
print(f"\n결과: {len(docs)}개")

balkenhol_count = 0
for i, doc in enumerate(docs, 1):
    file_name = doc.metadata.get('file_name', 'N/A')
    page = doc.metadata.get('page_number', 'N/A')

    if "Balkenhol" in doc.page_content or "balkenhol" in doc.page_content:
        balkenhol_count += 1
        content = doc.page_content[:150].replace('\n', ' ')
        print(f"  {i}. [{file_name}] Page {page} ✓")
        print(f"      {content}...")
    else:
        print(f"  {i}. [{file_name}] Page {page} ✗ (Balkenhol 없음)")

print(f"\n→ Top-5 중 {balkenhol_count}개에서 'Balkenhol' 발견")

# 테스트 2: 하이브리드 검색 (BM25 0.5)
print(f"\n{'=' * 80}")
print("[테스트 2] 하이브리드 검색 (Keyword:0.5 / Vector:0.5)")
print("=" * 80)

results = vector_manager.similarity_search_hybrid(
    "Balkenhol",
    initial_k=20,
    vector_weight=0.5,
    keyword_weight=0.5,
    top_k=5
)

# 튜플 리스트를 Document 리스트로 변환
docs = [doc for doc, score in results] if results and isinstance(results[0], tuple) else results

print(f"\n결과: {len(docs)}개")

balkenhol_count = 0
for i, doc in enumerate(docs, 1):
    file_name = doc.metadata.get('file_name', 'N/A')
    page = doc.metadata.get('page_number', 'N/A')

    if "Balkenhol" in doc.page_content or "balkenhol" in doc.page_content:
        balkenhol_count += 1
        content = doc.page_content[:150].replace('\n', ' ')
        print(f"  {i}. [{file_name}] Page {page} ✓")
        print(f"      {content}...")
    else:
        print(f"  {i}. [{file_name}] Page {page} ✗ (Balkenhol 없음)")

print(f"\n→ Top-5 중 {balkenhol_count}개에서 'Balkenhol' 발견")

# 테스트 3: BM25 가중치 높임 (0.8)
print(f"\n{'=' * 80}")
print("[테스트 3] 하이브리드 검색 (Keyword:0.8 / Vector:0.2)")
print("=" * 80)

results = vector_manager.similarity_search_hybrid(
    "Balkenhol",
    initial_k=20,
    vector_weight=0.2,
    keyword_weight=0.8,
    top_k=5
)

docs = [doc for doc, score in results] if results and isinstance(results[0], tuple) else results

print(f"\n결과: {len(docs)}개")

balkenhol_count = 0
for i, doc in enumerate(docs, 1):
    file_name = doc.metadata.get('file_name', 'N/A')
    page = doc.metadata.get('page_number', 'N/A')

    if "Balkenhol" in doc.page_content or "balkenhol" in doc.page_content:
        balkenhol_count += 1
        content = doc.page_content[:150].replace('\n', ' ')
        print(f"  {i}. [{file_name}] Page {page} ✓")
        print(f"      {content}...")
    else:
        print(f"  {i}. [{file_name}] Page {page} ✗ (Balkenhol 없음)")

print(f"\n→ Top-5 중 {balkenhol_count}개에서 'Balkenhol' 발견")

# 테스트 4: 순수 BM25 (1.0)
print(f"\n{'=' * 80}")
print("[테스트 4] 순수 Keyword 검색 (Keyword:1.0 / Vector:0.0)")
print("=" * 80)

results = vector_manager.similarity_search_hybrid(
    "Balkenhol",
    initial_k=20,
    vector_weight=0.0,
    keyword_weight=1.0,
    top_k=5
)

docs = [doc for doc, score in results] if results and isinstance(results[0], tuple) else results

print(f"\n결과: {len(docs)}개")

balkenhol_count = 0
for i, doc in enumerate(docs, 1):
    file_name = doc.metadata.get('file_name', 'N/A')
    page = doc.metadata.get('page_number', 'N/A')

    if "Balkenhol" in doc.page_content or "balkenhol" in doc.page_content:
        balkenhol_count += 1
        content = doc.page_content[:150].replace('\n', ' ')
        print(f"  {i}. [{file_name}] Page {page} ✓")
        print(f"      {content}...")
    else:
        print(f"  {i}. [{file_name}] Page {page} ✗ (Balkenhol 없음)")

print(f"\n→ Top-5 중 {balkenhol_count}개에서 'Balkenhol' 발견")

print(f"\n{'=' * 80}")
print("분석 결과")
print("=" * 80)

print(f"""
[핵심 질문]
1. 하이브리드 검색이 실제로 작동하는가?
2. BM25가 "Balkenhol" 키워드를 매칭하는가?
3. BM25 가중치를 높이면 개선되는가?

[기대 결과]
- 순수 벡터 검색: 'Balkenhol' 찾기 어려움 (의미적 거리)
- 하이브리드 0.5: 일부 개선
- 하이브리드 0.8: 많이 개선
- 순수 BM25 1.0: 모든 결과에 'Balkenhol' 포함

실제 결과가 기대와 다르다면 → 하이브리드 검색 구현 이슈
""")
