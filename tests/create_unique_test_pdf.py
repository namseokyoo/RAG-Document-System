"""
고유한 내용의 테스트 PDF 생성
- 검색 가능한 고유 키워드 포함
- 간단한 텍스트 전용 (Vision 필요 없음)
"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import random
import string

def create_unique_test_pdf():
    """고유한 테스트 내용을 가진 PDF 생성"""

    # 고유 식별자 생성
    unique_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    filename = f"data/test_pdf/UNIQUE_TEST_{unique_id}.pdf"

    # PDF 생성
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # 페이지 1: 고유 내용
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, f"UNIQUE TEST DOCUMENT {unique_id}")

    c.setFont("Helvetica", 12)
    y = height - 1.5*inch

    unique_content = f"""
This is a test document with unique identifier: {unique_id}

MAGIC KEYWORD: XYLOPHONE_{unique_id}_ZEBRA

Test Content:
- This document discusses the revolutionary XYLOPHONE_{unique_id}_ZEBRA theory
- The theory was developed specifically for testing PDF Vision RAG integration
- Key finding: XYLOPHONE_{unique_id}_ZEBRA improves search accuracy by 999%

Conclusion:
If you can find this document when searching for "XYLOPHONE_{unique_id}_ZEBRA",
then the RAG system is working correctly.
"""

    for line in unique_content.strip().split('\n'):
        c.drawString(1*inch, y, line)
        y -= 0.25*inch

    c.showPage()

    # 페이지 2: 추가 검증 내용
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1*inch, height - 1*inch, "Page 2: Additional Test Content")

    c.setFont("Helvetica", 12)
    y = height - 1.5*inch

    additional_content = f"""
SECONDARY MAGIC KEYWORD: QUANTUM_{unique_id}_BANANA

This page contains additional test information:
- The QUANTUM_{unique_id}_BANANA experiment was successful
- Results show 100% correlation with XYLOPHONE_{unique_id}_ZEBRA theory
- Both keywords should be searchable in the RAG system

Test Question Examples:
Q1: What is XYLOPHONE_{unique_id}_ZEBRA?
A1: A revolutionary theory for testing (should find this document)

Q2: Tell me about QUANTUM_{unique_id}_BANANA
A2: An experiment related to the theory (should find this document)

Q3: What is the unique identifier of this test?
A3: {unique_id} (should find this document)
"""

    for line in additional_content.strip().split('\n'):
        c.drawString(1*inch, y, line)
        y -= 0.25*inch
        if y < 1*inch:
            break

    c.save()

    return filename, unique_id

if __name__ == "__main__":
    import os
    os.makedirs("data/test_pdf", exist_ok=True)

    filename, unique_id = create_unique_test_pdf()
    print(f"Created test PDF: {filename}")
    print(f"Unique ID: {unique_id}")
    print(f"\nTest keywords:")
    print(f"  - XYLOPHONE_{unique_id}_ZEBRA")
    print(f"  - QUANTUM_{unique_id}_BANANA")
    print(f"  - {unique_id}")
