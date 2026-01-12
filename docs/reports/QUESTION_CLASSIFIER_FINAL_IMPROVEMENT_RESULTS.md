# 질문 분류기 최종 개선 결과 보고서

**작성일**: 2025-12-09  
**테스트 일시**: 2025-12-09 21:56:31  
**테스트 보고서**: `logs/test/question_classifier_accuracy_report_20251209_215610.txt`

---

## 📊 개선 결과 요약

### 전체 정확도
- **이전(2025-12-09 19:51)**: 80.00% (80/100)
- **현재(2025-12-09 21:56)**: 82.00% (82/100)
- **변화**: +2.00%p (Soft Boosting 적용)

### Semantic Router 상태
- 캐시 재사용 + Soft Boosting 적용
- **분류 방법별 정확도**:
  - Semantic Router: 61/76 (80.3%)
  - Regex Fast-Track: 18/19 (94.7%)
  - Hierarchical: 3/5 (60.0%)

---

## ✅ Phase별 개선 결과

### Phase 1: `normal_translation_search` 정확도 복구 ✅

#### 목표
- `normal_translation_search`: 80% → 100%

#### 결과
- **달성**: 100% (10/10) ✅
- **오분류**: 0개

#### 개선 내용
- `_requires_search_for_translation` 메서드 순서 변경
  - 검색 키워드 체크를 최우선으로 배치
  - 직접 번역 패턴 체크를 차순위로 이동
  - "검색한 뒤", "검색 후", "find ... and translate" 패턴 강화

#### 성공 사례
- "Find the conclusion of this paper and translate it" → `normal_translation_search` ✅
- "증착 공정 가이드라인을 검색한 뒤 영어로 바꿔줘" → `normal_translation_search` ✅

---

### Phase 2: `simple_keyword` 예시 질문 개선 ⚠️

#### 목표
- `simple_keyword`: 70% → 85%+

#### 결과
- **현재**: 30% (3/10) ⚠️
- **오분류**: 7개 (대부분 `exhaustive_keyword`로 상승 분류, 1건 translation_search)

#### 문제 분석
- Semantic Router가 정상 작동했으나, 고유 식별자 예시가 “전수 검색” 톤으로 읽혀 `exhaustive_keyword`로 라우팅
- “모든/전체/전부” 어휘 없이도 “찾아줘/검색해” 패턴이 exhaustive로 끌려감
  - 예: “Changmin Keum 교수가 쓴 논문 찾아줘.” → exhaustive_keyword

#### 개선 내용
- 고유 식별자(숫자, 코드, 이름) 포함 예시 추가
- "특정 문서 하나를 콕 집어 찾는" 예시로만 채움
- "다 찾아줘" 표현을 `exhaustive_keyword`로 이동

#### 예시 개선
**이전**:
```json
"파일명에 'OLED'가 들어가는 파일 찾아줘."  // ❌ 모호
```

**개선**:
```json
"논문 ID-2024-001 찾아줘.",  // ✅ 고유 식별자
"특허 KR-10-2023-0012345 검색해.",  // ✅ 고유 식별자
"김철수 연구원이 작성한 보고서 보여줘."  // ✅ 특정 인물
```

---

### Phase 3: `normal_definition` 키워드 가중치 강화 ✅

#### 목표
- `normal_definition`: 80% → 90%+

#### 결과
- **현재**: 90% (9/10) ✅
- **오분류**: 1개 (`complex_relationship`으로 이동)

#### 문제 분석
- Semantic Router 가동 후 키워드 가중치 효과 확인
- “설명해줘” 톤 1건이 여전히 `normal_explanation`으로 이동 (추가 키워드 튜닝 여지)

#### 개선 내용
- `CATEGORY_KEYWORDS`에 `normal_definition` 키워드 추가
  - Positive: "정의", "뜻", "의미", "개념", "란", "무엇인가", "뭐야", "역할"
  - Negative: "원인", "이유", "원리", "메커니즘", "작동", "왜", "어떻게"

---

## 📈 카테고리별 정확도

| 카테고리 | 정확도 | 오분류 수 | 상태 |
|---------|--------|----------|------|
| `normal_translation_search` | **100%** | 0개 | ✅ 목표 달성 |
| `complex_comparison` | **100%** | 0개 | ✅ 목표 달성 |
| `exhaustive_list` | **100%** | 0개 | ✅ 달성 |
| `normal_definition` | 90% | 1개 | ✅ 양호 |
| `normal_explanation` | 90% | 1개 | ✅ 양호 |
| `simple_fact` | 90% | 1개 | ✅ 양호 |
| `exhaustive_keyword` | 80% | 2개 | ⚠️ 개선 필요 |
| `complex_relationship` | 60% | 4개 | ⚠️ 추가 튜닝 |
| `normal_translation_direct` | 80% | 2개 | ⚠️ 개선 필요 |
| `simple_keyword` | 30% | 7개 | ❌ 집중 개선 필요 |

---

## 🔍 분류 방법별 성능

### Regex Fast-Track
- **정확도**: 94.7% (18/19)
- **상태**: ✅ 우수
- **처리 질문**: 번역 관련 질문

### Hierarchical 라우팅
- **정확도**: 33.3% (1/3)
- **상태**: ⚠️ 데이터 적음 / 프롬프트 개선 여지
- **처리 질문**: Semantic Router 임계치 미달 케이스 소수

### Semantic Router
- **정확도**: 78.2% (61/78)
- **상태**: ⚠️ 추가 튜닝 필요 (특히 simple_keyword ↔ exhaustive_keyword 경계)
- **참고**: 캐시 재생성 후 정상 작동

---

## 🎯 주요 성과

### ✅ 달성한 목표

1. **`normal_translation_search` 100% 달성** ✅
   - Phase 1 목표 완전 달성
   - Regex 순서 변경으로 검색 키워드 우선 처리 성공

2. **`complex_comparison` 100% 유지** ✅
   - 비교 키워드 부스팅 추가 후 안정화

3. **Regex Fast-Track 94.7% 정확도** ✅
   - 번역 질문 처리에서 매우 우수한 성능

---

## ⚠️ 문제점 및 해결 방안

### 1. simple_keyword ↔ exhaustive_keyword 경계 불명확
- **문제**: 7건 상승(대부분 exhaustive), 1건 translation_search 이탈
- **원인**: “찾아줘/검색해” + 주제어가 전수 조사로 해석
- **대응**:
  - `simple_keyword`는 “단일/특정/ID/번호/파일명/문서명/NO.” 등 고유성 강조
  - `exhaustive_keyword`는 “모든/전체/전부/싹 다/리스트/목록” 의무 포함
  - 부스팅 규칙 유지, 추가 실험 시 가중치 미세 조정

### 2. complex_relationship 혼선
- **문제**: 4건이 `normal_explanation`/`complex_comparison`으로 이동
- **원인**: 영향/관계 vs 원인/비교 어휘 혼재
- **대응**:
  - 관계/영향/상관관계 어휘를 positive로 보강, 비교/원인 어휘는 페널티 검토

### 3. normal_translation_direct 경계
- **문제**: 2건(`normal_explanation`, `normal_translation_search`)으로 이동
- **원인**: “보고서 말투로 번역” 등 검색+번역 의도
- **대응**:
  - Regex Fast-Track 패턴에 “말투/톤/보고서 스타일”을 direct로 묶을지 검토

---

## 📋 다음 단계

### 즉시 조치 (우선순위: 최고)
1. **simple_keyword vs exhaustive_keyword 분리 강화**
   - [ ] 예시 문구 재정비 (단일/특정 vs 모두/전체)
   - [ ] Semantic Router 키워드 가중치 분리
2. **simple_fact 예시 보강**
   - [ ] 수치/단위/페이지 지시어 추가
3. **normal_translation_direct 오분류 2건 원인 파악**
   - [ ] “보고서 말투로 번역” 케이스 규칙 재점검

### 중기 개선 (우선순위: 높음)
1. **Semantic Router 가중치 튜닝**
   - [ ] 카테고리별 positive/negative 키워드 조정
   - [ ] 임계값(semantic confidence) 재조정
2. **Hierarchical 프롬프트 최소화**
   - [ ] Semantic Router 확신도 기준 상향 조정 검토

### 장기 개선 (우선순위: 중간)
1. **예시 질문 데이터셋 확장**
   - [ ] 카테고리별 20개 → 30개 (경계 케이스 포함)
2. **키워드 가중치 자동 학습**
   - [ ] 오분류 로그 기반 가중치 업데이트 자동화

---

## 📝 결론

### 주요 성과
- ✅ **Phase 1 유지**: `normal_translation_search` 100%
- ✅ **`complex_comparison` 100%**, **`exhaustive_list` 100%**, **`normal_definition` 90%**, **`simple_fact` 90%**
- ✅ Soft Boosting 적용 후 전체 정확도 82%

### 현재 제약사항
- ⚠️ `simple_keyword` 30% (exhaustive로 상승 분류 다수)
- ⚠️ `complex_relationship` 60% (관계/영향 vs 원인/비교 혼선)
- ⚠️ `normal_translation_direct` 80% (검색+번역 뉘앙스 1건, 설명으로 1건)

### 예상 효과 (추가 튜닝 후)
- simple_keyword/관계 튜닝 시 전체 정확도 **90%±** 전망
- 번역 경계 Regex 보강으로 translation_direct 오분류 감소 기대

---

**보고서 작성일**: 2025-12-09  
**테스트 보고서**: `logs/test/question_classifier_accuracy_report_20251209_215610.txt`  
**개선 플랜**: `docs/guides/QUESTION_CLASSIFIER_FINAL_IMPROVEMENT_PLAN.md`


