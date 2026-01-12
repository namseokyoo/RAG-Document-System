# 논리적 페이지 번호 추출 및 표시 구현 계획

## 문제 분석

**사용자 보고**: 
- 로그에서 "페이지: 16" (물리적 페이지 번호)
- 로그에서 "섹션: Page 13" (실제 문서에 표시된 논리적 페이지 번호)
- 실제 PDF 뷰어에서 보이는 페이지 번호와 시스템이 저장한 페이지 번호가 불일치

**근본 원인**:
- 시스템은 PDF의 물리적 페이지 번호(16)만 저장
- PDF 문서 내부에는 논리적 페이지 번호(13)가 표시됨
- 사용자가 PDF 뷰어에서 보는 것은 논리적 페이지 번호

## 해결 방안

### Phase 1: 논리적 페이지 번호 추출 함수 구현

**목표**: PDF 페이지 텍스트에서 "Page X" 패턴 추출

**위치**: `utils/pdf_chunking_engine.py`

**구현 내용**:
1. `_extract_logical_page_number()` 메서드 추가
   - PDF 페이지 텍스트에서 "Page X" 패턴 찾기
   - 정규표현식: `r'\bPage\s+(\d+)\b'` (대소문자 무시)
   - 페이지 하단/헤더에서 찾기 (일반적으로 페이지 번호 위치)
   - 여러 개 발견 시 첫 번째 사용

2. 페이지 처리 시 논리적 페이지 번호 추출
   - `process_pdf_document()`에서 각 페이지 처리 시 호출
   - 추출된 논리적 페이지 번호를 메타데이터에 저장

### Phase 2: 메타데이터 구조 확장

**위치**: `utils/pdf_chunking.py`

**수정 내용**:
- `ChunkMetadata`에 `logical_page_number: Optional[int] = None` 필드 추가
- 물리적 페이지 번호(`page_number`)와 논리적 페이지 번호(`logical_page_number`) 모두 저장

**위치**: `utils/document_processor.py`

**수정 내용**:
- 메타데이터 변환 시 `logical_page_number` 필드 추가

### Phase 3: UI 표시 개선

**위치**: `ui/chat_widget.py`

**수정 내용**:
- `_format_sources()`에서 논리적 페이지 번호 우선 표시
  - `logical_page_number`가 있으면: `p.{logical_page_number}` 표시
  - 없으면: `p.{page_number}` 표시 (기존 동작)

**위치**: `utils/rag_chain.py`

**수정 내용**:
- `get_source_documents()`에서 논리적 페이지 번호도 반환
- `_format_docs()`에서 논리적 페이지 번호 표시

## 구현 순서

1. ✅ 문제 분석 및 계획 수립
2. ⏳ 논리적 페이지 번호 추출 함수 구현
3. ⏳ ChunkMetadata에 logical_page_number 필드 추가
4. ⏳ 페이지 처리 시 논리적 페이지 번호 추출 및 저장
5. ⏳ UI에서 논리적 페이지 번호 우선 표시
6. ⏳ 테스트 및 검증

## 예상 결과

### 수정 전:
```
📄 문서 #1
   파일명: OLED_1908.00197v1.pdf
   페이지: 16
   섹션: Page 13
```
→ UI 표시: "p.16"

### 수정 후:
```
📄 문서 #1
   파일명: OLED_1908.00197v1.pdf
   페이지: 16 (물리적)
   논리적 페이지: 13
   섹션: Page 13
```
→ UI 표시: "p.13" (논리적 페이지 번호)

## 참고사항

- 논리적 페이지 번호가 추출되지 않는 경우: 물리적 페이지 번호 사용 (기존 동작)
- 여러 패턴 지원: "Page X", "page X", "P. X" 등
- 로마 숫자 페이지 번호는 향후 확장 고려 (i, ii, iii...)

