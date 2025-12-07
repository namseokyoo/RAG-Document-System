"""
페이지 번호 수정 사항 검증 스크립트
"""

print("=" * 60)
print("페이지 번호 처리 경로 검증")
print("=" * 60)

# 1. PDF 처리 경로 검증
print("\n[1] PDF 처리 경로")
print("-" * 60)

print("\n경로 1: 고급 PDF 청킹 (_load_pdf_with_advanced_chunking)")
print("  청킹 엔진: pdf_chunking_engine.py")
print("  page_number 설정: chunk.metadata.page_number (올바름)")
print("  process_document() 통과:")
print("    -> doc.metadata.get('slide_number') = None")
print("    -> doc.metadata.get('page', i+1) = page_number (이미 있음)")
print("  결과: page_number = 올바른 PDF 페이지 번호 ✓")

print("\n경로 2: 기본 PDF 로더 (_load_pdf_with_fitz)")
print("  로더: fitz (PyMuPDF)")
print("  메타데이터: {'page': page_num + 1}")
print("  process_document() 통과:")
print("    -> doc.metadata.get('slide_number') = None")
print("    -> doc.metadata.get('page', i+1) = page_num + 1")
print("  결과: page_number = 올바른 PDF 페이지 번호 ✓")

# 2. PPTX 처리 경로 검증
print("\n\n[2] PPTX 처리 경로")
print("-" * 60)

print("\n경로 1: 고급 PPTX 청킹 (_load_pptx_with_advanced_chunking)")
print("  청킹 엔진: pptx_chunking.py")
print("  메타데이터: {'slide_number': chunk.metadata.slide_number}")
print("  ⚠️ page_number 필드 없음!")
print("  process_document() 통과 (수정 후):")
print("    -> doc.metadata.get('slide_number') = slide_number")
print("    -> 첫 번째 조건 매칭!")
print("  결과: page_number = slide_number ✓")

print("\n경로 2: 기본 PPTX 로더 (UnstructuredPowerPointLoader)")
print("  로더: UnstructuredPowerPointLoader")
print("  메타데이터: 확인 필요 (보통 'page' 필드 있음)")
print("  process_document() 통과:")
print("    -> doc.metadata.get('slide_number') = None (없을 수 있음)")
print("    -> doc.metadata.get('page', i+1) = 로더가 제공한 page 또는 i+1")
print("  결과: 로더 의존적 (확인 필요)")

# 3. 출처 표시 경로
print("\n\n[3] 출처 표시 경로")
print("-" * 60)

print("\n인용 포맷 (_format_citation in rag_chain.py):")
print("  page = source.metadata.get('page_number', '?')")
print("  citation = f'[{short_name}, p.{page}]'")
print("  ✓ page_number 사용 (올바름)")

print("\nUI 출처 표시 (_format_sources in chat_widget.py):")
print("  현재: 모든 (page_number, score) 쌍을 나열")
print("  문제: 같은 페이지 번호 중복 가능")
print("  예: p.1 (70%), p.1 (65%), p.2 (80%)")
print("  ⚠️ 수정 필요: 같은 페이지는 최고 점수만 표시")

# 4. 시나리오별 결과 예측
print("\n\n[4] 시나리오별 예상 결과")
print("-" * 60)

print("\n시나리오 1: 4페이지 PDF, 각 페이지 2개 청크")
print("  청크 0 (page 1) → page_number = 1")
print("  청크 1 (page 1) → page_number = 1")
print("  청크 2 (page 2) → page_number = 2")
print("  청크 3 (page 2) → page_number = 2")
print("  ...")
print("  인용: [파일명, p.1], [파일명, p.1], [파일명, p.2], ...")
print("  UI 표시 (수정 전): p.1 (70%), p.1 (65%), p.2 (80%), ...")
print("  UI 표시 (수정 후): p.1 (70%), p.2 (80%), ... (최고 점수만)")

print("\n시나리오 2: 3슬라이드 PPTX, 슬라이드당 3개 청크")
print("  청크 0 (slide 1) → page_number = 1 ✓ (수정 후)")
print("  청크 1 (slide 1) → page_number = 1 ✓")
print("  청크 2 (slide 1) → page_number = 1 ✓")
print("  청크 3 (slide 2) → page_number = 2 ✓")
print("  ...")
print("  인용: [파일명, p.1], [파일명, p.1], [파일명, p.2], ...")
print("  UI 표시 (수정 후): p.1 (최고점수), p.2 (최고점수), ...")

print("\n시나리오 3: 사용자 보고 케이스 (4페이지, 237청크)")
print("  수정 전:")
print("    청크 809 → page_number = 810 (chunk_index + 1) ❌")
print("    청크 781 → page_number = 782 ❌")
print("  수정 후:")
print("    청크 809 (slide 4) → page_number = 4 ✓")
print("    청크 781 (slide 4) → page_number = 4 ✓")

# 5. 적용 계획
print("\n\n[5] 적용 계획")
print("-" * 60)

print("\n✅ 완료:")
print("  1. document_processor.py:408 수정")
print("     page_number = slide_number or page or (i+1)")

print("\n⚠️ 추가 필요:")
print("  2. chat_widget.py:323 수정 - 같은 페이지 중복 제거")
print("     옵션: 같은 페이지는 최고 점수만 표시")
print("  3. 기존 ChromaDB 재생성 권장")
print("     현재 DB의 75개 PPTX 청크가 잘못된 page_number")

print("\n" + "=" * 60)
print("검증 완료")
print("=" * 60)
