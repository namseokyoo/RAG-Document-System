#!/usr/bin/env python3
"""
Diversity Penalty 결과 분석 스크립트
Day 2 Phase 5: 다양성 개선 분석
"""

from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()  # Windows 터미널 한글 출력 설정

import json
from collections import Counter
from pathlib import Path

def analyze_diversity(summary_path):
    """Summary 파일에서 diversity 지표 추출"""
    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = data.get("test_results", [])  # 수정: "results" -> "test_results"

    # 통계 수집
    unique_docs_list = []
    diversity_ratios = []
    source_distributions = []

    for result in results:
        citation = result.get("citation", {})  # 수정: metadata -> citation

        # 사용된 문서 추출 (citation.sources에서 file_name 추출)
        file_names = []
        sources = citation.get("sources", [])
        for source in sources:
            file_name = source.get("file_name", "")
            if file_name:
                file_names.append(file_name)

        if file_names:
            # 고유 문서 수
            unique_files = len(set(file_names))
            unique_docs_list.append(unique_files)

            # Diversity ratio
            diversity_ratio = unique_files / len(file_names)
            diversity_ratios.append(diversity_ratio)

            # Source distribution
            source_dist = dict(Counter(file_names))
            source_distributions.append(source_dist)

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
        "total_tests": len(results),
        "unique_docs_distribution": Counter(unique_docs_list),
        "source_distributions": source_distributions
    }


def main():
    """메인 분석 함수"""
    print("="*80)
    print("Diversity Penalty 결과 분석 (Day 2, Phase 5)")
    print("="*80)

    # 두 Summary 파일 분석
    comprehensive_path = Path("test_logs_comprehensive_full/test_summary_full.json")
    balanced_path = Path("test_logs_balanced/test_summary_balanced.json")

    if not comprehensive_path.exists():
        print(f"\n[ERROR] {comprehensive_path} 파일이 없습니다.")
        return

    if not balanced_path.exists():
        print(f"\n[ERROR] {balanced_path} 파일이 없습니다.")
        return

    # Comprehensive 테스트 분석
    print("\n" + "="*80)
    print("[1] Comprehensive Test (35 tests)")
    print("="*80)

    comp_results = analyze_diversity(comprehensive_path)

    print(f"\n평균 고유 문서 수: {comp_results['avg_unique_docs']:.2f}")
    print(f"평균 Diversity Ratio: {comp_results['avg_diversity_ratio']:.2%}")
    print(f"Multi-doc 테스트 수: {comp_results['multi_doc_tests']}/{comp_results['total_tests']} ({comp_results['multi_doc_ratio']:.1%})")

    print(f"\n고유 문서 수 분포:")
    for docs, count in sorted(comp_results['unique_docs_distribution'].items()):
        percentage = (count / comp_results['total_tests']) * 100
        bar = "#" * int(percentage / 5)
        print(f"  {docs}개 문서: {count:2d}회 ({percentage:5.1f}%) {bar}")

    # Balanced 테스트 분석
    print("\n" + "="*80)
    print("[2] Balanced Test (20 tests)")
    print("="*80)

    bal_results = analyze_diversity(balanced_path)

    print(f"\n평균 고유 문서 수: {bal_results['avg_unique_docs']:.2f}")
    print(f"평균 Diversity Ratio: {bal_results['avg_diversity_ratio']:.2%}")
    print(f"Multi-doc 테스트 수: {bal_results['multi_doc_tests']}/{bal_results['total_tests']} ({bal_results['multi_doc_ratio']:.1%})")

    print(f"\n고유 문서 수 분포:")
    for docs, count in sorted(bal_results['unique_docs_distribution'].items()):
        percentage = (count / bal_results['total_tests']) * 100
        bar = "#" * int(percentage / 5)
        print(f"  {docs}개 문서: {count:2d}회 ({percentage:5.1f}%) {bar}")

    # 전체 통계 (Comprehensive + Balanced)
    print("\n" + "="*80)
    print("[3] Overall Statistics (55 tests total)")
    print("="*80)

    total_tests = comp_results['total_tests'] + bal_results['total_tests']
    total_unique_docs = (comp_results['avg_unique_docs'] * comp_results['total_tests'] +
                         bal_results['avg_unique_docs'] * bal_results['total_tests']) / total_tests
    total_diversity_ratio = (comp_results['avg_diversity_ratio'] * comp_results['total_tests'] +
                             bal_results['avg_diversity_ratio'] * bal_results['total_tests']) / total_tests
    total_multi_doc = comp_results['multi_doc_tests'] + bal_results['multi_doc_tests']
    total_multi_doc_ratio = total_multi_doc / total_tests

    print(f"\n총 테스트 수: {total_tests}")
    print(f"평균 고유 문서 수: {total_unique_docs:.2f}")
    print(f"평균 Diversity Ratio: {total_diversity_ratio:.2%}")
    print(f"Multi-doc 테스트 수: {total_multi_doc}/{total_tests} ({total_multi_doc_ratio:.1%})")

    # Day 1 목표 대비 비교
    print("\n" + "="*80)
    print("[4] Day 1 목표 대비 달성률")
    print("="*80)

    print(f"\n[목표 1] 평균 고유 문서 수 >= 3.0")
    print(f"  현재: {total_unique_docs:.2f} / 목표: 3.0")
    if total_unique_docs >= 3.0:
        print(f"  [OK] 달성! (+{((total_unique_docs/1.0-1)*100):.1f}% from baseline 1.0)")
    elif total_unique_docs >= 2.5:
        print(f"  [WARN] 보수적 목표 달성 (+{((total_unique_docs/1.0-1)*100):.1f}% from baseline 1.0)")
    else:
        print(f"  [TODO] 미달성 (+{((total_unique_docs/1.0-1)*100):.1f}% from baseline 1.0)")

    print(f"\n[목표 2] Diversity Ratio >= 0.70")
    print(f"  현재: {total_diversity_ratio:.2%} / 목표: 70.0%")
    if total_diversity_ratio >= 0.70:
        print(f"  [OK] 달성! (+{((total_diversity_ratio/0.23-1)*100):.1f}% from baseline 23%)")
    elif total_diversity_ratio >= 0.50:
        print(f"  [WARN] 보수적 목표 달성 (+{((total_diversity_ratio/0.23-1)*100):.1f}% from baseline 23%)")
    else:
        print(f"  [TODO] 미달성 (+{((total_diversity_ratio/0.23-1)*100):.1f}% from baseline 23%)")

    print(f"\n[목표 3] Multi-doc 테스트 비율 >= 80%")
    print(f"  현재: {total_multi_doc_ratio:.1%} / 목표: 80.0%")
    if total_multi_doc_ratio >= 0.80:
        print(f"  [OK] 달성! (baseline 0% → {total_multi_doc_ratio:.1%})")
    elif total_multi_doc_ratio >= 0.50:
        print(f"  [WARN] 부분 달성 (baseline 0% → {total_multi_doc_ratio:.1%})")
    else:
        print(f"  [TODO] 미달성")

    print("\n" + "="*80)
    print("분석 완료")
    print("="*80)

    # 결과 JSON 저장
    results_output = {
        "comprehensive": comp_results,
        "balanced": bal_results,
        "overall": {
            "total_tests": total_tests,
            "avg_unique_docs": total_unique_docs,
            "avg_diversity_ratio": total_diversity_ratio,
            "multi_doc_tests": total_multi_doc,
            "multi_doc_ratio": total_multi_doc_ratio
        }
    }

    output_path = Path("diversity_analysis_day2.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results_output, f, indent=2, ensure_ascii=False)

    print(f"\n결과 저장: {output_path}")


if __name__ == "__main__":
    main()
