"""
Cosmology 관련 검색 테스트
OLED_2503.13183v2.pdf는 실제로 우주론(Cosmology) 논문
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
print("Cosmology 논문 검색 테스트")
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

# 테스트 쿼리들
test_queries = [
    "Lennart Balkenhol cosmology",
    "CMB temperature power spectrum",
    "Online Learning Emulation",
    "SPT-3G",
    "Lennart Balkenhol 의 논문",
]

for query in test_queries:
    print(f"\n{'=' * 80}")
    print(f"질문: {query}")
    print("=" * 80)

    docs = vector_manager.similarity_search(query, k=5)

    balkenhol_found = False
    for i, doc in enumerate(docs, 1):
        file_name = doc.metadata.get('file_name', 'N/A')
        page = doc.metadata.get('page_number', 'N/A')

        if "Balkenhol" in doc.page_content or "balkenhol" in doc.page_content:
            balkenhol_found = True
            content = doc.page_content[:200].replace('\n', ' ')
            print(f"\n  ✓ {i}. [{file_name}] Page {page}")
            print(f"      {content}...")
        elif file_name == "OLED_2503.13183v2.pdf":
            content = doc.page_content[:200].replace('\n', ' ')
            print(f"\n  ○ {i}. [{file_name}] Page {page} (우주론 논문)")
            print(f"      {content}...")

    if balkenhol_found:
        print(f"\n  → ✓ 'Balkenhol' 문서 발견!")
    elif any(doc.metadata.get('file_name') == "OLED_2503.13183v2.pdf" for doc in docs):
        print(f"\n  → △ 우주론 논문은 검색되었으나 'Balkenhol' 언급 부분은 없음")
    else:
        print(f"\n  → ✗ 'Balkenhol' 문서 검색 실패")

print(f"\n{'=' * 80}")
print("분석 결과")
print("=" * 80)

print(f"""
[핵심 발견]
OLED_2503.13183v2.pdf는 실제로 OLED 논문이 아닙니다!

제목: "OLÉ - Online Learning Emulation in Cosmology"
저자: Sven Günther, Lennart Balkenhol, Christian Fidler, ...
주제: 우주론(Cosmology), CMB(Cosmic Microwave Background) 분석

[문제 원인]
1. arXiv 검색 시 "OLED"로 검색했으나, "OLÉ"(Online Learning Emulation) 논문이 검색됨
2. 파일명에 "OLED_" 접두사가 붙었지만, 내용은 우주론
3. 벡터 검색:
   - "Lennart Balkenhol 논문" → OLED 기술과 의미적으로 거리가 멈
   - "cosmology", "CMB" → 우주론 논문과 의미적으로 가까움

[해결 방법]
1. 인명 검색 기능 추가 (메타데이터 기반)
2. 하이브리드 검색에서 BM25 가중치 증가 (키워드 매칭 강화)
3. 문서 카테고리 분류 (OLED vs Cosmology)
""")
