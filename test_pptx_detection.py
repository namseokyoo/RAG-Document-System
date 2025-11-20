"""
PPTX 변환 PDF 감지 기능 테스트
_is_pptx_converted_pdf() 메서드 검증
"""
from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()

import glob
from utils.pdf_chunking_engine import PDFChunkingEngine
from config import ConfigManager

print("=" * 80)
print("PPTX 변환 PDF 감지 테스트")
print("=" * 80)

# PDFChunkingEngine 초기화
config_manager = ConfigManager()
config = config_manager.get_all()

pdf_engine = PDFChunkingEngine(config)

# DB에서 PDF 샘플 가져오기
pdf_files = glob.glob("data/embedded_documents/**/*.pdf", recursive=True)
if not pdf_files:
    pdf_files = glob.glob("data/embedded_documents_archive/**/*.pdf", recursive=True)

print(f"\n발견된 PDF: {len(pdf_files)}개")
print("=" * 80)

# 처음 10개 테스트
for i, pdf_path in enumerate(pdf_files[:10], 1):
    import os
    filename = os.path.basename(pdf_path)

    print(f"\n[{i}] {filename}")
    print("-" * 80)

    try:
        # PPTX 변환 PDF 감지
        is_pptx = pdf_engine._is_pptx_converted_pdf(pdf_path)

        if is_pptx:
            print(f"  ✅ PPTX 변환 PDF 감지됨 → Full Vision 모드 적용")
        else:
            print(f"  ℹ️  일반 PDF → Hybrid 모드 적용")

    except Exception as e:
        print(f"  ❌ 오류: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("테스트 완료")
print("=" * 80)

# 결과 요약
print("\n[요약]")
print("  - PPTX 변환 PDF: Full Vision 모드로 모든 슬라이드 분석")
print("  - 일반 PDF: Hybrid 모드로 이미지/표만 Vision 분석")
print("  - 감지 기준: 메타데이터 (PowerPoint 등) + 화면 비율 (16:9, 4:3)")
