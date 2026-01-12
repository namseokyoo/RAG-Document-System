# PDF 페이지 번호 불일치 문제 분석

## 문제 요약

**사용자 보고**: 출처에 표시되는 페이지 번호가 실제 문서의 페이지와 일치하지 않음

**예시**:
- 출처에 "p.16" 표시
- 실제 PDF를 열어보면 논리적 페이지 번호가 다를 수 있음

## 근본 원인

PDF 문서에는 두 가지 페이지 번호 체계가 존재합니다:

### 1. 물리적 페이지 번호 (Physical Page Number)
- PDF 파일의 실제 페이지 순서: 1, 2, 3, 4, 5...
- 현재 시스템이 저장하는 방식
- `enumerate(pdf.pages, 1)`로 추출

### 2. 논리적 페이지 번호 (Logical Page Number / Page Label)
- PDF 뷰어에서 사용자에게 표시되는 페이지 번호
- 논문/책의 경우:
  - 표지, 목차: 로마 숫자 (i, ii, iii, iv, v)
  - 본문 시작: 아라비아 숫자 1부터 다시 시작
- 예시:
  - 물리적 페이지 1-5 = 표지, 목차 (논리적: i, ii, iii, iv, v)
  - 물리적 페이지 6 = 본문 시작 (논리적: 1)
  - 물리적 페이지 21 = 본문 16페이지 (논리적: 16)

## 현재 코드 분석

### PDF 처리 코드
```python
# utils/pdf_chunking_engine.py:237
for page_num, page in enumerate(pdf.pages, 1):
    # page_num은 물리적 페이지 번호 (1, 2, 3...)
    chunk.metadata.page_number = page_num
```

### 메타데이터 저장
```python
# utils/document_processor.py:171
"page_number": chunk.metadata.page_number  # 물리적 페이지 번호만 저장
```

## 해결 방안

### 방안 1: 논리적 페이지 번호 추출 및 저장 (권장)

**장점**:
- 사용자가 PDF 뷰어에서 보는 번호와 일치
- 가장 사용자 친화적

**구현 방법**:
1. PyMuPDF (fitz)를 사용하여 논리적 페이지 번호 추출
2. 물리적 페이지 번호와 논리적 페이지 번호 모두 저장
3. UI에서 논리적 페이지 번호 우선 표시

**코드 예시**:
```python
import fitz  # PyMuPDF

def get_logical_page_number(pdf_path: str, physical_page_num: int) -> str:
    """물리적 페이지 번호에 대응하는 논리적 페이지 번호 추출"""
    doc = fitz.open(pdf_path)
    try:
        page = doc[physical_page_num - 1]  # 0-based index
        # 논리적 페이지 레이블 추출 시도
        # PyMuPDF의 page_label 속성 사용
        label = page.get_label() if hasattr(page, 'get_label') else None
        
        if label:
            return label
        else:
            # 논리적 레이블이 없으면 물리적 번호 반환
            return str(physical_page_num)
    finally:
        doc.close()
```

### 방안 2: 물리적/논리적 페이지 번호 모두 저장

**메타데이터 구조**:
```python
{
    "page_number": 21,  # 물리적 페이지 번호 (파일 내부 인덱스)
    "logical_page_number": "16",  # 논리적 페이지 번호 (뷰어 표시)
    "page_label": "16"  # 페이지 레이블 (i, ii, 1, 2...)
}
```

### 방안 3: UI에서 명확히 표시

**표시 방식**:
- 논리적 페이지 번호가 있으면: "p.16"
- 논리적 페이지 번호가 없으면: "p.16 (물리적)"
- 또는: "p.16" + 툴팁에 "물리적 페이지: 21" 표시

## 구현 단계

### Phase 1: 논리적 페이지 번호 추출 함수 추가
- `utils/pdf_chunking_engine.py`에 논리적 페이지 번호 추출 메서드 추가
- PyMuPDF를 사용하여 PDF 페이지 레이블 추출

### Phase 2: 메타데이터 구조 확장
- `ChunkMetadata`에 `logical_page_number` 필드 추가
- `document_processor.py`에서 논리적 페이지 번호 저장

### Phase 3: UI 수정
- `ui/chat_widget.py`의 `_format_sources()`에서 논리적 페이지 번호 우선 표시
- 물리적 페이지 번호는 툴팁으로 제공

### Phase 4: 파일 열기 기능 개선
- 물리적 페이지 번호를 사용하여 정확한 페이지로 이동
- PDF 뷰어 API 사용 (가능한 경우)

## 참고 자료

- PDF 페이지 레이블 명세: PDF 1.3 이상에서 지원
- PyMuPDF 문서: `fitz.Page` 객체의 페이지 레이블 접근
- 논문 PDF 특성: 대부분 표지/목차가 로마 숫자, 본문이 아라비아 숫자

## 우선순위

1. **높음**: 논리적 페이지 번호 추출 및 저장
2. **중간**: UI에서 논리적 페이지 번호 표시
3. **낮음**: 파일 열기 시 정확한 페이지 이동 (PDF 뷰어 의존적)

