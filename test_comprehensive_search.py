"""
종합 검색 테스트
- 인명 (고유명사)
- 기술 용어
- 문서명
- 일반 질문
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
print("종합 검색 테스트")
print("=" * 80)

config_manager = ConfigManager()
config = config_manager.get_all()

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

print(f"\n[설정 확인]")
print(f"  - Hybrid Search: {rag_chain.enable_hybrid_search}")
print(f"  - BM25 Weight: {config.get('hybrid_bm25_weight')}")
print(f"  - Reranker: {rag_chain.use_reranker}")

# 테스트 케이스
test_cases = [
    {
        "category": "인명 (고유명사)",
        "query": "Lennart Balkenhol",
        "expected_file": "OLED_2503.13183v2.pdf",
        "keywords": ["Balkenhol", "balkenhol"]
    },
    {
        "category": "기술 용어",
        "query": "TADF",
        "expected_file": "HF_OLED",
        "keywords": ["TADF", "thermally activated delayed fluorescence"]
    },
    {
        "category": "문서명/약어",
        "query": "ESTA",
        "expected_file": "ESTA",
        "keywords": ["ESTA", "Electronic System"]
    },
    {
        "category": "시스템명",
        "query": "HRD-Net",
        "expected_file": "HRD-Net",
        "keywords": ["HRD-Net", "출결관리"]
    },
    {
        "category": "일반 질문",
        "query": "OLED 효율",
        "expected_file": None,
        "keywords": ["OLED", "효율", "efficiency"]
    },
    {
        "category": "복합 질문",
        "query": "형광 에미터의 특징",
        "expected_file": None,
        "keywords": ["형광", "에미터", "fluorescence"]
    },
    {
        "category": "영문 고유명사",
        "query": "Customs and Border Protection",
        "expected_file": "ESTA",
        "keywords": ["Customs", "Border Protection", "CBP"]
    }
]

results = []

for i, test_case in enumerate(test_cases, 1):
    print(f"\n{'=' * 80}")
    print(f"[테스트 {i}/{len(test_cases)}] {test_case['category']}")
    print(f"{'=' * 80}")
    print(f"\n질문: {test_case['query']}")
    print(f"-" * 80)

    try:
        # RAG Chain으로 검색
        result = rag_chain.query(test_case['query'])

        # 답변 출력
        answer = result.get('answer', '')[:300]
        print(f"\n[답변]")
        print(f"{answer}...")

        # 검색된 문서 확인
        sources = result.get('sources', [])
        print(f"\n[검색된 문서] {len(sources)}개")

        found_expected = False
        found_keywords = []

        for j, source in enumerate(sources[:5], 1):
            file_name = source.get('file_name', 'N/A')
            page = source.get('page_number', 'N/A')
            content = source.get('content', '')

            # 예상 파일 확인
            if test_case['expected_file'] and test_case['expected_file'] in file_name:
                found_expected = True

            # 키워드 확인
            for keyword in test_case['keywords']:
                if keyword.lower() in content.lower():
                    found_keywords.append(keyword)
                    break

            print(f"  {j}. [{file_name}] Page {page}")

        # 결과 판정
        if test_case['expected_file']:
            success = found_expected
            status = "✓ 성공" if success else "✗ 실패"
            print(f"\n{status}: 예상 파일 '{test_case['expected_file']}' {'발견' if found_expected else '미발견'}")
        else:
            success = len(found_keywords) > 0
            status = "✓ 성공" if success else "△ 부분 성공"
            print(f"\n{status}: 키워드 {len(found_keywords)}/{len(test_case['keywords'])}개 발견")

        results.append({
            'category': test_case['category'],
            'query': test_case['query'],
            'success': success,
            'found_expected': found_expected if test_case['expected_file'] else None,
            'found_keywords': found_keywords
        })

    except Exception as e:
        print(f"\n[오류] {e}")
        import traceback
        traceback.print_exc()

        results.append({
            'category': test_case['category'],
            'query': test_case['query'],
            'success': False,
            'error': str(e)
        })

# 최종 결과 요약
print(f"\n{'=' * 80}")
print(f"테스트 결과 요약")
print(f"{'=' * 80}")

success_count = sum(1 for r in results if r.get('success'))
total_count = len(results)

print(f"\n전체: {success_count}/{total_count} 성공 ({success_count/total_count*100:.1f}%)")

print(f"\n[상세]")
for r in results:
    status = "✓" if r.get('success') else "✗"
    print(f"  {status} [{r['category']}] {r['query']}")
    if 'error' in r:
        print(f"     오류: {r['error']}")
    elif r.get('found_expected') is not None:
        print(f"     예상 파일: {'발견' if r['found_expected'] else '미발견'}")
    elif r.get('found_keywords'):
        print(f"     키워드: {', '.join(r['found_keywords'])}")

print(f"\n{'=' * 80}")
print(f"테스트 완료")
print(f"{'=' * 80}")

if success_count == total_count:
    print(f"\n✓ 모든 테스트 통과!")
elif success_count >= total_count * 0.7:
    print(f"\n△ 대부분 테스트 통과 ({success_count}/{total_count})")
else:
    print(f"\n✗ 일부 테스트 실패 ({total_count - success_count}개)")
