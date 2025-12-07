#!/usr/bin/env python3
"""
Quick Integration Test for Diversity Penalty
Phase 2 완료 후 통합 검증용
"""

from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()  # Windows 터미널 한글 출력 설정

import json
from config import ConfigManager

def test_config_loading():
    """Config 로딩 테스트"""
    print("="*80)
    print("TEST 1: Config 로딩 테스트")
    print("="*80)

    cfg = ConfigManager()

    diversity_penalty = cfg.get("diversity_penalty")
    diversity_source_key = cfg.get("diversity_source_key")

    print(f"\n[OK] Import 성공")
    print(f"  diversity_penalty: {diversity_penalty}")
    print(f"  diversity_source_key: {diversity_source_key}")

    assert diversity_penalty is not None, "diversity_penalty가 None입니다!"
    assert diversity_source_key is not None, "diversity_source_key가 None입니다!"

    print(f"\n[OK] Config 검증 완료")
    return True


def test_rag_chain_init():
    """RAGChain 초기화 테스트 (vectorstore 없이 시그니처만 확인)"""
    print("\n" + "="*80)
    print("TEST 2: RAGChain 시그니처 테스트")
    print("="*80)

    from utils.rag_chain import RAGChain
    import inspect

    # RAGChain.__init__ 시그니처 확인
    sig = inspect.signature(RAGChain.__init__)
    params = list(sig.parameters.keys())

    print(f"\n[OK] RAGChain import 성공")
    print(f"  Parameters: {len(params)} 개")

    assert "diversity_penalty" in params, "diversity_penalty 파라미터가 없습니다!"
    assert "diversity_source_key" in params, "diversity_source_key 파라미터가 없습니다!"

    print(f"  [OK] diversity_penalty 파라미터 존재")
    print(f"  [OK] diversity_source_key 파라미터 존재")

    return True


def test_config_test_json():
    """config_test.json diversity_penalty 값 확인"""
    print("\n" + "="*80)
    print("TEST 3: config_test.json 확인")
    print("="*80)

    with open("config_test.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    diversity_penalty = config.get("diversity_penalty")
    diversity_source_key = config.get("diversity_source_key")

    print(f"\n[OK] config_test.json 로딩 성공")
    print(f"  diversity_penalty: {diversity_penalty}")
    print(f"  diversity_source_key: {diversity_source_key}")

    assert diversity_penalty == 0.3, f"Expected 0.3, got {diversity_penalty}"
    assert diversity_source_key == "source", f"Expected 'source', got {diversity_source_key}"

    print(f"\n[OK] config_test.json 값 검증 완료")
    return True


def main():
    """전체 테스트 실행"""
    print("\n" + "#"*80)
    print("# Diversity Penalty Integration Test")
    print("# Phase 2 완료 검증")
    print("#"*80 + "\n")

    try:
        # Test 1: Config 로딩
        test_config_loading()

        # Test 2: RAGChain 시그니처
        test_rag_chain_init()

        # Test 3: config_test.json
        test_config_test_json()

        # 종합 결과
        print("\n" + "="*80)
        print("[SUCCESS] 전체 통합 테스트 통과!")
        print("="*80)
        print("\n다음 단계:")
        print("  1. 샘플 테스트 3개 실행 (diversity_penalty=0.3)")
        print("  2. 다양성 지표 확인")
        print("  3. Phase 4로 진행")
        print()

        return True

    except Exception as e:
        print(f"\n[FAIL] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
