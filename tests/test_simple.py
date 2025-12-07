# -*- coding: utf-8 -*-
"""
간단한 기능 검증 테스트
"""

def test_keyword_matching():
    """키워드 매칭 로직만 테스트"""

    # 우선순위 높은 키워드
    high_priority_keywords = [
        "모든 ", "전체 ", "모두 ", "각각의 ", "전부 ",
        "모든페이지", "모든슬라이드", "전체목록", "전체내용",
        "모든제목", "각페이지", "각슬라이드"
    ]

    # 중간 우선순위 키워드
    medium_priority_keywords = [
        "전체적으로", "리스트", "목록", "각각"
    ]

    def detect_exhaustive(question):
        question_lower = question.lower()

        for keyword in high_priority_keywords:
            if keyword in question_lower:
                return True, keyword

        for keyword in medium_priority_keywords:
            padded_question = f" {question_lower} "
            if f" {keyword} " in padded_question or f" {keyword}" in padded_question:
                return True, keyword

        return False, None

    test_cases = [
        ("모든 슬라이드의 제목을 알려줘", True),
        ("전체 페이지 내용 정리해줘", True),
        ("모두 나열해줘", True),
        ("각각의 항목을 설명해줘", True),
        ("OLED 효율은 얼마인가?", False),
        ("다양한 재료를 사용했습니다", False),
        ("리스트로 보여줘", True),
        ("전체적으로 요약해줘", True),
        ("참고 문서가 다 있나요?", False),
    ]

    print("=" * 70)
    print("Keyword Detection Test")
    print("=" * 70)

    passed = 0
    failed = 0

    for question, expected in test_cases:
        result, matched_keyword = detect_exhaustive(question)
        status = "PASS" if result == expected else "FAIL"

        if result == expected:
            passed += 1
        else:
            failed += 1

        keyword_info = f"(matched: '{matched_keyword}')" if matched_keyword else ""
        print(f"[{status}] Expected: {expected:5}, Got: {result:5} {keyword_info}")
        print(f"      Question: '{question}'")

    print(f"\nResult: {passed} passed, {failed} failed")
    print("=" * 70)
    return failed == 0


def test_adaptive_logic():
    """Adaptive max results 로직 검증"""

    def adaptive_max_results(question, num_candidates, max_num_results=20, exhaustive_max=100, min_results=3):
        """Simplified adaptive logic"""

        if num_candidates == 0:
            return max_num_results

        # Exhaustive 감지
        exhaustive_keywords = ["모든 ", "전체 ", "모두 "]
        if any(kw in question.lower() for kw in exhaustive_keywords):
            result = min(exhaustive_max, num_candidates)
            return max(result, min_results)

        # 기본값
        return max_num_results

    test_cases = [
        ("모든 슬라이드 제목", 50, 50),  # exhaustive mode
        ("OLED 효율은?", 50, 20),  # default mode
        ("전체 목록", 120, 100),  # exhaustive but capped
        ("일반 질문", 0, 20),  # empty candidates
    ]

    print("\n" + "=" * 70)
    print("Adaptive Max Results Test")
    print("=" * 70)

    passed = 0
    failed = 0

    for question, num_candidates, expected in test_cases:
        result = adaptive_max_results(question, num_candidates)
        is_match = result == expected
        status = "PASS" if is_match else "FAIL"

        if is_match:
            passed += 1
        else:
            failed += 1

        print(f"[{status}] Question: '{question}'")
        print(f"      Candidates: {num_candidates}, Expected: {expected}, Got: {result}")

    print(f"\nResult: {passed} passed, {failed} failed")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Exhaustive Retrieval Feature Test (v3.5.0)")
    print("=" * 70 + "\n")

    all_passed = True

    try:
        all_passed &= test_keyword_matching()
    except Exception as e:
        print(f"\nKeyword test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        all_passed &= test_adaptive_logic()
    except Exception as e:
        print(f"\nAdaptive test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("All tests PASSED!")
    else:
        print("Some tests FAILED")
    print("=" * 70 + "\n")
