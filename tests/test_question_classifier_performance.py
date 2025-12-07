"""
Question Classifier 성능 테스트

Phase 1 검증:
- 2. 100개 질문으로 정확도 테스트
- 3. LLM 호출 비율 측정 (목표: <30%)
- 4. 응답시간 벤치마크
"""

import time
import json
from typing import List, Dict
from utils.question_classifier import QuestionClassifier, create_classifier


# ============ 테스트 질문 세트 ============

def generate_test_questions() -> List[Dict]:
    """100개 테스트 질문 생성"""

    questions = []

    # === Simple 질문 (30개) ===
    simple_questions = [
        "kFRET 값은?",
        "EQE는 얼마인가?",
        "수명은?",
        "IQE 값은?",
        "3페이지 내용은?",
        "PLQY는?",
        "효율 수치는?",
        "전압은?",
        "전류 밀도는?",
        "파장은?",
        "색좌표는?",
        "CRI 값은?",
        "발광 파장은?",
        "피크 파장은?",
        "반치폭은?",
        "5페이지 요약해줘",
        "제목은?",
        "저자는?",
        "발행일은?",
        "키워드는?",
        "온도는?",
        "농도는?",
        "두께는?",
        "밀도는?",
        "굴절률은?",
        "투과율은?",
        "반사율은?",
        "흡광도는?",
        "양자효율은?",
        "결과 수치는?",
    ]

    for q in simple_questions:
        questions.append({
            "question": q,
            "expected_type": "simple",
            "expected_multi_query": False,
            "expected_tokens_range": (400, 600),
        })

    # === Normal 질문 (40개) ===
    normal_questions = [
        "OLED 효율은?",
        "TADF 메커니즘은?",
        "작동 원리는?",
        "합성 방법은?",
        "측정 방법은?",
        "제작 공정은?",
        "특성은?",
        "장점은?",
        "단점은?",
        "적용 분야는?",
        "연구 배경은?",
        "목적은?",
        "의의는?",
        "한계는?",
        "과제는?",
        "전망은?",
        "트렌드는?",
        "발전 방향은?",
        "개선 방안은?",
        "최적화 방법은?",
        "구조를 설명해줘",
        "원리를 설명해줘",
        "특징을 설명해줘",
        "과정을 설명해줘",
        "방법을 설명해줘",
        "이유는 무엇인가?",
        "의미는 무엇인가?",
        "목적은 무엇인가?",
        "정의는 무엇인가?",
        "개념은 무엇인가?",
        "어떻게 작동하는가?",
        "어떻게 측정하는가?",
        "어떻게 제작하는가?",
        "어떻게 개선하는가?",
        "어떤 특성이 있는가?",
        "어떤 장점이 있는가?",
        "어떤 응용이 있는가?",
        "왜 사용하는가?",
        "왜 중요한가?",
        "언제 사용하는가?",
    ]

    for q in normal_questions:
        questions.append({
            "question": q,
            "expected_type": "normal",
            "expected_multi_query": False,
            "expected_tokens_range": (900, 1200),
        })

    # === Complex 질문 (20개) ===
    complex_questions = [
        "OLED와 QLED의 효율을 비교해줘",
        "TADF와 Phosphorescence의 차이는?",
        "효율과 수명의 관계를 분석해줘",
        "구조가 성능에 미치는 영향은?",
        "온도가 효율에 미치는 영향은?",
        "농도가 발광에 미치는 영향은?",
        "호스트와 도펀트의 관계는?",
        "에너지 전달 메커니즘을 분석해줘",
        "A와 B 재료의 특성을 비교해줘",
        "1세대와 2세대의 차이점은?",
        "청색과 녹색 소자를 비교해줘",
        "솔루션과 진공 공정의 장단점은?",
        "내부 효율과 외부 효율의 관계는?",
        "발광 효율과 전력 효율을 비교해줘",
        "형광과 인광의 차이를 분석해줘",
        "구조적 특징과 광학적 특성의 상관관계는?",
        "합성 온도가 결정성에 미치는 영향을 평가해줘",
        "도핑 농도와 색순도의 트레이드오프는?",
        "두 재료의 에너지 레벨을 비교 분석해줘",
        "공정 조건이 소자 성능에 미치는 영향을 종합적으로 분석해줘",
    ]

    for q in complex_questions:
        questions.append({
            "question": q,
            "expected_type": "complex",
            "expected_multi_query": True,
            "expected_tokens_range": (1800, 2200),
        })

    # === Exhaustive 질문 (10개) ===
    exhaustive_questions = [
        "모든 슬라이드의 제목을 나열해줘",
        "전체 페이지의 그림을 나열해줘",
        "모든 표를 나열해줘",
        "전체 참고문헌을 나열해줘",
        "각각의 실험 결과를 나열해줘",
        "모든 재료를 나열해줘",
        "전체 공정 단계를 나열해줘",
        "모든 측정 데이터를 리스트로 보여줘",
        "전부 요약해줘",
        "각 장의 핵심 내용을 모두 나열해줘",
    ]

    for q in exhaustive_questions:
        questions.append({
            "question": q,
            "expected_type": "exhaustive",
            "expected_multi_query": False,
            "expected_tokens_range": (1800, 2200),
        })

    return questions


# ============ 테스트 실행 ============

def run_classifier_test(use_llm: bool = True):
    """분류기 성능 테스트"""

    print("=" * 80)
    print("Question Classifier 성능 테스트")
    print("=" * 80)
    print(f"LLM 사용: {use_llm}")
    print()

    # 분류기 초기화
    classifier = create_classifier(llm=None, use_llm=use_llm, verbose=False)

    # 테스트 질문 로드
    test_questions = generate_test_questions()
    print(f"테스트 질문 수: {len(test_questions)}")
    print(f"  - Simple: {sum(1 for q in test_questions if q['expected_type']=='simple')}")
    print(f"  - Normal: {sum(1 for q in test_questions if q['expected_type']=='normal')}")
    print(f"  - Complex: {sum(1 for q in test_questions if q['expected_type']=='complex')}")
    print(f"  - Exhaustive: {sum(1 for q in test_questions if q['expected_type']=='exhaustive')}")
    print()

    # 통계 변수
    total_time = 0
    correct_type = 0
    correct_multi_query = 0
    correct_tokens = 0

    type_confusion = {
        "simple": {"simple": 0, "normal": 0, "complex": 0, "exhaustive": 0},
        "normal": {"simple": 0, "normal": 0, "complex": 0, "exhaustive": 0},
        "complex": {"simple": 0, "normal": 0, "complex": 0, "exhaustive": 0},
        "exhaustive": {"simple": 0, "normal": 0, "complex": 0, "exhaustive": 0},
    }

    results = []

    # 테스트 실행
    for i, test_case in enumerate(test_questions, 1):
        question = test_case["question"]
        expected_type = test_case["expected_type"]
        expected_multi_query = test_case["expected_multi_query"]
        expected_tokens_range = test_case["expected_tokens_range"]

        # 분류 실행
        start_time = time.time()
        classification = classifier.classify(question)
        elapsed_time = time.time() - start_time

        total_time += elapsed_time

        # 결과 분석
        actual_type = classification["type"]
        actual_multi_query = classification["multi_query"]
        actual_tokens = classification["max_tokens"]

        # 정확도 체크
        type_match = (actual_type == expected_type)
        multi_query_match = (actual_multi_query == expected_multi_query)
        tokens_match = (expected_tokens_range[0] <= actual_tokens <= expected_tokens_range[1])

        if type_match:
            correct_type += 1
        if multi_query_match:
            correct_multi_query += 1
        if tokens_match:
            correct_tokens += 1

        # Confusion matrix
        type_confusion[expected_type][actual_type] += 1

        # 결과 저장
        results.append({
            "question": question,
            "expected_type": expected_type,
            "actual_type": actual_type,
            "type_match": type_match,
            "multi_query_match": multi_query_match,
            "tokens_match": tokens_match,
            "method": classification["method"],
            "confidence": classification["confidence"],
            "elapsed_time": elapsed_time,
        })

        # 진행 상황 출력 (10개마다)
        if i % 10 == 0:
            print(f"[{i}/{len(test_questions)}] 진행 중... (평균 {total_time/i:.3f}초/질문)")

    # 결과 분석
    print("\n" + "=" * 80)
    print("테스트 결과")
    print("=" * 80)

    # 1. 정확도
    type_accuracy = correct_type / len(test_questions) * 100
    multi_query_accuracy = correct_multi_query / len(test_questions) * 100
    tokens_accuracy = correct_tokens / len(test_questions) * 100

    print(f"\n[정확도]")
    print(f"  - 질문 유형 분류: {correct_type}/{len(test_questions)} ({type_accuracy:.1f}%)")
    print(f"  - Multi-Query 판단: {correct_multi_query}/{len(test_questions)} ({multi_query_accuracy:.1f}%)")
    print(f"  - Max Tokens 범위: {correct_tokens}/{len(test_questions)} ({tokens_accuracy:.1f}%)")

    # 2. LLM 호출 비율
    classifier.print_stats()

    # 3. 응답시간
    avg_time = total_time / len(test_questions) * 1000  # ms
    print(f"\n[평균 응답시간]")
    print(f"  {avg_time:.1f}ms")

    # 4. Confusion Matrix
    print(f"\n[Confusion Matrix (예상 -> 실제)]")
    print(f"{'':>12} {'simple':>10} {'normal':>10} {'complex':>10} {'exhaustive':>10}")
    for expected in ["simple", "normal", "complex", "exhaustive"]:
        row = f"{expected:>12}"
        for actual in ["simple", "normal", "complex", "exhaustive"]:
            count = type_confusion[expected][actual]
            row += f" {count:>10}"
        print(row)

    # 5. 유형별 정확도
    print(f"\n[유형별 정확도]")
    for q_type in ["simple", "normal", "complex", "exhaustive"]:
        total = sum(type_confusion[q_type].values())
        correct = type_confusion[q_type][q_type]
        accuracy = correct / total * 100 if total > 0 else 0
        print(f"  - {q_type:>12}: {correct}/{total} ({accuracy:.1f}%)")

    # 6. 오분류 케이스
    print(f"\n[오분류 케이스 (상위 10개)]")
    misclassified = [r for r in results if not r["type_match"]]
    for i, case in enumerate(misclassified[:10], 1):
        print(f"{i}. \"{case['question'][:40]}...\"")
        print(f"   예상: {case['expected_type']}, 실제: {case['actual_type']}, "
              f"방법: {case['method']}, 신뢰도: {case['confidence']:.0%}")

    # 7. 결과 저장
    report = {
        "summary": {
            "total_questions": len(test_questions),
            "type_accuracy": type_accuracy,
            "multi_query_accuracy": multi_query_accuracy,
            "tokens_accuracy": tokens_accuracy,
            "avg_time_ms": avg_time,
            "llm_usage_rate": classifier.stats["llm_used"] / classifier.stats["total"] * 100,
        },
        "confusion_matrix": type_confusion,
        "stats": classifier.stats,
        "results": results,
    }

    with open("test_classifier_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n[상세 결과 저장]")
    print(f"  test_classifier_report.json")

    # 8. 목표 달성 여부
    print(f"\n[Phase 1 목표 달성]")
    print(f"  [OK] 100개 질문 테스트: 완료 ({len(test_questions)}개)")

    llm_rate = classifier.stats["llm_used"] / classifier.stats["total"] * 100
    llm_target = llm_rate < 30
    print(f"  [{'OK' if llm_target else 'FAIL'}] LLM 호출 <30%: {llm_rate:.1f}% ({'달성' if llm_target else '미달성'})")

    type_target = type_accuracy >= 80
    print(f"  [{'OK' if type_target else 'FAIL'}] 유형 분류 >80%: {type_accuracy:.1f}% ({'달성' if type_target else '미달성'})")

    time_target = avg_time < 100  # 100ms 미만
    print(f"  [{'OK' if time_target else 'FAIL'}] 응답시간 <100ms: {avg_time:.1f}ms ({'달성' if time_target else '미달성'})")

    return report


# ============ 메인 실행 ============

if __name__ == "__main__":
    print("\n테스트 시작...\n")

    # 규칙 기반만 테스트
    print("\n" + "▶" * 40)
    print("▶ 모드 1: 규칙 기반만 (LLM 없음)")
    print("▶" * 40 + "\n")
    report_rule_only = run_classifier_test(use_llm=False)

    print("\n\n" + "=" * 80)
    print("테스트 완료!")
    print("=" * 80)
