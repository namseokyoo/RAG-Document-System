#!/usr/bin/env python3
"""
맥락 이해 테스트: 키워드 매칭 vs. 의미 이해
다양한 명확도의 질문으로 시스템의 맥락 파악 능력 검증
"""

from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()  # Windows 터미널 한글 출력 설정

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.file_aggregator import FileAggregator
import time


def test_query(vectorstore, aggregator, query, description, expected_relevance):
    """단일 쿼리 테스트"""
    print(f"\n{'='*80}")
    print(f"[TEST] {description}")
    print(f"Query: \"{query}\"")
    print(f"Expected Relevance: {expected_relevance}")
    print('='*80)

    # 검색
    start_time = time.time()
    chunks = vectorstore.similarity_search(query, k=50)
    search_time = time.time() - start_time

    print(f"\n검색 완료: {len(chunks)}개 청크 ({search_time:.2f}초)")

    # File aggregation
    file_results = aggregator.aggregate_chunks_to_files(chunks, top_n=10, min_chunks=1)

    print(f"\n[파일 리스트] Top 10:")
    for i, file_info in enumerate(file_results[:10], 1):
        file_name = file_info['file_name'].split('\\')[-1]  # 파일명만
        score = file_info['relevance_score']
        chunks_count = file_info['num_matching_chunks']

        # 파일명에서 관련도 추정 (간단한 휴리스틱)
        is_relevant = "UNKNOWN"
        if "OLED" in file_name or "HF_" in file_name:
            is_relevant = "RELEVANT"
        elif "lgd_display" in file_name:
            is_relevant = "MAYBE"

        print(f"  {i:2d}. [{is_relevant:8s}] {file_name[:50]:50s} | Score: {score:.2f} | Chunks: {chunks_count}")

    # 통계
    stats = aggregator.get_statistics(file_results)
    print(f"\n통계:")
    print(f"  총 파일: {stats['total_files']}")
    print(f"  평균 점수: {stats['avg_score']:.3f}")
    print(f"  파일당 평균 청크: {stats['avg_chunks_per_file']:.1f}")

    return file_results


def main():
    """메인 테스트"""
    print("="*80)
    print("맥락 이해 능력 테스트")
    print("키워드 매칭 vs. 의미 이해")
    print("="*80)

    # 초기화
    print("\n[초기화] VectorStore 로딩...")
    cfg = ConfigManager()
    vectorstore = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=cfg.get("embedding_api_type", "ollama"),
        embedding_base_url=cfg.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=cfg.get("embedding_model", "mxbai-embed-large:latest")
    )

    aggregator = FileAggregator(strategy="weighted")

    print(f"  DB 문서 수: {vectorstore.vectorstore._collection.count()}")

    # 테스트 케이스 5개
    test_cases = [
        {
            "query": "OLED 소자의 ETL 재료 평가",
            "description": "명확한 쿼리 (OLED 명시, 구체적)",
            "expected": "HIGH - OLED ETL 관련 문서만 검색되어야 함"
        },
        {
            "query": "ETL 재료 평가",
            "description": "애매한 쿼리 (도메인 불명확)",
            "expected": "MEDIUM - OLED ETL 위주지만 노이즈 가능"
        },
        {
            "query": "Hyperfluorescence 기술",
            "description": "특정 기술 검색 (맥락 명확)",
            "expected": "HIGH - HF_OLED 문서가 상위여야 함"
        },
        {
            "query": "디스플레이 효율 개선",
            "description": "추상적 쿼리 (넓은 의미)",
            "expected": "MEDIUM - 다양한 OLED 문서 검색"
        },
        {
            "query": "ZnO 나노입자",
            "description": "구체적 재료명 (맥락: OLED ETL)",
            "expected": "HIGH - ZnO 관련 OLED 논문"
        }
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n{'#'*80}")
        print(f"# Test {i}/5")
        print(f"{'#'*80}")

        file_results = test_query(
            vectorstore,
            aggregator,
            test_case['query'],
            test_case['description'],
            test_case['expected']
        )

        results.append({
            'query': test_case['query'],
            'description': test_case['description'],
            'expected': test_case['expected'],
            'files_found': len(file_results),
            'top_file': file_results[0]['file_name'].split('\\')[-1] if file_results else "N/A"
        })

    # 최종 요약
    print(f"\n\n{'='*80}")
    print("최종 요약")
    print('='*80)

    for i, result in enumerate(results, 1):
        print(f"\n[Test {i}] {result['description']}")
        print(f"  Query: \"{result['query']}\"")
        print(f"  Expected: {result['expected']}")
        print(f"  Found: {result['files_found']}개 파일")
        print(f"  Top 1: {result['top_file']}")

    print(f"\n{'='*80}")
    print("분석:")
    print("1. 명확한 쿼리(Test 1, 3, 5)는 관련 문서만 검색되는지 확인")
    print("2. 애매한 쿼리(Test 2, 4)는 노이즈가 얼마나 섞이는지 확인")
    print("3. File aggregation으로 청크 단위 노이즈 감소 효과 확인")
    print('='*80)

    return True


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
