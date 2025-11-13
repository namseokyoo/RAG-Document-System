#!/usr/bin/env python3
"""
테스트 결과 분석 스크립트
로그 데이터를 분석하고 개선점을 도출
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict
import statistics


def load_test_summary(file_path: str) -> Dict:
    """테스트 요약 JSON 로드"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_response_times(logs: List[Dict]) -> Dict:
    """응답 시간 분석"""
    times = [log['total']['elapsed_time'] for log in logs]
    times_sorted = sorted(times)

    # 질문 유형별 응답 시간
    times_by_type = defaultdict(list)
    for log in logs:
        q_type = log['classification']['type']
        times_by_type[q_type].append(log['total']['elapsed_time'])

    return {
        "overall": {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0,
            "min": min(times),
            "max": max(times),
            "p95": times_sorted[int(len(times) * 0.95)],
            "p99": times_sorted[int(len(times) * 0.99)] if len(times) > 1 else max(times)
        },
        "by_type": {
            q_type: {
                "mean": statistics.mean(times_list),
                "median": statistics.median(times_list),
                "count": len(times_list)
            }
            for q_type, times_list in times_by_type.items()
        }
    }


def analyze_classification_accuracy(logs: List[Dict]) -> Dict:
    """분류기 정확도 분석"""
    classifications = defaultdict(int)
    confidences = []

    for log in logs:
        q_type = log['classification']['type']
        confidence = log['classification']['confidence']
        classifications[q_type] += 1
        confidences.append(confidence)

    return {
        "distribution": dict(classifications),
        "confidence": {
            "mean": statistics.mean(confidences),
            "median": statistics.median(confidences),
            "min": min(confidences),
            "max": max(confidences)
        }
    }


def generate_simple_report(summary: Dict, output_file: str = "TEST_ANALYSIS.md"):
    """간단한 분석 보고서 생성"""

    logs = summary['test_results']

    # 기본 분석
    response_time_analysis = analyze_response_times(logs)
    classification_analysis = analyze_classification_accuracy(logs)

    # 보고서 생성
    report = f"""# RAG 시스템 테스트 분석 보고서 (간단 버전)

**생성일**: {summary['timestamp']}
**총 테스트**: {summary['total_tests']}개

---

## 1. 응답 시간 분석

- **평균**: {response_time_analysis['overall']['mean']:.2f}초
- **중앙값**: {response_time_analysis['overall']['median']:.2f}초
- **최소/최대**: {response_time_analysis['overall']['min']:.2f}초 / {response_time_analysis['overall']['max']:.2f}초

### 질문 유형별
"""

    for q_type, data in response_time_analysis['by_type'].items():
        report += f"\n- **{q_type}**: 평균 {data['mean']:.2f}초 ({data['count']}개)"

    report += f"""

---

## 2. 질문 분류 분석

"""

    for q_type, count in classification_analysis['distribution'].items():
        percentage = count / summary['total_tests'] * 100
        report += f"- **{q_type}**: {count}개 ({percentage:.1f}%)\n"

    report += f"""
**분류 신뢰도 평균**: {classification_analysis['confidence']['mean']:.2f}

---

## 3. 다음 단계

1. 전체 테스트 실행 (실제 RAGChain 연동)
2. 상세 분석 실행
3. 개선 사항 구현
"""

    # 파일 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"[INFO] 분석 보고서 저장: {output_file}")
    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="테스트 결과 분석")
    parser.add_argument(
        "--input",
        required=True,
        help="테스트 요약 JSON 파일"
    )
    parser.add_argument(
        "--output",
        default="TEST_ANALYSIS.md",
        help="분석 보고서 출력 파일"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("테스트 결과 분석 시작")
    print("=" * 60)

    # 요약 로드
    print(f"\n테스트 결과 로드 중: {args.input}")
    summary = load_test_summary(args.input)
    print(f"총 테스트: {summary['total_tests']}개")

    # 보고서 생성
    print(f"\n분석 보고서 생성 중: {args.output}")
    generate_simple_report(summary, args.output)

    print("\n분석 완료!")


if __name__ == "__main__":
    main()
