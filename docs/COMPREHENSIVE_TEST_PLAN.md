# RAG 시스템 종합 테스트 계획

**작성일**: 2025-11-11
**버전**: v3.6.2
**목적**: 현재 시스템 품질 평가 및 개선 가능성 분석

---

## 🎯 테스트 목표

### 1. 성능 측정
- 검색 정확도 (Precision, Recall)
- 답변 품질 (Relevance, Completeness)
- 인용 정확도 (Citation Accuracy)
- 응답 시간 (Latency)

### 2. 한계 파악
- 실패 케이스 분석
- 에지 케이스 발견
- 개선 가능 영역 식별

### 3. 최적화 기회
- 현재 설정의 효율성
- 알고리즘 개선 가능성
- 파라미터 튜닝 여지

---

## 📋 테스트 케이스 설계

### Phase 1: 질문 유형별 테스트 (Question Type Coverage)

#### 1.1 Simple Questions (단순 사실 확인)
```
목표: Question Classifier의 Simple 분류 검증
예상 응답 시간: ~12초
예상 검색 문서: 3-5개
```

**테스트 케이스:**
1. "OLED의 정의는?"
2. "페로브스카이트 태양전지는 무엇인가?"
3. "그래핀의 주요 특성은?"
4. "백금 촉매의 역할은?"
5. "양자점의 크기는 얼마인가?"

**평가 기준:**
- ✅ 정답 포함 여부
- ✅ 간결성 (불필요한 정보 없음)
- ✅ 인용 정확도
- ✅ 분류기 정확도 (Simple로 분류되었는가?)

---

#### 1.2 Normal Questions (일반 질문)
```
목표: 기본 RAG 파이프라인 검증
예상 응답 시간: ~30초
예상 검색 문서: 10-20개
```

**테스트 케이스:**
1. "OLED 디바이스의 효율을 향상시키는 방법은?"
2. "페로브스카이트 태양전지의 안정성 문제를 해결하는 방법은?"
3. "그래핀 기반 센서의 감도를 높이는 전략은?"
4. "백금 촉매를 대체할 수 있는 물질은?"
5. "양자점 합성에서 크기를 제어하는 방법은?"

**평가 기준:**
- ✅ 답변의 완전성 (여러 방법 포함)
- ✅ 컨텍스트 품질
- ✅ 인용의 다양성
- ✅ Small-to-Large 효과

---

#### 1.3 Complex Questions (복잡한 질문)
```
목표: Multi-Query 및 고급 검색 검증
예상 응답 시간: ~45초
예상 검색 문서: 30-60개
```

**테스트 케이스:**
1. "OLED와 QLED의 효율, 수명, 색재현율을 비교해줘"
2. "페로브스카이트 태양전지와 실리콘 태양전지의 장단점을 분석해줘"
3. "그래핀과 CNT의 전기 전도도와 기계적 강도를 비교해줘"
4. "백금 촉매와 팔라듐 촉매의 활성도와 비용을 비교해줘"
5. "CdSe 양자점과 InP 양자점의 발광 특성을 비교해줘"

**평가 기준:**
- ✅ 비교 구조 (A vs B)
- ✅ 다양한 관점 포함
- ✅ 균형 잡힌 정보
- ✅ Multi-Query 효과

---

#### 1.4 Exhaustive Questions (전체 조회)
```
목표: Exhaustive Retrieval 검증
예상 응답 시간: ~35초
예상 검색 문서: 50-100개
```

**테스트 케이스:**
1. "OLED 관련 모든 연구를 요약해줘"
2. "페로브스카이트 태양전지 논문 전체를 분석해줘"
3. "그래핀 연구의 모든 응용 분야를 나열해줘"
4. "촉매 연구의 전체 트렌드를 파악해줘"
5. "양자점 관련 모든 합성 방법을 정리해줘"

**평가 기준:**
- ✅ 포괄성 (Coverage)
- ✅ 중복 제거
- ✅ 구조화된 요약
- ✅ Exhaustive mode 활성화 여부

---

### Phase 2: 검색 기능별 테스트 (Retrieval Feature Testing)

#### 2.1 Hybrid Search (Vector + BM25)
```
목표: 의미 검색과 키워드 검색의 조화 검증
```

**테스트 케이스:**
1. "OLED efficiency enhancement" (영어 전문 용어)
2. "페로브스카이트 안정성" (한국어 키워드)
3. "그래핀 electrical conductivity" (한영 혼합)
4. "백금 Pt catalyst" (한영 혼합 + 기호)
5. "CdSe quantum dot synthesis" (화학식 포함)

**평가 기준:**
- ✅ 키워드 매칭 정확도
- ✅ 의미적 유사도
- ✅ Alpha 가중치 효과 (0.5)

---

#### 2.2 Small-to-Large (컨텍스트 확장)
```
목표: 청크 경계 문제 해결 검증
```

**테스트 케이스:**
1. "표 3에 나온 효율 값은?" (표 참조)
2. "그림 5의 결과를 설명해줘" (그림 참조)
3. "실험 방법의 2단계는?" (단계별 설명)
4. "결론 부분에서 언급된 주요 발견은?" (문맥 필요)
5. "참고문헌 10번 논문의 주제는?" (인용 추적)

**평가 기준:**
- ✅ 완전한 컨텍스트 제공
- ✅ 청크 경계 극복
- ✅ 전후 문맥 포함

---

#### 2.3 Reranker (검색 결과 재정렬)
```
목표: BGE Reranker 효과 검증
```

**테스트 케이스:**
1. "OLED 효율 20% 이상인 연구" (수치 필터)
2. "2020년 이후 페로브스카이트 연구" (시간 필터)
3. "Kim 저자의 그래핀 논문" (저자 필터)
4. "Nature 저널의 촉매 논문" (출처 필터)
5. "리뷰 논문만 찾아줘" (문서 유형)

**평가 기준:**
- ✅ 관련도 순서 정확도
- ✅ Score threshold 효과
- ✅ Top-k vs Score-based filtering

---

#### 2.4 Citation System (인용 정확도)
```
목표: 95% 인용 정확도 검증
```

**테스트 케이스:**
1. "OLED 효율 향상 방법" → 인용된 페이지 수동 확인
2. "페로브스카이트 안정성" → 인용 중복 확인
3. "그래핀 특성" → 인용 정확도 확인
4. "백금 촉매" → 인용 완전성 확인
5. "양자점 합성" → 인용 형식 확인

**평가 기준:**
- ✅ 페이지 번호 정확도
- ✅ 문서명 정확도
- ✅ 중복 제거 효과
- ✅ 인용 형식 일관성

---

### Phase 3: 에지 케이스 테스트 (Edge Case Testing)

#### 3.1 부정확한 질문
```
목표: 모호한 질문 처리 능력 검증
```

**테스트 케이스:**
1. "그거 뭐였지?" (대명사 참조)
2. "아까 말한 그 효율" (문맥 의존)
3. "비슷한 거 있어?" (모호한 기준)
4. "더 좋은 방법은?" (주관적 평가)
5. "이게 맞나?" (확인 질문)

**평가 기준:**
- ✅ 명확화 요청 여부
- ✅ 추론 능력
- ✅ 오류 처리

---

#### 3.2 존재하지 않는 정보
```
목표: Hallucination 방지 검증
```

**테스트 케이스:**
1. "OLED의 양자 터널링 효과는?" (관련 없음)
2. "페로브스카이트의 초전도 현상은?" (부적절)
3. "그래핀의 생물학적 분해는?" (잘못된 영역)
4. "백금의 광합성 촉매 역할은?" (맥락 오류)
5. "양자점의 중력파 방출은?" (완전 무관)

**평가 기준:**
- ✅ "정보 없음" 응답
- ✅ Hallucination 없음
- ✅ 대안 제시

---

#### 3.3 복합 조건 질문
```
목표: 필터링 기능 한계 테스트
```

**테스트 케이스:**
1. "OLED 논문 중 2020년 이후이고 효율 20% 이상인 연구"
2. "Kim 저자의 페로브스카이트 논문 중 Nature 저널만"
3. "그래핀 센서 연구 중 상온에서 작동하는 것만"
4. "백금 촉매 논문 중 실험 데이터가 있는 것만"
5. "양자점 합성 논문 중 수율 80% 이상인 것만"

**평가 기준:**
- ✅ 조건 인식 여부
- ✅ 필터링 정확도
- ✅ 한계 명확화

---

### Phase 4: 성능 및 비용 테스트 (Performance Testing)

#### 4.1 응답 시간 측정
```
목표: 질문 유형별 응답 시간 검증
```

**측정 항목:**
- Simple: 목표 ~12초
- Normal: 목표 ~30초
- Complex: 목표 ~45초
- Exhaustive: 목표 ~35초

**분석:**
- ✅ 병목 구간 식별
- ✅ 최적화 기회 발견
- ✅ Question Classifier 효과

---

#### 4.2 LLM 호출 횟수 및 비용
```
목표: 비용 효율성 검증
```

**측정 항목:**
- LLM 호출 횟수 (Query Expansion, Generation)
- 토큰 사용량 (Input, Output)
- 예상 비용 ($)

**분석:**
- ✅ 불필요한 호출 식별
- ✅ 토큰 최적화 효과
- ✅ ROI 계산

---

#### 4.3 검색 품질 지표
```
목표: 정량적 품질 측정
```

**측정 항목:**
- Precision@k (상위 k개 중 정답 비율)
- Recall@k (전체 정답 중 검색된 비율)
- MRR (Mean Reciprocal Rank)
- nDCG (Normalized Discounted Cumulative Gain)

**분석:**
- ✅ 검색 알고리즘 효과
- ✅ Top-k 파라미터 최적화
- ✅ Reranker 효과

---

## 🔬 중간 단계 로깅 시스템

### 로깅 구조

```python
{
  "test_id": "test_001",
  "timestamp": "2025-11-11T10:30:00",
  "question": "OLED 효율 향상 방법은?",

  # Phase 1: Question Classification
  "classification": {
    "type": "normal",
    "confidence": 0.85,
    "method": "rule-based",
    "multi_query": true,
    "max_results": 20,
    "max_tokens": 2048,
    "elapsed_time": 0.05
  },

  # Phase 2: Query Expansion
  "query_expansion": {
    "enabled": true,
    "original_query": "OLED 효율 향상 방법은?",
    "expanded_queries": [
      "OLED 발광 효율을 개선하는 기술은?",
      "유기 발광 다이오드 성능 최적화 방법은?",
      "OLED 디바이스 효율성 증대 전략은?"
    ],
    "elapsed_time": 2.3,
    "llm_calls": 1,
    "tokens_used": 150
  },

  # Phase 3: Hybrid Search
  "search": {
    "vector_search": {
      "query": "OLED 효율 향상 방법은?",
      "k": 60,
      "results": 58,
      "elapsed_time": 1.2,
      "embedding_time": 0.3
    },
    "bm25_search": {
      "query": "OLED 효율 향상 방법",
      "k": 60,
      "results": 42,
      "elapsed_time": 0.5
    },
    "fusion": {
      "alpha": 0.5,
      "combined_results": 60,
      "elapsed_time": 0.1
    }
  },

  # Phase 4: Reranking
  "reranking": {
    "input_docs": 60,
    "reranker_model": "multilingual-mini",
    "output_docs": 18,
    "score_threshold": 0.5,
    "scores": [0.89, 0.82, 0.76, ...],
    "elapsed_time": 3.5
  },

  # Phase 5: Small-to-Large
  "context_expansion": {
    "initial_chunks": 18,
    "expanded_chunks": 36,
    "context_size_total": 28000,
    "elapsed_time": 0.2
  },

  # Phase 6: Answer Generation
  "generation": {
    "llm_model": "gemma3:4b",
    "temperature": 0.3,
    "max_tokens": 2048,
    "context_tokens": 1800,
    "output_tokens": 350,
    "elapsed_time": 12.5,
    "streaming": true
  },

  # Phase 7: Citation
  "citation": {
    "sources": [
      {"source": "oled_paper_1.pdf", "page": 5},
      {"source": "oled_paper_2.pdf", "page": 12},
      {"source": "oled_paper_3.pdf", "page": 8}
    ],
    "deduplication": true,
    "accuracy_check": true
  },

  # Total Metrics
  "total": {
    "elapsed_time": 23.5,
    "llm_calls": 2,
    "total_tokens": 2300,
    "estimated_cost": 0.023
  },

  # Result
  "answer": "OLED 효율을 향상시키는 방법은...",
  "answer_quality": {
    "relevance": 0.9,
    "completeness": 0.85,
    "citation_accuracy": 0.95
  }
}
```

---

## 📊 분석 방법

### 1. 자동 분석
- 응답 시간 통계 (평균, 중앙값, P95, P99)
- 검색 품질 지표 (Precision, Recall, MRR, nDCG)
- 비용 분석 (LLM 호출, 토큰 사용)
- 분류기 정확도 (혼동 행렬)

### 2. 수동 분석
- 답변 품질 평가 (5점 척도)
- 인용 정확도 검증 (샘플링)
- 실패 케이스 분류
- 개선 아이디어 수집

### 3. 비교 분석
- 설정별 성능 비교 (Reranker ON/OFF 등)
- 모델별 성능 비교
- 알고리즘별 효과 측정

---

## 🎯 성공 기준

### Tier 1: 기본 품질
- ✅ Simple 질문 정확도 > 90%
- ✅ Normal 질문 정확도 > 80%
- ✅ 인용 정확도 > 90%
- ✅ 응답 시간 < 60초 (95%)

### Tier 2: 고급 품질
- ✅ Complex 질문 정확도 > 70%
- ✅ Hallucination 비율 < 5%
- ✅ 답변 완전성 > 80%
- ✅ 사용자 만족도 > 4.0/5.0

### Tier 3: 최적화 품질
- ✅ 비용 효율성 ($/query < $0.05)
- ✅ Question Classifier 정확도 > 85%
- ✅ Reranker 효과 > 15% 향상
- ✅ Small-to-Large 효과 > 10% 향상

---

## 🚀 실행 계획

### Phase 1: 준비 (1일)
1. ✅ 테스트 케이스 작성 (50개)
2. ✅ 로깅 시스템 구현
3. ✅ DB 상태 확인 및 수정
4. ✅ 테스트 스크립트 개발

### Phase 2: 실행 (1일)
1. ✅ 자동 테스트 실행 (50개 케이스)
2. ✅ 로그 수집 (중간 단계 포함)
3. ✅ 수동 검증 (샘플링)
4. ✅ 이슈 기록

### Phase 3: 분석 (1일)
1. ✅ 정량 분석 (지표 계산)
2. ✅ 정성 분석 (실패 케이스)
3. ✅ 병목 구간 식별
4. ✅ 개선 제안 도출

### Phase 4: 보고서 (0.5일)
1. ✅ 종합 보고서 작성
2. ✅ 개선 우선순위 결정
3. ✅ 로드맵 제시

---

## 📁 산출물

### 1. 테스트 결과
- `test_results.json`: 전체 테스트 결과
- `test_logs/`: 개별 테스트 로그 (중간 단계 포함)
- `test_summary.csv`: 요약 통계

### 2. 분석 보고서
- `QUALITY_ANALYSIS_REPORT.md`: 품질 분석
- `PERFORMANCE_ANALYSIS_REPORT.md`: 성능 분석
- `IMPROVEMENT_RECOMMENDATIONS.md`: 개선 제안

### 3. 시각화
- `charts/response_time.png`: 응답 시간 분포
- `charts/accuracy_by_type.png`: 유형별 정확도
- `charts/cost_analysis.png`: 비용 분석
- `charts/bottleneck_analysis.png`: 병목 분석

---

## 🔧 도구 및 스크립트

### 1. 테스트 실행
```bash
python comprehensive_test.py --test-cases test_cases.json --output test_results.json
```

### 2. 로그 분석
```bash
python analyze_test_logs.py --input test_results.json --output analysis_report.md
```

### 3. 시각화
```bash
python visualize_results.py --input test_results.json --output charts/
```

---

## 📌 다음 단계

### 즉시 실행
1. DB 상태 확인 및 수정 (ChromaDB 오류 해결)
2. 로깅 시스템 구현
3. 테스트 케이스 작성

### 순차 실행
1. Phase 1 테스트 (질문 유형별)
2. Phase 2 테스트 (검색 기능별)
3. Phase 3 테스트 (에지 케이스)
4. Phase 4 테스트 (성능 측정)

### 분석 및 개선
1. 결과 분석
2. 개선 제안 도출
3. 우선순위 결정
4. 구현 계획 수립

---

**작성자**: Claude Code
**상태**: ✅ 계획 수립 완료
**다음**: 로깅 시스템 구현 및 테스트 케이스 작성
