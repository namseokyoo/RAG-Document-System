# Vision 청킹 문제 분석 및 개선안 (v2)

**작성일**: 2025-11-19
**목적**: 현재 상태 재정의 및 추가 개선 방안 도출

---

## 📊 현재 상태 요약

### 정확도 현황

| 슬라이드 | 실제 제목 | Vision 상태 | 숫자 정확도 | 문제 |
|---------|---------|-----------|-----------|------|
| 1 | 2024년 1분기 경영 성과 분석 | ❌ **매칭 실패** | - | COM에서 이 슬라이드가 누락됨 |
| 2 | (제목 없음) | ❌ **매칭 실패** | - | COM과 제목이 다름 |
| 3 | 비용 구조 분석 | ✅ **성공** | **100%** | 제목 매칭 성공 |
| 4 | 전략적 분석 및 계획 | ✅ **성공** | **90%** | 제목 매칭 성공 |

**전체 정확도**: **50%** (2/4 슬라이드)
**Vision 성공 슬라이드 정확도**: **95%** (숫자, 주제 모두 정확)

### 적용 완료된 수정

✅ **Fix 1**: 빈 제목 처리 (`제목없음-슬라이드N` 형식)
✅ **Fix 2**: 제목 유무별 프롬프트 분기
✅ **Fix 3**: 제목 기반 이미지 매칭
✅ **Fix 4**: COM과 python-pptx 제목 형식 통일

---

## 🔍 남은 문제 상세 분석

### 문제 1: PPT 파일 내부 순서 불일치

**진단 결과** ([diagnose_ppt_structure.py](diagnose_ppt_structure.py)):

```
COM (PowerPoint 앱):
  Slide 1: SlideID=257, SlideIndex=2, 제목=제목없음-슬라이드1
  Slide 2: SlideID=258, SlideIndex=3, 제목=비용 구조 분석
  Slide 3: SlideID=259, SlideIndex=4, 제목=전략적 분석 및 계획
  Slide 4: SlideID=259, SlideIndex=4, 제목=전략적 분석 및 계획 ← 중복!

python-pptx (XML 파싱):
  Slide 1: 제목=2024년 1분기 경영 성과 분석
  Slide 2: 제목=제목없음-슬라이드2
  Slide 3: 제목=비용 구조 분석
  Slide 4: 제목=전략적 분석 및 계획
```

**핵심 문제**:
1. **COM이 python-pptx Slide 1을 보지 못함** → "2024년 1분기 경영 성과 분석" 누락
2. **COM Slides 3과 4가 동일** (같은 SlideID 259) → 중복 렌더링
3. **제목으로 비교하면 1칸씩 밀림**:
   - COM Slide 1 (제목없음) ≠ python-pptx Slide 1 (2024년 1분기...)
   - COM Slide 1 (제목없음) ≈ python-pptx Slide 2 (제목없음) ← 비슷하지만 번호가 다름!

### 문제 2: 제목 없는 슬라이드 매칭 불가

**슬라이드 2 매칭 실패 원인**:
- python-pptx: `제목없음-슬라이드2`
- COM Slide 1: `제목없음-슬라이드1`
- 제목이 다르므로 매칭 실패

**왜 다른가?**
- python-pptx는 자신의 순서(2번째)로 번호 부여
- COM은 자신의 순서(1번째)로 번호 부여
- 근본적으로 보는 슬라이드가 다름!

---

## 💡 개선 방안

### Option A: PPT 파일 재생성 (가장 확실)

**난이도**: ★☆☆☆☆ (매우 쉬움)
**효과**: ★★★★★ (완벽)
**시간**: 5분

**방법**:
1. PowerPoint에서 파일 열기
2. 숨겨진 슬라이드 확인 (보기 > 슬라이드 쇼 탭)
3. 슬라이드 1이 숨김 설정되어 있으면 해제
4. 다른 이름으로 저장

**예상 효과**:
- COM과 python-pptx 순서 일치 → **100% 매칭**
- 테스트 정확도: **100%**

**장점**:
- 근본적인 해결
- 다른 코드 수정 불필요

**단점**:
- 사용자가 제공한 PPT 파일을 수정해야 함
- 다른 PPT 파일에도 같은 문제가 있을 수 있음

---

### Option B: 슬라이드 내용 기반 매칭 (권장)

**난이도**: ★★★☆☆ (중간)
**효과**: ★★★★☆ (높음)
**시간**: 1-2시간

**개념**:
제목으로 매칭되지 않으면 슬라이드 내용을 비교하여 매칭

**구현 1: 표 구조 비교** (제목 없는 슬라이드용)

```python
def _match_by_table_structure(self, pptx_slide, com_images: Dict) -> str:
    """표 구조로 이미지 매칭"""

    # python-pptx에서 표 구조 추출
    pptx_tables = []
    for shape in pptx_slide.shapes:
        if shape.has_table:
            table = shape.table
            pptx_tables.append({
                "rows": len(table.rows),
                "cols": len(table.columns),
                "first_row": [cell.text for cell in table.rows[0].cells]
            })

    if not pptx_tables:
        return None  # 표 없으면 매칭 불가

    # COM 이미지에 OCR 또는 Vision으로 표 구조 추출
    for img_data in com_images.values():
        # Vision API로 표 구조 감지
        detected_tables = self._detect_table_in_image(img_data["image"])

        # 구조 비교
        for pptx_table in pptx_tables:
            for detected in detected_tables:
                if (pptx_table["rows"] == detected["rows"] and
                    pptx_table["cols"] == detected["cols"]):
                    # 헤더 텍스트 유사도 확인
                    similarity = self._compare_headers(
                        pptx_table["first_row"],
                        detected["first_row"]
                    )
                    if similarity > 0.8:
                        return img_data["image"]

    return None
```

**장점**:
- 제목 없어도 매칭 가능
- 표가 있는 슬라이드에 효과적

**단점**:
- Vision API 추가 호출 필요 (비용 증가)
- 표 없는 슬라이드는 여전히 문제

**구현 2: 텍스트 유사도 비교** (범용)

```python
def _match_by_content_similarity(self, pptx_slide, com_images: Dict) -> str:
    """텍스트 유사도로 이미지 매칭"""

    # python-pptx에서 모든 텍스트 추출
    pptx_text = self._extract_full_text_from_slide(pptx_slide)
    pptx_embedding = self.embedding_model.embed(pptx_text)

    best_match = None
    best_score = 0

    for img_data in com_images.values():
        # Vision으로 이미지에서 텍스트 추출
        img_text = self._extract_text_from_image(img_data["image"])
        img_embedding = self.embedding_model.embed(img_text)

        # 코사인 유사도 계산
        similarity = cosine_similarity(pptx_embedding, img_embedding)

        if similarity > best_score:
            best_score = similarity
            best_match = img_data["image"]

    # 유사도 70% 이상이면 매칭
    if best_score > 0.7:
        return best_match

    return None
```

**장점**:
- 모든 슬라이드에 적용 가능
- 제목, 표 유무 무관

**단점**:
- 임베딩 모델 필요
- Vision API 추가 호출
- 계산 비용 높음

---

### Option C: 슬라이드 번호 하드코딩 매핑 (임시 해결)

**난이도**: ★☆☆☆☆ (매우 쉬움)
**효과**: ★★☆☆☆ (낮음, 이 파일에만 적용)
**시간**: 2분

**방법**:
```python
# 특정 파일에 대한 매핑 테이블
KNOWN_FILE_MAPPINGS = {
    "advanced_01_financial_report.pptx": {
        # python-pptx index -> COM index
        0: None,  # python-pptx Slide 1은 COM에 없음
        1: 0,     # python-pptx Slide 2 = COM Slide 1
        2: 1,     # python-pptx Slide 3 = COM Slide 2
        3: 2,     # python-pptx Slide 4 = COM Slide 3
    }
}

def _match_slide_image_by_title(self, slide_title, slide_index, slide_images):
    # 파일명으로 매핑 테이블 확인
    if self.pptx_path in KNOWN_FILE_MAPPINGS:
        mapping = KNOWN_FILE_MAPPINGS[self.pptx_path]
        com_index = mapping.get(slide_index)
        if com_index is not None and com_index in slide_images:
            return slide_images[com_index]["image"]

    # 기존 제목 기반 매칭
    ...
```

**장점**:
- 즉시 100% 정확도
- 코드 간단

**단점**:
- 이 파일에만 적용
- 확장성 없음
- 유지보수 어려움

---

### Option D: 숨겨진 슬라이드 처리 개선

**난이도**: ★★☆☆☆ (쉬움)
**효과**: ★★★★☆ (높음, 근본 해결)
**시간**: 30분

**가설**: python-pptx Slide 1이 PowerPoint에서 숨김 처리되어 있을 수 있음

**검증 방법**:
```python
def _check_hidden_slides(self):
    """숨겨진 슬라이드 확인"""
    import win32com.client

    powerpoint = win32com.client.Dispatch("PowerPoint.Application")
    presentation = powerpoint.Presentations.Open(abs_path)

    for i in range(1, presentation.Slides.Count + 1):
        slide = presentation.Slides[i]

        # 숨김 여부 확인
        is_hidden = slide.SlideShowTransition.Hidden

        print(f"Slide {i}: Hidden={is_hidden}, Title={slide.Shapes.Title.TextFrame.TextRange.Text if slide.Shapes.HasTitle else 'None'}")

    presentation.Close()
    powerpoint.Quit()
```

**해결책 1: 숨겨진 슬라이드도 렌더링**
```python
# COM 렌더링 시 숨겨진 슬라이드 포함
for i in range(1, presentation.Slides.Count + 1):
    slide = presentation.Slides[i]

    # 숨김 여부 무시하고 렌더링
    # (기존 코드는 숨김 슬라이드를 건너뛸 수 있음)
```

**해결책 2: python-pptx에서도 숨김 확인**
```python
from pptx import Presentation
from pptx.util import Inches

prs = Presentation(pptx_path)

for slide in prs.slides:
    # python-pptx는 숨김 슬라이드를 기본적으로 포함
    # 하지만 명시적으로 확인 가능
    # (속성 접근 방법 찾기)
```

---

### Option E: Pillow 렌더링으로 전환

**난이도**: ★☆☆☆☆ (쉬움)
**효과**: ★★★☆☆ (중간)
**시간**: 5분

**개념**: COM 대신 Pillow로 모든 슬라이드 렌더링 → 순서 불일치 문제 해결

**방법**:
```python
# COM 렌더링 비활성화
if sys.platform == "win32":
    # COM 사용 안 함
    use_com = False
else:
    use_com = False

# Pillow로 렌더링
for slide_index, slide in enumerate(presentation.slides):
    img_base64 = self._slide_to_base64_image(slide, slide_index)
    # Pillow는 python-pptx와 같은 순서로 렌더링됨
```

**장점**:
- python-pptx와 순서 일치 보장
- 크로스 플랫폼

**단점**:
- Pillow 렌더링 품질이 COM보다 낮을 수 있음
- 텍스트만 렌더링 (이미지, 차트는 빈 박스)

---

## 📋 권장 실행 순서

### 즉시 실행 (오늘)

**1. Option D: 숨겨진 슬라이드 확인** (30분)
- 진단 스크립트 실행
- 숨김 설정 확인
- 숨김 슬라이드가 원인인지 확인

**2. Option A: PPT 파일 재생성** (5분)
- 테스트용으로만 수행
- 숨김 설정 해제 후 저장
- 100% 정확도 달성 확인

**결과 예상**:
- 숨김 슬라이드가 원인이면 → **100% 해결**
- 아니면 → Option B로 진행

### 단기 실행 (1-2일)

**3. Option B-1: 표 구조 기반 매칭** (1-2시간)
- 제목 없는 슬라이드에만 적용
- Vision으로 표 행/열 감지
- 구조 일치하면 매칭

**예상 효과**:
- 슬라이드 2 매칭 성공 가능
- 정확도: 50% → **75%**

### 중기 실행 (1주)

**4. Option B-2: 텍스트 유사도 매칭** (1일)
- 모든 슬라이드에 적용 가능
- 임베딩 모델 사용
- 제목 매칭 실패 시 폴백

**예상 효과**:
- 정확도: 75% → **90-95%**

---

## 🎯 추가 개선 가능 사항

### 1. Smart Vision Decision (비용 절감)

**현재**: 모든 슬라이드에 Vision 사용

**개선**: 슬라이드 타입별로 Vision 사용 여부 결정

```python
def _should_use_vision(self, slide) -> bool:
    """Vision 사용 여부 결정"""

    # 표만 있는 슬라이드: python-pptx로 직접 추출
    if self._has_table_only(slide):
        return False

    # 차트 있는 슬라이드: Vision 필수
    if self._has_chart(slide):
        return True

    # 이미지 있는 슬라이드: Vision 필수
    if self._has_image(slide):
        return True

    # 텍스트만: Vision 불필요
    if self._is_text_only(slide):
        return False

    return True  # 기본값
```

**효과**:
- Vision 호출 **50-70% 감소**
- 비용 절감
- 표 정확도 향상 (python-pptx 직접 추출이 더 정확)

### 2. Vision API High Detail 옵션

**현재**: 모든 슬라이드 `detail: "low"`

**개선**: 복잡한 표/차트만 `detail: "high"`

```python
def _get_vision_detail_level(self, slide) -> str:
    """Vision detail 레벨 결정"""

    # 복잡한 표 (5행 이상 또는 5열 이상)
    for shape in slide.shapes:
        if shape.has_table:
            table = shape.table
            if len(table.rows) >= 5 or len(table.columns) >= 5:
                return "high"

    # 작은 차트/표
    return "low"
```

**효과**:
- 복잡한 표 정확도 향상
- 비용은 필요한 곳에만 증가 (선택적)

### 3. 캐싱 시스템

**개념**: 같은 PPT 파일을 여러 번 처리할 때 Vision 결과 재사용

```python
import hashlib
import json
from pathlib import Path

def _get_vision_cache_key(self, pptx_path: str, slide_index: int) -> str:
    """캐시 키 생성"""
    # 파일 해시 + 슬라이드 인덱스
    with open(pptx_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    return f"{file_hash}_{slide_index}"

def _get_cached_vision_result(self, cache_key: str) -> str:
    """캐시된 Vision 결과 조회"""
    cache_dir = Path("data/vision_cache")
    cache_file = cache_dir / f"{cache_key}.json"

    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)["vision_text"]

    return None

def _cache_vision_result(self, cache_key: str, vision_text: str):
    """Vision 결과 캐싱"""
    cache_dir = Path("data/vision_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / f"{cache_key}.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({"vision_text": vision_text}, f, ensure_ascii=False)
```

**효과**:
- 같은 파일 재처리 시 비용 **0원**
- 처리 속도 대폭 향상

### 4. 배치 처리 최적화

**현재**: 슬라이드별로 Vision API 호출 (순차)

**개선**: 여러 슬라이드를 한 번에 처리

```python
# Vision API가 배치 요청을 지원하면
def _analyze_slides_batch(self, slides_with_images: List[Tuple[slide, image]]):
    """여러 슬라이드 한 번에 분석"""

    # 한 번의 API 호출로 여러 이미지 처리
    messages = []
    for i, (slide, img_base64) in enumerate(slides_with_images):
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": f"슬라이드 {i+1}을 분석하세요"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
            ]
        })

    # 배치 요청
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=messages
    )

    # 응답 파싱
    ...
```

**효과**:
- API 호출 횟수 감소
- 처리 속도 향상

### 5. 에러 복구 메커니즘

**현재**: Vision 실패 시 텍스트 청킹으로 폴백

**개선**: 재시도 로직 추가

```python
def _analyze_with_retry(self, slide, img_base64, max_retries=3):
    """재시도 로직이 있는 Vision 분석"""

    for attempt in range(max_retries):
        try:
            result = self._analyze_slide_with_vision(slide, img_base64)

            # 결과 검증
            if self._is_valid_result(result):
                return result

            # 결과가 이상하면 재시도
            print(f"  [WARN] Vision 결과 이상, 재시도 {attempt+1}/{max_retries}")

        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"  [WARN] Vision 실패, 재시도 {attempt+1}/{max_retries}: {e}")
            time.sleep(1)  # 잠시 대기

    return None

def _is_valid_result(self, result: str) -> bool:
    """Vision 결과 검증"""
    # "[정보 없음]"이면 실패
    if "[정보 없음]" in result:
        return False

    # 너무 짧으면 실패
    if len(result) < 50:
        return False

    return True
```

**효과**:
- 일시적 오류 복구
- 정확도 향상

---

## 📊 예상 최종 결과

### 단계별 정확도

| 단계 | 개선 사항 | 정확도 | 비용 |
|------|----------|--------|------|
| **현재** | 제목 기반 매칭 | 50% | 기준 |
| **+Option D** | 숨김 슬라이드 처리 | **75-100%** | 동일 |
| **+Option B-1** | 표 구조 매칭 | **75%** | +20% |
| **+Option B-2** | 텍스트 유사도 | **90-95%** | +30% |
| **+Smart Vision** | 타입별 Vision 사용 | 90-95% | **-50%** |
| **+캐싱** | Vision 결과 재사용 | 90-95% | **-90%** (재처리 시) |

---

## 💡 최종 권장안

### 즉시 실행 (1-2시간)

1. ✅ **숨겨진 슬라이드 확인** (Option D)
2. ✅ **PPT 파일 재생성 테스트** (Option A)
3. ⚠️ 숨김이 원인이 아니면 → **표 구조 매칭** (Option B-1)

### 단기 실행 (1주)

4. ✅ **Smart Vision Decision** (비용 절감)
5. ✅ **캐싱 시스템** (재처리 비용 제로)

### 중기 실행 (2-3주)

6. ✅ **텍스트 유사도 매칭** (Option B-2)
7. ✅ **배치 처리** (속도 향상)
8. ✅ **에러 복구** (안정성)

**예상 최종 정확도**: **90-95%**
**예상 비용 절감**: **50-70%**

---

**작성자**: Claude Code
**버전**: v2.1
**다음 단계**: 숨겨진 슬라이드 확인 스크립트 실행
