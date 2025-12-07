"""
이미지-슬라이드 매칭 검증 스크립트
COM 렌더링된 이미지가 올바른 슬라이드와 매칭되는지 확인
"""

import sys
import os
from pathlib import Path

# 환경변수 설정 (이미지 저장 활성화)
os.environ['DEBUG_VISION_IMAGES'] = 'true'

sys.path.insert(0, str(Path(__file__).parent))

from utils.pptx_chunking_engine import PPTXChunkingEngine
from config import ConfigManager

def verify_image_matching():
    """이미지 매칭 검증"""

    test_file = Path("data/test_pptx/advanced_01_financial_report.pptx")

    print("=" * 80)
    print(f"이미지 매칭 검증: {test_file.name}")
    print("=" * 80)
    print()
    print("[DEBUG] 환경변수 DEBUG_VISION_IMAGES 설정됨")
    print("[DEBUG] 렌더링된 이미지가 debug_vision/ 폴더에 저장됩니다")
    print()

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    engine = PPTXChunkingEngine(config)

    # Vision 청킹 실행 (debug 이미지 자동 저장)
    chunks = engine.process_pptx_document(
        pptx_path=str(test_file),
        enable_vision=True,
        llm_api_type=config['llm_api_type'],
        llm_base_url=config.get('llm_base_url', ''),
        llm_model=config['llm_model'],
        llm_api_key=config.get('llm_api_key', '')
    )

    print()
    print("=" * 80)
    print("검증 결과")
    print("=" * 80)
    print()
    print(f"총 {len(chunks)}개 청크 생성")
    print()
    print("Debug 이미지 저장 위치:")
    debug_dir = test_file.parent / "debug_vision"
    print(f"  {debug_dir}")
    print()
    print("저장된 파일:")
    if debug_dir.exists():
        for img_file in sorted(debug_dir.glob("*.png")):
            file_size = img_file.stat().st_size / 1024  # KB
            print(f"  - {img_file.name} ({file_size:.1f} KB)")
    else:
        print("  [WARN] debug_vision 폴더가 생성되지 않았습니다")
    print()
    print("=" * 80)
    print("다음 단계:")
    print("=" * 80)
    print()
    print("1. 위 폴더의 이미지들을 육안으로 확인하세요")
    print("2. 파일명의 슬라이드 번호와 실제 이미지 내용이 일치하는지 확인하세요")
    print("   예: slide_2_com_index_1.png는 실제 슬라이드 2의 내용이어야 함")
    print()
    print("만약 불일치한다면:")
    print("  - COM과 python-pptx의 슬라이드 순서가 다를 수 있습니다")
    print("  - 이 경우 슬라이드 ID나 제목으로 매칭을 다시 해야 합니다")
    print()


if __name__ == "__main__":
    verify_image_matching()
