# RAG 품질 개선 구현 계획서

**작성일**: 2025-10-29  
**목표**: 종합 테스트 점수 57점 → 80점 이상 달성

---

## 📋 개선 항목 및 우선순위

### 긴급 (1주 내) 🔴

1. **검색 관련성 개선 (음수 similarity score 해결)**
   - 현재 점수: 40/100
   - 목표 점수: 70/100
   - 예상 개선 효과: +30점

2. **구체적 정보 추출 개선**
   - 현재 점수: 50/100
   - 목표 점수: 75/100
   - 예상 개선 효과: +25점

### 중요 (1개월 내) 🟡

3. **엔티티 추출 기능 개선**
   - 현재 점수: 57.2% 신뢰도
   - 목표 점수: 70%+ 신뢰도
   - 예상 개선 효과: +15점

4. **요약 기능 개선**
   - 현재 점수: 50/100
   - 목표 점수: 70/100
   - 예상 개선 효과: +20점

5. **프롬프트 엔지니어링**
   - 현재 점수: 60/100
   - 목표 점수: 80/100
   - 예상 개선 효과: +20점

---

## 🔧 구현 세부사항

### 1. 검색 관련성 개선

#### 문제점
- 음수 similarity score 발생 (최대 -442.1%)
- 벡터 거리 → 유사도 변환 공식 부정확
- Reranker 점수 정규화 문제
- 하이브리드 검색 점수 통합 문제

#### 해결 방안

**1.1 Similarity Score 정규화 개선**
```python
# vector_store.py
def similarity_search_hybrid():
    # 기존: similarity = max(0.0, 2.0 - float(score))
    # 개선: 거리 기반 유사도 정규화 개선
    
    # 방법 1: Cosine Similarity 직접 계산
    # 방법 2: 거리 → 유사도 변환 공식 개선
    similarity = max(0.0, 1.0 / (1.0 + float(score)))  # 하이퍼볼릭 변환
    
    # 방법 3: 점수 분포 기반 정규화
    # 모든 점수를 [0, 1] 범위로 Min-Max 정규화
```

**1.2 Reranker 점수 정규화**
```python
# rag_chain.py
def _normalize_scores():
    # 기존 softmax 정규화 → Z-score 정규화 + Min-Max
    # 음수 값 제거 및 상대적 순위 유지
```

**1.3 하이브리드 검색 점수 통합**
```python
# vector_store.py
def similarity_search_hybrid():
    # 벡터 점수와 BM25 점수 정규화 후 통합
    # 가중치 동적 조정 (쿼리 유형별)
```

---

### 2. 구체적 정보 추출 개선

#### 문제점
- 구체적인 이름, 수치, 구조식 추출 실패
- Small-to-Large 전략 미활용
- 엔티티 기반 검색 미통합

#### 해결 방안

**2.1 Small-to-Large 검색 통합**
```python
# rag_chain.py
def _get_context():
    # 쿼리 타입 감지
    query_type = self._detect_query_type(question)
    
    if query_type == "specific_info":
        # 구체적 정보 추출 모드
        # 1. Small-to-Large 검색 사용
        stl_search = SmallToLargeSearch(self.vectorstore)
        results = stl_search.search_with_context_expansion(
            question, top_k=20, max_parents=5
        )
        # 2. top_k 증가 (10 → 20)
        # 3. 엔티티 기반 검색 추가
```

**2.2 구조 인식 청킹 활용**
```python
# document_processor.py
# PDF/PPTX 고급 청킹이 이미 구현되어 있음
# 이를 활용한 메타데이터 기반 검색 추가
```

**2.3 엔티티 기반 검색 강화**
```python
# rag_chain.py
def _search_with_entity_boost():
    # 엔티티 매칭 청크 우선순위 상승
    # 엔티티가 포함된 청크 자동 추가
```

---

### 3. 엔티티 추출 기능 개선

#### 문제점
- 엔티티 추출 실패율 높음
- 한국어 엔티티 추출 부족
- 엔티티 인덱스 활용 미흡

#### 해결 방안

**3.1 엔티티 추출 프롬프트 개선**
```python
# entity_extractor.py
# 한국어 프롬프트 추가
# 도메인 특화 엔티티 타입 추가
```

**3.2 정규식 Fallback 강화**
```python
# entity_extractor.py
# 화합물명, 수치, 측정값 패턴 확장
# 한국어 패턴 추가
 мног```

**3.3 엔티티 인덱스 활용**
```python
# vector_store.py
# 엔티티 기반 검색 API 추가
# 검색 시 엔티티 매칭 우선
```

---

### 4. 요약 기능 개선

#### 문제점
- 논문 전체 요약 불가능
- 문서 구조 인식 부족
- 계층적 요약 미구현

#### 해결 방안

**4.1 계층적 요약 전략**
```python
# rag_chain.py
def _summarize_document():
    # 1. 섹션별 요약
    # 2. 페이지별 요약
    # 3. 전체 통합 요약
```

**4.2 문서 구조 인식 요약**
```python
# rag_chain.py
def _structured_summary():
    # 제목, 본문, 결론 등 구조 기반 요약
    # 메타데이터 활용 (section_title, chunk_type)
```

---

### 5. 프롬프트 엔지니어링

#### 문제점
- 모든 질문에 동일한 프롬프트 사용
- "정보 없음" 응답이 너무 자주 발생
- 부분 답변 허용 전략 부족

#### 해결 방안

**5.1 질문 유형별 프롬프트**
```python
# rag_chain.py
def _get_prompt_template(query_type):
    templates = {
        "specific_info": "...",  # 구체적 정보 추출용
        "summary": "...",        # 요약용
        "comparison": "...",     # 비교 분석용
        "relationship": "...",   # 관계 분석용
    }
```

**5.2 부분 답변 전략**
```python
# rag_chain.py 프롬프트
"""
문서에서 정확한 정보를 찾지 못하더라도:
1. 관련된 부분 정보라도 제공
2. 추론 가능한 내용은 명시하며 제공
3. "정보 없음"은 최후의 수단으로만 사용
"""
```

---

## 📊 구현 순서

1. **1단계**: 검색 관련성 개선 (1-2일)
   - Similarity score 정규화
   - Reranker 점수 정규화
   - 하이브리드 검색 개선

2. **2단계**: 구체적 정보 추출 개선 (2-3일)
   - Small-to-Large 통합
   - 쿼리 타입 감지
   - 엔티티 기반 검색

3. **3단계**: 엔티티 추출 개선 (1-2일)
   - 프롬프트 개선
   - Fallback 강화
   - 인덱스 활용

4. **4단계**: 요약 기능 개선 (2일)
   - 계층적 요약
   - 구조 인식 요약

5. **5단계**: 프롬프트 엔지니어링 (1일)
   - 질문 유형별 프롬프트
   - 부분 답변 전략

---

## ✅ 검증 방법

각 단계마다:
1. 단위 테스트 작성
2. 종합 테스트 실행
3. 점수 비교 (이전 vs 이후)
4. 문제점 파악 및 개선

---

**예상 최종 점수**: 80-85/100


