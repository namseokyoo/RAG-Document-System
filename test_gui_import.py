"""
Phase 3.5 GUI 통합 테스트 - Import 검증
"""
import sys

print("=" * 80)
print("PHASE 3.5 GUI IMPORT TEST")
print("=" * 80)
print()

try:
    print("[1/5] Importing SessionContext...")
    from utils.session_context import SessionContext
    print("  [OK] SessionContext import 성공")

    print("[2/5] Importing IntentDetector...")
    from utils.intent_detector import IntentDetector
    print("  [OK] IntentDetector import 성공")

    print("[3/5] Importing RAGChain...")
    from utils.rag_chain import RAGChain
    print("  [OK] RAGChain import 성공")

    print("[4/5] Importing MainWindow...")
    from ui.main_window import MainWindow
    print("  [OK] MainWindow import 성공")

    print("[5/5] Importing DocumentWidget...")
    from ui.document_widget import DocumentWidget
    print("  [OK] DocumentWidget import 성공")

    print()
    print("=" * 80)
    print("[PASS] ALL IMPORTS SUCCESSFUL")
    print("=" * 80)
    print()

    # SessionContext 기본 기능 테스트
    print("SessionContext 기본 테스트:")
    session = SessionContext(timeout_seconds=300)
    print(f"  [OK] SessionContext 생성 (timeout={session.timeout_seconds}s)")
    print(f"  [OK] 활성 상태: {session.is_active()}")

    # IntentDetector 기본 테스트
    print()
    print("IntentDetector 기본 테스트:")
    detector = IntentDetector()
    result = detector.detect_document_reference("이 문서에서 뭐라고 했어?")
    print(f"  [OK] Intent 감지: has_reference={result['has_reference']}")
    print(f"  [OK] 신뢰도: {result['confidence']:.2f}")

    print()
    print("=" * 80)
    print("Phase 3.5 GUI 통합 준비 완료!")
    print("=" * 80)

    sys.exit(0)

except Exception as e:
    print()
    print("=" * 80)
    print("[FAIL] IMPORT ERROR")
    print("=" * 80)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
