# Vision 청킹 개선 로드맵

**작성일**: 2025-11-19
**현재 정확도**: 50% (2/4 슬라이드)
**목표 정확도**: 90-95%

---

## 🔍 진단 결과

### 숨겨진 슬라이드 확인 완료 ✅

**결과**: **숨겨진 슬라이드 없음** (모든 슬라이드 [VISIBLE])

**의미**:
- 숨김 설정이 순서 불일치의 원인이 **아님**
- PPT 파일 내부 구조 문제 또는 COM API 이슈로 추정
- 다른 해결 방법 필요 → Phase 1-B로 진행

---

## 📋 개선 로드맵 (3단계)

---

## 🎯 Phase 1: 즉시 해결 (1-3일)

**목표**: 정확도 50% → **75-100%**
**우선순위**: 높음
**투입 시간**: 1-3일

### Phase 1-A: PPT 파일 재생성 테스트 ⭐ 최우선

**난이도**: ★☆☆☆☆
**효과**: ★★★★★
**시간**: 10분
**비용 영향**: 없음

**작업 내용**:
1. PowerPoint에서 `advanced_01_financial_report.pptx` 열기
2. 모든 슬라이드 확인 (순서, 내용)
3. "다른 이름으로 저장" → `advanced_01_financial_report_fixed.pptx`
4. 새 파일로 테스트 실행

**검증 방법**:
```bash
venv/Scripts/python.exe diagnose_ppt_structure.py
# COM과 python-pptx 순서 일치 확인
```

**예상 결과**:
- ✅ 순서 문제 해결되면 → **정확도 100%** 달성
- ❌ 문제 지속되면 → Phase 1-B로 진행

**코드 변경**: 없음

---

### Phase 1-B: 표 구조 기반 매칭 ⭐ 권장

**난이도**: ★★★☆☆
**효과**: ★★★★☆
**시간**: 1-2일
**비용 영향**: Vision API 호출 약간 증가 (+10-20%)

**개념**:
제목으로 매칭 안 되면 **표 구조 (행/열 개수, 헤더)**로 매칭

**구현 위치**: [utils/pptx_chunking_engine.py](utils/pptx_chunking_engine.py)

**코드**:
```python
def _match_slide_image_by_title(self, slide_title, slide_index, slide_images):
    """제목 기반 매칭 (기존)"""

    # 1순위: 제목 정확 매칭
    if clean_title:
        for img_data in slide_images.values():
            if img_data["title"] == clean_title:
                return img_data["image"]

    # 2순위: 표 구조 매칭 (신규!)
    matched_image = self._match_by_table_structure(
        slide_index, slide_images
    )
    if matched_image:
        return matched_image

    # 3순위: 인덱스 폴백
    ...

def _match_by_table_structure(self, slide_index, slide_images):
    """표 구조로 이미지 매칭 (신규 함수)"""

    # python-pptx에서 표 구조 추출
    slide = self.presentation.slides[slide_index]
    pptx_tables = []

    for shape in slide.shapes:
        if shape.has_table:
            table = shape.table
            pptx_tables.append({
                "rows": len(table.rows),
                "cols": len(table.columns),
                "header": [cell.text for cell in table.rows[0].cells]
            })

    if not pptx_tables:
        return None

    # Vision으로 각 COM 이미지에서 표 감지
    for img_data in slide_images.values():
        # 이미 제목으로 매칭된 이미지는 건너뜀
        if img_data.get("matched"):
            continue

        # Vision API로 표 구조 감지
        table_info = self._detect_table_structure(img_data["image"])

        # 구조 비교
        for pptx_table in pptx_tables:
            if (table_info["rows"] == pptx_table["rows"] and
                table_info["cols"] == pptx_table["cols"]):

                # 헤더 텍스트 유사도 확인
                similarity = self._compare_text_lists(
                    pptx_table["header"],
                    table_info["header"]
                )

                if similarity > 0.7:  # 70% 이상 유사
                    print(f"  [Vision] 표 구조 매칭: {pptx_table['rows']}행 x {pptx_table['cols']}열")
                    img_data["matched"] = True
                    return img_data["image"]

    return None

def _detect_table_structure(self, img_base64):
    """Vision API로 이미지에서 표 구조 감지"""

    prompt = """이 이미지에 표가 있으면 다음 정보를 JSON 형식으로 출력하세요:
{
  "has_table": true/false,
  "rows": 행 개수,
  "cols": 열 개수,
  "header": [첫 번째 행의 각 셀 텍스트]
}

표가 없으면 has_table: false만 출력하세요."""

    # Vision API 호출 (기존 _analyze_slide_with_vision 재사용)
    response = self._call_vision_api(img_base64, prompt)

    # JSON 파싱
    import json
    try:
        result = json.loads(response)
        if not result.get("has_table"):
            return None
        return result
    except:
        return None

def _compare_text_lists(self, list1, list2):
    """두 텍스트 리스트의 유사도 계산"""

    if len(list1) != len(list2):
        return 0.0

    matches = 0
    for t1, t2 in zip(list1, list2):
        # 대소문자 무시, 공백 제거 후 비교
        t1_clean = t1.lower().strip()
        t2_clean = t2.lower().strip()

        if t1_clean == t2_clean:
            matches += 1
        elif t1_clean in t2_clean or t2_clean in t1_clean:
            matches += 0.5

    return matches / len(list1)
```

**테스트 방법**:
```bash
venv/Scripts/python.exe test_vision_detail.py
# 슬라이드 2 매칭 확인
```

**예상 결과**:
- 슬라이드 2: 7행 5열 표 → COM 이미지에서 같은 구조 찾기 → 매칭 성공
- **정확도: 50% → 75%** (3/4 슬라이드)

**비용**:
- 표 구조 감지를 위한 Vision API 추가 호출
- 매칭 안 된 이미지당 1회 호출
- 예상 비용 증가: 10-20%

**다음 단계**: Phase 2로 진행

---

### Phase 1-C: Pillow 렌더링 전환 (대안)

**난이도**: ★☆☆☆☆
**효과**: ★★★☆☆
**시간**: 30분
**비용 영향**: 없음

**개념**: COM 대신 Pillow로 렌더링 → python-pptx와 순서 일치

**구현**:
```python
# process_pptx_document()에서
if sys.platform == "win32":
    # COM 비활성화
    use_com = False  # 강제로 Pillow 사용
```

**장점**:
- python-pptx와 순서 100% 일치
- 크로스 플랫폼

**단점**:
- Pillow 렌더링 품질 낮음 (텍스트만, 이미지/차트는 빈 박스)
- Vision 분석 정확도 하락 가능

**추천**: Phase 1-A 실패 시 임시 해결책으로만 사용

---

## 🚀 Phase 2: 비용 최적화 (1주)

**목표**: 비용 50-70% 절감
**우선순위**: 중간
**투입 시간**: 2-3일

### Phase 2-A: Smart Vision Decision ⭐ 강력 권장

**난이도**: ★★☆☆☆
**효과**: ★★★★★ (비용 절감)
**시간**: 1일
**비용 영향**: **-50~70%**

**개념**: 슬라이드 타입별로 Vision 사용 여부 결정

**구현 위치**: [utils/pptx_chunking_engine.py](utils/pptx_chunking_engine.py)

**코드**:
```python
def _should_use_vision(self, slide) -> bool:
    """Vision 사용 여부 결정"""

    has_table = False
    has_chart = False
    has_image = False
    text_only = True

    for shape in slide.shapes:
        if shape.has_table:
            has_table = True
            text_only = False

            # 표 크기 확인
            table = shape.table
            if len(table.rows) >= 5 or len(table.columns) >= 5:
                # 복잡한 표는 Vision 사용
                return True

            # 간단한 표는 python-pptx로 직접 추출
            # Vision 불필요
            continue

        if shape.has_chart:
            has_chart = True
            text_only = False
            # 차트는 Vision 필수
            return True

        if shape.shape_type == 13:  # Picture
            has_image = True
            text_only = False
            # 이미지는 Vision 필수
            return True

    # 텍스트만 있는 슬라이드: Vision 불필요
    if text_only:
        return False

    # 간단한 표만: Vision 불필요
    if has_table and not has_chart and not has_image:
        return False

    return True

# process_pptx_document()에서
if self.enable_small_to_large:
    # Vision 사용 여부 결정
    should_use_vision = (
        enable_vision and
        self._should_use_vision(slide) and
        slide_images
    )

    if should_use_vision:
        # Vision 청킹
        ...
    else:
        # 텍스트 청킹
        print(f"  [Vision] 건너뜀 (표 직접 추출 또는 텍스트만)")
        ...
```

**예상 효과**:
- **Vision 호출 50-70% 감소**
- 100장 PPT 기준: $0.015 → **$0.005** (67% 절감)
- 표 정확도 향상 (python-pptx 직접 추출이 더 정확)

**테스트**:
```python
# 통계 출력
vision_used = 0
vision_skipped = 0

for slide in slides:
    if self._should_use_vision(slide):
        vision_used += 1
    else:
        vision_skipped += 1

print(f"Vision 사용: {vision_used}개, 건너뜀: {vision_skipped}개")
print(f"절감률: {vision_skipped / len(slides) * 100:.1f}%")
```

---

### Phase 2-B: 캐싱 시스템

**난이도**: ★★☆☆☆
**효과**: ★★★★★ (재처리 시)
**시간**: 1일
**비용 영향**: 재처리 시 **-100%** (무료)

**개념**: Vision 결과를 파일로 저장하여 재사용

**구현**:
```python
import hashlib
import json
from pathlib import Path

def _get_vision_cache_key(self, pptx_path: str, slide_index: int) -> str:
    """캐시 키 생성 (파일 해시 + 슬라이드 인덱스)"""
    with open(pptx_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    return f"{file_hash}_{slide_index}"

def _get_cached_vision(self, cache_key: str):
    """캐시된 Vision 결과 조회"""
    cache_dir = Path("data/vision_cache")
    cache_file = cache_dir / f"{cache_key}.json"

    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"  [Vision] 캐시 사용 (비용 절감!)")
            return data["vision_text"]

    return None

def _cache_vision_result(self, cache_key: str, vision_text: str):
    """Vision 결과 캐싱"""
    cache_dir = Path("data/vision_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / f"{cache_key}.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({
            "vision_text": vision_text,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

# _analyze_slide_with_vision()에서
def _analyze_slide_with_vision(self, slide, ...):
    # 캐시 확인
    cache_key = self._get_vision_cache_key(self.pptx_path, slide_index)
    cached = self._get_cached_vision(cache_key)

    if cached:
        return cached

    # Vision API 호출
    vision_text = ... (기존 로직)

    # 캐싱
    self._cache_vision_result(cache_key, vision_text)

    return vision_text
```

**효과**:
- 같은 파일 재처리: **비용 0원**
- 처리 속도: 6초/슬라이드 → 0.1초/슬라이드 (60배 빠름)

**캐시 관리**:
```python
# 캐시 정리 유틸리티
def clear_vision_cache(older_than_days=30):
    """오래된 캐시 삭제"""
    cache_dir = Path("data/vision_cache")
    cutoff = datetime.now() - timedelta(days=older_than_days)

    for cache_file in cache_dir.glob("*.json"):
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if mtime < cutoff:
            cache_file.unlink()
            print(f"삭제: {cache_file.name}")
```

---

### Phase 2-C: Vision API High Detail 옵션

**난이도**: ★☆☆☆☆
**효과**: ★★★☆☆ (정확도 향상)
**시간**: 1시간
**비용 영향**: 복잡한 슬라이드만 +600% (전체적으로는 +10-20%)

**개념**: 복잡한 표/차트만 `detail: "high"` 사용

**구현**:
```python
def _get_vision_detail_level(self, slide) -> str:
    """Vision detail 레벨 결정"""

    for shape in slide.shapes:
        if shape.has_table:
            table = shape.table

            # 큰 표는 high detail
            if len(table.rows) >= 7 or len(table.columns) >= 6:
                return "high"

            # 숫자가 많은 표
            cell_count = len(table.rows) * len(table.columns)
            if cell_count >= 30:
                return "high"

        if shape.has_chart:
            # 차트는 항상 high detail
            return "high"

    return "low"

# _analyze_slide_with_vision()에서
payload = {
    "model": llm_model,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt_text},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{slide_img_base64}",
                    "detail": self._get_vision_detail_level(slide)  # 동적 결정
                }
            }
        ]
    }]
}
```

**효과**:
- 복잡한 표/차트: 정확도 향상
- 간단한 슬라이드: 비용 절감 유지

**비용 예시** (100장 PPT):
- 모두 low: $0.015
- 20%만 high: $0.015 * 0.8 + $0.10 * 0.2 = **$0.032** (2배 증가)
- 하지만 Smart Vision Decision과 함께 사용하면 상쇄됨

---

## 📈 Phase 3: 고급 기능 (2-3주)

**목표**: 정확도 90-95%, 안정성 향상
**우선순위**: 낮음
**투입 시간**: 1-2주

### Phase 3-A: 텍스트 유사도 매칭

**난이도**: ★★★☆☆
**효과**: ★★★★☆
**시간**: 2-3일
**비용 영향**: +20-30%

**개념**: 임베딩 모델로 슬라이드 내용 유사도 계산하여 매칭

**필요 라이브러리**:
```bash
pip install sentence-transformers
```

**구현**:
```python
from sentence_transformers import SentenceTransformer

class PPTXChunkingEngine:
    def __init__(self, config):
        ...
        # 임베딩 모델 로드 (한 번만)
        self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    def _match_by_content_similarity(self, slide, slide_images):
        """텍스트 유사도로 이미지 매칭"""

        # python-pptx에서 모든 텍스트 추출
        pptx_text = self._extract_full_text_from_slide(slide)
        pptx_embedding = self.embedding_model.encode(pptx_text)

        best_match = None
        best_score = 0

        for img_data in slide_images.values():
            # Vision으로 이미지에서 텍스트 추출
            img_text = self._extract_text_from_image_vision(img_data["image"])

            if not img_text:
                continue

            img_embedding = self.embedding_model.encode(img_text)

            # 코사인 유사도
            from sklearn.metrics.pairwise import cosine_similarity
            similarity = cosine_similarity(
                pptx_embedding.reshape(1, -1),
                img_embedding.reshape(1, -1)
            )[0][0]

            if similarity > best_score:
                best_score = similarity
                best_match = img_data

        # 70% 이상 유사하면 매칭
        if best_score > 0.7:
            print(f"  [Vision] 텍스트 유사도 매칭: {best_score:.1%}")
            return best_match["image"]

        return None

    def _extract_text_from_image_vision(self, img_base64):
        """Vision API로 이미지에서 모든 텍스트 추출"""

        prompt = "이 이미지의 모든 텍스트를 추출하세요. 제목, 본문, 표, 차트 레이블 모두 포함."

        response = self._call_vision_api(img_base64, prompt)
        return response
```

**매칭 순서**:
1. 제목 정확 매칭
2. 표 구조 매칭
3. **텍스트 유사도 매칭** (신규)
4. 인덱스 폴백

**예상 효과**:
- 슬라이드 1 매칭 성공 가능 (제목으로 안 되지만 내용으로 가능)
- **정확도: 75% → 90-95%**

**비용**:
- Vision API로 텍스트 추출 (매칭 안 된 이미지당)
- 임베딩 계산은 무료 (로컬)

---

### Phase 3-B: 에러 복구 메커니즘

**난이도**: ★★☆☆☆
**효과**: ★★★☆☆ (안정성)
**시간**: 1일

**구현**:
```python
def _analyze_with_retry(self, slide, img_base64, max_retries=3):
    """재시도 로직이 있는 Vision 분석"""

    last_error = None

    for attempt in range(max_retries):
        try:
            result = self._analyze_slide_with_vision(slide, img_base64)

            # 결과 검증
            if self._is_valid_vision_result(result):
                return result

            print(f"  [WARN] Vision 결과 이상, 재시도 {attempt+1}/{max_retries}")

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"  [WARN] Vision 실패, 재시도 {attempt+1}/{max_retries}: {e}")
                time.sleep(2 ** attempt)  # 지수 백오프
            else:
                raise last_error

    return None

def _is_valid_vision_result(self, result: str) -> bool:
    """Vision 결과 검증"""

    # 너무 짧으면 실패
    if len(result.strip()) < 30:
        return False

    # "[정보 없음]"만 있으면 실패
    if "[정보 없음]" in result and len(result) < 100:
        return False

    # "주제:"가 없으면 실패
    if "주제:" not in result:
        return False

    return True
```

**효과**:
- 일시적 네트워크 오류 복구
- Vision API 응답 불안정 대응
- 정확도 소폭 향상

---

### Phase 3-C: 배치 처리 (선택)

**난이도**: ★★★★☆
**효과**: ★★☆☆☆ (속도)
**시간**: 2-3일

**주의**: OpenAI API가 배치 요청을 지원하는지 확인 필요

**개념**: 여러 슬라이드를 한 번에 Vision API로 처리

**구현** (API가 지원하는 경우):
```python
def _analyze_slides_batch(self, slides_data: List):
    """여러 슬라이드 배치 처리"""

    # 한 번에 최대 4개 슬라이드
    batch_size = 4
    results = []

    for i in range(0, len(slides_data), batch_size):
        batch = slides_data[i:i+batch_size]

        # 배치 요청
        messages = []
        for slide_idx, (slide, img_base64) in enumerate(batch):
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": f"슬라이드 {slide_idx+1}:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]
            })

        response = self._call_vision_api_batch(messages)
        results.extend(response)

    return results
```

**효과**:
- API 호출 횟수 75% 감소
- 처리 속도 향상 가능

---

## 📊 전체 로드맵 요약

| Phase | 내용 | 시간 | 정확도 | 비용 |
|-------|------|------|--------|------|
| **현재** | 제목 기반 매칭 | - | 50% | 기준 |
| **Phase 1-A** | PPT 파일 재생성 | 10분 | **100%** | 동일 |
| **Phase 1-B** | 표 구조 매칭 | 1-2일 | **75%** | +10-20% |
| **Phase 2-A** | Smart Vision | 1일 | 75% | **-50~70%** |
| **Phase 2-B** | 캐싱 시스템 | 1일 | 75% | **-100%** (재처리) |
| **Phase 2-C** | High Detail | 1시간 | **80%** | +10-20% |
| **Phase 3-A** | 텍스트 유사도 | 2-3일 | **90-95%** | +20-30% |
| **Phase 3-B** | 에러 복구 | 1일 | 90-95% | 동일 |

### 최종 목표 (모든 Phase 완료 시)

**정확도**: **90-95%**
**비용**: 기준 대비 **-30~50%** (Smart Vision + 캐싱 효과)
**안정성**: 재시도 로직으로 향상

---

## 🎯 권장 실행 순서

### Week 1: 즉시 해결

**Day 1**:
- ✅ Phase 1-A: PPT 파일 재생성 테스트
- ✅ 결과 확인 → 100% 달성 시 완료!

**Day 2-3** (1-A 실패 시):
- ✅ Phase 1-B: 표 구조 매칭 구현
- ✅ 테스트 → 75% 달성

### Week 2: 비용 최적화

**Day 1-2**:
- ✅ Phase 2-A: Smart Vision Decision
- ✅ 비용 50-70% 절감 확인

**Day 3**:
- ✅ Phase 2-B: 캐싱 시스템
- ✅ 재처리 테스트

**Day 4**:
- ✅ Phase 2-C: High Detail 옵션
- ✅ 복잡한 표 정확도 확인

### Week 3-4: 고급 기능 (선택)

**Day 1-3**:
- ⚠️ Phase 3-A: 텍스트 유사도 매칭
- ⚠️ 90-95% 정확도 목표

**Day 4**:
- ⚠️ Phase 3-B: 에러 복구
- ⚠️ 안정성 테스트

---

## 🚦 각 Phase 시작 조건

### Phase 1-A
**선행 조건**: 없음 (즉시 실행 가능)
**완료 기준**: COM과 python-pptx 순서 일치 확인

### Phase 1-B
**선행 조건**: Phase 1-A 실패 시
**완료 기준**: 정확도 75% 이상

### Phase 2-A
**선행 조건**: Phase 1 완료
**완료 기준**: Vision 호출 50% 이상 감소

### Phase 2-B
**선행 조건**: Phase 2-A 완료 (독립적으로도 가능)
**완료 기준**: 재처리 시 캐시 사용 확인

### Phase 3-A
**선행 조건**: Phase 1-2 완료, 정확도 75% 이상
**완료 기준**: 정확도 90% 이상

---

## 📝 각 Phase별 체크리스트

### Phase 1-A 체크리스트
- [ ] PowerPoint에서 파일 열기
- [ ] 슬라이드 순서/내용 확인
- [ ] 다른 이름으로 저장
- [ ] `diagnose_ppt_structure.py` 실행
- [ ] COM과 python-pptx 순서 일치 확인
- [ ] `test_vision_detail.py`로 정확도 확인

### Phase 1-B 체크리스트
- [ ] `_match_by_table_structure()` 함수 작성
- [ ] `_detect_table_structure()` 함수 작성
- [ ] `_compare_text_lists()` 함수 작성
- [ ] `_match_slide_image_by_title()`에 통합
- [ ] 테스트 실행
- [ ] 정확도 75% 확인
- [ ] 비용 영향 측정

### Phase 2-A 체크리스트
- [ ] `_should_use_vision()` 함수 작성
- [ ] `process_pptx_document()`에 통합
- [ ] 통계 출력 (Vision 사용/건너뜀)
- [ ] 테스트 실행
- [ ] Vision 호출 감소율 확인
- [ ] 정확도 유지 확인

### Phase 2-B 체크리스트
- [ ] 캐시 디렉토리 구조 설계
- [ ] `_get_vision_cache_key()` 함수 작성
- [ ] `_get_cached_vision()` 함수 작성
- [ ] `_cache_vision_result()` 함수 작성
- [ ] `_analyze_slide_with_vision()`에 통합
- [ ] 첫 처리 실행
- [ ] 재처리 실행 → 캐시 사용 확인

---

**작성자**: Claude Code
**버전**: v1.0
**다음 단계**: Phase 1-A 실행
