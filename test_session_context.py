"""
SessionContext 단위 테스트
Phase 1: 세션 컨텍스트 기본 기능 검증
"""
import unittest
import time
from datetime import datetime, timedelta
from utils.session_context import SessionContext, UploadedDocument


class TestSessionContext(unittest.TestCase):
    """SessionContext 기능 검증"""

    def setUp(self):
        """각 테스트 전에 새 SessionContext 생성"""
        # 테스트용 짧은 타임아웃 (5초)
        self.session = SessionContext(timeout_seconds=5)

    def test_initialization(self):
        """초기화 테스트"""
        self.assertEqual(self.session.timeout_seconds, 5)
        self.assertEqual(len(self.session.recent_uploads), 0)
        self.assertFalse(self.session.is_active())

    def test_add_upload(self):
        """문서 업로드 기록 테스트"""
        self.session.add_upload(
            document_id="doc_001",
            file_name="test.pdf",
            num_chunks=10
        )

        self.assertEqual(len(self.session.recent_uploads), 1)
        self.assertTrue(self.session.is_active())

        # 저장된 정보 확인
        doc = self.session.recent_uploads[0]
        self.assertEqual(doc.document_id, "doc_001")
        self.assertEqual(doc.file_name, "test.pdf")
        self.assertEqual(doc.num_chunks, 10)
        self.assertIsInstance(doc.upload_timestamp, datetime)

    def test_multiple_uploads(self):
        """여러 문서 업로드 테스트"""
        self.session.add_upload("doc_001", "file1.pdf", 10)
        self.session.add_upload("doc_002", "file2.pdf", 20)
        self.session.add_upload("doc_003", "file3.pdf", 15)

        self.assertEqual(len(self.session.recent_uploads), 3)
        self.assertEqual(len(self.session.get_active_documents()), 3)

    def test_get_active_documents(self):
        """활성 문서 필터링 테스트"""
        self.session.add_upload("doc_001", "file1.pdf", 10)

        # 즉시 확인 - 활성 상태여야 함
        active = self.session.get_active_documents()
        self.assertEqual(len(active), 1)

        # 타임아웃 대기 (5초 + 여유)
        time.sleep(6)

        # 타임아웃 후 - 비활성 상태여야 함
        active = self.session.get_active_documents()
        self.assertEqual(len(active), 0)
        self.assertFalse(self.session.is_active())

    def test_get_active_document_ids(self):
        """활성 문서 ID 리스트 반환 테스트"""
        self.session.add_upload("doc_001", "file1.pdf", 10)
        self.session.add_upload("doc_002", "file2.pdf", 20)

        doc_ids = self.session.get_active_document_ids()
        self.assertEqual(len(doc_ids), 2)
        self.assertIn("doc_001", doc_ids)
        self.assertIn("doc_002", doc_ids)

    def test_get_active_file_names(self):
        """활성 파일명 리스트 반환 테스트"""
        self.session.add_upload("doc_001", "file1.pdf", 10)
        self.session.add_upload("doc_002", "file2.pdf", 20)

        file_names = self.session.get_active_file_names()
        self.assertEqual(len(file_names), 2)
        self.assertIn("file1.pdf", file_names)
        self.assertIn("file2.pdf", file_names)

    def test_get_most_recent_document(self):
        """최근 문서 반환 테스트"""
        # 빈 세션
        self.assertIsNone(self.session.get_most_recent_document())

        # 문서 추가
        self.session.add_upload("doc_001", "file1.pdf", 10)
        time.sleep(0.1)  # 타임스탬프 차이를 위해
        self.session.add_upload("doc_002", "file2.pdf", 20)
        time.sleep(0.1)
        self.session.add_upload("doc_003", "file3.pdf", 15)

        # 가장 최근 문서 확인
        most_recent = self.session.get_most_recent_document()
        self.assertIsNotNone(most_recent)
        self.assertEqual(most_recent.document_id, "doc_003")
        self.assertEqual(most_recent.file_name, "file3.pdf")

    def test_clear(self):
        """세션 초기화 테스트"""
        self.session.add_upload("doc_001", "file1.pdf", 10)
        self.session.add_upload("doc_002", "file2.pdf", 20)

        self.assertEqual(len(self.session.recent_uploads), 2)

        # 초기화
        self.session.clear()

        self.assertEqual(len(self.session.recent_uploads), 0)
        self.assertFalse(self.session.is_active())
        self.assertIsNone(self.session.get_most_recent_document())

    def test_get_session_info(self):
        """세션 정보 반환 테스트"""
        # 빈 세션
        info = self.session.get_session_info()
        self.assertFalse(info['active'])
        self.assertEqual(info['num_active_docs'], 0)
        self.assertEqual(info['active_files'], [])
        self.assertIsNone(info['most_recent'])

        # 문서 추가 후
        self.session.add_upload("doc_001", "file1.pdf", 10)
        info = self.session.get_session_info()

        self.assertTrue(info['active'])
        self.assertEqual(info['num_active_docs'], 1)
        self.assertEqual(info['active_files'], ["file1.pdf"])
        self.assertEqual(info['most_recent'], "file1.pdf")
        self.assertEqual(info['timeout_seconds'], 5)
        self.assertIsNotNone(info['most_recent_elapsed'])
        self.assertLess(info['most_recent_elapsed'], 5)

    def test_cleanup_old_uploads(self):
        """오래된 업로드 자동 정리 테스트"""
        # 짧은 타임아웃으로 새 세션 생성
        session = SessionContext(timeout_seconds=2)

        session.add_upload("doc_001", "file1.pdf", 10)
        self.assertEqual(len(session.recent_uploads), 1)

        # 타임아웃의 2배 이상 대기 (4초 + 여유)
        time.sleep(5)

        # 새 문서 추가 - 이때 _cleanup_old_uploads() 실행됨
        session.add_upload("doc_002", "file2.pdf", 20)

        # 오래된 문서는 제거되어야 함
        self.assertEqual(len(session.recent_uploads), 1)
        self.assertEqual(session.recent_uploads[0].document_id, "doc_002")

    def test_timeout_behavior(self):
        """타임아웃 동작 테스트 (시간 경과에 따른 활성/비활성)"""
        session = SessionContext(timeout_seconds=3)

        session.add_upload("doc_001", "file1.pdf", 10)

        # 즉시: 활성
        self.assertTrue(session.is_active())
        self.assertEqual(len(session.get_active_documents()), 1)

        # 2초 후: 여전히 활성 (타임아웃 3초)
        time.sleep(2)
        self.assertTrue(session.is_active())
        self.assertEqual(len(session.get_active_documents()), 1)

        # 4초 후 (총 6초): 비활성
        time.sleep(4)
        self.assertFalse(session.is_active())
        self.assertEqual(len(session.get_active_documents()), 0)

    def test_partial_timeout(self):
        """부분 타임아웃 테스트 (일부 문서만 만료)"""
        session = SessionContext(timeout_seconds=3)

        # 첫 번째 문서
        session.add_upload("doc_001", "file1.pdf", 10)
        time.sleep(2)

        # 두 번째 문서 (2초 후)
        session.add_upload("doc_002", "file2.pdf", 20)
        time.sleep(2)

        # 총 4초 경과: 첫 번째는 만료(3초 초과), 두 번째는 활성(2초)
        active = session.get_active_documents()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].document_id, "doc_002")

    def test_repr_methods(self):
        """__repr__ 메서드 테스트"""
        self.session.add_upload("doc_001", "test.pdf", 10)

        # SessionContext __repr__
        session_repr = repr(self.session)
        self.assertIn("SessionContext", session_repr)
        self.assertIn("active=1", session_repr)
        self.assertIn("timeout=5s", session_repr)

        # UploadedDocument __repr__
        doc = self.session.recent_uploads[0]
        doc_repr = repr(doc)
        self.assertIn("UploadedDocument", doc_repr)
        self.assertIn("test.pdf", doc_repr)
        self.assertIn("chunks=10", doc_repr)


class TestUploadedDocument(unittest.TestCase):
    """UploadedDocument 데이터클래스 테스트"""

    def test_creation(self):
        """생성 테스트"""
        doc = UploadedDocument(
            document_id="doc_001",
            file_name="test.pdf",
            upload_timestamp=datetime.now(),
            num_chunks=10
        )

        self.assertEqual(doc.document_id, "doc_001")
        self.assertEqual(doc.file_name, "test.pdf")
        self.assertEqual(doc.num_chunks, 10)
        self.assertIsInstance(doc.upload_timestamp, datetime)

    def test_repr(self):
        """문자열 표현 테스트"""
        doc = UploadedDocument(
            document_id="doc_001",
            file_name="test.pdf",
            upload_timestamp=datetime.now(),
            num_chunks=10
        )

        repr_str = repr(doc)
        self.assertIn("UploadedDocument", repr_str)
        self.assertIn("test.pdf", repr_str)
        self.assertIn("chunks=10", repr_str)
        self.assertIn("elapsed=", repr_str)


def run_tests():
    """테스트 실행"""
    print("=" * 80)
    print("SESSION CONTEXT UNIT TESTS")
    print("=" * 80)
    print()

    # 테스트 스위트 생성
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 모든 테스트 추가
    suite.addTests(loader.loadTestsFromTestCase(TestSessionContext))
    suite.addTests(loader.loadTestsFromTestCase(TestUploadedDocument))

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
