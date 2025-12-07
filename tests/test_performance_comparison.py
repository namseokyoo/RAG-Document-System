"""
Phase 3-4 성능 비교 테스트
- 기준선 (Phase 1-2만): Hybrid Search OFF
- Phase 3-4 적용: Hybrid Search ON + Slide Type Classification

동일한 문서, 동일한 쿼리로 비교하여 성능 향상 측정
"""
import sys
import os
import json
import time
from datetime import datetime

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def test_scenario(enable_hybrid: bool, test_name: str, test_queries: list):
    """테스트 시나리오 실행"""
    print("\n" + "=" * 80)
    print(f"테스트 시나리오: {test_name}")
    print(f"Hybrid Search: {'ON' if enable_hybrid else 'OFF'}")
    print("=" * 80)

    # 1. 설정 로드
    config = ConfigManager().get_all()

    # 2. VectorStoreManager 초기화 (기존 DB 사용)
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    # 3. RAGChain 초기화
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "ollama"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:4b"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=0.3,
        top_k=3,
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=20,
        enable_hybrid_search=enable_hybrid,
        hybrid_bm25_weight=0.5
    )

    # 4. 검색 테스트
    results = []

    for i, query in enumerate(test_queries, 1):
        print(f"\n[쿼리 {i}/{len(test_queries)}] {query}")
        print("-" * 60)

        try:
            start_time = time.time()
            result = rag_chain.query(query)
            elapsed_time = time.time() - start_time

            if result.get("success"):
                answer = result['answer']
                confidence = result['confidence']
                sources_count = len(result['sources'])

                # 출력 (인코딩 에러 방지)
                try:
                    print(f"[OK] 답변: {answer[:150]}...")
                except:
                    print(f"[OK] 답변: (출력 불가 - 인코딩 문제)")

                print(f"[STAT] 신뢰도: {confidence:.1%}")
                print(f"[INFO] 출처: {sources_count}개 문서")
                print(f"[TIME] 응답 시간: {elapsed_time:.2f}초")

                # 결과 저장
                results.append({
                    "query": query,
                    "answer": answer,
                    "confidence": confidence,
                    "sources_count": sources_count,
                    "time": elapsed_time,
                    "success": True
                })
            else:
                print(f"[ERROR] 검색 실패: {result.get('answer')}")
                results.append({
                    "query": query,
                    "error": result.get('answer'),
                    "success": False
                })

        except Exception as e:
            print(f"[ERROR] 오류: {str(e)}")
            results.append({
                "query": query,
                "error": str(e),
                "success": False
            })

    return results


def calculate_statistics(results: list) -> dict:
    """결과 통계 계산"""
    successful = [r for r in results if r.get("success")]

    if not successful:
        return {
            "success_rate": 0.0,
            "avg_confidence": 0.0,
            "avg_time": 0.0,
            "avg_sources": 0.0
        }

    return {
        "success_rate": len(successful) / len(results) * 100,
        "avg_confidence": sum(r["confidence"] for r in successful) / len(successful) * 100,
        "avg_time": sum(r["time"] for r in successful) / len(successful),
        "avg_sources": sum(r["sources_count"] for r in successful) / len(successful)
    }


def main():
    """메인 테스트 실행"""
    print("=" * 80)
    print("Phase 3-4 성능 비교 테스트")
    print("=" * 80)

    # 테스트 쿼리 세트
    test_queries = [
        # 키워드 검색 (BM25가 유리)
        "TADF 재료는?",
        "ACRSA 효율은?",
        "kFRET 값은?",

        # 의미 기반 검색 (Vector가 유리)
        "논문의 핵심 결론은?",
        "분자 구조와 성능의 관계는?",

        # 복합 검색 (Hybrid가 유리)
        "DMAC-TRZ와 ACRSA를 비교해주세요",
        "FRET 효율을 향상시키는 방법은?",
    ]

    print(f"\n[INFO] 테스트 쿼리: {len(test_queries)}개")
    print(f"[INFO] 기존 임베딩된 문서 사용 (data/chroma_db)")

    # 1. 기준선 테스트 (Hybrid OFF)
    print("\n\n" + "=" * 80)
    print("1단계: 기준선 테스트 (Phase 1-2만, Hybrid OFF)")
    print("=" * 80)
    baseline_results = test_scenario(
        enable_hybrid=False,
        test_name="기준선 (Phase 1-2)",
        test_queries=test_queries
    )

    # 2. Phase 3-4 테스트 (Hybrid ON)
    print("\n\n" + "=" * 80)
    print("2단계: Phase 3-4 테스트 (Hybrid ON)")
    print("=" * 80)
    phase34_results = test_scenario(
        enable_hybrid=True,
        test_name="Phase 3-4 적용",
        test_queries=test_queries
    )

    # 3. 결과 비교
    print("\n\n" + "=" * 80)
    print("결과 비교")
    print("=" * 80)

    baseline_stats = calculate_statistics(baseline_results)
    phase34_stats = calculate_statistics(phase34_results)

    print("\n[기준선 (Hybrid OFF)]")
    print(f"  - 성공률: {baseline_stats['success_rate']:.1f}%")
    print(f"  - 평균 신뢰도: {baseline_stats['avg_confidence']:.1f}%")
    print(f"  - 평균 응답 시간: {baseline_stats['avg_time']:.2f}초")
    print(f"  - 평균 출처 개수: {baseline_stats['avg_sources']:.1f}개")

    print("\n[Phase 3-4 (Hybrid ON)]")
    print(f"  - 성공률: {phase34_stats['success_rate']:.1f}%")
    print(f"  - 평균 신뢰도: {phase34_stats['avg_confidence']:.1f}%")
    print(f"  - 평균 응답 시간: {phase34_stats['avg_time']:.2f}초")
    print(f"  - 평균 출처 개수: {phase34_stats['avg_sources']:.1f}개")

    print("\n[성능 향상]")
    if baseline_stats['success_rate'] > 0:
        confidence_improvement = ((phase34_stats['avg_confidence'] - baseline_stats['avg_confidence'])
                                  / baseline_stats['avg_confidence'] * 100)
        time_change = ((phase34_stats['avg_time'] - baseline_stats['avg_time'])
                      / baseline_stats['avg_time'] * 100)

        print(f"  - 신뢰도 변화: {confidence_improvement:+.1f}%")
        print(f"  - 응답 시간 변화: {time_change:+.1f}%")
    else:
        print("  - 기준선 테스트 실패로 비교 불가")

    # 4. 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"test_results/performance_comparison_{timestamp}.json"

    os.makedirs("test_results", exist_ok=True)

    comparison_data = {
        "timestamp": timestamp,
        "test_queries": test_queries,
        "baseline": {
            "results": baseline_results,
            "statistics": baseline_stats
        },
        "phase34": {
            "results": phase34_results,
            "statistics": phase34_stats
        }
    }

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(comparison_data, f, ensure_ascii=False, indent=2)

    print(f"\n[INFO] 결과 저장: {result_file}")

    print("\n" + "=" * 80)
    print("테스트 완료!")
    print("=" * 80)

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARN] 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
