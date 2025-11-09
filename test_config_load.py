"""
Phase 1 설정 검증 테스트
"""
import sys
import os

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 환경 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

try:
    print("=" * 60)
    print("Phase 1 설정 검증 테스트")
    print("=" * 60)

    # 1. ConfigManager 로드
    print("\n[1/4] ConfigManager 로드...")
    from config import ConfigManager
    config = ConfigManager().get_all()
    print("  [OK] ConfigManager 로드 성공")

    # 2. 주요 설정값 확인
    print("\n[2/4] 주요 설정값 확인...")
    checks = {
        "temperature": (0.3, config.get("temperature")),
        "small_to_large_context_size": (800, config.get("small_to_large_context_size")),
        "enable_vision_chunking": (False, config.get("enable_vision_chunking")),
        "enable_question_classifier": (True, config.get("enable_question_classifier")),
        "enable_exhaustive_retrieval": (True, config.get("enable_exhaustive_retrieval")),
        "enable_score_filtering": (True, config.get("enable_score_filtering")),
    }

    all_ok = True
    for key, (expected, actual) in checks.items():
        status = "[OK]" if expected == actual else "[FAIL]"
        print(f"  {status} {key}: {actual} (예상: {expected})")
        if expected != actual:
            all_ok = False

    # 3. 미사용 설정 제거 확인
    print("\n[3/4] 미사용 설정 제거 확인...")
    removed_keys = ["top_k_results", "reranker_top_k"]
    for key in removed_keys:
        if key in config:
            print(f"  [FAIL] {key}: 아직 존재함 (제거 필요)")
            all_ok = False
        else:
            print(f"  [OK] {key}: 제거됨")

    # 4. 주요 모듈 임포트 테스트
    print("\n[4/4] 주요 모듈 임포트 테스트...")
    try:
        from utils.vector_store import VectorStoreManager
        print("  [OK] VectorStoreManager 임포트 성공")
    except Exception as e:
        print(f"  [FAIL] VectorStoreManager 임포트 실패: {e}")
        all_ok = False

    try:
        from utils.rag_chain import RAGChain
        print("  [OK] RAGChain 임포트 성공")
    except Exception as e:
        print(f"  [FAIL] RAGChain 임포트 실패: {e}")
        all_ok = False

    try:
        from utils.document_processor import DocumentProcessor
        print("  [OK] DocumentProcessor 임포트 성공")
    except Exception as e:
        print(f"  [FAIL] DocumentProcessor 임포트 실패: {e}")
        all_ok = False

    # 최종 결과
    print("\n" + "=" * 60)
    if all_ok:
        print("[SUCCESS] Phase 1 검증 성공!")
        print("          빌드 환경과 개발 환경이 일치합니다.")
        sys.exit(0)
    else:
        print("[FAIL] Phase 1 검증 실패!")
        print("       일부 설정이 올바르지 않습니다.")
        sys.exit(1)

except Exception as e:
    print(f"\n[ERROR] 오류 발생: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
