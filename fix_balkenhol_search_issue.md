# Lennart Balkenhol 검색 실패 원인 및 해결방안

## 🔍 근본 원인

### 문제
사용자 질문: "Lennart Balkenhol 의 논문을 찾아서 요약좀 해줄래?"
- DB에는 "Balkenhol"이 포함된 문서가 6개 청크 존재
- 벡터 검색만 사용 시: Top-5에서 0개 발견 ✗
- 하이브리드 검색(0.5/0.5) 사용 시: Top-5에서 2개 발견 ✓

**하지만 RAG Chain 실행 시: 0개 발견 ✗**

### 원인 분석

#### 1. 검색 경로 우선순위

[utils/rag_chain.py:503](utils/rag_chain.py#L503) `_search_candidates` 메서드:

```python
def _search_candidates(self, question: str, search_mode: str = "integrated"):
    # 1순위: search_with_mode (듀얼 DB 기능)
    if hasattr(self.vectorstore, 'search_with_mode'):  # ← 이게 True
        hybrid = self.vectorstore.search_with_mode(
            query=question,
            search_mode=search_mode,
            initial_k=initial_k,
            top_k=initial_k,
            use_reranker=self.use_reranker,
            reranker_model=self.reranker_model
            # ⚠️ hybrid_bm25_weight 파라미터 누락!
        )
    # 2순위: HybridRetriever (BM25+Vector)
    elif self.enable_hybrid_search and self.hybrid_retriever:
        hybrid_results = self.hybrid_retriever.search(question, top_k=initial_k)
    # 3순위: similarity_search_hybrid
    else:
        hybrid = self.vectorstore.similarity_search_hybrid(
            question, initial_k=initial_k, top_k=initial_k
        )
```

**실제 실행된 경로**: 1순위 (`search_with_mode`)
**사용된 경로**: 2순위 (` HybridRetriever`) 또는 3순위여야 함

#### 2. search_with_mode의 문제점

[utils/vector_store.py:977](utils/vector_store.py#L977) `search_with_mode` 메서드:

```python
def search_with_mode(
    self,
    query: str,
    search_mode: str = "integrated",
    initial_k: int = 40,
    top_k: int = 10,
    use_reranker: bool = True,
    reranker_model: str = "multilingual-base",
    # ⚠️ hybrid_bm25_weight 파라미터 없음!
) -> List[tuple]:
```

이 메서드는:
- `hybrid_bm25_weight` 파라미터를 받지 않음
- 내부에서 하드코딩된 가중치를 사용하거나 순수 벡터 검색만 수행
- `config.json`의 `hybrid_bm25_weight: 0.5` 설정이 무시됨

#### 3. 실제 로그 분석

`test_balkenhol_simple.py` 실행 로그:

```
[SEARCH] 듀얼 DB 검색 모드: integrated, initial_k=30
[VectorStore] 공유 DB 비활성화 - 개인 DB만 검색
[Embeddings] ... (벡터 임베딩만 수행)
[Timing] candidate_retrieval (fallback): 4.14s (candidates=30)
[Timing] final_rerank (fallback): 2.18s
```

→ **하이브리드 검색이 아닌 순수 벡터 검색 수행!**
→ `[Hybrid-RRF]` 로그가 없음
→ BM25 검색이 전혀 수행되지 않음

#### 4. 직접 테스트 vs RAG Chain

**직접 테스트** (`test_hybrid_search_debug.py`):
```python
docs = vector_manager.similarity_search_hybrid(
    "Balkenhol",
    initial_k=20,
    vector_weight=0.5,
    keyword_weight=0.5,
    top_k=5
)
# 결과: Top-5에서 2개 발견 ✓
# 로그: [Hybrid-RRF] query='Balkenhol...' ✓
```

**RAG Chain**:
```python
result = rag_chain.query(question)
# 결과: Top-5에서 0개 발견 ✗
# 로그: [Hybrid-RRF] 없음 ✗
```

---

## ✅ 해결 방안

### 방안 1: search_with_mode에 hybrid_bm25_weight 전달 (권장)

#### Step 1: search_with_mode 시그니처 수정

[utils/vector_store.py:977](utils/vector_store.py#L977):

```python
def search_with_mode(
    self,
    query: str,
    search_mode: str = "integrated",
    initial_k: int = 40,
    top_k: int = 10,
    use_reranker: bool = True,
    reranker_model: str = "multilingual-base",
    hybrid_bm25_weight: float = 0.5,  # ← 추가
) -> List[tuple]:
```

#### Step 2: search_with_mode 내부에서 하이브리드 검색 사용

```python
def search_with_mode(..., hybrid_bm25_weight: float = 0.5):
    # 개인 DB 검색
    if search_mode in ["personal", "integrated"]:
        # ⚠️ 기존: similarity_search_with_score (벡터만)
        # ✓ 개선: similarity_search_hybrid (BM25+벡터)
        personal_results = self.similarity_search_hybrid(
            query,
            initial_k=initial_k,
            vector_weight=1 - hybrid_bm25_weight,
            keyword_weight=hybrid_bm25_weight,
            top_k=top_k
        )
```

#### Step 3: RAG Chain에서 파라미터 전달

[utils/rag_chain.py:516](utils/rag_chain.py#L516):

```python
hybrid = self.vectorstore.search_with_mode(
    query=question,
    search_mode=search_mode,
    initial_k=initial_k,
    top_k=initial_k,
    use_reranker=self.use_reranker,
    reranker_model=self.reranker_model,
    hybrid_bm25_weight=self.hybrid_bm25_weight  # ← 추가
)
```

### 방안 2: HybridRetriever 우선 사용 (간단)

[utils/rag_chain.py:503](utils/rag_chain.py#L503):

```python
def _search_candidates(self, question: str, search_mode: str = "integrated"):
    # 순서 변경: HybridRetriever를 먼저 확인
    if self.enable_hybrid_search and self.hybrid_retriever:
        # HybridRetriever 사용 (BM25+Vector)
        hybrid_results = self.hybrid_retriever.search(question, top_k=initial_k)
        ...
    elif hasattr(self.vectorstore, 'search_with_mode'):
        # 듀얼 DB 모드
        hybrid = self.vectorstore.search_with_mode(...)
    else:
        # 폴백
        hybrid = self.vectorstore.similarity_search_hybrid(...)
```

**장점**: 코드 수정 최소화, 즉시 적용 가능
**단점**: 듀얼 DB 기능(공유 DB vs 개인 DB) 사용 불가

### 방안 3: search_with_mode를 하이브리드 검색으로 교체

[utils/vector_store.py:977](utils/vector_store.py#L977) `search_with_mode` 내부:

```python
def search_with_mode(self, query, ...):
    # 개인 DB 검색
    if search_mode in ["personal", "integrated"]:
        # 기존 코드
        personal_results = self.similarity_search_with_score(query, k=initial_k)

        # ↓ 변경
        personal_results = self.similarity_search_hybrid(
            query,
            initial_k=initial_k,
            vector_weight=0.5,  # 또는 self.hybrid_bm25_weight
            keyword_weight=0.5,
            top_k=initial_k
        )
```

---

## 📊 예상 효과

| 방안 | 수정 범위 | 효과 | 듀얼 DB 유지 |
|-----|---------|------|-------------|
| **방안 1** (권장) | 중간 | ✓✓✓ 완전한 해결 | ✓ |
| **방안 2** | 최소 | ✓✓ 즉시 해결 | ✗ |
| **방안 3** | 최소 | ✓✓ 해결 | ✓ |

**권장**: 방안 1 (완전한 해결 + 듀얼 DB 유지)
**빠른 적용**: 방안 2 (5분 내 적용 가능)

---

## 🧪 검증 계획

### 1. 수정 후 테스트

```bash
python test_hybrid_search_debug.py
```

**기대 결과**:
- 하이브리드 검색 0.5/0.5: Top-5에서 2개 발견 ✓
- 하이브리드 검색 0.8/0.2: Top-5에서 3+ 개 발견 ✓
- 순수 키워드 1.0: Top-5에서 모두 Balkenhol 포함 ✓

### 2. RAG Chain 통합 테스트

```bash
python test_balkenhol_simple.py
```

**기대 로그**:
```
[SEARCH] [Phase 4] Hybrid Search (BM25+Vector) 사용
[Hybrid-RRF] query='Balkenhol...' candidates={'vector': 20, 'bm25': 7130}, top_k=5
```

**기대 결과**:
- 검색된 문서: 2-3개 중 "Balkenhol" 포함 ✓
- 답변: "OLÉ - Online Learning Emulation in Cosmology 논문 요약..." ✓

---

## ⚠️ 주의사항

1. **RRF 가중치 문제**: 현재 하이브리드 검색이 RRF(Reciprocal Rank Fusion)를 사용하는데, RRF는 **가중치와 무관하게 순위만으로 결합**합니다.
   - `vector_weight`, `keyword_weight` 파라미터가 있지만 실제로는 무시됨
   - 이 문제는 별도로 수정 필요 (우선순위 낮음)

2. **config.json vs 코드**: `config.json`의 `hybrid_bm25_weight: 0.5`를 읽어서 사용하도록 해야 합니다.

3. **backward compatibility**: 기존 코드가 `search_with_mode`를 `hybrid_bm25_weight` 없이 호출하는 경우를 대비해 기본값 설정 필요

---

*분석 완료: 2025-01-08*
