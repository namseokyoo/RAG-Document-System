"""
IntentDetector 단위 테스트
Phase 2: 문서 참조 의도 감지 기능 검증
"""
import unittest
from utils.intent_detector import IntentDetector


class TestIntentDetector(unittest.TestCase):
    """IntentDetector 기능 검증"""

    def setUp(self):
        """각 테스트 전에 새 IntentDetector 생성"""
        self.detector = IntentDetector()

    def test_initialization(self):
        """초기화 테스트"""
        self.assertIsNotNone(self.detector.ko_reference_patterns)
        self.assertIsNotNone(self.detector.en_reference_patterns)
        self.assertIsNotNone(self.detector.filename_patterns)
        self.assertGreater(len(self.detector.compiled_ko_patterns), 0)
        self.assertGreater(len(self.detector.compiled_en_patterns), 0)

    def test_filename_extraction_basic(self):
        """기본 파일명 추출 테스트"""
        # 확장자 포함
        filename = self.detector._extract_filename("report.pdf에서 결론 부분 찾아줘")
        self.assertEqual(filename, "report.pdf")

        filename = self.detector._extract_filename("analysis.docx 내용 요약해줘")
        self.assertEqual(filename, "analysis.docx")

        # 한글 파일명
        filename = self.detector._extract_filename("논문.pdf 읽어줘")
        self.assertEqual(filename, "논문.pdf")

    def test_filename_extraction_quoted(self):
        """따옴표로 감싼 파일명 추출 테스트"""
        filename = self.detector._extract_filename('"최종보고서.pdf" 내용 알려줘')
        self.assertEqual(filename, "최종보고서.pdf")

        filename = self.detector._extract_filename("'project_plan.docx' 요약해줘")
        self.assertEqual(filename, "project_plan.docx")

    def test_filename_extraction_mention_style(self):
        """@멘션 스타일 파일명 추출 테스트"""
        filename = self.detector._extract_filename("@report.pdf 참고해서 답변해줘")
        self.assertEqual(filename, "report.pdf")

    def test_filename_extraction_no_match(self):
        """파일명 없을 때 테스트"""
        filename = self.detector._extract_filename("일반적인 질문입니다")
        self.assertIsNone(filename)

        filename = self.detector._extract_filename("PDF에 대해 알려줘")
        self.assertIsNone(filename)

    def test_korean_reference_patterns(self):
        """한국어 문서 참조 패턴 감지 테스트"""
        # 지시대명사
        result = self.detector.detect_document_reference("이 문서에서 뭐라고 했어?")
        self.assertTrue(result['has_reference'])
        self.assertGreater(result['confidence'], 0.6)

        result = self.detector.detect_document_reference("그 파일 내용 요약해줘")
        self.assertTrue(result['has_reference'])

        # 시간 기반
        result = self.detector.detect_document_reference("방금 올린 PDF 분석해줘")
        self.assertTrue(result['has_reference'])

        result = self.detector.detect_document_reference("아까 업로드한 자료에서 찾아줘")
        self.assertTrue(result['has_reference'])

        # 동작 기반
        result = self.detector.detect_document_reference("내가 올린 논문 읽어줘")
        self.assertTrue(result['has_reference'])

        result = self.detector.detect_document_reference("첨부한 파일 요약해줘")
        self.assertTrue(result['has_reference'])

    def test_english_reference_patterns(self):
        """영어 문서 참조 패턴 감지 테스트"""
        result = self.detector.detect_document_reference("What does this document say?")
        self.assertTrue(result['has_reference'])

        result = self.detector.detect_document_reference("Analyze the uploaded file")
        self.assertTrue(result['has_reference'])

        result = self.detector.detect_document_reference("I just attached a PDF")
        self.assertTrue(result['has_reference'])

    def test_filename_mentioned_highest_confidence(self):
        """파일명 명시 시 최고 신뢰도 테스트"""
        result = self.detector.detect_document_reference("report.pdf에서 찾아줘")
        self.assertTrue(result['has_reference'])
        self.assertEqual(result['confidence'], 1.0)
        self.assertEqual(result['mentioned_filename'], "report.pdf")

    def test_no_reference_patterns(self):
        """문서 참조 없는 일반 질문 테스트"""
        result = self.detector.detect_document_reference("인공지능이 뭐야?")
        self.assertFalse(result['has_reference'])
        self.assertEqual(result['confidence'], 0.0)

        result = self.detector.detect_document_reference("날씨 어때?")
        self.assertFalse(result['has_reference'])

        result = self.detector.detect_document_reference("파이썬 문법 알려줘")
        self.assertFalse(result['has_reference'])

    def test_multiple_patterns_increase_confidence(self):
        """여러 패턴 매칭 시 신뢰도 증가 테스트"""
        # 단일 패턴
        result1 = self.detector.detect_document_reference("이 문서")
        confidence1 = result1['confidence']

        # 다중 패턴 (지시대명사 + 시간 기반)
        result2 = self.detector.detect_document_reference("방금 올린 이 문서")
        confidence2 = result2['confidence']

        # 다중 패턴이 더 높은 신뢰도
        self.assertGreater(confidence2, confidence1)

    def test_extract_all_filenames(self):
        """여러 파일명 추출 테스트"""
        filenames = self.detector.extract_all_filenames(
            "report.pdf와 analysis.docx를 비교해줘"
        )
        self.assertEqual(len(filenames), 2)
        self.assertIn("report.pdf", filenames)
        self.assertIn("analysis.docx", filenames)

    def test_get_reference_strength(self):
        """참조 강도 측정 간편 메서드 테스트"""
        strength = self.detector.get_reference_strength("이 문서 요약해줘")
        self.assertGreater(strength, 0.0)
        self.assertLessEqual(strength, 1.0)

        strength = self.detector.get_reference_strength("일반 질문")
        self.assertEqual(strength, 0.0)

    def test_has_strong_reference(self):
        """강한 참조 여부 판단 테스트"""
        # 파일명 명시 - 강한 참조
        self.assertTrue(
            self.detector.has_strong_reference("report.pdf 읽어줘", threshold=0.7)
        )

        # 일반 패턴 - 임계값에 따라
        has_ref = self.detector.has_strong_reference("이 문서 요약해줘", threshold=0.7)
        self.assertTrue(has_ref)

        # 참조 없음
        self.assertFalse(
            self.detector.has_strong_reference("일반 질문", threshold=0.7)
        )

    def test_matched_patterns_tracking(self):
        """매칭된 패턴 추적 테스트"""
        result = self.detector.detect_document_reference("이 문서에서 찾아줘")
        self.assertGreater(len(result['matched_patterns']), 0)

        result = self.detector.detect_document_reference("report.pdf 읽어줘")
        self.assertIn("filename:report.pdf", result['matched_patterns'])

    def test_complex_korean_sentences(self):
        """복잡한 한국어 문장 테스트"""
        # 긴 문장 내 참조
        result = self.detector.detect_document_reference(
            "저기요, 제가 조금 전에 올린 파일 있잖아요, 그거 요약해주실 수 있나요?"
        )
        self.assertTrue(result['has_reference'])

        # 공손한 표현
        result = self.detector.detect_document_reference(
            "방금 업로드한 문서에 대해서 질문 드리고 싶은데요"
        )
        self.assertTrue(result['has_reference'])

    def test_edge_cases(self):
        """엣지 케이스 테스트"""
        # 빈 문자열
        result = self.detector.detect_document_reference("")
        self.assertFalse(result['has_reference'])

        # 공백만
        result = self.detector.detect_document_reference("   ")
        self.assertFalse(result['has_reference'])

        # 특수문자
        result = self.detector.detect_document_reference("!@#$%^&*()")
        self.assertFalse(result['has_reference'])

    def test_filename_with_spaces(self):
        """공백 포함 파일명 테스트"""
        filename = self.detector._extract_filename("Final Report 2024.pdf 요약해줘")
        self.assertEqual(filename, "Final Report 2024.pdf")

        filename = self.detector._extract_filename('"최종 보고서.pdf" 읽어줘')
        self.assertEqual(filename, "최종 보고서.pdf")

    def test_various_file_extensions(self):
        """다양한 확장자 테스트"""
        extensions = ['pdf', 'docx', 'xlsx', 'pptx', 'txt', 'hwp']

        for ext in extensions:
            filename = self.detector._extract_filename(f"test.{ext} 읽어줘")
            self.assertEqual(filename, f"test.{ext}")

    def test_repr(self):
        """__repr__ 메서드 테스트"""
        repr_str = repr(self.detector)
        self.assertIn("IntentDetector", repr_str)
        self.assertIn("ko_patterns", repr_str)
        self.assertIn("en_patterns", repr_str)


class TestIntentDetectorRealWorldScenarios(unittest.TestCase):
    """실제 사용 시나리오 테스트"""

    def setUp(self):
        self.detector = IntentDetector()

    def test_scenario_1_upload_then_ask(self):
        """시나리오 1: 업로드 직후 질문"""
        questions = [
            "이 논문 요약해줘",
            "방금 올린 파일에서 결론 부분 찾아줘",
            "이 문서가 뭐에 대한 내용이야?",
        ]

        for q in questions:
            result = self.detector.detect_document_reference(q)
            self.assertTrue(result['has_reference'],
                          f"Failed to detect reference in: {q}")

    def test_scenario_2_filename_mention(self):
        """시나리오 2: 파일명 직접 언급"""
        questions = [
            "research_paper.pdf 읽어줘",
            "분석보고서.docx에서 표 찾아줘",
            "@project_plan.pdf 요약해줘",
        ]

        for q in questions:
            result = self.detector.detect_document_reference(q)
            self.assertTrue(result['has_reference'])
            self.assertEqual(result['confidence'], 1.0)
            self.assertIsNotNone(result['mentioned_filename'])

    def test_scenario_3_no_document_context(self):
        """시나리오 3: 문서와 무관한 일반 질문"""
        questions = [
            "파이썬으로 리스트 정렬하는 방법 알려줘",
            "오늘 날씨 어때?",
            "머신러닝이 뭐야?",
            "PDF 파일 형식에 대해 설명해줘",  # PDF 언급하지만 특정 문서 참조 아님
        ]

        for q in questions:
            result = self.detector.detect_document_reference(q)
            self.assertFalse(result['has_reference'],
                           f"False positive for: {q}")

    def test_scenario_4_mixed_language(self):
        """시나리오 4: 한영 혼용 (현실적 케이스)"""
        # 한국어 키워드 + 영어 내용
        result = self.detector.detect_document_reference(
            "이 문서에서 table 찾아줘"
        )
        self.assertTrue(result['has_reference'])

        # 한국어 시간 키워드 + 영어 명사
        result = self.detector.detect_document_reference(
            "방금 올린 file 분석해줘"
        )
        self.assertTrue(result['has_reference'])

        # 영어 전체 문장
        result = self.detector.detect_document_reference(
            "Find table in this document"
        )
        self.assertTrue(result['has_reference'])


def run_tests():
    """테스트 실행"""
    print("=" * 80)
    print("INTENT DETECTOR UNIT TESTS")
    print("=" * 80)
    print()

    # 테스트 스위트 생성
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 모든 테스트 추가
    suite.addTests(loader.loadTestsFromTestCase(TestIntentDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestIntentDetectorRealWorldScenarios))

    # 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 80)
    if result.wasSuccessful():
        print("[PASS] ALL TESTS PASSED")
    else:
        print("[FAIL] SOME TESTS FAILED")
    print("=" * 80)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
