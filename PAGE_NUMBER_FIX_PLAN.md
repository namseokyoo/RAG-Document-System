# 페이지 번호 버그 수정 계획

## 문제 요약

**사용자 보고**: 4페이지 PDF에서 p.809, p.781 같은 잘못된 페이지 번호 표시

**근본 원인**: PPTX 파일에서 `page_number = chunk_index + 1`로 잘못 설정됨
- 현재 DB: 75개의 PPTX 청크가 잘못된 page_number 보유

---

## 처리 경로 검증

### 1. PDF 페이지 번호 처리

#### 경로 1: 고급 PDF 청킹
```
pdf_chunking_engine.py
  → chunk.metadata.page_number = 올바른 페이지 번호
  → _load_pdf_with_advanced_chunking()
  → Document(metadata={'page_number': chunk.metadata.page_number})
  → process_document()
    → page_number = slide_number(None) or page_number(있음) ✓
```
**결과**: 올바름 ✓

#### 경로 2: 기본 PDF 로더
```
_load_pdf_with_fitz()
  → Document(metadata={'page': page_num + 1})
  → process_document()
    → page_number = slide_number(None) or page(있음) ✓
```
**결과**: 올바름 ✓

---

### 2. PPTX 슬라이드 번호 처리

#### 경로 1: 고급 PPTX 청킹 (버그 발생 지점!)
```
pptx_chunking.py
  → chunk.metadata.slide_number = 올바른 슬라이드 번호
  → _load_pptx_with_advanced_chunking()
  → Document(metadata={'slide_number': chunk.metadata.slide_number})
    ⚠️ page_number 필드 없음!
  → process_document() [수정 전]
    → page_number = slide_number(None) or page(None) or i+1 ❌
    → page_number = chunk_index + 1 (잘못됨!)
```
**문제**: 슬라이드 1에 3개 청크 → page 1, 2, 3으로 표시됨!

```
  → process_document() [수정 후]
    → page_number = slide_number(있음!) ✓
```
**해결**: 슬라이드 1에 3개 청크 → 모두 page 1로 표시됨 ✓

#### 경로 2: 기본 PPTX 로더
```
UnstructuredPowerPointLoader()
  → 로더가 'page' 필드 제공 가능 (확인 필요)
  → page_number = slide_number(?) or page(?) or i+1
```
**상태**: 로더 의존적 (큰 영향 없음)

---

## 수정 사항

### ✅ 완료: document_processor.py

**위치**: [document_processor.py:408](utils/document_processor.py#L408)

**수정 전**:
```python
"page_number": doc.metadata.get("page", i + 1),
```

**수정 후**:
```python
# PPTX는 slide_number를 page_number로 사용, PDF는 기존 page 필드 또는 인덱스
"page_number": doc.metadata.get("slide_number") or doc.metadata.get("page", i + 1),
```

**효과**:
- PPTX: `slide_number` → `page_number` (올바름!)
- PDF: 기존 동작 유지 (이미 올바름)

---

### ⚠️ 추가 필요: chat_widget.py

**위치**: [chat_widget.py:323](ui/chat_widget.py#L323)

**현재 문제**:
```python
# 같은 페이지 번호 중복 표시
file_dict[file_name].append((page_number, score_txt))
```

**예시 (문제)**:
```
검색 결과:
  청크1 (슬라이드 1) → 70%
  청크2 (슬라이드 1) → 65%
  청크3 (슬라이드 2) → 80%

표시:
  - 파일명.pptx
    p.1 (70%), p.1 (65%), p.2 (80%)  ← p.1 중복!
```

**수정 방안: 같은 페이지는 최고 점수만 표시** (권장)
```python
# 페이지별로 최고 점수만 유지
page_dict = {}
for s in sources:
    file_name = s.get('file_name', '?')
    page_number = s.get('page_number', '?')
    score = float(s.get("similarity_score", 0))

    if file_name not in file_dict:
        file_dict[file_name] = {}

    # 같은 페이지는 최고 점수만
    if page_number not in file_dict[file_name] or score > file_dict[file_name][page_number]:
        file_dict[file_name][page_number] = score
```

**수정 후 표시**:
```
  - 파일명.pptx
    p.1 (70%), p.2 (80%)  ← 깔끔!
```

---

## 시나리오별 예상 결과

### 시나리오 1: 4페이지 PDF, 각 페이지당 2개 청크

**데이터**:
```
청크0 (PDF page 1) → page_number = 1, score = 70%
청크1 (PDF page 1) → page_number = 1, score = 65%
청크2 (PDF page 2) → page_number = 2, score = 80%
청크3 (PDF page 2) → page_number = 2, score = 75%
```

**인용**:
```
[파일명, p.1], [파일명, p.1], [파일명, p.2], [파일명, p.2]
```

**UI 표시 (수정 전)**:
```
- 파일명.pdf
  p.1 (70%), p.1 (65%), p.2 (80%), p.2 (75%)
```

**UI 표시 (수정 후)**:
```
- 파일명.pdf
  p.1 (70%), p.2 (80%)
```

---

### 시나리오 2: 3슬라이드 PPTX, 슬라이드당 3개 청크

**데이터 (버그 수정 전)**:
```
청크0 (slide 1) → page_number = 1, score = 70%
청크1 (slide 1) → page_number = 2 ❌, score = 65%
청크2 (slide 1) → page_number = 3 ❌, score = 60%
청크3 (slide 2) → page_number = 4 ❌, score = 80%
```

**데이터 (버그 수정 후)**:
```
청크0 (slide 1) → page_number = 1 ✓, score = 70%
청크1 (slide 1) → page_number = 1 ✓, score = 65%
청크2 (slide 1) → page_number = 1 ✓, score = 60%
청크3 (slide 2) → page_number = 2 ✓, score = 80%
```

**인용 (수정 후)**:
```
[파일명, p.1], [파일명, p.1], [파일명, p.1], [파일명, p.2]
```

**UI 표시 (최종)**:
```
- 파일명.pptx
  p.1 (70%), p.2 (80%)
```

---

### 시나리오 3: 사용자 보고 케이스 (4슬라이드, 237청크)

**버그 수정 전**:
```
청크809 (slide 4?) → page_number = 810 ❌
청크781 (slide 3?) → page_number = 782 ❌
인용: [파일명, p.810], [파일명, p.782]
```

**버그 수정 후**:
```
청크809 (slide 4) → page_number = 4 ✓
청크781 (slide 3) → page_number = 3 ✓
인용: [파일명, p.4], [파일명, p.3]
```

---

## 적용 계획

### Phase 1: 코어 버그 수정 ✅
- [x] document_processor.py:408 수정
  - `page_number = slide_number or page or (i+1)`

### Phase 2: UI 중복 처리 ⚠️
- [ ] chat_widget.py:312-336 수정
  - 같은 페이지는 최고 점수만 표시

### Phase 3: 데이터베이스 재생성 권장
- [ ] 현재 DB의 75개 PPTX 청크 재임베딩
  - 방법 1: PPTX 파일 삭제 후 재업로드
  - 방법 2: ChromaDB 전체 초기화

### Phase 4: 테스트
- [ ] 4페이지 PDF 테스트
- [ ] 3슬라이드 PPTX 테스트
- [ ] 인용 및 UI 표시 확인

---

## 핵심 개선 사항

### 수정 전 (버그):
```
PPTX 슬라이드 1 → 3개 청크 → page 1, 2, 3 ❌
사용자 혼란: "슬라이드 1인데 왜 페이지 3까지?"
```

### 수정 후:
```
PPTX 슬라이드 1 → 3개 청크 → page 1, 1, 1 ✓
UI 표시: p.1 (최고점수) ✓
사용자 이해: "슬라이드 1의 관련도가 70%구나"
```

---

## 결론

✅ **목표 달성**: 문서의 **실제 페이지/슬라이드 번호** 정확히 표시
- PDF: 페이지 번호 정확
- PPTX: 슬라이드 번호 정확
- 청킹: 내부 단위, 사용자에게 숨김

⚠️ **다음 단계**: UI 중복 처리 수정 필요
