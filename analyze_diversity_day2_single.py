#!/usr/bin/env python3
"""
Day 2 Diversity Penalty 단일 테스트 결과 분석
diversity_penalty=0.3 적용 결과 분석
"""

import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
from collections import Counter
from pathlib import Path

def analyze_diversity(summary_path):
    """Summary 파일에서 diversity 지표 추출"""
    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # detailed_results 사용
    results = data.get("detailed_results", [])

    if not results:
        print("[ERROR] detailed_results가 비어있습니다.")
        return None

    # 성공한 테스트만 필터링
    success_results = [r for r in results if r.get('success', False)]

    # 통계 수집
    unique_docs_list = []
    diversity_ratios = []
    source_distributions = []

    for result in success_results:
        sources_count = result.get("sources_count", 0)
        unique_sources_count = result.get("unique_sources_count", 0)

        if sources_count > 0:
            unique_docs_list.append(unique_sources_count)
            diversity_ratio = unique_sources_count / sources_count
            diversity_ratios.append(diversity_ratio)

    # 평균 계산
    avg_unique_docs = sum(unique_docs_list) / len(unique_docs_list) if unique_docs_list else 0
    avg_diversity_ratio = sum(diversity_ratios) / len(diversity_ratios) if diversity_ratios else 0

    # Multi-doc 테스트 비율 (2개 이상 문서 사용)
    multi_doc_tests = sum(1 for u in unique_docs_list if u >= 2)
    multi_doc_ratio = multi_doc_tests / len(unique_docs_list) if unique_docs_list else 0

    return {
        "avg_unique_docs": avg_unique_docs,
        "avg_diversity_ratio": avg_diversity_ratio,
        "multi_doc_tests": multi_doc_tests,
        "multi_doc_ratio": multi_doc_ratio,
        "total_tests": len(success_results),
        "unique_docs_distribution": Counter(unique_docs_list),
        "unique_docs_list": unique_docs_list
    }


def main():
    """메인 분석 함수"""
    print("="*80)
    print("Day 2 Diversity Penalty 검증 결과 분석")
    print("="*80)
    print("\n테스트 설정:")
    print("  - diversity_penalty: 0.3")
    print("  - diversity_source_key: source")
    print("  - LLM: gpt-4o-mini (OpenAI)")
    print("  - Test suite: Comprehensive (35 tests)")

    # Summary 파일 분석
    summary_path = Path("test_summary_diversity_day2_comprehensive.json")

    if not summary_path.exists():
        print(f"\n[ERROR] {summary_path} 파일이 없습니다.")
        return

    print("\n" + "="*80)
    print("Diversity Penalty 적용 결과 (penalty=0.3)")
    print("="*80)

    results = analyze_diversity(summary_path)

    if not results:
        return

    print(f"\n✓ 총 테스트 수: {results['total_tests']}개")
    print(f"\n[지표 1] 평균 고유 문서 수")
    print(f"  현재 값: {results['avg_unique_docs']:.2f}개")
    print(f"  목표: >= 2.5개 (보수적) / >= 3.0개 (이상적)")

    if results['avg_unique_docs'] >= 3.0:
        print(f"  상태: ✓ 이상적 목표 달성!")
    elif results['avg_unique_docs'] >= 2.5:
        print(f"  상태: ✓ 보수적 목표 달성")
    else:
        print(f"  상태: ✗ 목표 미달")

    print(f"\n[지표 2] Diversity Ratio (고유 문서 / 전체 문서)")
    print(f"  현재 값: {results['avg_diversity_ratio']:.1%}")
    print(f"  목표: >= 50% (보수적) / >= 70% (이상적)")

    if results['avg_diversity_ratio'] >= 0.70:
        print(f"  상태: ✓ 이상적 목표 달성!")
    elif results['avg_diversity_ratio'] >= 0.50:
        print(f"  상태: ✓ 보수적 목표 달성")
    else:
        print(f"  상태: ✗ 목표 미달")

    print(f"\n[지표 3] Multi-doc 테스트 비율 (2개 이상 문서 사용)")
    print(f"  현재 값: {results['multi_doc_tests']}/{results['total_tests']} ({results['multi_doc_ratio']:.1%})")
    print(f"  목표: >= 60% (보수적) / >= 80% (이상적)")

    if results['multi_doc_ratio'] >= 0.80:
        print(f"  상태: ✓ 이상적 목표 달성!")
    elif results['multi_doc_ratio'] >= 0.60:
        print(f"  상태: ✓ 보수적 목표 달성")
    else:
        print(f"  상태: ✗ 목표 미달")

    print(f"\n[상세 분포] 고유 문서 수별 테스트 분포:")
    for docs, count in sorted(results['unique_docs_distribution'].items()):
        percentage = (count / results['total_tests']) * 100
        bar = "█" * int(percentage / 2)
        print(f"  {docs}개 문서: {count:2d}회 ({percentage:5.1f}%) {bar}")

    # 최종 판정
    print("\n" + "="*80)
    print("최종 판정")
    print("="*80)

    goals_met = 0
    if results['avg_unique_docs'] >= 2.5:
        goals_met += 1
    if results['avg_diversity_ratio'] >= 0.50:
        goals_met += 1
    if results['multi_doc_ratio'] >= 0.60:
        goals_met += 1

    print(f"\n달성한 보수적 목표: {goals_met}/3")

    if goals_met == 3:
        print("\n✓✓✓ Day 2 검증 완료!")
        print("diversity_penalty=0.3 설정이 모든 보수적 목표를 달성했습니다.")
        print("다음 단계: Phase 3 Day 3 (회귀 테스트 및 성능 벤치마킹)")
    elif goals_met >= 2:
        print("\n✓✓ Day 2 부분 성공")
        print("대부분의 목표를 달성했으나, 일부 조정이 필요할 수 있습니다.")
    else:
        print("\n✗ Day 2 목표 미달")
        print("diversity_penalty 값 조정이 필요합니다.")

    # Day 2 Completion Report 기준 비교
    print("\n" + "="*80)
    print("Day 2 Completion Report 비교 (2025-11-08 기준)")
    print("="*80)
    print("\n이전 결과 (DAY2_COMPLETION_REPORT.md):")
    print("  - 평균 고유 문서: 2.51개")
    print("  - Diversity Ratio: 57%")
    print("  - Multi-doc 비율: 88.2%")

    print("\n현재 결과 (실제 테스트):")
    print(f"  - 평균 고유 문서: {results['avg_unique_docs']:.2f}개")
    print(f"  - Diversity Ratio: {results['avg_diversity_ratio']:.1%}")
    print(f"  - Multi-doc 비율: {results['multi_doc_ratio']:.1%}")

    # 변화율 계산
    prev_unique = 2.51
    prev_diversity = 0.57
    prev_multi_doc = 0.882

    change_unique = ((results['avg_unique_docs'] - prev_unique) / prev_unique) * 100
    change_diversity = ((results['avg_diversity_ratio'] - prev_diversity) / prev_diversity) * 100
    change_multi_doc = ((results['multi_doc_ratio'] - prev_multi_doc) / prev_multi_doc) * 100

    print("\n변화율:")
    print(f"  - 평균 고유 문서: {change_unique:+.1f}%")
    print(f"  - Diversity Ratio: {change_diversity:+.1f}%")
    print(f"  - Multi-doc 비율: {change_multi_doc:+.1f}%")

    print("\n" + "="*80)

    # 결과 JSON 저장
    output_data = {
        "test_date": "2025-11-12",
        "config": {
            "diversity_penalty": 0.3,
            "diversity_source_key": "source",
            "llm": "gpt-4o-mini"
        },
        "results": results,
        "comparison_with_day2_report": {
            "previous": {
                "avg_unique_docs": prev_unique,
                "diversity_ratio": prev_diversity,
                "multi_doc_ratio": prev_multi_doc
            },
            "current": {
                "avg_unique_docs": results['avg_unique_docs'],
                "diversity_ratio": results['avg_diversity_ratio'],
                "multi_doc_ratio": results['multi_doc_ratio']
            },
            "change": {
                "avg_unique_docs_pct": change_unique,
                "diversity_ratio_pct": change_diversity,
                "multi_doc_ratio_pct": change_multi_doc
            }
        },
        "goals_met": goals_met,
        "verdict": "PASS" if goals_met == 3 else ("PARTIAL" if goals_met >= 2 else "FAIL")
    }

    output_path = Path("diversity_analysis_day2_verification.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"분석 결과 저장: {output_path}")


if __name__ == "__main__":
    main()
