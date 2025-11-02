# PDF vs PPTX 청킹 알고리즘 비교 분석

## 📊 개요

현재 시스템은 PDF와 PPTX 문서를 각각 최적화된 방식으로 처리합니다. 이 문서는 두 방식의 공통점과 차이점을 상세히 분석합니다.

---

## 🔄 공통 아키텍처

### Small-to-Large 구조

**PDF와 PPTX 모두 동일한 아키텍처 사용:**

```python
# 공통 패턴
1. Large 청크 생성 (전체 컨텍스트)
   - PDF: 페이지 전체 텍스트
   - PPTX: 슬라이드 전체 텍스트
   - 가중치: 0.5 (컨텍스트 제공용)

2. Small 청크 생성 (세부 요소)
   - PDF: 제목, 문단, 표, 리스트 등
   - PPTX: 제목, 불릿 그룹, 표, 노트 등
   - 가중치: 1.0 ~ 2.0 (검색 우선순위)
```

### Fallback 메커니즘

**공통 사용: `ChunkingFallback` 클래스**

- 긴 내용 자동 분할
- 최소 길이 검증 (50자, 5단어)
- 문장 단위 스마트 분할
- 짧은 청크 병합

---

## ⚙️ 설정값 사용 방식

### 공통 설정값

| 설정 항목 | PDF | PPTX | 공통 여부 |
|----------|-----|------|----------|
| `max_size` | `chunk_size` (500) | 300 (고정) | ❌ **다름** |
| `overlap_size` | `chunk_overlap` (100) | 50 (고정) | ❌ **다름** |
| `enable_small_to_large` | ✅ True | ✅ True | ✅ **공통** |
| `min_chunk_size` | 50 | Fallback에서 사용 | ✅ **공통** |
| `min_word_count` | 5 | Fallback에서 사용 | ✅ **공통** |

### 설정값 전달 경로

```
DocumentProcessor.__init__()
├── chunk_size, chunk_overlap (사용자 설정)
│
├── PDF 엔진:
│   └── pdf_config = {
│       "max_size": chunk_size,        ← 사용자 설정 사용
│       "overlap_size": chunk_overlap, ← 사용자 설정 사용
│       "min_chunk_size": 50,
│       "min_word_count": 5,
│       "enable_small_to_large": True,
│       "enable_layout_analysis": True
│   }
│
└── PPTX 엔진:
    └── pptx_config = {
        "max_size": 300,               ← 하드코딩 (차이점!)
        "overlap_size": 50,            ← 하드코딩 (차이점!)
        "enable_small_to_large": True
    }
```

### ⚠️ 발견된 문제점

**PPTX 설정값이 하드코딩되어 있음:**

```python
# utils/document_processor.py (현재)
pptx_config = {
    "max_size": 300,      # ❌ 하드코딩
    "overlap_size": 50,   # ❌ 하드코딩
    "enable_small_to_large": True
}
```

**개선 필요:**
- PPTX도 사용자 설정값(`chunk_size`, `chunk_overlap`)을 사용하되, PPTX 특성에 맞게 조정
- 예: `max_size = min(chunk_size, 300)` 또는 비율 적용

---

## 📋 처리 로직 비교

### 1. 문서 구조 인식

| 항목 | PDF | PPTX |
|------|-----|------|
| **구조 단위** | 페이지 (Page) | 슬라이드 (Slide) |
| **제목 추출** | `PDFLayoutAnalyzer`로 폰트 크기/굵기 분석 | `slide.shapes.title.text` 직접 접근 |
| **레이아웃 분석** | ✅ Layout-Aware (pdfplumber) | ❌ 없음 (구조화된 API 사용) |
| **섹션 추적** | ✅ 동적 추적 (`_update_section_title`) | ✅ 슬라이드 제목으로 고정 |

### 2. 청크 타입 및 가중치

#### PDF 청크 타입

```python
CHUNK_TYPE_WEIGHTS = {
    "title": 2.0,           # 제목
    "heading": 2.0,         # 헤딩 (H1, H2, H3)
    "caption": 1.8,         # 캡션 (그림/표 설명)
    "list": 1.5,            # 리스트
    "table": 1.2,           # 표
    "paragraph": 1.0,       # 일반 문단
    "page_summary": 0.5,    # 페이지 요약
    "list_segment": 0.9     # 분할된 리스트
}
```

#### PPTX 청크 타입

```python
PPTX_CHUNK_TYPE_WEIGHTS = {
    "slide_title": 2.0,        # 슬라이드 제목
    "slide_notes": 1.7,        # 발표자 노트
    "table": 1.2,              # 표
    "bullet_group": 1.0,       # 불릿 그룹
    "slide_summary": 0.5,      # 슬라이드 요약
    "bullet_group_segment": 0.9  # 분할된 불릿 그룹
}
```

**비교 분석:**
- ✅ 공통: 제목/타이틀 = 2.0 (최우선)
- ✅ 공통: 표 = 1.2
- ✅ 공통: 요약 = 0.5 (컨텍스트용)
- ⚠️ 차이: PDF는 `heading`, `caption` 등 더 세분화
- ⚠️ 차이: PPTX는 `slide_notes` (발표자 노트) 특화

### 3. 불릿/리스트 처리

#### PDF 리스트 처리

```python
# PDF: 리스트 항목 버퍼링 후 그룹화
if elem_type == "list_item":
    current_list_buffer.append(elem_content)
    continue

# 리스트 버퍼 비우기 (다른 요소 만날 때)
if current_list_buffer:
    list_chunks = self._create_list_chunks(...)
```

**특징:**
- 레이아웃 분석 기반 리스트 감지
- 연속된 리스트 항목 자동 그룹화
- 폰트/위치 정보 활용

#### PPTX 불릿 처리

```python
# PPTX: paragraph.level 기반 그룹핑
for paragraph in text_frame.paragraphs:
    indent_level = paragraph.level
    
    # Level 0 = 새 그룹 시작
    if indent_level == 0 and current_bullet_group_lines:
        # 지금까지 모은 그룹을 청크로 생성
        group_content = "\n".join(current_bullet_group_lines)
        # Fallback 적용
```

**특징:**
- `paragraph.level` 속성 직접 활용 (0, 1, 2...)
- Level 0을 기준으로 그룹 분리
- ⚠️ 문제: `bullet_level` 메타데이터가 항상 0으로 고정됨

**비교:**
- ✅ PDF: 레이아웃 기반 (더 유연하지만 복잡)
- ✅ PPTX: 구조 기반 (간단하지만 제한적)
- ⚠️ PPTX 개선 필요: 실제 `bullet_level` 값 저장

### 4. 표(Table) 처리

#### PDF 표 처리

```python
# PDF: pdfplumber로 표 추출
tables = page.extract_tables()
for table in tables:
    # 테이블 데이터를 2D 리스트로 처리
    table_data = [[cell for cell in row] for row in table]
    # Markdown 형식으로 변환
    markdown_table = self._convert_table_to_markdown(table_data)
```

#### PPTX 표 처리

```python
# PPTX: python-pptx API로 표 접근
if hasattr(shape, 'table') and shape.has_table:
    markdown_table = self._convert_table_to_markdown(shape.table)
    # Fallback 적용
```

**비교:**
- ✅ 공통: Markdown 형식으로 변환
- ✅ 공통: Fallback으로 긴 표 분할
- ⚠️ 차이: PDF는 2D 리스트, PPTX는 Table 객체 직접 사용

### 5. 에러 처리 및 Fallback

#### PDF 에러 처리

```python
try:
    # 고급 청킹 시도
    with pdfplumber.open(pdf_path) as pdf:
        # Layout-Aware 처리
except Exception as e:
    # 폴백 1: 기본 텍스트 추출
    basic_text = page.extract_text()
    # 폴백 2: 전체 문서 텍스트 추출
    # 최종 폴백: 기본 분할기 사용
```

#### PPTX 에러 처리

```python
try:
    # 고급 청킹 시도
    presentation = Presentation(pptx_path)
    # 슬라이드 구조 기반 처리
except Exception as e:
    # ⚠️ 현재: 에러만 출력, 폴백 없음
    print(f"PPTX 처리 중 오류 발생: {e}")
    # → UnstructuredPowerPointLoader로 폴백해야 함
```

**비교:**
- ⚠️ PPTX: 에러 발생 시 폴백 로직 부족
- ✅ PDF: 다단계 폴백 메커니즘 완비

---

## 📊 메타데이터 구조 비교

### PDF 메타데이터

```python
@dataclass
class ChunkMetadata:
    document_id: str
    page_number: int
    parent_chunk_id: Optional[str]
    section_title: str
    chunk_type_weight: float
    font_size: float          # ✅ 폰트 정보
    is_bold: bool             # ✅ 굵기 정보
    coordinates: Optional[tuple]  # ✅ 좌표 정보
    word_count: int
    char_count: int
    has_code: bool
    has_table: bool
    has_list: bool
    has_formula: bool
    language: str
    heading_level: Optional[str]  # H1, H2, H3
    caption_type: Optional[str]   # figure, table
    section_number: Optional[str]  # 1.1, 2.3.1
```

### PPTX 메타데이터

```python
@dataclass
class PPTXChunkMetadata:
    document_id: str
    slide_number: int
    parent_chunk_id: Optional[str]
    slide_title: str          # ✅ 슬라이드 제목
    chunk_type_weight: float
    word_count: int
    char_count: int
    bullet_level: Optional[int]  # ⚠️ 항상 0으로 고정됨
    has_notes: bool              # ✅ 노트 포함 여부
    has_table: bool
    shape_type: str              # text, table, chart
    language: str
```

**비교:**
- ✅ 공통: `document_id`, `parent_chunk_id`, `chunk_type_weight`
- ✅ 공통: `word_count`, `char_count`, `has_table`
- ⚠️ 차이: PDF는 레이아웃 정보(폰트, 좌표) 풍부
- ⚠️ 차이: PPTX는 구조 정보(슬라이드, 노트) 특화
- ❌ 문제: PPTX `bullet_level`이 실제 값 반영 안 됨

---

## 🔍 핵심 차이점 요약

### 1. 구조 인식 방식

| 항목 | PDF | PPTX |
|------|-----|------|
| **방식** | 레이아웃 분석 (시각적) | 구조 API (프로그래밍) |
| **도구** | pdfplumber + LayoutAnalyzer | python-pptx |
| **장점** | 다양한 레이아웃 대응 | 정확한 구조 정보 |
| **단점** | 복잡한 로직, 성능 부담 | 구조화되지 않은 내용 처리 어려움 |

### 2. 설정값 활용

| 항목 | PDF | PPTX |
|------|-----|------|
| **max_size** | 사용자 설정값 사용 | 하드코딩 (300) |
| **overlap_size** | 사용자 설정값 사용 | 하드코딩 (50) |
| **유연성** | 높음 | 낮음 |

### 3. 에러 처리

| 항목 | PDF | PPTX |
|------|-----|------|
| **폴백 단계** | 3단계 (고급 → 기본 → 전체) | 1단계 (에러 출력만) |
| **안정성** | 높음 | 낮음 |

### 4. 불릿/리스트 처리

| 항목 | PDF | PPTX |
|------|-----|------|
| **방식** | 레이아웃 기반 버퍼링 | Level 기반 그룹핑 |
| **메타데이터** | 정확한 레벨 정보 | ⚠️ 항상 0으로 고정 |

---

## ✅ 개선 제안

### 1. PPTX 설정값 통합

```python
# 개선안: PPTX도 사용자 설정값 사용
pptx_config = {
    "max_size": min(chunk_size, 400),  # PPTX 최적값 고려
    "overlap_size": min(chunk_overlap, 100),  # 오버랩도 설정값 사용
    "enable_small_to_large": True
}
```

또는 비율 적용:

```python
pptx_config = {
    "max_size": int(chunk_size * 0.3),  # PPTX는 PDF의 30% 크기
    "overlap_size": int(chunk_overlap * 0.25),  # 오버랩도 비율 적용
    "enable_small_to_large": True
}
```

### 2. PPTX bullet_level 수정

```python
# 현재 (문제)
bullet_level=0  # 항상 0으로 고정

# 개선안
bullet_level=indent_level  # 실제 레벨 값 저장
```

### 3. PPTX 에러 처리 개선

```python
# 현재
except Exception as e:
    print(f"PPTX 처리 중 오류 발생: {e}")
    # → 빈 리스트 반환

# 개선안
except Exception as e:
    print(f"고급 PPTX 청킹 실패, 기본 방식으로 폴백: {e}")
    try:
        loader = UnstructuredPowerPointLoader(pptx_path)
        documents = loader.load()
        return documents
    except Exception as fallback_error:
        print(f"기본 PPTX 로드도 실패: {fallback_error}")
        return []
```

### 4. 공통 설정값 상수화

```python
# config.py 또는 상수 파일에 정의
PPTX_CHUNK_SIZE_RATIO = 0.3  # PDF 대비 PPTX 청크 크기 비율
PPTX_OVERLAP_RATIO = 0.25    # PDF 대비 PPTX 오버랩 비율
```

---

## 📈 성능 및 품질 비교

### 예상 청크 수

| 문서 타입 | 평균 청크 수 | 최적 크기 |
|----------|------------|----------|
| PDF (10페이지) | 50-100개 | 500자 |
| PPTX (10슬라이드) | 30-60개 | 300자 |

### 검색 정확도 예상

| 청크 타입 | PDF | PPTX |
|----------|-----|------|
| 제목/타이틀 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 표 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 리스트/불릿 | ⭐⭐⭐⭐ | ⭐⭐⭐ (Level 정보 부족) |
| 노트 | N/A | ⭐⭐⭐⭐⭐ |

---

## 🎯 결론

### 공통점 (잘 된 부분)

1. ✅ Small-to-Large 아키텍처 공통 사용
2. ✅ Fallback 메커니즘 공통 사용
3. ✅ 가중치 시스템 유사
4. ✅ 메타데이터 구조 유사

### 차이점 (개선 필요)

1. ⚠️ PPTX 설정값 하드코딩 → 사용자 설정값 사용 필요
2. ⚠️ PPTX bullet_level 정보 손실 → 실제 값 저장 필요
3. ⚠️ PPTX 에러 처리 부족 → 다단계 폴백 필요
4. ⚠️ PPTX 레이아웃 정보 부족 → 가능한 한 정보 보강

### ✅ 개선 적용 현황

1. **✅ 1단계**: PPTX 설정값 통합 (사용자 설정값 사용) - **완료**
2. **✅ 2단계**: bullet_level 수정 (실제 값 저장) - **완료**
3. **✅ 3단계**: 에러 처리 개선 (폴백 메커니즘 추가) - **완료**
4. **✅ 4단계**: 메타데이터 풍부화 (추가 정보 수집) - **완료**

---

**작성일**: 2025-11-02  
**최종 업데이트**: 2025-11-02 (개선 사항 적용 완료)  
**버전**: 1.1

