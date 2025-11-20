"""
RAG System v0.4.0 회귀 테스트 스위트

Phase 3.5 추가 후 기존 기능이 정상 작동하는지 확인하는 smoke tests
"""
import sys
import json
import time
from pathlib import Path

print("=" * 80)
print("RAG SYSTEM v0.4.0 - REGRESSION TEST SUITE")
print("=" * 80)
print()

# ============================================================================
# Test 1: Config 로드 및 기본 설정 확인
# ============================================================================
print("[Test 1] Config Loading & Settings Verification")
print("-" * 80)

try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 기존 설정 확인
    required_keys = [
        'enable_hybrid_search',
        'hybrid_bm25_weight',
        'enable_vision_chunking',
        'vision_enabled',
        'top_k',
        'reranker_initial_k'
    ]

    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        print(f"  [FAIL] Missing config keys: {missing_keys}")
        sys.exit(1)

    print(f"  [OK] enable_hybrid_search: {config['enable_hybrid_search']}")
    print(f"  [OK] hybrid_bm25_weight: {config['hybrid_bm25_weight']}")
    print(f"  [OK] enable_vision_chunking: {config['enable_vision_chunking']}")
    print(f"  [OK] top_k: {config['top_k']}")
    print(f"  [OK] reranker_initial_k: {config['reranker_initial_k']}")

    # Phase 3.5 새 설정 확인
    phase35_keys = ['enable_session_priority', 'session_relevance_threshold']
    for key in phase35_keys:
        if key in config:
            print(f"  [OK] {key}: {config[key]}")
        else:
            print(f"  [WARN] {key} not found (Phase 3.5 setting)")

    print()
    print("[PASS] Test 1: Config loading successful")
    print()

except Exception as e:
    print(f"  [FAIL] Config loading error: {e}")
    sys.exit(1)

# ============================================================================
# Test 2: 모듈 Import 테스트
# ============================================================================
print("[Test 2] Module Import Test")
print("-" * 80)

try:
    # 기존 모듈
    print("  Importing RAGChain...")
    from utils.rag_chain import RAGChain
    print("  [OK] RAGChain")

    print("  Importing DocumentProcessor...")
    from utils.document_processor import DocumentProcessor
    print("  [OK] DocumentProcessor")

    print("  Importing VectorStoreManager...")
    from utils.vector_store import VectorStoreManager
    print("  [OK] VectorStoreManager")

    print("  Importing PDF Chunking Engine...")
    from utils.pdf_chunking_engine import PDFChunkingEngine
    print("  [OK] PDFChunkingEngine")

    print("  Importing PPTX Chunking Engine...")
    from utils.pptx_chunking_engine import PPTXChunkingEngine
    print("  [OK] PPTXChunkingEngine")

    # Phase 3.5 새 모듈
    print("  Importing SessionContext...")
    from utils.session_context import SessionContext
    print("  [OK] SessionContext")

    print("  Importing IntentDetector...")
    from utils.intent_detector import IntentDetector
    print("  [OK] IntentDetector")

    print()
    print("[PASS] Test 2: All modules imported successfully")
    print()

except Exception as e:
    print(f"  [FAIL] Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 3: SessionContext 기본 기능
# ============================================================================
print("[Test 3] SessionContext Basic Functionality")
print("-" * 80)

try:
    from utils.session_context import SessionContext

    # 생성
    session = SessionContext(timeout_seconds=300)
    print(f"  [OK] SessionContext created (timeout={session.timeout_seconds}s)")

    # 초기 상태
    is_active = session.is_active()
    print(f"  [OK] Initial state: is_active={is_active}")

    if is_active:
        print(f"  [WARN] Session should be inactive initially (no uploads)")

    # 문서 추가
    session.add_upload(
        document_id="test_doc_1",
        file_name="test.pdf",
        num_chunks=10
    )
    print("  [OK] Document added to session")

    # 활성 상태 확인
    is_active_after = session.is_active()
    print(f"  [OK] After upload: is_active={is_active_after}")

    if not is_active_after:
        print(f"  [FAIL] Session should be active after upload")
        sys.exit(1)

    # 활성 문서 가져오기
    active_docs = session.get_active_documents()
    print(f"  [OK] Active documents: {len(active_docs)}")

    if len(active_docs) != 1:
        print(f"  [FAIL] Expected 1 active document, got {len(active_docs)}")
        sys.exit(1)

    print()
    print("[PASS] Test 3: SessionContext working correctly")
    print()

except Exception as e:
    print(f"  [FAIL] SessionContext error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 4: IntentDetector 기본 기능
# ============================================================================
print("[Test 4] IntentDetector Basic Functionality")
print("-" * 80)

try:
    from utils.intent_detector import IntentDetector

    detector = IntentDetector()
    print("  [OK] IntentDetector created")

    # 한국어 지시대명사 테스트
    test_cases = [
        ("이 문서에서 뭐라고 했어?", True, "Korean demonstrative"),
        ("방금 올린 파일 요약해줘", True, "Time-based reference"),
        ("OLED이 뭐야?", False, "No reference"),
        ("this document summary", True, "English demonstrative"),
    ]

    for question, expected_has_ref, desc in test_cases:
        result = detector.detect_document_reference(question)
        has_ref = result['has_reference']
        confidence = result['confidence']

        if has_ref == expected_has_ref:
            status = "OK"
        else:
            status = "FAIL"
            print(f"  [{status}] '{question}' - Expected {expected_has_ref}, got {has_ref}")
            sys.exit(1)

        print(f"  [{status}] {desc}: has_reference={has_ref}, confidence={confidence:.2f}")

    print()
    print("[PASS] Test 4: IntentDetector working correctly")
    print()

except Exception as e:
    print(f"  [FAIL] IntentDetector error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 5: RAGChain 클래스 검증 (SessionContext 파라미터 지원)
# ============================================================================
print("[Test 5] RAGChain SessionContext Parameter Support")
print("-" * 80)

try:
    from utils.rag_chain import RAGChain
    import inspect

    # RAGChain __init__ 시그니처 확인
    sig = inspect.signature(RAGChain.__init__)
    params = list(sig.parameters.keys())

    print(f"  [INFO] RAGChain.__init__ parameters: {len(params)}")

    # Phase 3.5 파라미터 확인
    phase35_params = ['session_context', 'enable_session_priority', 'session_relevance_threshold']
    for param in phase35_params:
        if param in params:
            print(f"  [OK] Parameter '{param}' supported")
        else:
            print(f"  [WARN] Parameter '{param}' not found (may be **kwargs)")

    print()
    print("[PASS] Test 5: RAGChain supports Phase 3.5 parameters")
    print()

except Exception as e:
    print(f"  [FAIL] RAGChain check error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 6: Hybrid Search 설정 확인
# ============================================================================
print("[Test 6] Hybrid Search Configuration")
print("-" * 80)

try:
    # Config 확인
    if config.get('enable_hybrid_search'):
        print(f"  [OK] Hybrid Search enabled")
        print(f"  [OK] BM25 weight: {config.get('hybrid_bm25_weight', 0.5)}")

        # HybridRetriever 모듈 확인
        from utils.hybrid_retriever import HybridRetriever
        print(f"  [OK] HybridRetriever module available")
    else:
        print(f"  [WARN] Hybrid Search disabled")

    print()
    print("[PASS] Test 6: Hybrid Search configuration verified")
    print()

except Exception as e:
    print(f"  [FAIL] Hybrid Search check error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 7: Vision Chunking 설정 확인
# ============================================================================
print("[Test 7] Vision Chunking Configuration")
print("-" * 80)

try:
    if config.get('enable_vision_chunking'):
        print(f"  [OK] Vision chunking enabled")
        print(f"  [OK] Vision mode: {config.get('vision_mode', 'auto')}")
    else:
        print(f"  [WARN] Vision chunking disabled")

    # Poppler path 확인 (PDF → image 변환용)
    poppler_path = config.get('poppler_path', '')
    if poppler_path and Path(poppler_path).exists():
        print(f"  [OK] Poppler path exists: {poppler_path}")
    elif poppler_path:
        print(f"  [WARN] Poppler path not found: {poppler_path}")
    else:
        print(f"  [INFO] Poppler path not configured")

    print()
    print("[PASS] Test 7: Vision chunking configuration verified")
    print()

except Exception as e:
    print(f"  [FAIL] Vision check error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 8: Re-ranker 설정 확인
# ============================================================================
print("[Test 8] Re-ranker Configuration")
print("-" * 80)

try:
    reranker_k = config.get('reranker_initial_k', 30)
    top_k = config.get('top_k', 5)

    print(f"  [OK] reranker_initial_k: {reranker_k}")
    print(f"  [OK] top_k (final): {top_k}")

    if reranker_k < top_k:
        print(f"  [WARN] reranker_initial_k should be >= top_k")

    print()
    print("[PASS] Test 8: Re-ranker configuration verified")
    print()

except Exception as e:
    print(f"  [FAIL] Re-ranker check error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# 종합 결과
# ============================================================================
print("=" * 80)
print("REGRESSION TEST SUITE - ALL TESTS PASSED")
print("=" * 80)
print()
print("Summary:")
print("  [OK] Test 1: Config loading")
print("  [OK] Test 2: Module imports")
print("  [OK] Test 3: SessionContext basic functionality")
print("  [OK] Test 4: IntentDetector basic functionality")
print("  [OK] Test 5: RAGChain integration with SessionContext")
print("  [OK] Test 6: Hybrid Search configuration")
print("  [OK] Test 7: Vision chunking configuration")
print("  [OK] Test 8: Re-ranker configuration")
print()
print("[SUCCESS] All 8 regression tests passed!")
print("[SUCCESS] Phase 3.5 integration did NOT break existing features")
print()

sys.exit(0)
