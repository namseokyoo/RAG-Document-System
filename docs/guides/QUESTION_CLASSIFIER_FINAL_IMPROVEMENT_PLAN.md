# 질문 분류기 최종 개선 플랜 (86% → 90%+)

**작성일**: 2025-12-09  
**목표**: 남은 14% 오분류 해결하여 전체 정확도 90%+ 달성

---

## 📊 현재 상태 분석

### 전체 정확도
- **현재**: 86.00% (86/100)
- **목표**: 90.00%+ (90/100+)
- **개선 필요**: 4%p 이상

### 카테고리별 정확도 및 문제점

| 카테고리 | 정확도 | 오분류 수 | 주요 문제 |
|---------|--------|----------|----------|
| `normal_translation_search` | 80% | 2개 | Regex 순서 문제로 direct로 오분류 |
| `simple_keyword` | 70% | 3개 | exhaustive와의 경계 모호 |
| `normal_definition` | 80% | 2개 | explanation과의 경계 모호 |
| `complex_comparison` | 90% | 1개 | translation으로 오분류 |
| `simple_fact` | 80% | 2개 | relationship/keyword로 오분류 |
| `exhaustive_keyword` | 90% | 1개 | definition으로 오분류 |
| `exhaustive_list` | 90% | 1개 | translation으로 오분류 |

---

## 🎯 핵심 문제 분석

### 1. `normal_translation_search`의 역설 (80% → 목표: 100%)

#### 문제 원인
- **현상**: Regex가 너무 똑똑해져서 검색 키워드가 있어도 direct로 오분류
- **오분류 사례**:
  - "Find the conclusion of this paper and translate it" → `normal_translation_direct`
  - "증착 공정 가이드라인을 검색한 뒤 영어로 바꿔줘" → `normal_translation_direct`
- **근본 원인**: `_requires_search_for_translation` 메서드에서 **직접 번역 패턴 체크가 검색 패턴 체크보다 먼저 실행**되어, "this paper", "following" 같은 지시어가 있으면 검색 키워드가 있어도 직접 번역으로 판단됨

#### 해결 방안
**검색 키워드 체크를 최우선으로 배치**

```python
def _requires_search_for_translation(self, question: str) -> bool:
    # 1. [최우선] 검색 의도가 명확하면 무조건 Search
    search_indicators = [
        r'찾아서', r'검색해서', r'검색한', r'찾은',
        r'search\s+for', r'find\s+the', r'retrieve',
        r'find.*and\s+translate', r'search.*and\s+translate',
        r'검색.*후', r'검색.*뒤', r'검색한\s*뒤',
    ]
    if any(re.search(p, question, re.IGNORECASE) for p in search_indicators):
        return True
    
    # 2. [차순위] 지시어/대명사가 있으면 Direct
    direct_indicators = [
        r'이\s*문단', r'이\s*내용', r'following', r'this', r'that', r'above'
    ]
    if any(re.search(p, question, re.IGNORECASE) for p in direct_indicators):
        return False
    
    # ... 나머지 로직
```

**예상 효과**: 80% → 100% (2개 오분류 해결)

---

### 2. `simple_keyword`의 모호함 (70% → 목표: 85%+)

#### 문제 원인
- **현상**: 임베딩 공간에서 keyword 검색과 definition/exhaustive 질문이 겹침
- **오분류 사례**:
  - "'Degradation' 단어가 들어가는 페이지 검색" → `exhaustive_keyword`
  - "파일명에 'OLED'가 들어가는 파일 검색해" → `normal_definition`
  - "키워드 'Inkjet'으로 검색해봐" → `simple_fact`
- **근본 원인**: 
  1. `simple_keyword` 예시가 "다 찾아줘", "검색해줘" 같은 표현을 포함하여 exhaustive와 경계가 모호
  2. "특정 문서 하나를 콕 집어 찾는" 예시가 부족

#### 해결 방안
**`simple_keyword` 예시를 "특정 문서 하나를 콕 집어 찾는" 것으로만 채우기**

**현재 예시 (문제)**:
```json
"simple_keyword": [
  "파일명에 'OLED'가 들어가는 파일 찾아줘.",  // ❌ 모호 (여러 개일 수 있음)
  "'TADF' 단어가 포함된 섹션 검색해줘.",      // ❌ 모호
]
```

**개선 예시 (권장)**:
```json
"simple_keyword": [
  "Changmin Keum 교수가 쓴 논문 찾아줘.",      // ✅ 특정 저자 논문 하나
  "특허 번호 US10234567 검색해줘.",           // ✅ 특정 특허 하나
  "작성자가 '김연구'인 보고서 찾아.",          // ✅ 특정 작성자 보고서
  "제목이 'OLED 수명 분석'인 문서 보여줘.",   // ✅ 특정 제목 문서
  "2024년 3월에 작성된 실험 보고서 찾아줘.",  // ✅ 특정 날짜 문서
]
```

**"다 찾아줘" 표현은 `exhaustive_keyword`로 이동**

**예상 효과**: 70% → 85%+ (2-3개 오분류 해결)

---

### 3. `normal_definition` vs `normal_explanation` 경계 (80% → 목표: 90%+)

#### 문제 원인
- **현상**: "설명해줘" 키워드가 있으면 `normal_explanation`으로 오분류
- **오분류 사례**:
  - "Polaron이 뭔지 설명해줘" → `normal_explanation` (정답: `normal_definition`)
  - "정공 수송층(HTL)의 역할이 뭐야?" → `simple_fact` (정답: `normal_definition`)

#### 해결 방안
**키워드 가중치 시스템 강화**

`CATEGORY_KEYWORDS`에 `normal_definition` 키워드 추가:
```python
CATEGORY_KEYWORDS = {
    "normal_definition": {
        "positive": ["정의", "뜻", "의미", "개념", "란", "무엇인가", "뭐야", "역할"],
        "negative": ["원인", "이유", "원리", "메커니즘", "작동", "왜", "어떻게"]
    },
    # ...
}
```

**예상 효과**: 80% → 90%+ (1-2개 오분류 해결)

---

### 4. `hierarchical` 라우팅의 부진 (33% → 목표: 유지)

#### 문제 원인
- **현상**: Semantic Router가 실패해서 넘어온 **'정말 어려운 질문'**들만 처리
- **근본 원인**: Semantic Router의 커버리지가 높아져서 LLM까지 넘어오는 질문이 매우 어려운 케이스만 남음

#### 해결 방안
**억지로 올리기보다, Semantic Router의 커버리지를 높여서 LLM까지 넘어오는 일을 줄이는 게 더 효율적**

현재 방향성이 맞으므로 추가 개선은 보류.

---

## 🛠️ 구현 계획

### Phase 1: `normal_translation_search` 정확도 복구 (우선순위: 최고)

#### 작업 내용
1. `utils/question_classifier.py`의 `_requires_search_for_translation` 메서드 수정
   - 검색 키워드 체크를 최우선으로 배치
   - 직접 번역 패턴 체크를 차순위로 이동
   - "검색한 뒤", "검색 후", "find ... and translate" 패턴 강화

#### 예상 소요 시간
- 코드 수정: 30분
- 테스트: 10분
- **총 40분**

#### 예상 효과
- `normal_translation_search`: 80% → 100% (+20%p)
- 전체 정확도: 86% → 88% (+2%p)

---

### Phase 2: `simple_keyword` 예시 질문 개선 (우선순위: 높음)

#### 작업 내용
1. `utils/data/router_examples.json`의 `simple_keyword` 예시 수정
   - "특정 문서 하나를 콕 집어 찾는" 예시로만 채우기
   - "다 찾아줘", "검색해줘" 같은 표현 제거
   - `exhaustive_keyword` 예시에 "다 찾아줘" 표현 추가

2. Semantic Router 캐시 재생성 (자동)
   - 프로그램 재시작 시 자동으로 재계산

#### 예상 소요 시간
- 예시 수정: 20분
- 테스트: 10분
- **총 30분**

#### 예상 효과
- `simple_keyword`: 70% → 85%+ (+15%p)
- 전체 정확도: 88% → 89%+ (+1%p)

---

### Phase 3: `normal_definition` 키워드 가중치 강화 (우선순위: 중간)

#### 작업 내용
1. `utils/question_classifier.py`의 `CATEGORY_KEYWORDS` 수정
   - `normal_definition`에 "역할", "뭐야" 키워드 추가
   - `normal_definition`의 negative 키워드에 "원인", "이유", "원리" 추가

#### 예상 소요 시간
- 코드 수정: 15분
- 테스트: 10분
- **총 25분**

#### 예상 효과
- `normal_definition`: 80% → 90%+ (+10%p)
- 전체 정확도: 89% → 90%+ (+1%p)

---

## 📋 작업 체크리스트

### Phase 1: `normal_translation_search` 정확도 복구
- [ ] `_requires_search_for_translation` 메서드 순서 변경
  - [ ] 검색 키워드 체크를 최우선으로 배치
  - [ ] 직접 번역 패턴 체크를 차순위로 이동
  - [ ] "검색한 뒤", "검색 후" 패턴 추가
  - [ ] "find ... and translate" 패턴 강화
- [ ] 테스트 실행 및 결과 확인
- [ ] 보고서 업데이트

### Phase 2: `simple_keyword` 예시 질문 개선
- [ ] `router_examples.json`의 `simple_keyword` 예시 수정
  - [ ] "특정 문서 하나를 콕 집어 찾는" 예시로만 채우기
  - [ ] "다 찾아줘" 표현 제거
  - [ ] `exhaustive_keyword` 예시에 "다 찾아줘" 표현 추가
- [ ] Semantic Router 캐시 재생성 확인
- [ ] 테스트 실행 및 결과 확인
- [ ] 보고서 업데이트

### Phase 3: `normal_definition` 키워드 가중치 강화
- [ ] `CATEGORY_KEYWORDS` 수정
  - [ ] `normal_definition` positive 키워드 추가
  - [ ] `normal_definition` negative 키워드 추가
- [ ] 테스트 실행 및 결과 확인
- [ ] 보고서 업데이트

---

## 🎯 최종 목표

### 정확도 목표
- **전체 정확도**: 86% → **90%+** (+4%p 이상)
- **카테고리별 목표**:
  - `normal_translation_search`: 80% → **100%** (+20%p)
  - `simple_keyword`: 70% → **85%+** (+15%p)
  - `normal_definition`: 80% → **90%+** (+10%p)
  - 기타 카테고리: 현재 수준 유지 또는 소폭 향상

### 예상 오분류 감소
- 현재: 14개 오분류
- 목표: 10개 이하 오분류 (-28.6% 이상)

---

## 📝 참고 사항

### Semantic Router 캐시 재생성
- `router_examples.json` 수정 후 프로그램 재시작 시 자동으로 재계산됨
- 캐시 파일: `utils/data/router_embeddings_{model_hash}.pkl`
- 수동 삭제 필요 시: 캐시 파일 삭제 후 재시작

### 테스트 방법
```bash
# 가상환경 활성화
.\venv\Scripts\activate

# 테스트 실행
.\venv\Scripts\python.exe tests/test_question_classifier_accuracy.py
```

### 보고서 위치
- 개선 결과 보고서: `docs/reports/QUESTION_CLASSIFIER_IMPROVEMENT_REPORT.md`
- 테스트 보고서: `logs/test/question_classifier_accuracy_report_YYYYMMDD_HHMMSS.txt`

---

**작성일**: 2025-12-09  
**최종 업데이트**: 2025-12-09

