"""
PDF 파일 읽기 테스트
"""
from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()

import pdfplumber

try:
    from PyPDF2 import PdfReader
except ImportError:
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None

test_pdf = r"C:/Users/yns19/Downloads/항공권_유남석.pdf"

print("=== pdfplumber 테스트 ===")
try:
    with pdfplumber.open(test_pdf) as pdf:
        print(f"✅ 성공! 페이지 수: {len(pdf.pages)}")
        print(f"첫 페이지 텍스트 길이: {len(pdf.pages[0].extract_text() or '')}")
except Exception as e:
    print(f"❌ 실패: {e}")

print("\n=== PyPDF2/pypdf 테스트 ===")
if PdfReader:
    try:
        reader = PdfReader(test_pdf)
        print(f"✅ 성공! 페이지 수: {len(reader.pages)}")
    except Exception as e:
        print(f"❌ 실패: {e}")
        import traceback
        traceback.print_exc()
else:
    print("PyPDF2/pypdf 미설치")
