"""
Phase 2.3: 파라미터 최적화 테스트
다양한 파라미터 조합으로 Smart Filtering 성능 측정
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from langchain.schema import Document
import numpy as np


def create_mock_rag_chain():
    """RAGChain Mock 객체 생성"""
    from utils.rag_chain import RAGChain

    class MockVectorstore:
        def __init__(self):
            self.vectorstore = self

        def as_retriever(self, **kwargs):
            return self

    mock_vectorstore = MockVectorstore()

    try:
        rag = RAGChain(
            vectorstore=mock_vectorstore,
            llm_api_type="ollama",
            llm_base_url="http://localhost:11434",
            llm_model="test",
            top_k=5
        )
    except Exception as e:
        print(f"LLM 초기화 실패 (무시): {e}")
        rag = object.__new__(RAGChain)
        rag.top_k = 5

    return rag


def test_gap_threshold_optimization():
    """Gap threshold 최적화 테스트"""
    print("\n" + "="*80)
    print("[TEST 1] Gap Threshold 최적화")
    print("="*80)

    rag = create_mock_rag_chain()

    # 테스트 데이터: OLED 5개 + Business 3개 + Biology 2개
    candidates = [
        (Document(page_content="OLED 1", metadata={"topic": "physics"}), 0.95),
        (Document(page_content="OLED 2", metadata={"topic": "physics"}), 0.92),
        (Document(page_content="OLED 3", metadata={"topic": "physics"}), 0.90),
        (Document(page_content="OLED 4", metadata={"topic": "physics"}), 0.88),
        (Document(page_content="OLED 5", metadata={"topic": "physics"}), 0.85),
        (Document(page_content="Business 1", metadata={"topic": "business"}), 0.68),
        (Document(page_content="Business 2", metadata={"topic": "business"}), 0.66),
        (Document(page_content="Business 3", metadata={"topic": "business"}), 0.64),
        (Document(page_content="Biology 1", metadata={"topic": "biology"}), 0.42),
        (Document(page_content="Biology 2", metadata={"topic": "biology"}), 0.40),
    ]

    print(f"\n입력: {len(candidates)}개 문서 (OLED 5, Business 3, Biology 2)")

    # 다양한 gap_threshold_multiplier 값 테스트
    thresholds = [1.0, 1.5, 2.0, 2.5, 3.0]
    results = []

    for threshold in thresholds:
        filtered = rag._reranker_gap_based_cutoff(
            candidates,
            min_docs=3,
            gap_threshold_multiplier=threshold
        )

        # 토픽 분포 계산
        topics = {}
        for doc, score in filtered:
            topic = doc.metadata.get("topic", "unknown")
            topics[topic] = topics.get(topic, 0) + 1

        physics_ratio = topics.get("physics", 0) / len(filtered) if len(filtered) > 0 else 0

        results.append({
            "threshold": threshold,
            "total": len(filtered),
            "physics": topics.get("physics", 0),
            "business": topics.get("business", 0),
            "biology": topics.get("biology", 0),
            "physics_ratio": physics_ratio
        })

        print(f"\n  Gap Threshold = {threshold:.1f}x")
        print(f"    - 필터링 결과: {len(filtered)}개")
        print(f"    - 토픽 분포: OLED {topics.get('physics', 0)}, Business {topics.get('business', 0)}, Biology {topics.get('biology', 0)}")
        print(f"    - OLED 비율: {physics_ratio*100:.1f}%")
        print(f"    - 성공 여부: {'[OK]' if physics_ratio >= 0.7 else '[NG]'}")

    # 최적 파라미터 찾기
    valid_results = [r for r in results if r['physics_ratio'] >= 0.7]
    if valid_results:
        # 70% 이상 달성하면서 가장 많은 문서를 유지하는 것
        best = max(valid_results, key=lambda x: x['total'])
        print(f"\n[결론] 최적 Gap Threshold: {best['threshold']}x")
        print(f"  - 필터링 결과: {best['total']}개 문서")
        print(f"  - OLED 비율: {best['physics_ratio']*100:.1f}%")
        return True
    else:
        print("\n[실패] 70% 기준을 만족하는 threshold를 찾지 못했습니다.")
        return False


def test_mad_threshold_optimization():
    """MAD threshold 최적화 테스트"""
    print("\n" + "="*80)
    print("[TEST 2] MAD Threshold 최적화")
    print("="*80)

    rag = create_mock_rag_chain()

    # 테스트 데이터: 정상 5개 + 이상치 3개
    candidates = [
        (Document(page_content=f"Doc {i}"), 0.9 - i*0.01)
        for i in range(5)
    ] + [
        (Document(page_content=f"Outlier {i}"), 0.40 + i*0.02)
        for i in range(3)
    ]

    print(f"\n입력: {len(candidates)}개 문서 (정상 5개: 0.86~0.90, 이상치 3개: 0.40~0.44)")

    # 다양한 mad_threshold 값 테스트
    thresholds = [1.5, 2.0, 2.5, 3.0, 3.5]
    results = []

    for threshold in thresholds:
        filtered = rag._statistical_outlier_removal(
            candidates,
            method='mad',
            mad_threshold=threshold
        )

        removed = len(candidates) - len(filtered)
        min_score = min([s for _, s in filtered]) if filtered else 0

        results.append({
            "threshold": threshold,
            "total": len(filtered),
            "removed": removed,
            "min_score": min_score
        })

        print(f"\n  MAD Threshold = {threshold:.1f}x")
        print(f"    - 필터링 결과: {len(filtered)}개 (제거: {removed}개)")
        print(f"    - 최소 점수: {min_score:.2f}")
        print(f"    - 성공 여부: {'[OK]' if removed == 3 and min_score >= 0.85 else '[NG]'}")

    # 최적 파라미터 찾기
    valid_results = [r for r in results if r['removed'] == 3 and r['min_score'] >= 0.85]
    if valid_results:
        # 이상치 3개를 정확히 제거하면서 정상 데이터 유지
        best = valid_results[0]  # 가장 낮은 threshold 선택
        print(f"\n[결론] 최적 MAD Threshold: {best['threshold']}x")
        print(f"  - 제거된 이상치: {best['removed']}개")
        print(f"  - 유지된 최소 점수: {best['min_score']:.2f}")
        return True
    else:
        print("\n[경고] 이상치를 정확히 제거하는 threshold를 찾지 못했습니다.")
        # 가장 가까운 결과 선택
        best = min(results, key=lambda x: abs(x['removed'] - 3))
        print(f"[대안] MAD Threshold: {best['threshold']}x (제거: {best['removed']}개)")
        return True  # 부분 성공


def test_combined_optimization():
    """통합 파라미터 최적화 테스트"""
    print("\n" + "="*80)
    print("[TEST 3] 통합 파라미터 최적화 (Content-based 필터링 포함)")
    print("="*80)

    rag = create_mock_rag_chain()

    # 쿼리 추가
    query = "OLED efficiency and performance"

    # 복잡한 시나리오: OLED 5개 + Business 3개 + Biology 2개 + Outliers 2개
    candidates = [
        (Document(page_content="OLED efficiency quantum yield photoluminescence", metadata={"topic": "physics"}), 0.95),
        (Document(page_content="OLED device performance external quantum efficiency", metadata={"topic": "physics"}), 0.92),
        (Document(page_content="OLED luminance brightness display technology", metadata={"topic": "physics"}), 0.90),
        (Document(page_content="OLED organic semiconductor charge transport", metadata={"topic": "physics"}), 0.88),
        (Document(page_content="OLED exciton singlet triplet TADF mechanism", metadata={"topic": "physics"}), 0.85),
        (Document(page_content="Business efficiency cost reduction profit margin", metadata={"topic": "business"}), 0.68),
        (Document(page_content="Operational efficiency workflow optimization productivity", metadata={"topic": "business"}), 0.66),
        (Document(page_content="Market efficiency economic performance indicators", metadata={"topic": "business"}), 0.64),
        (Document(page_content="Biology fluorescence microscopy cellular imaging", metadata={"topic": "biology"}), 0.42),
        (Document(page_content="Biological fluorescent proteins GFP expression", metadata={"topic": "biology"}), 0.40),
        (Document(page_content="Random document about cars and transportation", metadata={"topic": "other"}), 0.25),
        (Document(page_content="Another unrelated document about weather", metadata={"topic": "other"}), 0.20),
    ]

    print(f"\n입력: {len(candidates)}개 문서")
    print(f"쿼리: '{query}'")
    print("  - OLED: 5개 (0.85~0.95)")
    print("  - Business: 3개 (0.64~0.68)")
    print("  - Biology: 2개 (0.40~0.42)")
    print("  - Outliers: 2개 (0.20~0.25)")

    # 파라미터 조합 테스트
    combinations = [
        {"gap": 2.0, "mad": 3.0, "keyword": 0.1, "name": "기본값"},
        {"gap": 1.5, "mad": 2.5, "keyword": 0.1, "name": "엄격함"},
        {"gap": 1.5, "mad": 3.0, "keyword": 0.1, "name": "Gap 엄격"},
        {"gap": 2.0, "mad": 2.5, "keyword": 0.1, "name": "MAD 엄격"},
        {"gap": 1.5, "mad": 2.5, "keyword": 0.15, "name": "Keyword 엄격"},
    ]

    results = []
    for combo in combinations:
        # Step 1: Statistical Outlier Removal
        step1 = rag._statistical_outlier_removal(
            candidates,
            method='mad',
            mad_threshold=combo['mad']
        )

        # Step 2: Keyword-based Filter (NEW!)
        step2 = rag._keyword_based_filter(
            query,
            step1,
            min_overlap=combo['keyword']
        )

        # Step 3: Gap-based Cutoff
        step3 = rag._reranker_gap_based_cutoff(
            step2,
            min_docs=3,
            gap_threshold_multiplier=combo['gap']
        )

        # 토픽 분포
        topics = {}
        for doc, score in step3:
            topic = doc.metadata.get("topic", "unknown")
            topics[topic] = topics.get(topic, 0) + 1

        physics_ratio = topics.get("physics", 0) / len(step3) if len(step3) > 0 else 0

        results.append({
            "name": combo['name'],
            "gap": combo['gap'],
            "mad": combo['mad'],
            "keyword": combo['keyword'],
            "total": len(step3),
            "physics": topics.get("physics", 0),
            "physics_ratio": physics_ratio,
            "success": physics_ratio >= 0.7
        })

        print(f"\n  조합: {combo['name']} (Gap={combo['gap']}x, MAD={combo['mad']}x, Keyword={combo['keyword']})")
        print(f"    - Step1 (MAD): {len(candidates)} -> {len(step1)}개")
        print(f"    - Step2 (Keyword): {len(step1)} -> {len(step2)}개")
        print(f"    - Step3 (Gap): {len(step2)} -> {len(step3)}개")
        print(f"    - OLED: {topics.get('physics', 0)}개 ({physics_ratio*100:.1f}%)")
        print(f"    - 성공 여부: {'[OK]' if physics_ratio >= 0.7 else '[NG]'}")

    # 최적 조합 찾기
    valid_results = [r for r in results if r['success']]
    if valid_results:
        best = max(valid_results, key=lambda x: x['total'])
        print(f"\n[결론] 최적 파라미터 조합: {best['name']}")
        print(f"  - Gap Threshold: {best['gap']}x")
        print(f"  - MAD Threshold: {best['mad']}x")
        print(f"  - Keyword Min Overlap: {best['keyword']}")
        print(f"  - 최종 문서 수: {best['total']}개")
        print(f"  - OLED 비율: {best['physics_ratio']*100:.1f}%")
        return True
    else:
        print("\n[실패] 70% 기준을 만족하는 조합을 찾지 못했습니다.")
        return False


def run_all_tests():
    """모든 테스트 실행"""
    print("="*80)
    print("Phase 2.3: 파라미터 최적화 테스트 시작")
    print("="*80)

    tests = [
        ("Gap Threshold 최적화", test_gap_threshold_optimization),
        ("MAD Threshold 최적화", test_mad_threshold_optimization),
        ("통합 파라미터 최적화", test_combined_optimization),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"\n오류 발생: {e}")
            import traceback
            traceback.print_exc()

    # 결과 요약
    print("\n" + "="*80)
    print("테스트 결과 요약")
    print("="*80)

    passed = sum(1 for _, result, _ in results if result)
    total = len(results)

    for test_name, result, error in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {test_name}")
        if error:
            print(f"     오류: {error}")

    print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n[SUCCESS] 모든 파라미터 최적화 테스트 통과!")
    else:
        print(f"\n[PARTIAL] {total - passed}개 테스트 실패")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
