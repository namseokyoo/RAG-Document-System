# RAG 시스템 성능 분석 및 개선 계획

## 📊 성능 지표 제안

### 1. 검색 정확도 지표
- **Recall@K**: 상위 K개 결과에 실제 관련 문서가 포함된 비율
- **Precision@K**: 상위 K개 결과 중 실제 관련 문서의 비율
- **MRR (Mean Reciprocal Rank)**: 첫 번째 관련 문서의 역순위 평균
- **NDCG@K (Normalized Discounted Cumulative Gain)**: 순위 고려 유사도 점수

### 2. 응답 품질 지표
- **Answer Relevance**: 답변이 질문과 관련 있는 정도 (0-1)
- **Answer Faithfulness**: 답변이 제공된 컨텍스트에 기반한 정도 (0-1)
- **Answer Completeness**: 답변이 질문에 완전히 답하는 정도 (0-1)
- **Citation Accuracy**: 인용된 출처가 실제 답변 내용과 일치하는 정도 (0-1)

### 3. 일관성 지표
- **Response Consistency**: 동일 질문에 대한 반복 응답의 일관성 (0-1)
- **Score Stability**: 동일 문서에 대한 검색 점수의 변동성 (표준편차)
- **Context Stability**: 동일 질문에 대한 검색 컨텍스트의 일관성

### 4. 응답 속도 지표
- **Time to First Token (TTFT)**: 질문 입력부터 첫 토큰까지 시간
- **Total Response Time**: 전체 응답 생성 시간
- **Search Latency**: 검색 단계 소요 시간
- **Reranking Latency**: Reranking 단계 소요 시간

### 5. 효율성 지표
- **Context Utilization**: 제공된 컨텍스트 중 실제 사용된 비율
- **Token Efficiency**: 생성된 토큰 대비 유용한 정보 비율
- **Cost per Query**: 쿼리당 API 호출 비용 (토큰 수 기반)

---

## 🔍 현재 파이프라인 분석

### 파이프라인 단계별 현황

#### 1. 질문 분류 (Question Classifier)
**현재 상태:**
- 규칙 기반 + LLM 하이브리드 분류
- simple/normal/complex/exhaustive 4가지 유형
- 분류 결과에 따라 파라미터 동적 조정

**개선 포인트:**
- ✅ 이미 구현됨: 동적 파라미터 조정
- ⚠️ 개선 가능: 분류 정확도 향상 (더 정교한 프롬프트)
- ⚠️ 개선 가능: 분류 결과 캐싱 (유사 질문 재사용)

#### 2. 임베딩 검색 (Hybrid Search)
**현재 상태:**
- Vector Search (Cosine Similarity)
- BM25 키워드 검색
- Hybrid: BM25 + Vector 가중치 합산 (기본 0.5:0.5)
- Multi-Query 확장 (기본 3개 쿼리, 병렬 처리)

**개선 포인트:**
- ⚠️ **BM25 가중치 최적화**: 현재 0.5 고정 → 질문 유형별 동적 조정
- ⚠️ **임베딩 모델 품질**: 현재 `mxbai-embed-large` → 더 큰 모델 또는 도메인 특화 모델
- ⚠️ **Query Expansion 개선**: Multi-Query 외에 동의어 확장 활성화 검토
- ⚠️ **초기 후보 수 최적화**: `reranker_initial_k=30` → 질문 복잡도별 조정

#### 3. Reranking
**현재 상태:**
- Cross-Encoder 기반 (`multilingual-mini`)
- Diversity Penalty 적용 (기본 0.3)
- 점수 정규화 및 조정

**개선 포인트:**
- ⚠️ **Reranker 모델 업그레이드**: 더 큰 모델로 교체 (정확도 향상, 속도 트레이드오프)
- ⚠️ **Diversity Penalty 최적화**: 현재 0.3 → 질문 유형별 조정
- ⚠️ **Reranker 점수 정규화 개선**: 점수 분포 분석 후 정규화 방식 개선

#### 4. Score Filtering
**현재 상태:**
- 통계 기반 이상치 제거 (MAD 방식)
- Adaptive Threshold (top1의 60%)
- 최소/최대 개수 제한 (3-20개)

**개선 포인트:**
- ⚠️ **Adaptive Threshold 최적화**: 현재 0.6 → 질문 유형별 조정
- ⚠️ **Gap-based Cutoff 활성화**: 점수 gap 기반 자동 컷오프 (현재 미사용)
- ⚠️ **Semantic Similarity Filter 추가**: 임베딩 기반 추가 필터링

#### 5. Small-to-Large
**현재 상태:**
- 부모-자식 청크 구조 활용
- Context size: 800자
- 부모 청크 주변 컨텍스트 확장

**개선 포인트:**
- ⚠️ **Context Size 최적화**: 현재 800 → 질문 유형별 조정
- ⚠️ **부모 청크 선택 개선**: 단순 거리 기반 → 의미론적 관련성 기반

#### 6. LLM 응답 생성
**현재 상태:**
- 프롬프트 템플릿 기반
- Temperature: 0.3 (일관성 우선)
- Max Tokens: 4096

**개선 포인트:**
- ⚠️ **프롬프트 최적화**: Few-shot 예시 추가, 구조화된 출력 지시
- ⚠️ **Temperature 조정**: 질문 유형별 동적 조정 (simple: 0.1, complex: 0.5)
- ⚠️ **Self-Consistency Check**: 여러 답변 생성 후 일관성 검증 (현재 비활성화)

---

## 🎯 우선순위별 개선 방안

### Phase 1: 빠른 개선 (Quick Wins) - 1-2일

#### 1.1 BM25 가중치 동적 조정
**목표**: 질문 유형에 따라 BM25/Vector 가중치 최적화

**방법**:
- Simple 질문: BM25 가중치 증가 (0.7) - 키워드 매칭 중요
- Complex 질문: Vector 가중치 증가 (0.7) - 의미론적 유사도 중요
- Exhaustive 질문: 균형 유지 (0.5:0.5)

**예상 효과**: 검색 정확도 +5-10%

#### 1.2 Adaptive Threshold 최적화
**목표**: 질문 유형별 threshold 조정

**방법**:
- Simple: 0.7 (엄격한 필터링)
- Normal: 0.6 (현재값)
- Complex: 0.5 (완화된 필터링)
- Exhaustive: 0.4 (최대한 많은 문서)

**예상 효과**: Precision +3-5%, Recall +2-3%

#### 1.3 Gap-based Cutoff 활성화
**목표**: 점수 gap 기반 자동 컷오프

**방법**:
- Reranker 점수 gap 분석
- 평균 gap의 2배 이상 차이 시 컷오프
- 최소 문서 수 보장 (3개)

**예상 효과**: 노이즈 제거, 정확도 +3-5%

#### 1.4 프롬프트 Few-shot 예시 추가
**목표**: LLM 응답 품질 향상

**방법**:
- 질문 유형별 예시 추가
- Citation 형식 예시
- 수식/수치 정확도 예시

**예상 효과**: Answer Faithfulness +5-10%

### Phase 2: 중기 개선 (Medium-term) - 3-5일

#### 2.1 Reranker 모델 업그레이드
**목표**: 더 정확한 재순위화

**방법**:
- `multilingual-mini` → `multilingual-base` 또는 더 큰 모델
- 속도 vs 정확도 트레이드오프 분석
- A/B 테스트

**예상 효과**: Reranking 정확도 +10-15%, 속도 -20-30%

#### 2.2 임베딩 모델 최적화
**목표**: 검색 품질 향상

**방법**:
- 현재: `mxbai-embed-large` (1024차원)
- 대안: `bge-large-en-v1.5` 또는 도메인 특화 모델
- 임베딩 차원 증가 (1024 → 1536)

**예상 효과**: 검색 Recall +5-10%

#### 2.3 Self-Consistency Check 활성화
**목표**: 응답 일관성 향상

**방법**:
- 복잡한 질문에 대해 N개 답변 생성
- 일관성 검증 후 최종 답변 선택
- Confidence score 계산

**예상 효과**: Response Consistency +10-15%, 속도 -30-50%

#### 2.4 Context Utilization 최적화
**목표**: 컨텍스트 효율성 향상

**방법**:
- 컨텍스트 길이 동적 조정
- 질문 유형별 최적 컨텍스트 크기
- 불필요한 컨텍스트 제거

**예상 효과**: Token Efficiency +10-15%, Cost -5-10%

### Phase 3: 장기 개선 (Long-term) - 1-2주

#### 3.1 질문 분류 정확도 향상
**목표**: 더 정확한 질문 분류

**방법**:
- Fine-tuned 분류 모델
- 분류 결과 캐싱
- 사용자 피드백 기반 학습

**예상 효과**: 분류 정확도 +15-20%

#### 3.2 도메인 특화 임베딩
**목표**: 도메인 특화 검색

**방법**:
- 과학/기술 문서용 Fine-tuned 임베딩
- 도메인 용어 사전 확장
- 엔티티 인식 개선

**예상 효과**: 도메인 특화 질문 정확도 +20-30%

#### 3.3 멀티모달 검색 개선
**목표**: 이미지/표 검색 품질 향상

**방법**:
- Vision 임베딩 품질 개선
- 표 구조 인식 정확도 향상
- 이미지-텍스트 매칭 개선

**예상 효과**: Vision 청크 검색 정확도 +15-25%

---

## 📈 성능 측정 방법

### 1. 벤치마크 데이터셋 구축
- 질문-답변 쌍 수집 (최소 50-100개)
- Ground truth 문서 매핑
- 카테고리별 균형 유지

### 2. 자동 평가 스크립트
```python
# 평가 지표 계산
- Recall@K
- Precision@K
- MRR
- NDCG@K
- Answer Relevance (LLM 기반)
- Answer Faithfulness (LLM 기반)
```

### 3. A/B 테스트 프레임워크
- 기존 설정 vs 개선 설정 비교
- 통계적 유의성 검증
- 사용자 피드백 수집

---

## 🔧 구현 우선순위

### 즉시 구현 가능 (High Impact, Low Effort)
1. ✅ BM25 가중치 동적 조정
2. ✅ Adaptive Threshold 최적화
3. ✅ Gap-based Cutoff 활성화
4. ✅ 프롬프트 Few-shot 예시 추가

### 단기 구현 (High Impact, Medium Effort)
5. Reranker 모델 업그레이드 (테스트 필요)
6. Self-Consistency Check 활성화 (복잡 질문만)
7. Context Utilization 최적화

### 중장기 구현 (Medium Impact, High Effort)
8. 임베딩 모델 교체 (재임베딩 필요)
9. 도메인 특화 Fine-tuning
10. 멀티모달 검색 개선

---

## 📝 다음 단계

1. **성능 측정**: 현재 성능 기준선 수립
2. **Quick Wins 구현**: Phase 1 항목 우선 구현
3. **A/B 테스트**: 개선 효과 검증
4. **점진적 확장**: 검증된 개선사항만 확장

