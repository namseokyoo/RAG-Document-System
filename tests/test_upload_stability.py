"""
업로드 안정성 개선 테스트 스크립트
"""
import sys
import traceback

print("=" * 60)
print("업로드 안정성 개선 - Import 테스트")
print("=" * 60)

# Test 1: 예외 클래스 import
print("\n[Test 1] 예외 클래스 import 테스트...")
try:
    from utils.pdf_chunking_engine import CancelledException, PartialUploadException
    print("  ✓ CancelledException import 성공")
    print("  ✓ PartialUploadException import 성공")

    # 예외 객체 생성 테스트
    exc1 = CancelledException("테스트 취소")
    print(f"  ✓ CancelledException 객체 생성: {exc1}")

    exc2 = PartialUploadException("페이지 4 실패", 4)
    print(f"  ✓ PartialUploadException 객체 생성: {exc2}")
    print(f"    - failed_page: {exc2.failed_page}")

except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 2: PDFChunkingEngine import
print("\n[Test 2] PDFChunkingEngine import 테스트...")
try:
    from utils.pdf_chunking_engine import PDFChunkingEngine
    print("  ✓ PDFChunkingEngine import 성공")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 3: DocumentProcessor import
print("\n[Test 3] DocumentProcessor import 테스트...")
try:
    from utils.document_processor import DocumentProcessor
    print("  ✓ DocumentProcessor import 성공")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 4: UI 컴포넌트 import
print("\n[Test 4] DocumentWidget import 테스트...")
try:
    from ui.document_widget import UploadWorker
    print("  ✓ UploadWorker import 성공")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 5: 콜백 시그니처 확인
print("\n[Test 5] 메서드 시그니처 확인...")
try:
    import inspect

    # PDFChunkingEngine.process_pdf_document 시그니처
    sig = inspect.signature(PDFChunkingEngine.process_pdf_document)
    params = list(sig.parameters.keys())
    print(f"  PDFChunkingEngine.process_pdf_document 파라미터:")
    print(f"    {params}")

    assert 'cancel_callback' in params, "cancel_callback 파라미터 누락"
    assert 'progress_callback' in params, "progress_callback 파라미터 누락"
    print("  ✓ cancel_callback 파라미터 존재")
    print("  ✓ progress_callback 파라미터 존재")

    # DocumentProcessor.process_document 시그니처
    sig = inspect.signature(DocumentProcessor.process_document)
    params = list(sig.parameters.keys())
    print(f"\n  DocumentProcessor.process_document 파라미터:")
    print(f"    {params}")

    assert 'cancel_callback' in params, "cancel_callback 파라미터 누락"
    assert 'progress_callback' in params, "progress_callback 파라미터 누락"
    print("  ✓ cancel_callback 파라미터 존재")
    print("  ✓ progress_callback 파라미터 존재")

except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 6: time 모듈 import 확인
print("\n[Test 6] time 모듈 import 확인...")
try:
    import utils.pdf_chunking_engine as pce
    # 모듈 내부에서 time이 import되었는지 확인
    assert hasattr(pce, 'time'), "time 모듈이 import되지 않음"
    print("  ✓ time 모듈 import 성공")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 모든 Import 테스트 통과!")
print("=" * 60)

# 추가 정보
print("\n[추가 정보]")
print(f"  - CancelledException: {CancelledException.__doc__}")
print(f"  - PartialUploadException: {PartialUploadException.__doc__}")
print(f"  - PartialUploadException.failed_page 타입: int")
