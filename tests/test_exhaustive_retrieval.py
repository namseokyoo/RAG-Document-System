"""
Exhaustive Retrieval 기능 테스트
v3.5.0 - Score-based Filtering + Adaptive Max Results
"""

def test_keyword_detection():
    """키워드 감지 테스트"""
    from utils.rag_chain import RAGChain

    # Mock vectorstore
    class MockVectorStore:
        def __init__(self):
            self.vectorstore = None

    # RAGChain 초기화 (최소 설정)
    rag = RAGChain(
        vectorstore=MockVectorStore(),
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:4b"
    )

    test_cases = [
        # (질문, 예상결과, 설명)
        ("모든 슬라이드의 제목을 알려줘", True, "모든 + 공백"),
        ("전체 페이지 내용 정리해줘", True, "전체 + 공백"),
        ("모두 나열해줘", True, "모두 + 공백"),
        ("각각의 항목을 설명해줘", True, "각각의 + 공백"),
        ("OLED 효율은 얼마인가?", False, "단일 사실 질문"),
        ("다양한 재료를 사용했습니다", False, "오탐 방지 - '다'"),
        ("리스트로 보여줘", True, "리스트 (단독)"),
        ("전체적으로 요약해줘", True, "전체적으로"),
        ("참고 문서가 다 있나요?", False, "오탐 방지 - '다'"),
    ]

    print("=" * 60)
    print("키워드 감지 테스트")
    print("=" * 60)

    passed = 0
    failed = 0

    for question, expected, description in test_cases:
        result = rag._detect_exhaustive_query(question)
        status = "✅ PASS" if result == expected else "❌ FAIL"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} | {description:30s} | '{question}'")
        print(f"       예상: {expected}, 실제: {result}")

    print(f"\n결과: {passed}개 통과, {failed}개 실패")
    return failed == 0


def test_adaptive_max_results():
    """Adaptive Max Results 로직 테스트"""
    from utils.rag_chain import RAGChain
    from langchain.schema import Document

    # Mock vectorstore
    class MockVectorStore:
        def __init__(self):
            self.vectorstore = None

    rag = RAGChain(
        vectorstore=MockVectorStore(),
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:4b"
    )

    # Mock candidates (50개)
    candidates = [
        (Document(page_content=f"Content {i}", metadata={"file_name": "test.pptx"}), 0.9 - i*0.01)
        for i in range(50)
    ]

    test_cases = [
        ("모든 슬라이드 제목", 50, "Exhaustive mode"),
        ("OLED 효율은?", 20, "Default mode"),
        ("이 슬라이드의 내용", 50, "Single file mode"),
    ]

    print("\n" + "=" * 60)
    print("Adaptive Max Results 테스트")
    print("=" * 60)

    passed = 0
    failed = 0

    for question, expected_range, description in test_cases:
        result = rag._adaptive_max_results(question, candidates)
        # 범위 체크 (정확한 값보다는 합리적인 범위)
        is_valid = (expected_range - 10 <= result <= expected_range + 10) if expected_range > 20 else (result <= expected_range + 5)
        status = "✅ PASS" if is_valid else "❌ FAIL"

        if is_valid:
            passed += 1
        else:
            failed += 1

        print(f"{status} | {description:20s} | '{question}'")
        print(f"       예상 범위: ~{expected_range}, 실제: {result}")

    print(f"\n결과: {passed}개 통과, {failed}개 실패")
    return failed == 0


def test_edge_cases():
    """엣지 케이스 테스트"""
    from utils.rag_chain import RAGChain

    # Mock vectorstore
    class MockVectorStore:
        def __init__(self):
            self.vectorstore = None

    rag = RAGChain(
        vectorstore=MockVectorStore(),
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:4b"
    )

    print("\n" + "=" * 60)
    print("엣지 케이스 테스트")
    print("=" * 60)

    passed = 0
    failed = 0

    # 1. 빈 candidates
    result = rag._adaptive_max_results("모든 슬라이드", [])
    if result == rag.max_num_results:
        print("✅ PASS | 빈 candidates 처리")
        passed += 1
    else:
        print(f"❌ FAIL | 빈 candidates 처리 (결과: {result})")
        failed += 1

    # 2. None question 처리
    try:
        result = rag._detect_exhaustive_query("")
        print("✅ PASS | 빈 문자열 질문 처리")
        passed += 1
    except Exception as e:
        print(f"❌ FAIL | 빈 문자열 질문 처리 (에러: {e})")
        failed += 1

    # 3. _count_file_chunks 빈 리스트
    result = rag._count_file_chunks([])
    if result == 0:
        print("✅ PASS | _count_file_chunks 빈 리스트 처리")
        passed += 1
    else:
        print(f"❌ FAIL | _count_file_chunks 빈 리스트 처리 (결과: {result})")
        failed += 1

    print(f"\n결과: {passed}개 통과, {failed}개 실패")
    return failed == 0


if __name__ == "__main__":
    print("\nExhaustive Retrieval Test Started\n")

    all_passed = True

    try:
        all_passed &= test_keyword_detection()
    except Exception as e:
        print(f"\n❌ 키워드 감지 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        all_passed &= test_adaptive_max_results()
    except Exception as e:
        print(f"\n❌ Adaptive Max Results 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        all_passed &= test_edge_cases()
    except Exception as e:
        print(f"\n❌ 엣지 케이스 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 모든 테스트 통과!")
    else:
        print("❌ 일부 테스트 실패")
    print("=" * 60)
