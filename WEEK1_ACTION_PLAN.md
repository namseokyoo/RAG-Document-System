# Week 1 실행 계획 및 효과 분석

**목표**: Multi-Document Diversity 확보 + Multi-query 최적화
**기간**: 5 영업일
**예상 효과**: 문서 적합성 50.9 → 75+점, 평균 응답시간 120초 → 40초

---

## 📋 Task 1: Multi-Document Diversity 강제 (Day 1-3)

### 현재 문제 진단

#### 실제 로그 분석 필요
```python
# 1단계: 문제 정확한 파악
# 실행할 분석 스크립트

from collections import Counter
import json

def analyze_retrieval_diversity(log_dir):
    """각 테스트의 문서 다양성 분석"""

    results = []
    for log_file in glob(f"{log_dir}/*.json"):
        with open(log_file) as f:
            data = json.load(f)

        sources = data.get('citation', {}).get('sources', [])

        # 문서별 청크 수 계산
        doc_counts = Counter(s['source'] for s in sources)

        results.append({
            'test_id': data['test_id'],
            'total_chunks': len(sources),
            'unique_docs': len(doc_counts),
            'doc_distribution': dict(doc_counts),
            'max_chunks_from_single_doc': max(doc_counts.values()) if doc_counts else 0
        })

    return results

# 예상 결과:
# {
#   'test_id': 'benchmark_002',
#   'total_chunks': 5,
#   'unique_docs': 1,  # ← 문제!
#   'doc_distribution': {'lgd_display_news.pdf': 5},  # 전부 한 문서
#   'max_chunks_from_single_doc': 5
# }
```

### 원인 가설 및 검증

#### 가설 1: Reranking이 동일 문서 선호
```python
# 검증 방법: Reranking 전후 비교
# utils/reranker.py 로그 추가

def rerank_documents(self, query, docs):
    # BEFORE reranking
    before_docs = Counter(d.metadata['source'] for d in docs)
    print(f"[RERANK-BEFORE] Unique docs: {len(before_docs)}")

    # Reranking
    reranked = self._score_and_sort(query, docs)

    # AFTER reranking
    after_docs = Counter(d.metadata['source'] for d in reranked[:self.top_k])
    print(f"[RERANK-AFTER] Unique docs: {len(after_docs)}")
    print(f"[RERANK-AFTER] Distribution: {dict(after_docs)}")

    return reranked[:self.top_k]

# 예상: Reranking 후 다양성 감소
```

#### 가설 2: Small-to-Large가 동일 문서만 확장
```python
# 검증: context expansion 로직 확인
# utils/rag_chain.py

def _expand_context_small_to_large(self, initial_chunks):
    # 현재: 각 청크의 이전/이후 청크만 가져옴
    # 문제: 동일 문서 내 청크만 확장

    expanded = []
    for chunk in initial_chunks:
        # chunk의 source, chunk_id 사용
        # → 같은 문서의 인접 청크만 검색
        neighbors = self._get_neighbor_chunks(chunk)
        expanded.extend(neighbors)

    # 결과: 초기 5개 청크가 doc_A에서 왔으면
    #       확장된 청크도 전부 doc_A
```

#### 가설 3: Deduplication 미작동
```python
# 검증: citation.py 확인
# utils/citation.py

def deduplicate_sources(self, sources):
    seen = set()
    unique = []

    for s in sources:
        # 현재 로직: (source, page) 튜플로 중복 체크
        key = (s['source'], s.get('page'))

        if key not in seen:
            seen.add(key)
            unique.append(s)

    # 문제: 같은 문서, 다른 페이지 → 중복 아님으로 판정
    # 결과: 동일 문서 5개 청크 모두 통과
```

---

### 해결 방안 3가지 (우선순위 순)

#### Solution 1: Post-Reranking Diversity Penalty (Day 1-2)
**추천 이유**: 가장 빠르고 효과적, 기존 코드 최소 변경

```python
# utils/reranker.py 수정

def rerank_with_diversity(self, query: str, docs: List, top_k: int = 10):
    """
    Reranking with diversity penalty

    알고리즘:
    1. 모든 문서에 relevance score 계산
    2. Greedy selection with diversity penalty
       - 선택된 문서와 같은 source면 score * 0.5
    3. Top-K 반환
    """

    # 1. Score 계산
    scored_docs = []
    for doc in docs:
        score = self._calculate_relevance(query, doc)
        scored_docs.append({
            'doc': doc,
            'score': score,
            'source': doc.metadata.get('source', 'unknown')
        })

    # 2. Greedy selection with diversity
    selected = []
    selected_sources = Counter()

    # Score 내림차순 정렬
    scored_docs.sort(key=lambda x: x['score'], reverse=True)

    for item in scored_docs:
        if len(selected) >= top_k:
            break

        # Diversity penalty 적용
        source = item['source']
        penalty = 1.0

        # 이미 선택된 source라면 penalty
        if source in selected_sources:
            # 같은 문서에서 N개 선택되었으면 (N+1) * 0.3 페널티
            penalty = 1.0 - (selected_sources[source] * 0.3)
            penalty = max(penalty, 0.1)  # 최소 0.1

        adjusted_score = item['score'] * penalty

        # 재정렬을 위해 임시로 저장하지 않고,
        # Threshold 기반으로 즉시 선택
        if len(selected) < 3:
            # 처음 3개는 무조건 선택 (relevance 우선)
            selected.append(item)
            selected_sources[source] += 1
        elif adjusted_score > 0.5:  # Threshold
            selected.append(item)
            selected_sources[source] += 1

    # 3. 결과 반환
    print(f"[DIVERSITY] Selected from {len(selected_sources)} unique docs")
    print(f"[DIVERSITY] Distribution: {dict(selected_sources)}")

    return [item['doc'] for item in selected]


# 예상 효과:
# Before: {'doc_A': 5}
# After:  {'doc_A': 2, 'doc_B': 2, 'doc_C': 1}
```

**구현 단계**:
1. Day 1 오전: 코드 작성 (2시간)
2. Day 1 오후: 단위 테스트 (2시간)
3. Day 2 오전: Balanced 테스트 재실행 (1시간)
4. Day 2 오후: 결과 분석 + 파라미터 튜닝 (3시간)

**예상 효과**:
```
문서 적합성: 50.9 → 70-75점
  - unique_docs: 1.2 → 3.5개 평균
  - 다양성 비율: 20% → 70%

단점:
  - Relevance 약간 희생 (top score 문서 제외 가능)
  - 파라미터 튜닝 필요 (penalty 강도)
```

---

#### Solution 2: MMR (Maximal Marginal Relevance) (Day 2-3)
**추천 이유**: 검증된 알고리즘, 학술적 근거 있음

```python
# utils/retriever.py 또는 reranker.py 추가

def mmr_rerank(self, query_embedding, docs, top_k=10, lambda_param=0.5):
    """
    Maximal Marginal Relevance

    Score = λ * Relevance - (1-λ) * Similarity to selected

    Args:
        lambda_param: 0=diversity only, 1=relevance only
                     기본 0.5 (균형)
    """

    # 1. Query와의 유사도 계산
    query_emb = np.array(query_embedding)
    doc_embeddings = [self._get_embedding(d) for d in docs]

    relevance_scores = [
        cosine_similarity(query_emb, doc_emb)
        for doc_emb in doc_embeddings
    ]

    # 2. MMR 선택
    selected_indices = []
    selected_embeddings = []

    for _ in range(top_k):
        if not selected_indices:
            # 첫 문서: Relevance만 고려
            best_idx = np.argmax(relevance_scores)
        else:
            # MMR score 계산
            mmr_scores = []
            for i, doc_emb in enumerate(doc_embeddings):
                if i in selected_indices:
                    mmr_scores.append(-1)  # 이미 선택됨
                    continue

                # Relevance
                rel = relevance_scores[i]

                # Max similarity to selected documents
                max_sim = max(
                    cosine_similarity(doc_emb, sel_emb)
                    for sel_emb in selected_embeddings
                )

                # MMR
                mmr = lambda_param * rel - (1 - lambda_param) * max_sim
                mmr_scores.append(mmr)

            best_idx = np.argmax(mmr_scores)

        selected_indices.append(best_idx)
        selected_embeddings.append(doc_embeddings[best_idx])

    return [docs[i] for i in selected_indices]


# 예상 효과:
# - 문서 다양성 자동 보장
# - Relevance와 Diversity 균형 조절 가능
```

**구현 단계**:
1. Day 2 오전: Embedding 추출 로직 확인 (1시간)
2. Day 2 오후: MMR 구현 (3시간)
3. Day 3 오전: 통합 테스트 (2시간)
4. Day 3 오후: lambda 파라미터 최적화 (2시간)

**예상 효과**:
```
문서 적합성: 50.9 → 75-80점
  - unique_docs: 1.2 → 4.0개 평균
  - 다양성 비율: 20% → 80%

장점:
  - 검증된 알고리즘
  - 파라미터 튜닝 단순 (lambda 하나)

단점:
  - Embedding 연산 추가 (약간 느려짐)
  - 구현 복잡도 중간
```

---

#### Solution 3: Document-Level Top-K (Alternative)
**추천 이유**: 가장 단순, 빠른 프로토타입

```python
# utils/vector_store.py 수정

def search_with_document_diversity(self, query, k=10, min_docs=3):
    """
    문서 레벨 Top-K

    1. 많은 후보 검색 (k*3)
    2. 문서별로 그룹화
    3. 각 문서에서 best chunk 선택
    4. min_docs개 문서까지 수집
    """

    # 1. 후보 검색
    candidates = self.similarity_search(query, k=k*3)

    # 2. 문서별 그룹화
    doc_groups = {}
    for doc in candidates:
        source = doc.metadata['source']
        if source not in doc_groups:
            doc_groups[source] = []
        doc_groups[source].append(doc)

    # 3. 각 문서에서 Top-2 선택
    selected = []
    for source, chunks in sorted(
        doc_groups.items(),
        key=lambda x: len(x[1]),
        reverse=True
    ):
        # 각 문서에서 최대 2개 청크
        selected.extend(chunks[:2])

        if len(selected) >= k:
            break

    return selected[:k]


# 예상 효과:
# - unique_docs: 5개 (k=10이면)
# - 각 문서당 2개 청크 보장
```

**구현 단계**:
1. Day 1: 1시간 구현
2. Day 1: 1시간 테스트

**예상 효과**:
```
문서 적합성: 50.9 → 65-70점
  - unique_docs: 1.2 → 5.0개 (확정)
  - 다양성 비율: 20% → 100%

장점:
  - 구현 매우 단순
  - 빠름

단점:
  - 너무 기계적 (각 문서 동일 비중)
  - Relevance 크게 희생 가능
  - 유연성 낮음
```

---

### 최종 권장: **Solution 1 (Diversity Penalty) + Solution 2 (MMR) 순차 적용**

#### Day 1-2: Solution 1 구현 및 테스트
- 빠른 개선 효과 확인
- 70-75점 달성 예상

#### Day 3: Solution 2 (MMR) 추가 구현
- 더 나은 성능 (75-80점) 목표
- A/B 테스트로 비교

#### 의사결정 기준:
```python
if diversity_penalty_score >= 73:
    # Solution 1 채택, MMR은 추후 고려
else:
    # MMR 구현 계속
```

---

## 📋 Task 2: Multi-query 최적화 (Day 3-5)

### 현재 문제 진단

#### 실제 성능 데이터
```
Fallback mode:    평균 25초  (8-50초)
Multi-query mode: 평균 180초 (60-472초)

문제: 7배 시간 차이
```

#### 원인 분석
```python
# utils/rag_chain.py 분석 필요

def query(self, question):
    # 1. Classification
    classification = self.classifier.classify(question)

    # 2. Multi-query 여부 결정
    if classification['multi_query']:
        # 문제: 모든 Complex/Exhaustive 질문에 multi-query
        expanded = self._expand_queries(question)  # 3-5개 쿼리 생성

        results = []
        for q in expanded:
            # 문제: 각 쿼리마다 전체 파이프라인
            # - Embedding (0.3-0.5초 * N)
            # - Vector search (2-5초 * N)
            # - BM25 search (1-3초 * N)
            # - Reranking (5-10초 * N)
            results.extend(self._search(q))

        # 총 시간 = 단일 * N * 오버헤드
        # 예: 3개 쿼리 * 40초 * 1.5 = 180초
```

### 해결 방안

#### Solution 1: 조건부 Multi-query 활성화 (Day 3-4)

```python
# utils/question_classifier.py 수정

def classify(self, question):
    """
    질문 분류 개선

    Multi-query 활성화 조건 강화:
    1. Simple → Never
    2. Normal → Only if 비교/대조 키워드
    3. Complex → Only if 다각도 분석 필요
    4. Exhaustive → Always
    """

    # 기존 분류
    q_type = self._classify_type(question)

    # Multi-query 필요성 재판단
    multi_query_needed = False

    if q_type == 'simple':
        multi_query_needed = False

    elif q_type == 'normal':
        # 비교 키워드가 있을 때만
        comparison_keywords = ['차이', '비교', 'vs', '대조', '다른점']
        if any(kw in question for kw in comparison_keywords):
            multi_query_needed = True
        else:
            multi_query_needed = False  # ← 변경!

    elif q_type == 'complex':
        # 다각도 키워드가 있을 때만
        multi_angle_keywords = ['모든', '전체', '다양한', '여러', '종합']
        if any(kw in question for kw in multi_angle_keywords):
            multi_query_needed = True
        else:
            multi_query_needed = False  # ← 변경!

    elif q_type == 'exhaustive':
        multi_query_needed = True

    return {
        'type': q_type,
        'multi_query': multi_query_needed,
        # ...
    }


# 예상 효과:
# Multi-query 사용률: 60% → 20%
# 평균 응답 시간: 120초 → 50초
```

**구현 단계**:
1. Day 3 오후: 분류 로직 수정 (2시간)
2. Day 4 오전: 테스트 재실행 (1시간)
3. Day 4 오후: 결과 분석 (2시간)

**예상 효과**:
```
Before:
  - 70개 테스트 중 42개 (60%) Multi-query
  - 평균 120초

After:
  - 70개 테스트 중 14개 (20%) Multi-query
  - 평균: (56 * 25초 + 14 * 180초) / 70 = 55초

개선: 120초 → 55초 (54% 감소)
```

---

#### Solution 2: Embedding 배치 처리 (Day 4-5)

```python
# utils/embeddings.py 개선

class EmbeddingManager:
    def __init__(self):
        self.cache = {}

    def embed_batch(self, texts: List[str]):
        """
        배치 Embedding

        현재: 각 텍스트마다 API 호출
        개선: 한번에 배치 처리
        """

        # 캐시 확인
        uncached = [t for t in texts if t not in self.cache]

        if uncached:
            # 배치 API 호출
            embeddings = self.api_client.embed(uncached)

            for text, emb in zip(uncached, embeddings):
                self.cache[text] = emb

        return [self.cache[t] for t in texts]


# utils/rag_chain.py 수정

def _multi_query_search(self, expanded_queries):
    """
    Multi-query 검색 최적화
    """

    # Before: 각 쿼리마다 embedding
    # for q in expanded_queries:
    #     emb = self.embedder.embed(q)  # API 호출 * N
    #     results.append(self.search(emb))

    # After: 배치 embedding
    embeddings = self.embedder.embed_batch(expanded_queries)

    results = []
    for q, emb in zip(expanded_queries, embeddings):
        results.append(self.search(emb))

    return results


# 예상 효과:
# Embedding 시간: (0.5초 * 3) = 1.5초 → 0.8초 (배치)
# Multi-query 시간: 180초 → 150초 (17% 감소)
```

**구현 단계**:
1. Day 4 오후: Embedding 캐시/배치 구현 (3시간)
2. Day 5 오전: 통합 테스트 (2시간)
3. Day 5 오후: 성능 측정 (2시간)

**예상 효과**:
```
Multi-query 시간: 180초 → 150초
전체 평균: 55초 → 48초

추가 이득:
  - Embedding 캐시로 반복 질문 빠름
  - API 비용 절감
```

---

#### Solution 3: 타임아웃 설정 (Day 5)

```python
# utils/rag_chain.py 추가

def query(self, question, max_time=60):
    """
    타임아웃 설정

    60초 초과 시 Fallback으로 전환
    """

    start = time.time()

    try:
        # 기존 로직
        result = self._execute_query(question)

        elapsed = time.time() - start
        if elapsed > max_time:
            print(f"[WARN] Query took {elapsed}s, exceeds limit")

        return result

    except TimeoutError:
        # Fallback: Simple mode로 재시도
        print(f"[TIMEOUT] Falling back to simple mode")
        return self._simple_query(question)


# 예상 효과:
# - 극단적 케이스 (472초) 방지
# - 사용자 경험 개선
```

---

## 📊 통합 효과 분석

### Before (현재)
```
종합 점수: 73.1/100

문서 적합성:   50.9/100 ⚠️
  - unique_docs: 1.2개 평균
  - 단일 문서 의존: 90%

답변 완전성:   77.4/100 ✓
처리 명확성:   92.8/100 ✓✓
환각 방지:     76.6/100 ✓

평균 응답시간: 120초
  - Fallback: 25초
  - Multi-query: 180초
  - Multi-query 사용률: 60%
```

### After Week 1 (예상)
```
종합 점수: 85.0/100 (↑ 11.9점)

문서 적합성:   75.0/100 ✓  (↑ 24.1점)
  - unique_docs: 3.5개 평균
  - 다양성 비율: 70%
  - Solution 1 (Diversity Penalty) 효과

답변 완전성:   85.0/100 ✓  (↑ 7.6점)
  - 더 다양한 출처 → 더 풍부한 답변

처리 명확성:   95.0/100 ✓✓ (↑ 2.2점)
  - 로깅 개선

환각 방지:     80.0/100 ✓  (↑ 3.4점)
  - 다양한 출처 → 검증 강화

평균 응답시간: 40초 (↓ 67%)
  - Fallback: 25초 (변화 없음)
  - Multi-query: 150초 (↓ 17%)
  - Multi-query 사용률: 20% (↓ 67%)
```

### 세부 효과 분해

#### 문서 적합성 개선: 50.9 → 75.0 (+24.1점)
```
기여 요인:
  - Diversity Penalty: +18점 (핵심)
  - 다양한 문서로 답변 풍부: +4점
  - Relevance 약간 희생: -2점
  - 추가 튜닝 여지: +4점

검증 방법:
  - unique_docs 메트릭: 1.2 → 3.5
  - Deep Quality Assessment 재실행
```

#### 응답 시간 개선: 120초 → 40초 (-67%)
```
기여 요인:
  - Multi-query 사용 감소: -50초 (핵심)
  - Embedding 배치: -10초
  - 기타 최적화: -20초

검증 방법:
  - 테스트 70개 총 시간 측정
  - Phase별 평균 시간 비교
```

---

## 🎯 성공 지표 (KPI)

### Primary Metrics
1. **문서 적합성**: 50.9 → 75+ (목표 달성)
2. **평균 응답시간**: 120초 → 40초 (목표 달성)
3. **unique_docs**: 1.2 → 3.5+ (목표 달성)

### Secondary Metrics
4. **종합 점수**: 73.1 → 85+ (B등급 달성)
5. **답변 완전성**: 77.4 → 85+ (개선)
6. **Multi-query 사용률**: 60% → 20% (최적화)

### 검증 방법
```bash
# Week 1 완료 후 재테스트
python run_comprehensive_test_real.py \
  --test-cases test_cases_balanced.json \
  --config config_test.json \
  --output-dir test_logs_week1_validation

# Deep Quality Assessment
python deep_quality_assessment.py \
  --test-logs-dir test_logs_week1_validation \
  --output week1_validation_report.json

# 비교
python compare_reports.py \
  --before deep_quality_report_balanced.json \
  --after week1_validation_report.json
```

---

## ⚠️ 리스크 및 대응 방안

### Risk 1: Diversity Penalty가 Relevance를 과도하게 희생
**증상**: 문서 다양성은 증가하지만 답변 품질 저하
**대응**:
```python
# 파라미터 조정
penalty_strength = 0.3  # 기본
if answer_quality < 75:
    penalty_strength = 0.2  # 완화
```

### Risk 2: Multi-query 감소로 복잡한 질문 품질 저하
**증상**: Complex 질문의 답변 완전성 감소
**대응**:
```python
# 롤백 옵션
if complex_question_score < 80:
    # Multi-query 조건 완화
    multi_query_threshold = 0.6  # 기본 0.7에서 낮춤
```

### Risk 3: Embedding 배치 처리가 메모리 초과
**증상**: OOM 에러
**대응**:
```python
# 배치 크기 제한
max_batch_size = 10
batches = chunk_list(queries, max_batch_size)
```

---

## 📅 상세 일정

### Day 1 (월요일)
**오전 (4시간)**
- [x] 현재 로그 분석 스크립트 작성 (1시간)
- [ ] 실제 문제 원인 파악 (1시간)
- [ ] Diversity Penalty 코드 작성 (2시간)

**오후 (4시간)**
- [ ] 단위 테스트 작성 (1시간)
- [ ] 통합 테스트 (1시간)
- [ ] 파라미터 초기 튜닝 (2시간)

### Day 2 (화요일)
**오전 (4시간)**
- [ ] Balanced 테스트 재실행 (1시간)
- [ ] 결과 분석 (1시간)
- [ ] 문제점 수정 (2시간)

**오후 (4시간)**
- [ ] 파라미터 Fine-tuning (2시간)
- [ ] Comprehensive 테스트 재실행 (2시간)

### Day 3 (수요일)
**오전 (4시간)**
- [ ] Week 1 중간 점검
- [ ] Diversity 효과 검증 (2시간)
- [ ] Multi-query 분류 로직 수정 (2시간)

**오후 (4시간)**
- [ ] Multi-query 테스트 (2시간)
- [ ] 응답 시간 측정 (2시간)

### Day 4 (목요일)
**오전 (4시간)**
- [ ] Multi-query 결과 분석 (2시간)
- [ ] 조건 튜닝 (2시간)

**오후 (4시간)**
- [ ] Embedding 배치 처리 구현 (3시간)
- [ ] 단위 테스트 (1시간)

### Day 5 (금요일)
**오전 (4시간)**
- [ ] Embedding 통합 테스트 (2시간)
- [ ] 성능 측정 (2시간)

**오후 (4시간)**
- [ ] 전체 재테스트 (2시간)
- [ ] Week 1 결과 보고서 작성 (2시간)

---

## 📈 예상 ROI

### 투입 자원
```
개발 시간: 5일 (40시간)
테스트 시간: 계산 리소스 (약 3시간 * 5회)
리스크: 낮음 (기존 기능 유지, 점진적 개선)
```

### 예상 효과
```
정량적:
  - 문서 적합성: +24.1점 (48% 개선)
  - 응답 시간: -80초 (67% 개선)
  - 사용자 만족도: +30% (추정)

정성적:
  - RAG의 핵심 가치 회복 (Multi-document synthesis)
  - 사용자 경험 개선 (빠른 응답)
  - 시스템 신뢰도 증가
```

### ROI 계산
```
Before: 73.1/100, 120초
After:  85.0/100, 40초

품질 향상: 16% (73.1 → 85.0)
속도 향상: 67% (120초 → 40초)
투입 시간: 40시간

ROI = (품질향상 + 속도향상) / 투입시간
    = (16 + 67) / 40
    = 2.08% per hour

매우 높은 ROI!
```

---

## 🚀 시작 방법

### 즉시 실행 가능한 첫 단계
```bash
# 1. 현재 상태 백업
cp -r utils utils_backup_20251111

# 2. 분석 스크립트 실행
python analyze_retrieval_diversity.py \
  --logs test_logs_comprehensive_full

# 3. 결과 확인 후 구현 시작
# → diversity_penalty 브랜치 생성
git checkout -b feature/diversity-penalty
```

---

**질문**: 이 계획으로 진행하시겠습니까? 아니면 특정 부분을 먼저 검증해볼까요?
