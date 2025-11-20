# Vision 청킹 문제 근본 원인 분석

**작성일**: 2025-11-19
**목적**: 슬라이드 혼동 문제의 근본 원인 파악 및 수정 가능성 검토

---

## 🔍 관찰된 증상

### 테스트 결과

| 슬라이드 | 실제 제목 | Vision 주제 | 상태 |
|---------|---------|-----------|------|
| 1 | 2024년 1분기 경영 성과 분석 | 2024년 1분기 경영 성과 분석 | ✅ 정확 |
| 2 | **(제목 없음)** | **비용 구조 분석** | ❌ 슬라이드 3 제목 |
| 3 | 비용 구조 분석 | 비용 구조 분석 + [정보 없음] | ⚠️ 제목만, 내용 비어있음 |
| 4 | 전략적 분석 및 계획 | 2024년 전략적 목표 및 계획 | ✅ 대체로 일치 |

### 패턴

1. **슬라이드 2의 Vision 분석이 슬라이드 3의 제목 포함**
2. **슬라이드 3의 Vision 분석이 비어있음** (실제로는 표와 숫자 있음)
3. 슬라이드 1과 4는 정확

---

## 🧪 가설 검증

### 가설 1: 이미지-슬라이드 매칭 오류

**가능성**: ★★★★☆ (매우 높음)

**근거**:
```python
# COM 렌더링 (Windows PowerPoint)
for slide_index in range(total_slides):
    slide = presentation.Slides[slide_index + 1]  # 1-based (PowerPoint COM)
    slide_images[slide_index] = ...  # 0-based 키로 저장

# python-pptx 사용 (청킹)
for slide_index, slide in enumerate(presentation.slides):  # 0-based
    if enable_vision and slide_index in slide_images:
        vision = analyze(slide_images[slide_index])  # 0-based 키로 가져오기
```

**문제**:
- **두 개의 다른 `presentation` 객체**
  - PowerPoint COM: `win32com.client.Dispatch("PowerPoint.Application")`
  - python-pptx: `Presentation(pptx_path)`
- **순서 보장 불확실**

**검증 방법**:
1. 렌더링된 이미지를 파일로 저장
2. 실제 슬라이드와 매칭 확인

### 가설 2: 제목 없는 슬라이드 처리 문제

**가능성**: ★★★★★ (거의 확실)

**근거**:
```python
# 슬라이드 2: 제목 없음
slide_title = ""  # _extract_slide_title() 결과

# 프롬프트 생성
prompt = f"""
[슬라이드 정보]
제목: "{slide_title}"  # → 제목: ""
슬라이드: 2/4

[중요 지시사항]
1. 슬라이드 맨 위의 큰 제목이 "{slide_title}"과 일치하는지 확인하세요
   # → 슬라이드 맨 위의 큰 제목이 ""과 일치하는지 확인하세요
```

**문제**:
- LLM이 빈 제목(`""`)을 보고 혼란
- "제목이 없다"와 "제목이 빈 문자열"을 구분 못함
- 결과적으로 다른 슬라이드 내용을 가져옴

### 가설 3: Vision API 이미지 인식 실패

**가능성**: ★★★☆☆ (중간)

**근거**:
- 슬라이드 3에서 `[정보 없음]` 출력
- 실제로는 표와 숫자가 있음

**가능한 원인**:
1. 이미지 품질 문제 (해상도, 압축)
2. Base64 인코딩 오류
3. GPT-4o-mini의 한계 (`detail: "low"` 사용)

### 가설 4: 프롬프트 길이 증가로 인한 혼란

**가능성**: ★★☆☆☆ (낮음)

**근거**:
- 프롬프트가 28라인 → 45라인으로 증가
- 너무 복잡한 지시사항

**반박**:
- 슬라이드 1과 4는 정상 작동
- 문제는 슬라이드 2-3에만 국한

---

## 💡 종합 분석

### 가장 유력한 원인

**1순위: 제목 없는 슬라이드 처리 문제** (90% 확신)

**증거**:
- 슬라이드 2만 제목이 없음
- 슬라이드 2의 Vision이 슬라이드 3 제목 출력
- 제목 있는 슬라이드(1, 4)는 정상

**메커니즘**:
```
슬라이드 2: 제목 = ""
  ↓
프롬프트: '제목: ""과 일치하는지 확인'
  ↓
LLM: "빈 제목? 뭐지? 일단 이미지 보고 제목 찾자"
  ↓
이미지에서 가장 큰 텍스트 = "비용 구조 분석" (실제로는 표의 제목일 수도)
  ↓
결과: "비용 구조 분석" 출력 (슬라이드 3 제목과 우연히 일치)
```

**2순위: 이미지-슬라이드 매칭 오류** (30% 확신)

**증거**:
- 슬라이드 3의 Vision이 비어있음
- 슬라이드 2의 이미지가 실제로는 슬라이드 3일 가능성

**메커니즘**:
```
렌더링: COM Slide[1] → image[0]  # 슬라이드 1
        COM Slide[2] → image[1]  # 슬라이드 2
        COM Slide[3] → image[2]  # 슬라이드 3

하지만:
python-pptx slides[0] + image[0]  # ✅ 매칭
python-pptx slides[1] + image[1]  # ❌ 잘못된 매칭?
python-pptx slides[2] + image[2]  # ❌ 잘못된 매칭?
```

---

## 🔧 수정 가능성 평가

### 수정 A: 제목 없는 슬라이드 처리

**난이도**: ★☆☆☆☆ (매우 쉬움)
**효과**: ★★★★★ (매우 높음)
**시간**: 5분

**방법**:
```python
# Before
slide_title = self._extract_slide_title(slide)
# → 결과: ""

# After
slide_title = self._extract_slide_title(slide)
if not slide_title:
    slide_title = f"[슬라이드 {slide_num}]"
# → 결과: "[슬라이드 2]"
```

**프롬프트 개선**:
```python
# Before
f'제목: "{slide_title}"'  # → 제목: ""

# After
if slide_title:
    f'제목: "{slide_title}"'
else:
    f'제목: 없음 (슬라이드 {slide_num})'
```

**예상 효과**:
- 슬라이드 2 문제 **80% 해결**
- 명확한 지시사항 제공

### 수정 B: 이미지 매칭 검증

**난이도**: ★★★☆☆ (중간)
**효과**: ★★★★☆ (높음)
**시간**: 30분

**방법 1: 이미지 저장 및 육안 확인**
```python
# 렌더링 시 이미지 저장
for slide_index in range(total_slides):
    ...
    img.save(f"debug_slide_{slide_index+1}.png")
    slide_images[slide_index] = base64...
```

**방법 2: 슬라이드 번호 워터마크**
```python
# 이미지에 슬라이드 번호 텍스트 추가
from PIL import ImageDraw, ImageFont
draw = ImageDraw.Draw(img)
draw.text((10, 10), f"Slide {slide_index+1}", fill='red')
```

**예상 효과**:
- 매칭 오류 **100% 확인 가능**
- 문제 있으면 수정

### 수정 C: Vision API 파라미터 조정

**난이도**: ★☆☆☆☆ (쉬움)
**효과**: ★★☆☆☆ (낮음~중간)
**시간**: 2분

**방법**:
```python
# Before
"detail": "low"  # 85 tokens, 빠름, 저비용

# After
"detail": "high"  # 600 tokens, 느림, 고비용, 정확
```

**예상 효과**:
- 슬라이드 3 내용 인식 **개선 가능**
- 비용 **7배 증가** ($0.015 → $0.10/100장)

### 수정 D: 프롬프트 재간소화

**난이도**: ★★☆☆☆ (쉬움)
**효과**: ★☆☆☆☆ (낮음)
**시간**: 10분

**방법**:
```python
# 핵심만 남기고 불필요한 지시사항 제거
# 45라인 → 30라인
```

**예상 효과**:
- 토큰 감소
- 정확도 **개선 가능성 낮음**

---

## 📋 권장 수정 순서

### 1단계: 제목 없는 슬라이드 처리 (즉시)

**코드**:
```python
def _extract_slide_title(self, slide, slide_num: int = None) -> str:
    """슬라이드 제목 추출"""
    try:
        if slide.shapes.title and hasattr(slide.shapes.title, 'text'):
            title_text = slide.shapes.title.text.strip()
            if title_text:
                return title_text
    except:
        pass

    # 제목 없으면 슬라이드 번호 반환
    if slide_num:
        return f"[슬라이드 {slide_num}]"
    return "[제목 없음]"
```

**프롬프트 수정**:
```python
if not slide_title or slide_title.startswith("["):
    # 제목 없는 경우
    prompt = f"""
[슬라이드 정보]
슬라이드: {slide_num}/{total_slides}
주의: 이 슬라이드에는 제목이 없습니다

[중요 지시사항]
1. 슬라이드 번호 {slide_num}의 내용만 분석하세요
2. 다른 슬라이드와 혼동하지 마세요
...
"""
else:
    # 제목 있는 경우 (기존 로직)
    prompt = f"""
[슬라이드 정보]
제목: "{slide_title}"
슬라이드: {slide_num}/{total_slides}
...
"""
```

**예상 결과**:
- 정확도: 50% → **70-80%**
- 슬라이드 2 문제 대부분 해결

### 2단계: 이미지 매칭 검증 (1일 이내)

**목적**: 진짜 이미지 매칭 오류가 있는지 확인

**방법**:
```python
# 디버그 모드 추가
if debug_mode:
    for slide_index, img_base64 in slide_images.items():
        img_bytes = base64.b64decode(img_base64)
        with open(f"debug_slide_{slide_index+1}.png", "wb") as f:
            f.write(img_bytes)
```

**확인**:
- 저장된 이미지 육안 확인
- 슬라이드 2 이미지가 정말 슬라이드 2인지 확인

**만약 매칭 오류 발견 시**:
- COM과 python-pptx 순서 불일치 원인 파악
- 슬라이드 ID 또는 워터마크로 매칭 검증

### 3단계: Vision API 파라미터 실험 (선택)

**조건**: 1-2단계 후에도 슬라이드 3 문제 지속 시

**테스트**:
```python
# 슬라이드 3만 high detail
if slide_has_table:
    detail = "high"
else:
    detail = "low"
```

---

## 🎯 예상 최종 결과

### 1단계만 적용 시

- 정확도: 50% → **70-80%**
- 비용: 변화 없음
- 시간: 5분

### 1+2단계 적용 시

- 정확도: 50% → **80-90%**
- 비용: 변화 없음
- 시간: 35분

### 1+2+3단계 적용 시

- 정확도: 50% → **90-95%**
- 비용: 약간 증가 (표 슬라이드만 high detail)
- 시간: 1일

---

## 💭 결론

### 가장 유력한 원인

**제목 없는 슬라이드 처리 문제 (90% 확신)**

### 가장 쉬운 해결책

**제목 없으면 `[슬라이드 N]`으로 대체** (5분 작업)

### 권장 사항

1. ✅ **즉시 실행**: 제목 없는 슬라이드 처리 개선
2. ✅ **당일 검증**: 이미지 매칭 확인 (디버그 이미지 저장)
3. ⚠️ **조건부 실행**: Vision API 파라미터 조정 (필요 시)

### 수정 가능성

**매우 높음 (95% 이상)**

- 제목 처리는 100% 수정 가능
- 이미지 매칭은 확인 후 수정 가능
- 최악의 경우에도 80% 정확도 달성 가능

---

**다음 단계**: 제목 없는 슬라이드 처리부터 즉시 수정
