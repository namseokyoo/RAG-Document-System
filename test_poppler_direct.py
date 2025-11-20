"""
Poppler 직접 테스트
"""
from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()

from pdf2image import convert_from_path
from config import ConfigManager
import os

config = ConfigManager()
poppler_path = config.get('poppler_path')

print(f"Poppler 경로: {poppler_path}")
print(f"경로 존재: {os.path.exists(poppler_path) if poppler_path else False}")

if poppler_path and os.path.exists(poppler_path):
    pdftoppm_path = os.path.join(poppler_path, "pdftoppm.exe")
    print(f"pdftoppm.exe 존재: {os.path.exists(pdftoppm_path)}")

# 테스트 PDF 변환
test_pdf = r"C:/Users/yns19/Downloads/항공권_유남석.pdf"
print(f"\n테스트 PDF: {test_pdf}")
print(f"PDF 존재: {os.path.exists(test_pdf)}")

try:
    print("\n=== PDF → 이미지 변환 테스트 ===")
    kwargs = {"dpi": 150}
    if poppler_path:
        kwargs["poppler_path"] = poppler_path
        print(f"poppler_path 전달: {poppler_path}")

    images = convert_from_path(test_pdf, **kwargs)
    print(f"✅ 성공! {len(images)}개 이미지 생성")
except Exception as e:
    print(f"❌ 실패: {e}")
    import traceback
    traceback.print_exc()
