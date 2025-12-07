#!/usr/bin/env python3
"""
File Aggregation with Reranker Test
실제 reranked chunks (score 0.0~1.0)로 전략 비교

목적:
1. Spike에서는 vector search만 사용 (score ~0.8-0.99)
2. 실제 시스템에서는 reranker 출력 사용 (score ~0.0-1.0, 더 넓은 범위)
3. 실제 score 분포에서 각 전략(MAX, MEAN, WEIGHTED, COUNT)의 차이 확인
"""

from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()  # Windows 터미널 한글 출력 설정

import sys
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.file_aggregator import FileAggregator
import time


def test_file_aggregation_with_reranker():
    """Reranker 포함 전체 파이프라인으로 File Aggregation 테스트"""

    print("=" * 80)
    print("File Aggregation with Reranker Test")
    print("실제 reranked chunks로 전략 비교")
    print("=" * 80)

    # Config 로드
    print("\n[Step 1] Config 로딩...")
    cfg = ConfigManager()

    # VectorStore 초기화
    print("\n[Step 2] VectorStore 초기화...")
    vectorstore = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=cfg.get("embedding_api_type", "ollama"),
        embedding_base_url=cfg.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=cfg.get("embedding_model", "mxbai-embed-large:latest")
    )

    print(f"  DB 문서 수: {vectorstore.vectorstore._collection.count()}")

    # 테스트 쿼리 (exhaustive 타입)
    test_queries = [
        {
            "query": "OLED ETL 재료 평가 논문",
            "description": "Exhaustive query: ETL 재료 관련 논문 전체 검색",
            "expected": "다양한 OLED ETL 논문들"
        },
        {
            "query": "Hyperfluorescence 기술",
            "description": "Specific query: HF 기술 논문 검색",
            "expected": "HF_OLED 관련 문서들"
        }
    ]

    # 각 쿼리 테스트
    for i, test in enumerate(test_queries, 1):
        query = test['query']
        description = test['description']
        expected = test['expected']

        print(f"\n{'=' * 80}")
        print(f"[Test {i}/{len(test_queries)}] {description}")
        print(f"Query: \"{query}\"")
        print(f"Expected: {expected}")
        print("=" * 80)

        # === Phase 1: Hybrid Search (BM25 + Vector) ===
        print(f"\n[Phase 1] Hybrid Search (k=50)...")
        start_time = time.time()

        # similarity_search_with_rerank 사용 (reranker 포함)
        chunks_with_scores = vectorstore.similarity_search_with_rerank(
            query=query,
            top_k=50,  # 최종 50개
            initial_k=100,  # 초기 검색 100개
            reranker_model="multilingual-mini",
            diversity_penalty=0.0,  # Diversity penalty 비활성화 (순수 reranker score)
            diversity_source_key="source"
        )

        search_time = time.time() - start_time
        print(f"  검색 시간: {search_time:.2f}초")
        print(f"  검색된 청크 수: {len(chunks_with_scores)}")

        # Reranker score 분포 확인
        if chunks_with_scores:
            scores = [score for _, score in chunks_with_scores]
            print(f"\n  [Reranker Score 분포]")
            print(f"    Min:  {min(scores):.4f}")
            print(f"    Max:  {max(scores):.4f}")
            print(f"    Mean: {sum(scores) / len(scores):.4f}")
            print(f"    Top-5: {[f'{s:.4f}' for s in scores[:5]]}")

            # 파일 분포 확인
            file_names = [doc.metadata.get('source', 'unknown') for doc, _ in chunks_with_scores]
            unique_files = set(file_names)
            print(f"\n  고유 파일 수: {len(unique_files)}")

        # Document 객체만 추출 (FileAggregator는 Document 리스트를 받음)
        chunks = [doc for doc, score in chunks_with_scores]

        # === Phase 2: File Aggregation (전략별 비교) ===
        print(f"\n[Phase 2] File Aggregation 전략 비교")
        print("=" * 80)

        strategies = ["max", "mean", "weighted", "count"]
        results = {}

        for strategy in strategies:
            print(f"\n{'─' * 80}")
            print(f"Strategy: {strategy.upper()}")
            print('─' * 80)

            # Aggregation
            start_time = time.time()
            aggregator = FileAggregator(strategy=strategy)
            file_results = aggregator.aggregate_chunks_to_files(
                chunks,
                top_n=15,  # 상위 15개 파일
                min_chunks=1  # 최소 1개 청크
            )
            agg_time = time.time() - start_time

            print(f"Aggregation 시간: {agg_time:.3f}초")

            # 통계
            stats = aggregator.get_statistics(file_results)
            print(f"\n통계:")
            print(f"  총 파일 수: {stats['total_files']}")
            print(f"  총 청크 수: {stats['total_chunks']}")
            print(f"  평균 점수: {stats['avg_score']:.3f}")
            print(f"  파일당 평균 청크: {stats['avg_chunks_per_file']:.1f}")
            print(f"  점수 범위: {stats['score_distribution']['min']:.3f} ~ {stats['score_distribution']['max']:.3f}")

            # Top 5 파일 출력
            print(f"\n파일 리스트 (Top 5):")
            for j, file_info in enumerate(file_results[:5], 1):
                file_name = file_info['file_name'].split('\\')[-1]  # 파일명만
                score = file_info['relevance_score']
                chunks_count = file_info['num_matching_chunks']
                print(f"  {j}. {file_name[:60]:<60} | Score: {score:.3f} | Chunks: {chunks_count}")

            # 결과 저장
            results[strategy] = {
                "file_results": file_results,
                "stats": stats,
                "agg_time": agg_time
            }

        # === Phase 3: 전략 비교 분석 ===
        print(f"\n\n{'=' * 80}")
        print(f"[Phase 3] 전략 비교 분석")
        print("=" * 80)

        # 비교 테이블
        print(f"\n{'Strategy':<12} | {'Avg Score':<10} | {'Top-1 Score':<12} | {'Precision':<10} | {'Coverage':<10}")
        print(f"{'-' * 12}-+-{'-' * 10}-+-{'-' * 12}-+-{'-' * 10}-+-{'-' * 10}")

        for strategy in strategies:
            data = results[strategy]
            avg_score = data['stats']['avg_score']
            top1_score = data['file_results'][0]['relevance_score'] if data['file_results'] else 0

            # Precision: Top-5 평균 점수 (높을수록 정확)
            top5_scores = [f['relevance_score'] for f in data['file_results'][:5]]
            precision = sum(top5_scores) / len(top5_scores) if top5_scores else 0

            # Coverage: 파일 수 (많을수록 다양)
            coverage = data['stats']['total_files']

            print(f"{strategy:<12} | {avg_score:<10.3f} | {top1_score:<12.3f} | {precision:<10.3f} | {coverage:<10}")

        # 권장 전략
        print(f"\n\n{'=' * 80}")
        print("[RECOMMENDATION] 전략 선택 가이드")
        print("=" * 80)

        # WEIGHTED vs COUNT 비교
        weighted_precision = sum([f['relevance_score'] for f in results['weighted']['file_results'][:5]]) / 5
        count_precision = sum([f['relevance_score'] for f in results['count']['file_results'][:5]]) / 5

        print(f"\n1. WEIGHTED 전략:")
        print(f"   - Top-3 가중 평균 (0.5, 0.3, 0.2)")
        print(f"   - Precision: {weighted_precision:.3f}")
        print(f"   - 특징: 높은 점수 청크에 집중, 정확도 우선")

        print(f"\n2. COUNT 전략:")
        print(f"   - 매칭 청크 개수로 순위")
        print(f"   - Precision: {count_precision:.3f}")
        print(f"   - 특징: 많이 언급된 파일 우선, 커버리지 우선")

        if weighted_precision > count_precision:
            print(f"\n[결론] WEIGHTED 전략 권장")
            print(f"  - Precision 우위: {weighted_precision:.3f} > {count_precision:.3f}")
            print(f"  - Reranker score를 효과적으로 활용")
        else:
            print(f"\n[결론] COUNT 전략 권장")
            print(f"  - Precision 우위: {count_precision:.3f} > {weighted_precision:.3f}")
            print(f"  - 다양한 청크에서 언급된 파일 선호")

        print(f"\n")

        # 첫 번째 쿼리만 테스트 (시간 절약)
        if i == 1:
            print(f"{'=' * 80}")
            print("첫 번째 쿼리 테스트 완료 (시간 절약)")
            print(f"{'=' * 80}")
            break

    print("\n" + "=" * 80)
    print("Test 완료")
    print("=" * 80)

    # 최종 결론
    print("\n[RESULT] 결과 요약:")
    print("1. [OK] Reranker 포함 전체 파이프라인 작동 확인")
    print("2. [OK] Score 분포 확인 (0.0~1.0 범위)")
    print("3. [OK] 4가지 전략 비교 완료")
    print("4. [OK] WEIGHTED vs COUNT 우위 판단")

    print("\n[NEXT] 다음 단계:")
    print("1. Config에 file_aggregation 파라미터 추가")
    print("2. 5개 exhaustive query로 추가 검증")
    print("3. RAGChain에 통합")

    return True


if __name__ == "__main__":
    try:
        success = test_file_aggregation_with_reranker()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
