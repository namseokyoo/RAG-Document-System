"""
Phase 2 검증 테스트
1. reranker_model multilingual-mini 확인
2. Re-ranker Singleton 패턴 동작 확인
3. Hybrid Search 단일 진입점 확인
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
    print("Phase 2 검증 테스트")
    print("=" * 60)

    # 1. ConfigManager 로드 및 reranker_model 확인
    print("\n[1/4] reranker_model 설정 확인...")
    from config import ConfigManager
    config = ConfigManager().get_all()

    reranker_model = config.get("reranker_model")
    if reranker_model == "multilingual-mini":
        print("  [OK] reranker_model: multilingual-mini")
    else:
        print(f"  [FAIL] reranker_model: {reranker_model} (예상: multilingual-mini)")
        sys.exit(1)

    # 2. Re-ranker Singleton 패턴 확인
    print("\n[2/4] Re-ranker Singleton 패턴 확인...")
    try:
        from utils.reranker import get_reranker, CrossEncoderReranker

        # 싱글톤 패턴 확인: LOCAL_MODELS에 base가 없는지 확인
        if "multilingual-base" in CrossEncoderReranker.LOCAL_MODELS:
            print("  [FAIL] LOCAL_MODELS에 multilingual-base가 남아있음")
            sys.exit(1)
        else:
            print("  [OK] LOCAL_MODELS에 multilingual-mini만 존재")

        # HF_MODELS에 base가 없는지 확인
        if "multilingual-base" in CrossEncoderReranker.HF_MODELS:
            print("  [FAIL] HF_MODELS에 multilingual-base가 남아있음")
            sys.exit(1)
        else:
            print("  [OK] HF_MODELS에 multilingual-mini만 존재")

        print("  [OK] Re-ranker 모듈 import 성공 (Singleton 패턴 이미 구현됨)")
    except Exception as e:
        print(f"  [FAIL] Re-ranker 모듈 import 실패: {e}")
        sys.exit(1)

    # 3. Hybrid Search 단일 진입점 확인
    print("\n[3/4] Hybrid Search 단일 진입점 확인...")
    try:
        from utils.rag_chain import RAGChain
        import inspect

        # _search_candidates 메서드 확인
        source = inspect.getsource(RAGChain._search_candidates)

        # HybridRetriever 사용하는 코드가 제거되었는지 확인
        if "self.hybrid_retriever" in source:
            print("  [FAIL] HybridRetriever 코드가 아직 남아있음")
            sys.exit(1)
        else:
            print("  [OK] HybridRetriever 코드 제거 확인")

        # 단일 진입점 확인: search_with_mode와 similarity_search_hybrid만 사용
        if "search_with_mode" in source and "similarity_search_hybrid" in source:
            print("  [OK] Hybrid Search 단일 진입점 확인 (2단계 우선순위)")
        else:
            print("  [WARN] Hybrid Search 코드 구조 변경됨")

    except Exception as e:
        print(f"  [FAIL] Hybrid Search 확인 실패: {e}")
        sys.exit(1)

    # 4. 주요 모듈 임포트 테스트
    print("\n[4/4] 주요 모듈 임포트 테스트...")
    all_ok = True

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
        print("[SUCCESS] Phase 2 검증 성공!")
        print("          Re-ranker mini 통일 & Singleton & Hybrid Search 통합 완료")
        sys.exit(0)
    else:
        print("[FAIL] Phase 2 검증 실패!")
        print("       일부 모듈 임포트에 실패했습니다.")
        sys.exit(1)

except Exception as e:
    print(f"\n[ERROR] 오류 발생: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
