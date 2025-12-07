# Phase 1-B 구현 리포트: 표 구조 기반 이미지 매칭

**작성일**: 2025-11-19
**상태**: 구현 완료, 테스트 진행 중

---

## 개요

제목 없는 슬라이드의 이미지 매칭 문제를 해결하기 위해 표 구조 기반 매칭 알고리즘을 구현했습니다.

**문제**: 슬라이드 2처럼 제목이 없는 경우, COM과 python-pptx 순서 불일치로 인해 제목 기반 매칭 불가

**해결**: 슬라이드의 표 구조(행/열 개수)를 비교하여 매칭

---

## 구현 내용

### 1. 새로 추가된 함수 (3개)

#### 1.1. `_extract_table_structure()`

**위치**: [utils/pptx_chunking_engine.py:253-302](utils/pptx_chunking_engine.py#L253-L302)

**목적**: python-pptx 슬라이드에서 표 구조 추출

**반환값**:
```python
{
    "has_table": bool,
    "table_count": int,
    "tables": [
        {
            "rows": int,
            "cols": int,
            "headers": [str, ...]
        },
        ...
    ]
}
```

**코드 예시**:
```python
slide_structure = self._extract_table_structure(slide)
# 슬라이드 2 예상 결과: {"has_table": True, "table_count": 1, "tables": [{"rows": 5, "cols": 3, "headers": ["분기", "매출", "성장률"]}]}
```

---

#### 1.2. `_detect_table_structure_via_vision()`

**위치**: [utils/pptx_chunking_engine.py:304-405](utils/pptx_chunking_engine.py#L304-L405)

**목적**: Vision API로 이미지에서 표 구조 감지

**파라미터**:
- `image_base64`: Base64 인코딩된 슬라이드 이미지
- `llm_api_type`: "openai" (현재 OpenAI만 지원)
- `llm_api_key`: API 키
- `llm_model`: 모델 이름 (예: "gpt-4o-mini")

**Vision 프롬프트** (간소화):
```
이 슬라이드에 표가 있나요? 있다면:

1. 표의 개수
2. 각 표의 행(row) 개수와 열(column) 개수

다음 형식으로만 답변하세요:
표_개수: N
표1: R행 C열
표2: R행 C열
(표가 없으면 "표_개수: 0"만 출력)
```

**특징**:
- `detail: "low"` 사용 (비용 절감: 85 tokens vs 600 tokens)
- `max_tokens: 100` (표 구조 정보만 필요)
- `temperature: 0` (일관된 결과)

**반환값**:
```python
{
    "has_table": bool,
    "table_count": int,
    "tables": [
        {"rows": int, "cols": int},
        ...
    ]
}
```

---

#### 1.3. `_match_by_table_structure()`

**위치**: [utils/pptx_chunking_engine.py:407-485](utils/pptx_chunking_engine.py#L407-L485)

**목적**: 표 구조 비교로 최적의 이미지 매칭

**알고리즘**:

1. **python-pptx로 실제 슬라이드의 표 구조 추출**
   ```python
   slide_structure = self._extract_table_structure(slide)
   # 예: {"table_count": 1, "tables": [{"rows": 5, "cols": 3}]}
   ```

2. **제목 없는 COM 이미지들의 표 구조 감지**
   - 제목 있는 이미지는 건너뜀 (이미 제목으로 매칭됨)
   - Vision API로 각 이미지의 표 구조 감지

3. **유사도 점수 계산**
   ```python
   score = 0
   # 표 개수 일치: +10점
   if slide_structure["table_count"] == img_structure["table_count"]:
       score += 10

   # 각 표의 행/열 일치: +20점
   for s_tbl in slide_structure["tables"]:
       for i_tbl in img_structure["tables"]:
           if s_tbl["rows"] == i_tbl["rows"] and s_tbl["cols"] == i_tbl["cols"]:
               score += 20
               break
   ```

4. **최고 점수 이미지 선택**
   - 최소 점수: 20점 (1개 표 구조 일치 필요)
   - 완벽한 매칭: 30점 (표 개수 + 구조 일치)

**반환값**: 매칭된 이미지의 base64 문자열, 또는 None

---

### 2. 통합 코드 수정

**위치**: [utils/pptx_chunking_engine.py:133-163](utils/pptx_chunking_engine.py#L133-L163)

**변경 전** (제목 매칭만):
```python
matched_image_base64 = self._match_slide_image_by_title(
    slide_title, slide_index, slide_images
)

if matched_image_base64:
    # Vision 청킹
else:
    # 텍스트 청킹 폴백
```

**변경 후** (제목 → 표 구조 → 텍스트 청킹):
```python
# 1순위: 제목 기반 매칭
matched_image_base64 = self._match_slide_image_by_title(
    slide_title, slide_index, slide_images
)

# 2순위: 표 구조 기반 매칭
if not matched_image_base64:
    print(f"  [Vision] 제목 매칭 실패, 표 구조 기반 매칭 시도")
    matched_image_base64 = self._match_by_table_structure(
        slide, slide_index, slide_images,
        llm_api_type, llm_api_key or "", llm_model
    )

# 3순위: 텍스트 청킹 폴백
if matched_image_base64:
    # Vision 청킹
else:
    print(f"  [WARN] 슬라이드 {slide_number} 이미지 매칭 실패 (제목/표 구조 모두), 텍스트 청킹 사용")
    # 텍스트 청킹
```

---

## 기대 효과

### 정확도 향상

**현재 상태** (제목 매칭만):
- 슬라이드 1: 제목 매칭 실패 → 텍스트 청킹
- 슬라이드 2: 제목 매칭 실패 → 텍스트 청킹
- 슬라이드 3: 제목 매칭 성공 ✅
- 슬라이드 4: 제목 매칭 성공 ✅
- **Vision 사용률**: 50% (2/4)

**Phase 1-B 적용 후** (예상):
- 슬라이드 1: 제목 매칭 실패 → 표 없음 → 텍스트 청킹 (변화 없음)
- 슬라이드 2: 제목 매칭 실패 → **표 구조 매칭 성공** ✅ (신규)
- 슬라이드 3: 제목 매칭 성공 ✅
- 슬라이드 4: 제목 매칭 성공 ✅
- **Vision 사용률**: 75% (3/4) → **+50% 개선**

### 비용 영향

**추가 Vision API 호출**:
- 제목 매칭 실패한 슬라이드에만 표 구조 감지 실행
- 테스트 파일 기준: 최대 4개 이미지 × 표 구조 감지 = 4 API 호출

**API 호출당 비용**:
- 프롬프트: ~60 토큰
- 이미지 (`detail: "low"`): 85 토큰
- 응답 (`max_tokens: 100`): ~30 토큰
- **총**: ~175 토큰/호출

**gpt-4o-mini 가격** (2025-11 기준):
- Input: $0.150 / 1M tokens
- Output: $0.600 / 1M tokens
- 1회 표 구조 감지: ~$0.000044 (약 0.0044센트)

**4개 이미지 표 구조 감지 총 비용**: ~$0.000176 (약 0.02센트)

**결론**: 비용 증가 무시할 수 있는 수준, 정확도 향상 대비 매우 효율적

---

## 테스트 계획

### 테스트 스크립트

**파일**: [test_table_matching.py](test_table_matching.py)

**테스트 내용**:
1. python-pptx로 각 슬라이드의 표 구조 추출
2. COM 렌더링 이미지의 표 구조 감지 (Vision API)
3. 슬라이드 2 (제목 없음) 매칭 성공 여부 확인

**실행 방법**:
```bash
venv/Scripts/python.exe test_table_matching.py
```

**예상 결과**:
```
슬라이드 2: 제목없음-슬라이드2
  표 개수: 1
    표1: 5행 x 3열

COM 이미지 1 표 구조 감지 중...
  -> 1개 표 발견
     표1: 5행 x 3열
  -> 매칭 점수: 30

[Vision] 표 구조 매칭 성공! (점수: 30)

[SUCCESS] 표 구조 기반 매칭 성공!
```

### 통합 테스트

**기존 test_vision_detail.py 재실행**:
```bash
venv/Scripts/python.exe test_vision_detail.py
```

**검증 사항**:
- 슬라이드 2의 Vision 분석 결과 생성 여부
- 표 숫자 추출 정확도 (분기별 매출 등)

---

## 제한 사항 및 향후 개선

### 현재 제한 사항

1. **OpenAI API만 지원**
   - `_detect_table_structure_via_vision()`에서 `llm_api_type != "openai"` 체크
   - Ollama 등 다른 API는 향후 지원 예정

2. **간단한 파싱 로직**
   - "표_개수: N", "표1: R행 C열" 형식만 인식
   - LLM이 다른 형식으로 응답하면 실패 가능
   - 향후 더 유연한 파싱 로직 필요

3. **헤더 정보 미활용**
   - python-pptx는 헤더 추출하지만 매칭에 미사용
   - 향후 헤더 텍스트 유사도 비교 추가 가능

### Phase 2 개선 (계획)

**Phase 2-A: Smart Vision Decision**
- 표가 간단하면 Vision 건너뜀 (python-pptx로 직접 추출)
- 복잡한 표/차트만 Vision 사용
- 예상 비용 절감: 50-70%

**코드 예시**:
```python
# 표 구조 확인
table_structure = self._extract_table_structure(slide)

if table_structure["has_table"]:
    # 간단한 표인지 확인 (3x3 미만, 셀 병합 없음)
    is_simple = all(
        tbl["rows"] <= 3 and tbl["cols"] <= 3
        for tbl in table_structure["tables"]
    )

    if is_simple:
        # Vision 건너뜀, python-pptx로 직접 추출
        print(f"  [Vision] 간단한 표 감지, Vision 건너뜀 (비용 절감)")
        use_vision = False
    else:
        # 복잡한 표, Vision 사용
        use_vision = True
```

---

## 코드 변경 요약

**총 코드 추가**: ~250줄
**영향 받는 파일**: 1개 ([utils/pptx_chunking_engine.py](utils/pptx_chunking_engine.py))
**새 함수**: 3개
**수정 함수**: 1개 (슬라이드 처리 루프)
**테스트 스크립트**: 1개 ([test_table_matching.py](test_table_matching.py))

**Git Diff 주요 변경**:
- L253-302: `_extract_table_structure()` 추가
- L304-405: `_detect_table_structure_via_vision()` 추가
- L407-485: `_match_by_table_structure()` 추가
- L140-146: 표 구조 매칭 통합

---

## 다음 단계

**우선순위 1**: 테스트 결과 확인 및 디버깅
**우선순위 2**: Phase 2-A Smart Vision Decision 구현 (비용 절감)
**우선순위 3**: 실제 업무 PPT로 검증

---

**작성자**: Claude Code
**버전**: Phase 1-B (표 구조 매칭)
**완료일**: 2025-11-19
**상태**: 구현 완료, 테스트 대기 중
