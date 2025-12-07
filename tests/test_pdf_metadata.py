"""
PDF 메타데이터 분석 - PPTX 변환 여부 감지 테스트
"""
from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()

try:
    from PyPDF2 import PdfReader
except ImportError:
    from pypdf import PdfReader

import os

# 테스트할 PDF 파일 경로 (PPTX 변환 PDF 샘플)
test_pdfs = [
    # 여기에 테스트 PDF 경로를 추가하세요
    # "path/to/pptx_converted.pdf",
    # "path/to/normal.pdf",
]

# DB에서 PDF 샘플 가져오기
import glob
pdf_files = glob.glob("data/embedded_documents/**/*.pdf", recursive=True)

if not pdf_files:
    pdf_files = glob.glob("data/embedded_documents_archive/**/*.pdf", recursive=True)

print(f"발견된 PDF: {len(pdf_files)}개")
print("=" * 80)

for pdf_path in pdf_files[:5]:  # 처음 5개만 테스트
    print(f"\n[파일] {os.path.basename(pdf_path)}")
    print("-" * 80)

    try:
        reader = PdfReader(pdf_path)

        # 메타데이터 추출
        metadata = reader.metadata

        if metadata:
            print("📋 메타데이터:")
            for key, value in metadata.items():
                if value:
                    print(f"  {key}: {value}")
        else:
            print("  (메타데이터 없음)")

        # PPTX 변환 여부 판별 키워드
        pptx_indicators = [
            "PowerPoint",
            "Microsoft Office PowerPoint",
            "Impress",  # LibreOffice
            "Keynote",  # Apple
            "Presentation",
            "pptx",
            "ppt"
        ]

        is_pptx_converted = False
        matched_indicator = None

        if metadata:
            # Producer, Creator, Title 확인
            for key in ['/Producer', '/Creator', '/Title', '/Subject']:
                value = metadata.get(key, "")
                if value:
                    for indicator in pptx_indicators:
                        if indicator.lower() in str(value).lower():
                            is_pptx_converted = True
                            matched_indicator = f"{key}: {indicator}"
                            break
                if is_pptx_converted:
                    break

        # 페이지 크기 분석 (슬라이드 비율 확인)
        page = reader.pages[0]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        aspect_ratio = width / height if height > 0 else 0

        print(f"\n📐 페이지 크기: {width:.1f} x {height:.1f} (비율: {aspect_ratio:.2f})")

        # 일반적인 슬라이드 비율
        # 16:9 = 1.78, 4:3 = 1.33, A4 = 0.71 (세로)
        is_landscape = aspect_ratio > 1.2
        is_slide_ratio = 1.3 <= aspect_ratio <= 1.8

        print(f"  가로 모드: {is_landscape}")
        print(f"  슬라이드 비율 (4:3 or 16:9): {is_slide_ratio}")

        print(f"\n✅ PPTX 변환 PDF 여부: {is_pptx_converted}")
        if matched_indicator:
            print(f"  감지 근거: {matched_indicator}")
        if is_slide_ratio:
            print(f"  추가 근거: 슬라이드 화면 비율 ({aspect_ratio:.2f})")

    except Exception as e:
        print(f"  ❌ 오류: {e}")

print("\n" + "=" * 80)
print("테스트 완료")
