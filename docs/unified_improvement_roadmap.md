# RAG 시스템 통합 성능 개선 로드맵 (Qwen3 통합)

**작성일**: 2025-11-07
**버전**: v4.0 Unified Roadmap
**목표**: NotebookLM 수준 달성 + Qwen3-Embedding-8B 통합
**예상 완료**: 2-3주

---

## 📊 Executive Summary

### 현재 상태 (v3.1 + Phase A-2)
- **Embedding Model**: mxbai-embed-large (1024D, ~335M params)
- **Reranker Model**: multilingual-e5-small (기존 유지)
- **Citation Rate**: 80% (Phase A-2 구현 완료)
- **Average Response Time**: 91.1초
- **Cross-domain Pollution**: 4.5%

### 최종 목표 (v4.0)
- **Embedding Model**: Qwen3-Embedding-8B (최대 4096D, 8B params)
- **Reranker Model**: multilingual-e5-small (변경 없음)
- **Citation Rate**: 95% (NotebookLM 수준)
- **Average Response Time**: 60-70초 (25-30% 감소)
- **Cross-domain Pollution**: 0%

### 예상 성능 향상 (누적)
| 단계 | 정확도 향상 | 속도 개선 | Citation Rate | 주요 개선 사항 |
|------|-------------|-----------|---------------|----------------|
| **Phase A-3** | +5-8% | -10-15초 | 80% | Answer Verification 강화 |
| **Phase B-1** | +10-15% | -5초 | 80% | Qwen3 기본 통합 (2048D) |
| **Phase B-2** | +5-10% | -8-10초 | 80% | Matryoshka 최적화 |
| **Phase B-3** | +3-5% | -2초 | 80% | Instruction-aware Embedding |
| **Phase C** | +5-8% | +3초 | 95% | Citation 최적화 |
| **총합** | **+28-46%** | **-22-30초** | **95%** | **NotebookLM 수준 달성** |

---

## 🎯 Phase A-3: Answer Verification 개선 (우선순위 1)

### 목표
- 재생성 빈도 50% 감소 (20% → 10%)
- 응답 시간 10-15초 단축
- LLM 호출 비용 감소

### 현재 문제
```
Query: "kFRET 값은?"
1차 답변: "정보를 찾을 수 없습니다" (금지 구문)
→ 검증 실패
→ 2차 재생성 (+10-15초)
→ 성공

재생성 빈도: ~20% (5개 중 1개)
```

### 구현 내용

#### 1. Prompt Engineering 강화 (30분)

**파일**: `utils/rag_chain.py`
**라인**: ~120-180 (base_prompt_template)

**변경 사항**:
```python
# Before (현재)
⚠️ 중요 규칙:
1. 문서 우선 원칙
2. 일반 지식 금지
3. 정보 없음 금지

# After (개선)
⚠️ 핵심 규칙 (반드시 준수):

1. **금지 표현** (절대 사용 금지):
   ❌ "정보를 찾을 수 없습니다"
   ❌ "문서에 없습니다"
   ❌ "확인할 수 없습니다"

2. **권장 표현** (대신 사용):
   ✅ "제공된 문서에 따르면, [구체적 정보]..."
   ✅ "문서 #1의 5페이지에서 [내용]을 확인할 수 있습니다"
   ✅ "직접적인 수치는 명시되어 있지 않지만, 관련 정보로는 [내용]이 있습니다"

3. **NotebookLM 스타일 답변 예시**:
   "According to the provided document (HF_OLED.pptx, slide 5), the kFRET value is approximately 87.8%."
```

**예상 효과**:
- 재생성 빈도: 20% → 15% (-25%)
- 응답 시간: -4-6초

#### 2. Self-Consistency Check (2일)

**새 메서드**: `_generate_with_self_consistency()`

**핵심 로직**:
```python
def _generate_with_self_consistency(self, question: str, context: str, n: int = 3):
    """여러 번 생성 후 일관성 검증"""

    # 1. N번 독립적으로 답변 생성 (temperature=0.5)
    answers = []
    for i in range(n):
        answer = self._generate_answer_internal(question, context)
        answers.append(answer)

    # 2. 답변 간 일관성 점수 계산 (Jaccard similarity)
    consistency_score = self._calculate_answer_consistency(answers)

    # 3. 일관성에 따라 처리
    if consistency_score > 0.8:
        # 높은 일관성 → 가장 상세한 답변 선택
        return max(answers, key=lambda a: len(a))
    elif consistency_score > 0.5:
        # 중간 일관성 → 공통 정보 추출
        return self._extract_common_info(answers)
    else:
        # 낮은 일관성 → 경고 표시
        return f"⚠️ 낮은 신뢰도 (일관성: {consistency_score:.1%})\n{answers[0]}"
```

**예상 효과**:
- 재생성 빈도: 15% → 10% (-33%)
- 응답 시간: -6-9초 (검증 실패 시 재생성 횟수 감소)
- 답변 신뢰도: +15-20%

### Phase A-3 총 예상 성과

| 지표 | Before (A-2) | After (A-3) | 개선 |
|------|--------------|-------------|------|
| 재생성 빈도 | 20% | 10% | -50% |
| 응답 시간 | 91.1초 | 76-81초 | -10-15초 |
| 정확도 | 기준치 | +5-8% | +5-8% |
| LLM 호출 비용 | 기준치 | -10% | -10% |

**구현 우선순위**: ★★★★★ (즉시 착수)
**예상 구현 기간**: 2-3일
**리스크**: 낮음 (기존 시스템 유지)

---

## 🚀 Phase B-1: Qwen3-Embedding-8B 기본 통합 (우선순위 2)

### 목표
- 고성능 임베딩 모델로 교체
- 검색 정확도 대폭 향상
- 한국어/영어 혼합 문서 처리 개선

### Qwen3-Embedding-8B 특징

| 특성 | mxbai-embed-large | Qwen3-Embedding-8B | 개선 |
|------|-------------------|---------------------|------|
| **모델 크기** | ~335M params | 8B params | +24배 |
| **임베딩 차원** | 1024D (고정) | 1024D/2048D/4096D (가변) | 유연성 |
| **MTEB 점수** | ~56 | 70.58 | +26% |
| **다국어 지원** | 100+ languages | 100+ languages | 동일 |
| **특수 기능** | - | Matryoshka, Instruction-aware | 고급 |
| **VRAM 요구량** | ~2GB | ~16GB | - |

### 구현 내용

#### 1. VectorStore 수정 (1일)

**파일**: `utils/vector_store.py`

**변경 사항**:
```python
# Before
def __init__(self, embedding_model="mxbai-embed-large:latest"):
    self.embedding_model = embedding_model
    self.embedding_dimension = 1024  # 고정

# After
def __init__(self,
             embedding_model="qwen3-embedding-8b:latest",
             embedding_dimension=2048):  # 가변 (기본 2048D)

    self.embedding_model = embedding_model
    self.embedding_dimension = embedding_dimension

    # Qwen3 전용 설정 검증
    if "qwen3" in embedding_model.lower():
        assert embedding_dimension in [1024, 2048, 4096], \
            "Qwen3는 1024, 2048, 4096 차원만 지원합니다"
        print(f"[VectorStore] Qwen3-Embedding-8B 사용 (차원: {embedding_dimension}D)")
```

#### 2. ChromaDB 재구축 (4-6시간)

**필수 작업**:
1. 기존 ChromaDB 백업
2. 새 컬렉션 생성 (2048D 차원)
3. 전체 문서 재임베딩
4. 인덱스 재구축

**스크립트**: `scripts/migrate_to_qwen3.py`
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ChromaDB를 Qwen3-Embedding-8B로 마이그레이션"""

import os
from utils.vector_store import VectorStoreManager

def migrate_to_qwen3():
    """기존 문서를 Qwen3로 재임베딩"""

    # 1. 기존 DB 백업
    print("1. 기존 ChromaDB 백업 중...")
    os.system("cp -r ./chromadb ./chromadb_backup_mxbai")

    # 2. 기존 문서 목록 가져오기
    print("2. 기존 문서 목록 가져오는 중...")
    old_vectorstore = VectorStoreManager(
        embedding_model="mxbai-embed-large:latest",
        embedding_dimension=1024
    )
    existing_docs = old_vectorstore.get_all_documents()

    # 3. 새 VectorStore 초기화 (Qwen3)
    print("3. Qwen3 VectorStore 초기화 중...")
    new_vectorstore = VectorStoreManager(
        embedding_model="qwen3-embedding-8b:latest",
        embedding_dimension=2048,  # 균형 잡힌 차원
        persist_directory="./chromadb_qwen3"
    )

    # 4. 문서 재임베딩 및 추가
    print(f"4. {len(existing_docs)}개 문서 재임베딩 중...")
    for i, doc in enumerate(existing_docs):
        new_vectorstore.add_documents([doc])
        if (i+1) % 10 == 0:
            print(f"   진행: {i+1}/{len(existing_docs)} ({(i+1)/len(existing_docs)*100:.1f}%)")

    # 5. 기존 DB 교체
    print("5. 기존 ChromaDB 교체 중...")
    os.system("rm -rf ./chromadb")
    os.system("mv ./chromadb_qwen3 ./chromadb")

    print("✅ Qwen3 마이그레이션 완료!")

if __name__ == "__main__":
    migrate_to_qwen3()
```

#### 3. 차원 선택 전략 (30분)

**초기 권장**: 2048D (균형)

| 차원 | 정확도 | 속도 | VRAM | 추천 용도 |
|------|--------|------|------|-----------|
| 1024D | 보통 | 빠름 | 낮음 | 빠른 검색 우선 |
| 2048D | 높음 | 보통 | 중간 | **균형 잡힌 선택 (권장)** |
| 4096D | 최고 | 느림 | 높음 | 정확도 최우선 |

**테스트 후 조정**:
- 정확도 우선 → 4096D
- 속도 우선 → 1024D

### Phase B-1 예상 성과

| 지표 | Before (A-3) | After (B-1) | 개선 |
|------|--------------|-------------|------|
| 검색 정확도 | 기준치 | +10-15% | +10-15% |
| MTEB 점수 | ~56 | ~70.58 | +26% |
| 응답 시간 | 76-81초 | 71-76초 | -5초 |
| 한국어 처리 | 보통 | 우수 | +20% |
| 다중 도메인 검색 | 보통 | 우수 | +15% |

**구현 우선순위**: ★★★★☆ (Phase A-3 이후)
**예상 구현 기간**: 2일 (코드 수정) + 4-6시간 (재임베딩)
**리스크**: 중간 (VRAM 16GB 필요, 재임베딩 시간)

---

## ⚡ Phase B-2: Matryoshka 차원 최적화 (우선순위 3)

### 목표
- 다단계 검색으로 속도 30-50% 향상
- 정확도 유지 또는 소폭 향상
- 리소스 효율성 극대화

### Matryoshka Representation Learning (MRL) 원리

```
기존 방식 (Single-dimension):
Query → 2048D 임베딩 → 전체 DB 검색 (느림)

Matryoshka 방식 (Multi-stage):
Query → 1024D (빠른 필터링, 100개 후보)
      → 2048D (중간 Re-ranking, 20개 후보)
      → 4096D (정밀 최종 선택, 5개 결과)

결과: 속도 30-50% 향상, 정확도 유지
```

### 구현 내용

#### 1. HybridRetriever 확장 (2일)

**파일**: `utils/hybrid_retriever.py`

**새 메서드**: `hierarchical_search()`

```python
class HybridRetriever:
    """하이브리드 검색기 (Matryoshka 지원)"""

    def __init__(self, vectorstore, enable_matryoshka=False):
        self.vectorstore = vectorstore
        self.enable_matryoshka = enable_matryoshka

    def hierarchical_search(self, query: str, final_k: int = 5) -> List[Document]:
        """계층적 검색 (Matryoshka)

        3단계 검색:
        1. 1024D: 빠른 필터링 (k=100)
        2. 2048D: 중간 Re-ranking (k=20)
        3. 4096D: 정밀 최종 선택 (k=5)
        """

        if not self.enable_matryoshka:
            # 기존 방식: 단일 차원 검색
            return self.search(query, top_k=final_k)

        print("  [SEARCH] Matryoshka 계층적 검색 시작")

        # Stage 1: 빠른 필터링 (1024D)
        print("    [Stage 1] 1024D 검색 (k=100)")
        query_emb_1024 = self._embed_query(query, dimension=1024)
        candidates_100 = self.vectorstore.similarity_search_by_vector(
            query_emb_1024, k=100
        )
        print(f"    [OK] 100개 후보 추출 (0.5-1초)")

        # Stage 2: 중간 Re-ranking (2048D)
        print("    [Stage 2] 2048D Re-ranking (k=20)")
        query_emb_2048 = self._embed_query(query, dimension=2048)
        scores_2048 = [
            self._cosine_similarity(query_emb_2048, self._embed_doc(doc, 2048))
            for doc in candidates_100
        ]
        candidates_20 = self._top_k_by_score(candidates_100, scores_2048, k=20)
        print(f"    [OK] 20개 후보 추출 (2-3초)")

        # Stage 3: 정밀 최종 선택 (4096D)
        print("    [Stage 3] 4096D 정밀 검색 (k={final_k})")
        query_emb_4096 = self._embed_query(query, dimension=4096)
        scores_4096 = [
            self._cosine_similarity(query_emb_4096, self._embed_doc(doc, 4096))
            for doc in candidates_20
        ]
        final_results = self._top_k_by_score(candidates_20, scores_4096, k=final_k)
        print(f"    [OK] {final_k}개 최종 결과 (1-2초)")

        return final_results

    def _embed_query(self, text: str, dimension: int) -> np.ndarray:
        """쿼리 임베딩 (차원 지정)"""
        # Qwen3 Ollama API 호출 시 dimension 파라미터 전달
        response = ollama.embeddings(
            model=self.embedding_model,
            prompt=text,
            options={"dimension": dimension}
        )
        return np.array(response['embedding'])
```

#### 2. 차원별 캐싱 전략 (1일)

**최적화 포인트**:
- 1024D 임베딩 → 캐시 (메모리 효율)
- 2048D/4096D → 온디맨드 계산

### Phase B-2 예상 성과

| 지표 | Before (B-1) | After (B-2) | 개선 |
|------|--------------|-------------|------|
| 검색 속도 | 15-20초 | 8-12초 | -30-50% |
| 정확도 | 기준치 | +5-10% | +5-10% |
| 메모리 사용량 | 100% | 70% | -30% |
| CPU/GPU 효율 | 보통 | 높음 | +40% |

**구현 우선순위**: ★★★★☆ (Phase B-1 이후)
**예상 구현 기간**: 3일
**리스크**: 중간 (Ollama dimension 파라미터 지원 여부 확인 필요)

---

## 🎓 Phase B-3: Instruction-Aware Embedding (우선순위 4)

### 목표
- 태스크별 최적화로 정확도 1-5% 추가 향상
- 검색/문서 임베딩 구분으로 검색 품질 개선

### Instruction-Aware Embedding 원리

```
기존 방식:
Query: "TADF란 무엇인가?"
→ Embedding(query) vs Embedding(document)

Instruction-Aware:
Query: "Represent this query for retrieving relevant documents: TADF란 무엇인가?"
→ Embedding(instructed_query) vs Embedding(instructed_document)

효과: 검색 의도 명확화, +1-5% 정확도
```

### 구현 내용

#### 1. Instruction Template 정의 (30분)

**파일**: `utils/vector_store.py`

```python
class VectorStoreManager:
    """VectorStore 관리자 (Instruction-aware)"""

    # Instruction Templates (Qwen3 공식 권장)
    INSTRUCTION_TEMPLATES = {
        "retrieval_query": "Represent this query for retrieving relevant documents: ",
        "retrieval_document": "Represent this document for retrieval: ",
        "similarity_query": "Represent this sentence for measuring similarity: ",
        "classification": "Classify this document: "
    }

    def embed_with_instruction(self, text: str, task: str = "retrieval_query") -> np.ndarray:
        """Instruction-aware 임베딩

        Args:
            text: 임베딩할 텍스트
            task: 태스크 타입 (retrieval_query, retrieval_document 등)
        """
        instruction = self.INSTRUCTION_TEMPLATES.get(task, "")
        instructed_text = f"{instruction}{text}"

        return self._embed_text(instructed_text)
```

#### 2. RAGChain 통합 (1일)

**파일**: `utils/rag_chain.py`

**수정 위치**:
- `query()` 메서드: 쿼리 임베딩 시 "retrieval_query" 지시문
- `add_documents()` 메서드: 문서 임베딩 시 "retrieval_document" 지시문
- `_find_best_source_for_sentence()`: Citation 시 "similarity_query" 지시문

```python
# Query 임베딩
query_embedding = self.vectorstore.embed_with_instruction(
    question,
    task="retrieval_query"
)

# 문서 임베딩 (인덱싱 시)
doc_embedding = self.vectorstore.embed_with_instruction(
    document.page_content,
    task="retrieval_document"
)

# Citation 문장 매칭
sentence_embedding = self.vectorstore.embed_with_instruction(
    sentence,
    task="similarity_query"
)
```

### Phase B-3 예상 성과

| 지표 | Before (B-2) | After (B-3) | 개선 |
|------|--------------|-------------|------|
| 검색 정확도 | 기준치 | +3-5% | +3-5% |
| Citation 정확도 | 80% | 85-88% | +5-8% |
| 응답 시간 | 8-12초 | 6-10초 | -2초 |
| False Positive | 기준치 | -10-15% | -10-15% |

**구현 우선순위**: ★★★☆☆ (Phase B-2 이후)
**예상 구현 기간**: 1.5일
**리스크**: 낮음 (기존 시스템 확장)

---

## 🎯 Phase C: Citation Rate 최적화 (우선순위 5)

### 목표
- Citation Rate 80% → 95% (NotebookLM 수준)
- 모든 관련 문장에 정확한 출처 표시

### 현재 상태 (Phase A-2)
```
Query: "TADF란 무엇인가?"
답변: 4문장
Citation: 4/5 출처 (80%)

문제점:
- 1개 출처 누락
- 짧은 문장 (<15자) Skip
- 임계값 0.4 제약
```

### 구현 내용

#### 1. 임계값 최적화 (1일)

**파일**: `utils/rag_chain.py`
**메서드**: `_find_best_source_for_sentence()`

```python
# Before
SIMILARITY_THRESHOLD = 0.4  # 고정

# After
def _get_adaptive_threshold(self, sentence: str, sources: List[Document]) -> float:
    """문장 길이와 출처 개수에 따라 임계값 조정"""

    # 기본 임계값
    base_threshold = 0.35  # 0.4 → 0.35 (더 관대)

    # 문장 길이에 따라 조정
    if len(sentence) < 20:
        # 짧은 문장: 더 관대하게
        return base_threshold - 0.05  # 0.30
    elif len(sentence) > 50:
        # 긴 문장: 더 엄격하게
        return base_threshold + 0.05  # 0.40

    return base_threshold
```

**예상 효과**: 80% → 88-90% (+8-10%)

#### 2. 문장 분리 개선 (1일)

**현재 문제**:
```python
# 현재: 정규식 기반 분리
sentences = re.split(r'([.!?])\s+', text)

문제:
- "Dr.", "Mr." 등 예외 처리 부족
- 한국어 복문 처리 미흡
- 접속사 처리 불완전
```

**개선안**: KSS (Korean Sentence Splitter) 라이브러리 사용

```python
import kss

def _split_sentences(self, text: str) -> List[str]:
    """한국어 특화 문장 분리 (KSS)"""

    # KSS 사용 (한국어 특화)
    sentences = kss.split_sentences(text)

    # 너무 짧은 문장 병합 (접속사, 전환어 등)
    merged = []
    temp = ""
    for sent in sentences:
        if len(sent) < 10:
            temp += " " + sent
        else:
            if temp:
                merged.append(temp + " " + sent)
                temp = ""
            else:
                merged.append(sent)

    return merged
```

**예상 효과**: 88-90% → 92-93% (+3-4%)

#### 3. Multi-Source Citation (1일)

**아이디어**: 한 문장에 여러 출처 허용

```python
# Before
"TADF는 삼중항을 활용합니다. [문서1, p.5]"

# After (Multi-Source)
"TADF는 삼중항을 활용하며[문서1, p.5], 높은 효율을 보입니다[문서2, p.12]."
```

**구현**:
```python
def _find_all_relevant_sources(self, sentence: str, sources: List[Document]) -> List[Document]:
    """문장과 관련된 모든 출처 찾기 (임계값 이상)"""

    sentence_embedding = self._embed_text(sentence)
    relevant_sources = []

    for source in sources:
        source_embedding = self._embed_text(source.page_content[:500])
        similarity = self._cosine_similarity(sentence_embedding, source_embedding)

        # 임계값 이상이면 모두 추가
        if similarity > self._get_adaptive_threshold(sentence, sources):
            relevant_sources.append((source, similarity))

    # 유사도 순 정렬
    relevant_sources.sort(key=lambda x: x[1], reverse=True)

    # 최대 2개까지 (과도한 Citation 방지)
    return [src for src, _ in relevant_sources[:2]]
```

**예상 효과**: 92-93% → 95% (+2-3%)

### Phase C 예상 성과

| 지표 | Before (B-3) | After (C) | 개선 |
|------|--------------|-------------|------|
| Citation Rate | 80% | 95% | +15% |
| 정확도 | 기준치 | +5-8% | +5-8% |
| 사용자 신뢰도 | - | - | +25-30% |
| 응답 시간 | 6-10초 | 9-13초 | +3초 (Citation 계산) |

**구현 우선순위**: ★★★★☆ (Phase B-3 이후, 또는 A-3 직후)
**예상 구현 기간**: 3일
**리스크**: 낮음 (A-2 확장)

---

## 📊 통합 성능 예상치

### 누적 개선 효과

| Phase | 정확도 | 속도 (응답 시간) | Citation Rate | 누적 정확도 | 누적 시간 |
|-------|--------|------------------|---------------|-------------|-----------|
| **Baseline (v3.1)** | 0% | 91.1초 | 57.8% | 0% | 91.1초 |
| **+ A-2 (완료)** | - | 91.1초 | 80.0% | 0% | 91.1초 |
| **+ A-3** | +5-8% | -10-15초 | 80% | +5-8% | 76-81초 |
| **+ B-1 (Qwen3)** | +10-15% | -5초 | 80% | +15-23% | 71-76초 |
| **+ B-2 (Matryoshka)** | +5-10% | -8-10초 | 80% | +20-33% | 61-68초 |
| **+ B-3 (Instruction)** | +3-5% | -2초 | 85-88% | +23-38% | 59-66초 |
| **+ C (Citation)** | +5-8% | +3초 | 95% | +28-46% | 62-69초 |

### 최종 목표 달성 (v4.0)

| 지표 | v3.1 Baseline | v4.0 Final | 개선 |
|------|---------------|------------|------|
| **전체 정확도** | 기준치 | +28-46% | +28-46% |
| **응답 시간** | 91.1초 | 62-69초 | -22-29초 (-24-32%) |
| **Citation Rate** | 57.8% | 95% | +37.2%p |
| **재생성 빈도** | 20% | 10% | -50% |
| **크로스 도메인 오염** | 4.5% | 0% | -100% |
| **MTEB 점수** | ~56 | ~70.58 | +26% |
| **사용자 신뢰도** | - | - | +40-50% |

### 단계별 우선순위 (권장 순서)

```
1. Phase A-3 (Answer Verification)
   └─> 즉시 효과, 리스크 낮음

2. Phase B-1 (Qwen3 통합)
   └─> 가장 큰 성능 향상, VRAM 16GB 필요

3. Phase B-2 (Matryoshka 최적화)
   └─> 속도 대폭 향상, B-1 선행 필수

4. Phase B-3 (Instruction-Aware)
   └─> 추가 정확도 개선, B-1 선행 필수

5. Phase C (Citation 최적화)
   └─> NotebookLM 수준 달성, 독립 실행 가능
```

**대안 우선순위** (Citation 우선 시):
```
1. Phase A-3
2. Phase C (Citation 최적화)
3. Phase B-1 (Qwen3)
4. Phase B-2, B-3
```

---

## 🛠️ 구현 가이드

### Phase A-3 구현 단계

**Day 1-2: Prompt Engineering + Self-Consistency**
1. `utils/rag_chain.py` Prompt 수정 (30분)
2. `_generate_with_self_consistency()` 구현 (4시간)
3. `_calculate_answer_consistency()` 구현 (2시간)
4. 통합 테스트 (2시간)

**Day 3: 테스트 및 검증**
1. 45개 쿼리 재테스트
2. 재생성 빈도 측정
3. 성능 보고서 작성

### Phase B-1 구현 단계

**Day 1: Qwen3 다운로드 및 설정**
```bash
# Ollama에 Qwen3 모델 pull
ollama pull qwen3-embedding-8b:latest

# 모델 확인
ollama list | grep qwen3
```

**Day 2-3: 코드 수정**
1. `utils/vector_store.py` 수정 (2시간)
2. `scripts/migrate_to_qwen3.py` 작성 (2시간)
3. ChromaDB 마이그레이션 실행 (4-6시간)
4. 통합 테스트 (2시간)

**Day 4: 성능 비교**
1. mxbai vs Qwen3 비교 테스트
2. MTEB 점수 검증
3. 차원 조정 (1024D/2048D/4096D 비교)

### Phase B-2 구현 단계

**Day 1-2: Hierarchical Search 구현**
1. `utils/hybrid_retriever.py` 확장 (4시간)
2. `hierarchical_search()` 메서드 (4시간)
3. 캐싱 전략 구현 (2시간)

**Day 3: 최적화 및 테스트**
1. 속도 벤치마크
2. 정확도 검증
3. 하이퍼파라미터 튜닝 (k=100/20/5 조정)

### Phase B-3 구현 단계

**Day 1: Instruction Template**
1. `utils/vector_store.py` 확장 (2시간)
2. `embed_with_instruction()` 구현 (2시간)

**Day 2: RAGChain 통합**
1. Query 임베딩 수정 (1시간)
2. Document 임베딩 수정 (1시간)
3. Citation 임베딩 수정 (1시간)
4. 통합 테스트 (3시간)

### Phase C 구현 단계

**Day 1: 임계값 최적화**
1. `_get_adaptive_threshold()` 구현 (2시간)
2. 파라미터 튜닝 (2시간)

**Day 2: 문장 분리 개선**
1. KSS 라이브러리 설치 (`pip install kss`)
2. `_split_sentences()` 재구현 (3시간)

**Day 3: Multi-Source Citation**
1. `_find_all_relevant_sources()` 구현 (3시간)
2. Citation 포맷 개선 (2시간)
3. 최종 테스트 및 검증 (3시간)

---

## 📦 Dependencies 추가

**requirements.txt 업데이트**:
```txt
# 기존 dependencies
...

# Phase C: 한국어 문장 분리
kss>=4.5.4

# Phase B: Qwen3 (Ollama에서 제공, 별도 설치 불필요)
# ollama pull qwen3-embedding-8b:latest
```

---

## ⚠️ 리스크 및 대응

### Phase B-1 리스크: VRAM 부족

**문제**: Qwen3-Embedding-8B는 ~16GB VRAM 필요

**대응책**:
1. **차원 축소**: 2048D → 1024D (VRAM ~8GB)
2. **배치 처리**: 문서 임베딩 시 배치 사이즈 조정
3. **Fallback**: VRAM 부족 시 mxbai로 복귀

```python
try:
    # Qwen3 시도
    vectorstore = VectorStoreManager(
        embedding_model="qwen3-embedding-8b:latest",
        embedding_dimension=2048
    )
except OutOfMemoryError:
    # Fallback to mxbai
    print("⚠️ VRAM 부족, mxbai-embed-large로 복귀")
    vectorstore = VectorStoreManager(
        embedding_model="mxbai-embed-large:latest",
        embedding_dimension=1024
    )
```

### Phase B-2 리스크: Ollama Dimension 파라미터 미지원

**문제**: Ollama가 Qwen3의 `dimension` 파라미터를 지원하지 않을 수 있음

**대응책**:
1. **사전 확인**: Ollama API 문서 확인
2. **테스트**: 간단한 스크립트로 dimension 파라미터 테스트
3. **대안**: Dimension 고정 (2048D 또는 4096D) 사용

```python
# 테스트 스크립트
import ollama

try:
    response = ollama.embeddings(
        model="qwen3-embedding-8b:latest",
        prompt="test",
        options={"dimension": 1024}
    )
    print("✅ Dimension 파라미터 지원됨")
except Exception as e:
    print(f"❌ Dimension 파라미터 미지원: {e}")
    print("→ 대안: 고정 차원 (2048D) 사용")
```

### Phase C 리스크: Citation 계산 시간 증가

**문제**: Multi-Source Citation으로 인한 응답 시간 증가 (+3초)

**대응책**:
1. **캐싱**: 문장 임베딩 캐싱
2. **병렬 처리**: 문장별 Citation 병렬 계산
3. **조기 종료**: 임계값 이상 2개만 찾고 종료

---

## 📅 종합 일정 (예상)

### 옵션 1: 순차 진행 (안정적)

```
Week 1:
├─ Phase A-3 (3일)
└─ Phase B-1 준비 (Qwen3 다운로드, 백업)

Week 2:
├─ Phase B-1 구현 (4일)
└─ Phase B-1 테스트 (1일)

Week 3:
├─ Phase B-2 구현 (3일)
└─ Phase B-3 구현 (2일)

Week 4:
├─ Phase C 구현 (3일)
└─ 최종 통합 테스트 (2일)

총 소요 시간: 4주
```

### 옵션 2: 병렬 진행 (빠른 완료)

```
Week 1:
├─ Phase A-3 (3일) + Qwen3 다운로드 (백그라운드)
└─ Phase C 구현 시작 (2일, A-3와 독립)

Week 2:
├─ Phase B-1 구현 (4일)
└─ Phase C 완료 (1일)

Week 3:
├─ Phase B-2 + B-3 구현 (5일)
└─ 통합 테스트 (2일)

총 소요 시간: 3주
```

### 옵션 3: Citation 우선 (사용자 체감 개선)

```
Week 1:
├─ Phase A-3 (3일)
└─ Phase C 구현 (3일)

Week 2:
├─ Phase C 테스트 및 최적화 (2일)
└─ Phase B-1 준비 및 구현 (5일)

Week 3:
├─ Phase B-2 + B-3 (5일)
└─ 최종 테스트 (2일)

총 소요 시간: 3주
특징: Citation Rate 95% 조기 달성
```

---

## 🎯 핵심 요약

### 즉시 착수 권장: Phase A-3
- **기간**: 2-3일
- **효과**: 재생성 50% 감소, 응답 10-15초 단축
- **리스크**: 낮음
- **의존성**: 없음

### 최대 성능 향상: Phase B-1 (Qwen3)
- **기간**: 2일 + 4-6시간 (재임베딩)
- **효과**: 정확도 +10-15%, MTEB +26%
- **리스크**: 중간 (VRAM 16GB 필요)
- **의존성**: Ollama Qwen3 모델

### 사용자 신뢰도 향상: Phase C (Citation)
- **기간**: 3일
- **효과**: Citation Rate 80% → 95%
- **리스크**: 낮음
- **의존성**: Phase A-2 (완료)

### 총 예상 효과 (v4.0)
- ✅ **정확도**: +28-46%
- ✅ **응답 시간**: -22-29초 (-24-32%)
- ✅ **Citation Rate**: 57.8% → 95%
- ✅ **MTEB 점수**: ~56 → ~70.58
- ✅ **NotebookLM 수준 달성**

---

**다음 단계**: Phase A-3 구현 착수 권장

실행 명령:
```bash
# Phase A-3 구현 브랜치 생성
git checkout -b feature/phase-a3-answer-verification

# 구현 파일 열기
code utils/rag_chain.py
```
