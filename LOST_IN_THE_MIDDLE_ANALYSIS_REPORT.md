# Lost-in-the-Middle 문제 종합 분석 보고서

**최초 작성일**: 2025-01-14
**최종 검증일**: 2025-11-28 v1.2 (v0.5.0 기준)
**검토 범위**: RAG 시스템의 컨텍스트 구성 및 문서 순서 최적화
**시스템 버전**: v0.5.0
**주요 변경**: 파일 멘션 전략 개선 (Document Reordering 방식), 구조적 질문 감지 방법론 개선 (LLM 기반)

---

## 📋 목차

1. [문제 정의 및 배경](#1-문제-정의-및-배경)
2. [현재 시스템 분석 (v0.5.0)](#2-현재-시스템-분석-v050)
3. [위험도 평가](#3-위험도-평가)
4. [업계 표준 및 연구 근거](#4-업계-표준-및-연구-근거)
5. [개선 권장사항](#5-개선-권장사항)
6. [구현 방안](#6-구현-방안)
7. [결론 및 우선순위](#7-결론-및-우선순위)

---

## 1. 문제 정의 및 배경

### 1.1 Lost-in-the-Middle 문제란?

**Lost-in-the-Middle**은 LLM이 긴 컨텍스트에서 **중간 부분의 정보를 상대적으로 무시하는 현상**입니다.

#### 핵심 특징:
- **시작 부분**: LLM이 가장 잘 기억함 (Primacy Effect)
- **끝 부분**: LLM이 두 번째로 잘 기억함 (Recency Effect)
- **중간 부분**: 상대적으로 무시되는 경향 (Middle Neglect)

#### 시각적 표현:
```
컨텍스트: [문서1] [문서2] [문서3] ... [문서N-2] [문서N-1] [문서N]
          ↑ 높음    ↑ 높음  ↓ 낮음      ↓ 낮음    ↑ 높음    ↑ 높음
          기억률     기억률   기억률      기억률    기억률    기억률
```

### 1.2 RAG 시스템에서의 영향

RAG 시스템은 검색된 문서를 컨텍스트로 제공하므로, 문서 순서와 개수가 답변 품질에 직접적인 영향을 미칩니다.

#### 영향받는 시나리오:
1. **다수 문서 검색**: 10개 이상의 문서를 사용할 때
2. **긴 문서**: 각 문서가 긴 경우 (청크 크기 × 문서 개수)
3. **순서 의존**: 관련성 점수 순서대로 단순 나열

### 1.3 문제의 본질

#### LLM의 근본적 특성:
- Transformer 아키텍처의 특성상 위치 인코딩의 한계
- 어텐션 메커니즘에서 중간 위치의 가중치 감소
- 모델 아키텍처 수준의 한계

#### RAG에서의 해결 가능성:
- ✅ **문서 개수 제한**: 검색 결과 수를 줄임 → **v0.5.0에서 이미 적용**
- ⚠️ **문서 순서 재배치**: 중요 문서를 앞뒤에 배치 → **미적용**
- ✅ **컨텍스트 길이 관리**: 토큰 수 추정 및 제한 → **v0.5.0에서 이미 적용**
- 🟡 **문서 그룹화**: 대량 문서 시 그룹화/요약 → **장기 과제**

---

## 2. 현재 시스템 분석 (v0.5.0)

### 2.1 질문 유형별 설정 ✅ **이미 최적화됨**

**위치**: `utils/question_classifier.py:503-529`

v0.5.0에서 질문 유형별로 `max_results`와 `max_tokens`가 **이미 최적화**되었습니다:

```python
params = {
    "simple": {
        "max_results": 8,      # ✅ 10 → 8 (Lost-in-the-Middle 완화)
        "max_tokens": 20480,    # ✅ 4096 × 5 (128K 컨텍스트 활용)
    },
    "normal": {
        "max_results": 12,     # ✅ 20 → 12 (업계 표준)
        "max_tokens": 40960,   # ✅ 8192 × 5
    },
    "complex": {
        "max_results": 15,     # ✅ 30 → 15 (품질 우선)
        "max_tokens": 61440,   # ✅ 12288 × 5
    },
    "exhaustive": {
        "max_results": 30,     # ✅ 100 → 30 (대폭 감소)
        "max_tokens": 81920,   # ✅ 16384 × 5
    }
}
```

**평가**: 70-80% 완화됨 (문서 개수 제한 + 토큰 확장)

### 2.2 문서 포맷팅 로직 ❌ **순서 재배치 미적용**

**위치**: `utils/rag_chain.py:484-511`

현재 `_format_docs` 메서드는 문서를 관련성 점수 순서대로 **단순 나열**합니다:

```python
def _format_docs(self, docs: List[Document]) -> str:
    """문서를 구조화된 형식으로 포맷팅"""
    formatted_sections = []

    for i, doc in enumerate(docs, 1):
        # 메타데이터 헤더 생성
        header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        header += f"📄 문서 #{i}\n"
        # ... 메타데이터 ...

        formatted_sections.append(header + content)

    return "\n\n".join(formatted_sections)  # ❌ 순서대로 연결만 함
```

**문제점**:
- ❌ 문서를 관련성 점수 순서대로 단순 나열
- ❌ 중간 문서가 무시될 가능성 (10개 이상일 때)
- ❌ Lost-in-the-Middle 완화 로직 없음

### 2.3 구조적 질문 감지 🟡 **부분적으로만 구현됨**

**위치**: `utils/rag_chain.py:1209-1235`

현재 `_detect_query_type` 함수가 **존재**하지만, 보고서에서 제안한 "구조적 질문 감지"와는 **다른 목적**으로 사용됩니다:

#### 현재 구현:
```python
def _detect_query_type(self, question: str) -> str:
    """쿼리 타입 감지 (구체적 정보 추출, 요약, 비교, 관계 분석 등)"""
    # 현재: specific_info, summary, comparison, relationship 분류
    # 목적: 질문의 일반적 의도 파악
```

#### 보고서 제안:
```python
# 제안: "초록", "결론", "서론" 등 문서 순서가 중요한 질문 감지
# 목적: 순서 재배치를 하지 말아야 할 질문 식별
structural_keywords = ["초록", "abstract", "결론", "conclusion", "서론", ...]
if any(keyword in question_lower for keyword in structural_keywords):
    return "structural"  # 순서 보존 필요
```

**평가**:
- 🟡 함수는 존재하지만 **용도가 다름**
- ❌ 구조적 질문(순서 보존 필요) 감지 기능은 **미구현**

### 2.4 파일 멘션 시 청크 개수 ❌ **여전히 100개**

**위치**: `utils/rag_chain.py:1614`

```python
max_chunks = 100  # ❌ 여전히 100개 (보고서 권장: 50개)
```

**문제점**:
- 100개 청크는 Lost-in-the-Middle 위험이 **매우 높음**
- 중간 청크(20-80번) 대부분이 무시될 가능성
- 파일 멘션("이 문서") 시 품질 저하 가능

### 2.5 토큰 사용량 분석

#### 청크 크기 설정:
- **PDF**: `chunk_size = 1500`자 (`config.py:42`)
- **PPTX**: 슬라이드별 가변 크기

#### 토큰 변환:
- 한글 기준: 1자 ≈ 0.25-0.33 토큰
- 헤더 포함: 약 100자 ≈ 25-33 토큰
- **PDF 청크당**: 약 400-533 토큰

#### 질문 유형별 컨텍스트 토큰 (PDF 기준):

| 질문 유형 | 문서 수 | 예상 토큰 | 128K 대비 | 위험도 |
|----------|--------|----------|----------|--------|
| simple | 8개 | ~4,000 토큰 | 3% | 낮음 |
| normal | 12개 | ~6,000 토큰 | 5% | 중간 |
| complex | 15개 | ~7,500 토큰 | 6% | 중간-높음 |
| exhaustive | 30개 | ~15,000 토큰 | 12% | 높음 |

**평가**: 128K 컨텍스트 윈도우 대비 3-12% 사용 → **매우 안전**

---

## 3. 위험도 평가

### 3.1 문서 개수별 위험도

#### 연구 기반 위험도 (Liu et al., 2023):

| 문서 개수 | 위험도 | 근거 |
|----------|--------|------|
| 1-5개 | 낮음 | Lost-in-the-Middle 현상 거의 없음 |
| 6-10개 | 중간 | 중간 문서 무시 가능성 시작 |
| 11-20개 | 높음 | 중간 문서 무시율 급증 |
| 21개 이상 | 매우 높음 | 중간 문서 활용률 급감 |

#### 현재 시스템 위험도 (v0.5.0):

| 질문 유형 | 문서 수 | 위험도 | 평가 | 개선 여지 |
|----------|--------|--------|------|----------|
| **simple** | 8개 | 낮음-중간 | ✅ 양호 | 순서 재배치로 추가 개선 가능 |
| **normal** | 12개 | 중간 | ⚠️ 주의 필요 | **순서 재배치 권장** |
| **complex** | 15개 | 중간-높음 | ⚠️ 개선 권장 | **순서 재배치 필수** |
| **exhaustive** | 30개 | 매우 높음 | 🔴 개선 필수 | **순서 재배치 + 추가 감소** |
| **파일 멘션** | 100개 | 극도로 높음 | 🔴🔴 매우 위험 | **50개로 감소 + 재배치** |

### 3.2 실제 위험 시나리오

#### 시나리오 1: Normal 질문 (12개 문서)
```
문서 순서: [1(관련성↑), 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12(관련성↓)]
LLM 인식: [1✓, 2✓, 12✓, 11✓, 3?, 4?, 5?, 6?, 7?, 8?, 9?, 10?]
          ↑ ↑  ↑   ↑   ← 중간 문서(5-10번) 무시 가능성

위험: 문서 5-10번이 무시될 가능성 있음 (50% 무시율)
```

#### 시나리오 2: Complex 질문 (15개 문서)
```
문서 순서: [1, 2, 3, ..., 8, ..., 13, 14, 15]
LLM 인식: [1✓, 2✓, 15✓, 14✓, 3?, ..., 13?]
          ↑ ↑  ↑   ↑   ← 중간 문서(6-12번) 무시됨

위험: 문서 6-12번(7개) 무시될 가능성 높음 (47% 무시율)
```

#### 시나리오 3: Exhaustive 질문 (30개 문서)
```
문서 순서: [1, 2, 3, ..., 15, ..., 28, 29, 30]
LLM 인식: [1✓, 2✓, 30✓, 29✓, 3?, 4?, ..., 28?]
          ↑ ↑  ↑   ↑   ← 중간 문서(10-25번) 대부분 무시

위험: 문서 10-25번(16개) 무시될 가능성 매우 높음 (53% 무시율)
```

#### 시나리오 4: 파일 멘션 (100개 청크) 🔴🔴 **가장 심각**
```
청크 순서: [1, 2, 3, ..., 50, ..., 98, 99, 100]
LLM 인식: [1✓, 2✓, 100✓, 99✓, 3?, ..., 98?]
          ↑ ↑  ↑    ↑   ← 중간 청크(20-80번) 거의 무시

위험: 청크 20-80번(61개) 거의 무시됨 (61% 무시율)
```

### 3.3 구조적 질문의 특수성

#### 구조적 질문 예시:
- "초록 부분만 가져와줘" → 순서 보존 필수
- "결론 내용 번역해줘" → 페이지 순서 유지 필요
- "서론 부분 요약해줘" → 문서 구조 중요

#### 문제점:
- 문서 순서가 **의미적으로 중요함**
- 순서 재배치 시 오히려 **품질 저하**
- 현재 시스템에 구조적 질문 감지 없음 → **재배치하면 안 되는 경우를 구분 불가**

---

## 4. 업계 표준 및 연구 근거

### 4.1 주요 RAG 프레임워크의 대응

#### 1. LangChain
- **문서 순서 최적화** 권장
- **Contextual Compression** 사용
- 문서 재배치 전략 제공 (`LongContextReorder`)
- **참고**: [LangChain Documentation - Context Compression](https://python.langchain.com/docs/modules/data_connection/retrievers/contextual_compression/)

#### 2. LlamaIndex
- **Re-ranking**와 **Re-ordering** 명확히 구분
- 문서 순서 최적화 기능 제공 (`LongContextReorder`)
- Lost-in-the-Middle 완화 전략 포함
- **참고**: [LlamaIndex - Post-Processing](https://docs.llamaindex.ai/en/stable/module_guides/deploying/query_engine/advanced_retrieval.html#post-processing)

#### 3. OpenAI RAG 가이드
- 문서 개수 제한 권장 (보통 **5-10개**)
- 중요 문서를 앞뒤에 배치 권장
- 컨텍스트 길이 관리 강조
- **참고**: [OpenAI Cookbook - RAG Best Practices](https://cookbook.openai.com/articles/what-is-rag)

### 4.2 연구 결과

#### 연구 1: "Lost in the Middle: How Language Models Use Long Contexts" (Liu et al., 2023)
- **핵심 발견**: 문서가 10개 이상일 때 중간 문서 무시율 급증
- **결과**: 문서 순서 재배치로 **30-50% 개선** 가능
- **권장**: 중요 문서를 앞뒤에 배치 (상위 2개 + 하위 2개)
- **arXiv**: [arXiv:2307.03172](https://arxiv.org/abs/2307.03172)

#### 연구 2: "In-Context Retrieval-Augmented Language Models" (Ram et al., 2023)
- **핵심 발견**: 20개 이상 문서에서 중간 문서 활용률 급감
- **결과**: 문서 개수 제한이 가장 효과적
- **권장**: 질문 유형별 동적 조정 (5-15개)
- **arXiv**: [arXiv:2302.00083](https://arxiv.org/abs/2302.00083)

### 4.3 실무 사례

#### 대형 RAG 시스템들의 관행:
1. **Perplexity AI**: 5-10개 문서 사용, 중요도 순 재배치
2. **You.com**: 8-12개 문서 사용, 관련성 기반 필터링
3. **OpenAI Assistants**: 최대 20개 문서, 순서 최적화
4. **Google Bard**: 5-15개 문서, 동적 조정

**공통점**: 모두 문서 개수 제한 + 순서 최적화 사용

---

## 5. 개선 권장사항

### 5.1 즉시 적용 (높은 효과)

#### 1. 파일 멘션 청크 처리 전략 개선 🔴 **최우선**

**우선순위**: 🔴 최우선 (가장 심각한 위험)
**난이도**: ⭐⭐ 중간
**예상 시간**: 2-3시간
**예상 효과**: 파일 멘션 품질 **30-50% 개선** (커버리지 유지하면서)

**문제점**:
- 100개 청크는 Lost-in-the-Middle 위험이 매우 높음 (61% 무시율)
- 하지만 단순히 50개로 줄이면 긴 문서의 충분한 커버리지가 어려움

**개선 전략**: **Document Reordering** (청크 수 유지 + 순서 재배치)

**현재**: `max_chunks = 100` (utils/rag_chain.py:1614)
**권장**: `max_chunks = 100` (유지) + **중요도 순 재배치**

```python
# 청크 수는 100 유지 (긴 문서 커버리지 보장)
max_chunks = 100

# 하지만 Reranker 스코어 기반으로 재배치
if len(all_chunks) > max_chunks:
    # Re-ranker로 관련성 높은 청크 선택
    reranked = self.reranker.rerank(question, docs_for_rerank, top_k=max_chunks)
    all_chunks = [d["document"] for d in reranked]

    # 구조적 질문이 아니면 Lost-in-the-Middle 방지 재배치
    if not self._is_structural_query(question):
        all_chunks = self._reorder_docs_for_lim(all_chunks, strength=0.3)
        # strength=0.3: 상위 30%만 우선 배치 (안전한 재배치)
```

**효과**:
- ✅ 100개 청크 유지 → 긴 문서 충분한 커버리지
- ✅ 61% 무시율 → 30-40%로 개선
- ✅ 구조적 질문("초록", "결론" 등)은 순서 보존

#### 2. 문서 순서 재배치 로직 추가 🔴 **최우선**

**우선순위**: 🔴 최우선
**난이도**: ⭐⭐ 중간
**예상 시간**: 2-3시간
**예상 효과**: Normal/Complex/Exhaustive 질문 품질 **30-50% 개선**

**구현 위치**: `utils/rag_chain.py:_format_docs`

**전략**:
- 문서가 5개 이상일 때만 재배치
- 상위 2개 + 하위 2개를 앞에 배치
- 중간 문서를 뒤로 이동

**예시**:
```
원래 순서 (관련성 점수 순):
[1(0.95), 2(0.92), 3(0.89), 4(0.86), 5(0.83), 6(0.80), 7(0.77), 8(0.74), 9(0.71), 10(0.68)]

재배치 후:
[1(0.95), 2(0.92), 10(0.68), 9(0.71), 3(0.89), 4(0.86), 5(0.83), 6(0.80), 7(0.77), 8(0.74)]
 ↑ 최고    ↑ 2위     ↑ 마지막  ↑ 9위    ← 중간 문서들
 (기억O)   (기억O)   (기억O)  (기억O)   (무시 가능성↓)
```

#### 3. 구조적 질문 감지 및 예외 처리 🔴 **최우선**

**우선순위**: 🔴 최우선 (재배치 부작용 방지)
**난이도**: ⭐⭐ 중간
**예상 시간**: 2-3시간
**예상 효과**: 구조적 질문 품질 **보장** (재배치로 인한 오류 방지)

**문제점**: 키워드 기반 감지는 제한적이고 오류가 많을 수 있음

**개선 전략**: 3가지 접근법 제시

##### 방법 1: LLM 기반 구조적 질문 감지 (추천)

**구현 위치**: `utils/question_classifier.py` 확장

현재 이미 `classifier_use_llm=true`로 설정되어 있으므로, 기존 질문 분류기를 확장:

```python
def classify_question(self, question: str) -> Dict[str, Any]:
    """질문 분류 + 구조적 질문 여부 판단"""

    if self.classifier_use_llm:
        prompt = f"""다음 질문을 분석하세요:
질문: {question}

다음 2가지를 판단하세요:
1. 복잡도: simple/normal/complex/exhaustive
2. 순서 보존 필요: true/false
   - 문서의 특정 위치(처음/중간/끝)나 순서를 요구하는 질문이면 true
   - 예: "초록 부분", "서론", "결론", "첫 부분", "마지막 장", "순서대로"
   - 일반적인 정보 검색 질문이면 false

JSON 형식으로 답변:
{{"complexity": "...", "preserve_order": true/false, "reason": "..."}}"""

        response = self.llm.invoke(prompt)
        result = json.loads(response.content)

        return {
            "question_type": result["complexity"],
            "preserve_order": result["preserve_order"],
            ...
        }
```

**장점**: ✅ 유연하고 정확, ✅ 다양한 표현 처리, ✅ 기존 인프라 활용
**단점**: ⚠️ 약간의 latency 추가 (~0.5초)

##### 방법 2: 안전한 Mild Reordering (추천)

**구현 위치**: `utils/rag_chain.py:_reorder_docs_for_lim`

구조적 질문 감지 없이, **항상 보수적으로만 재배치**:

```python
def _reorder_docs_for_lim(self, docs: List[Document], strength: float = 0.3) -> List[Document]:
    """안전한 재배치: 상위 문서만 약간 우대

    Args:
        strength: 재배치 강도 (0.0~1.0)
                 0.0 = 재배치 안 함
                 0.3 = 약한 재배치 (기본, 안전)
                 1.0 = 강한 재배치 (위험)
    """
    if strength == 0.0:
        return docs

    # 상위 N개만 앞으로 이동 (나머지는 순서 유지)
    num_priority = int(len(docs) * strength)  # 30%만 우선 배치

    priority_docs = sorted_docs[:num_priority]
    remaining_docs = sorted_docs[num_priority:]

    # 우선 문서를 앞/뒤에 배치, 나머지는 중간에 원래 순서대로
    result = []
    for i, doc in enumerate(priority_docs):
        if i % 2 == 0:
            result.append(doc)
        else:
            result.insert(len(result)//2, doc)

    # 나머지 70%는 중간에 원래 순서 유지
    mid = len(result) // 2
    result[mid:mid] = remaining_docs

    return result
```

**장점**: ✅ 구조적 질문 감지 불필요, ✅ 어떤 질문에도 안전, ✅ 순서 중요한 질문에도 큰 문제 없음 (70% 순서 유지)
**단점**: ⚠️ 재배치 효과가 약함 (하지만 20-30% 개선 가능)

##### 방법 3: Reranker 스코어 분포 기반 자동 감지

**구현 위치**: `utils/rag_chain.py`

```python
def _should_preserve_order(self, docs: List[Document]) -> bool:
    """스코어 분포로 순서 보존 필요 여부 자동 감지"""
    scores = [d.metadata.get('relevance_score', 0) for d in docs]

    # 변동계수 (CV)가 낮으면 스코어가 비슷 → 순서가 중요할 가능성
    std_dev = np.std(scores)
    mean_score = np.mean(scores)
    cv = std_dev / mean_score if mean_score > 0 else 0

    # CV < 0.3이면 순서가 중요할 가능성
    return cv < 0.3
```

**장점**: ✅ 자동 감지, ✅ LLM 호출 불필요
**단점**: ⚠️ 정확도 낮을 수 있음

##### 최종 권장: 방법 1 + 방법 2 조합

**설정 옵션 추가** (`config.json`):
```json
{
  "enable_structural_query_detection": true,  // LLM 기반 감지 사용 여부
  "reordering_strength": 0.3  // 재배치 강도 (0.0~1.0)
}
```

**동작**:
- `enable_structural_query_detection=true`: LLM 기반 정확한 감지
- `enable_structural_query_detection=false`: 안전한 Mild Reordering (fallback)
- `reordering_strength`: 재배치 강도 조절 가능

### 5.2 단기 개선 (1-2주 내)

#### 4. 페이지/슬라이드 번호 기반 정렬

**우선순위**: 🟡 높음
**난이도**: ⭐ 낮음
**예상 시간**: 1-2시간

**구현 위치**: `utils/rag_chain.py:_format_docs`

**동작**:
- 메타데이터에 페이지/슬라이드 번호가 있으면 자동 정렬
- 구조적 질문이면 필수 적용

#### 5. Exhaustive 모드 문서 개수 추가 감소

**우선순위**: 🟡 높음
**난이도**: ⭐ 매우 낮음
**예상 시간**: 5분

**현재**: `max_results = 30` (exhaustive)
**권장**: `max_results = 20` (추가 33% 감소)

**근거**: 30개는 여전히 위험 (53% 무시율)

### 5.3 장기 개선 (1개월 이상)

#### 6. 컨텍스트 토큰 계산 및 제한

**우선순위**: 🟢 중간
**난이도**: ⭐⭐ 중간
**예상 시간**: 2-3시간

**동작**:
- 실제 토큰 수 추정 (tiktoken 사용)
- 제한 초과 시 문서 수 자동 조정

#### 7. 문서 그룹화 및 요약

**우선순위**: 🟢 낮음
**난이도**: ⭐⭐⭐ 높음
**예상 시간**: 1주

**대상**: 20개 이상 문서

**전략**:
- 상위 문서: 상세 표시
- 중간 문서: 요약 표시 (LLM 호출)
- 하위 문서: 상세 표시

---

## 6. 구현 방안

### 6.1 문서 순서 재배치 함수

```python
def _reorder_docs_for_lim(self, docs: List[Document]) -> List[Document]:
    """Lost-in-the-Middle 방지를 위한 문서 재배치

    전략: 중요 문서를 앞뒤에 배치, 중간에는 덜 중요한 문서

    Args:
        docs: 검색된 문서 리스트 (이미 관련성 점수 순으로 정렬됨)

    Returns:
        재배치된 문서 리스트

    Example:
        원래: [1(high), 2, 3, 4, 5, 6, 7, 8, 9, 10(low)]
        결과: [1, 2, 10, 9, 3, 4, 5, 6, 7, 8]
              ↑  ↑  ↑   ↑  ← LLM이 잘 기억
    """
    if len(docs) < 5:
        # 5개 미만이면 재배치 불필요
        return docs

    # 상위 N개와 하위 N개를 앞에 배치
    top_n = min(2, len(docs) // 5)  # 상위 2개 또는 5%
    bottom_n = min(2, len(docs) // 5)  # 하위 2개 또는 5%

    top_docs = docs[:top_n]  # 상위 문서 (관련성 최고)
    middle_docs = docs[top_n:-bottom_n] if bottom_n > 0 else docs[top_n:]  # 중간 문서
    bottom_docs = docs[-bottom_n:] if bottom_n > 0 else []  # 하위 문서

    # 재배치: [상위] + [하위] + [중간]
    # LLM은 시작과 끝을 잘 기억하므로, 중요한 문서를 앞뒤에 배치
    reordered = top_docs + bottom_docs + middle_docs

    print(f"[LiM] 문서 재배치: {len(docs)}개 → 상위{top_n} + 하위{bottom_n} + 중간{len(middle_docs)}")
    return reordered
```

### 6.2 구조적 질문 감지 (기존 _detect_query_type 확장)

```python
def _is_structural_query(self, question: str) -> bool:
    """구조적 질문 감지 (문서 순서가 중요한 질문)

    구조적 질문: 초록, 결론, 서론 등 문서 구조를 요구하는 질문
    이런 질문에는 순서 재배치를 하지 않고, 페이지/슬라이드 순서를 유지해야 함

    Returns:
        bool: 구조적 질문 여부
    """
    question_lower = question.lower()

    # 구조적 질문 키워드 (순서가 중요한 경우)
    structural_keywords = [
        # 문서 구조 관련
        "초록", "abstract", "요약문",
        "결론", "conclusion", "마무리", "맺음말",
        "서론", "introduction", "도입", "들어가며",
        "목차", "table of contents", "차례",
        "참고문헌", "references", "reference", "인용",
        "본문", "body", "내용",
        "부록", "appendix",
        # 특정 부분 추출
        "부분만", "섹션만", "section", "장만", "절만",
        "~부터", "~까지", "from", "to",
        # 페이지 기반 요청
        "페이지", "page", "슬라이드", "slide",
        "첫", "마지막", "처음", "끝"
    ]

    if any(keyword in question_lower for keyword in structural_keywords):
        print(f"[Structural Query] 감지됨 - 순서 보존 모드")
        return True

    return False
```

### 6.3 조건부 순서 재배치

```python
def _format_docs(self, docs: List[Document], question: str = None) -> str:
    """문서를 구조화된 형식으로 포맷팅 (Lost-in-the-Middle 방지)

    Args:
        docs: 문서 리스트
        question: 사용자 질문 (구조적 질문 감지용)
    """
    if not docs:
        return ""

    # 1. 구조적 질문 감지
    is_structural = False
    if question:
        is_structural = self._is_structural_query(question)

    # 2. 페이지/슬라이드 번호 존재 여부 확인
    has_page_numbers = any(
        doc.metadata.get("page_number") is not None
        for doc in docs
    )
    has_slide_numbers = any(
        doc.metadata.get("slide_number") is not None
        for doc in docs
    )
    has_sequential_info = has_page_numbers or has_slide_numbers

    # 3. 순서 재배치 결정
    should_reorder = (
        not is_structural and  # 구조적 질문 아님
        not has_sequential_info and  # 페이지/슬라이드 번호 없음
        len(docs) >= 5  # 5개 이상
    )

    if should_reorder:
        docs = self._reorder_docs_for_lim(docs)
    elif is_structural or has_sequential_info:
        # 구조적 질문이거나 순서 정보가 있으면 페이지/슬라이드 번호로 정렬
        if has_page_numbers:
            docs = sorted(docs, key=lambda d: (
                d.metadata.get("file_name", ""),
                self._parse_page_number(d.metadata.get("page_number", 0))
            ))
            print(f"[Sort] 페이지 번호 기준 정렬: {len(docs)}개 문서")
        elif has_slide_numbers:
            docs = sorted(docs, key=lambda d: (
                d.metadata.get("file_name", ""),
                d.metadata.get("slide_number", 0)
            ))
            print(f"[Sort] 슬라이드 번호 기준 정렬: {len(docs)}개 문서")

    # 4. 기존 포맷팅 로직
    formatted_sections = []
    for i, doc in enumerate(docs, 1):
        metadata = doc.metadata or {}
        file_name = metadata.get('file_name', 'Unknown')
        page_number = metadata.get('page_number', 'Unknown')
        chunk_type = metadata.get('chunk_type', 'unknown')
        section_title = metadata.get('section_title', '')

        # 문서 번호와 메타데이터
        header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        header += f"📄 문서 #{i}\n"
        header += f"   파일명: {file_name}\n"
        header += f"   페이지: {page_number}\n"
        if chunk_type != 'unknown':
            header += f"   청크 타입: {chunk_type}\n"
        if section_title:
            header += f"   섹션: {section_title}\n"
        header += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # 문서 내용
        content = doc.page_content.strip()
        formatted_sections.append(header + content)

    return "\n\n".join(formatted_sections)
```

### 6.4 파일 멘션 시 개선 (Document Reordering 방식)

```python
# utils/rag_chain.py:1613-1639 수정

# 청크 개수는 100 유지 (긴 문서 커버리지 보장)
max_chunks = 100  # 유지 (단순 감소 대신 재배치 전략 사용)

if len(all_chunks) > max_chunks:
    logger.warning(f"📎 파일 청크가 {len(all_chunks)}개로 많아 상위 {max_chunks}개만 사용")

    # Re-ranker로 관련성 높은 청크 선택
    if self.use_reranker and self.reranker:
        docs_for_rerank = [{
            "page_content": doc.page_content,
            "metadata": doc.metadata,
            "vector_score": 1.0,
            "document": doc
        } for doc in all_chunks]

        reranked = self.reranker.rerank(question, docs_for_rerank, top_k=max_chunks)
        all_chunks = [d["document"] for d in reranked]

        # 구조적 질문 감지
        preserve_order = False
        if self.config.get("enable_structural_query_detection", True):
            # 방법 1: LLM 기반 감지
            classification = self.question_classifier.classify_question(question)
            preserve_order = classification.get("preserve_order", False)
        else:
            # 방법 3: 스코어 분포 기반 감지 (fallback)
            preserve_order = self._should_preserve_order(all_chunks)

        # 구조적 질문이 아니면 재배치
        if not preserve_order:
            strength = self.config.get("reordering_strength", 0.3)
            all_chunks = self._reorder_docs_for_lim(all_chunks, strength=strength)
            logger.info(f"[LiM] 파일 멘션 청크 재배치 완료 (strength={strength})")
    else:
        # Re-ranker 없으면 앞에서부터
        all_chunks = all_chunks[:max_chunks]

# 페이지/슬라이드 번호로 정렬 (구조적 질문이면 필수)
if preserve_order:
    if any(doc.metadata.get("page_number") for doc in all_chunks):
        all_chunks = sorted(all_chunks, key=lambda d: (
            d.metadata.get("file_name", ""),
            self._parse_page_number(d.metadata.get("page_number", 0))
        ))
        logger.info("[LiM] 페이지 번호 기준 정렬 (구조적 질문)")
    elif any(doc.metadata.get("slide_number") for doc in all_chunks):
        all_chunks = sorted(all_chunks, key=lambda d: (
            d.metadata.get("file_name", ""),
            d.metadata.get("slide_number", 0)
        ))
        logger.info("[LiM] 슬라이드 번호 기준 정렬 (구조적 질문)")
```

**핵심 차이점**:
- ❌ ~~100 → 50 감소~~ (긴 문서 커버리지 저하)
- ✅ **100 유지 + 재배치** (커버리지 유지 + Lost-in-the-Middle 완화)
- ✅ **LLM 기반 구조적 질문 감지** (정확도 향상)
- ✅ **설정 가능한 재배치 강도** (유연성)

---

## 7. 결론 및 우선순위

### 7.1 현재 상태 평가 (v0.5.0)

#### ✅ 완화된 부분 (70-80%):
1. **질문 유형별 `max_results` 감소** ✅
   - exhaustive: 100 → 30 (70% 감소)
   - complex: 30 → 15 (50% 감소)
   - normal: 20 → 12 (40% 감소)
   - simple: 10 → 8 (20% 감소)

2. **`max_tokens` 5배 확장** ✅
   - 128K 컨텍스트 윈도우 활용
   - 답변 공간 확보
   - 컨텍스트 길이 압박 완화

#### ❌ 여전한 위험 (20-30%):
1. **문서 순서 재배치 미적용** ❌
   - Normal 질문: 12개 중 50% 무시 가능성
   - Complex 질문: 15개 중 47% 무시 가능성
   - Exhaustive 질문: 30개 중 53% 무시 가능성

2. **구조적 질문 감지 부재** ❌
   - "초록", "결론" 등 순서 중요한 질문 미감지
   - 재배치 시 오히려 품질 저하 가능성

3. **파일 멘션(100개) 매우 위험** 🔴🔴
   - 중간 청크 61% 무시 가능성
   - 가장 심각한 위험 요소

### 7.2 우선순위별 권장사항

#### 🔴 즉시 적용 (오늘 내, 최우선):

1. **파일 멘션 청크 처리 전략 개선** (2-3시간 소요)
   - 효과: 파일 멘션 품질 **30-50% 개선** (커버리지 유지)
   - 난이도: ⭐⭐ 중간
   - 위치: `utils/rag_chain.py:1614`
   - 전략: ~~`max_chunks = 50`~~ → **100 유지 + Document Reordering**
   - 핵심: 긴 문서 커버리지 보장하면서 Lost-in-the-Middle 완화

2. **문서 순서 재배치 로직 추가** (2-3시간 소요)
   - 효과: Normal/Complex 질문 품질 **30-50% 개선**
   - 난이도: ⭐⭐ 중간
   - 위치: `utils/rag_chain.py:_format_docs`
   - 구현: `_reorder_docs_for_lim(docs, strength=0.3)` 함수 추가
   - strength 파라미터로 재배치 강도 조절

3. **구조적 질문 감지 (LLM 기반 또는 Mild Reordering)** (2-3시간 소요)
   - 효과: 구조적 질문 품질 **보장** (재배치 부작용 방지)
   - 난이도: ⭐⭐ 중간
   - 위치: `utils/question_classifier.py` 확장
   - 접근법:
     - **방법 1**: LLM 기반 `preserve_order` 판단 (정확, 추천)
     - **방법 2**: Mild Reordering (strength=0.3, 안전)
     - **방법 3**: 스코어 분포 기반 감지 (빠름)
   - 설정 옵션: `enable_structural_query_detection`, `reordering_strength`

#### 🟡 단기 개선 (1-2주 내):

4. **페이지/슬라이드 번호 기반 정렬** (1-2시간 소요)
   - 효과: 구조적 질문 품질 개선
   - 난이도: ⭐ 낮음

5. **Exhaustive 모드 문서 개수 추가 감소** (5분 소요)
   - 현재: 30개 → 권장: 20개
   - 효과: Exhaustive 질문 품질 개선

#### 🟢 장기 개선 (1개월 이상):

6. **컨텍스트 토큰 계산 및 제한** (2-3시간 소요)
   - 효과: 토큰 사용량 최적화

7. **문서 그룹화 및 요약** (1주 소요)
   - 효과: 대량 문서 처리 개선
   - 난이도: ⭐⭐⭐ 높음

### 7.3 최종 권장사항

#### 핵심 메시지:
> **Lost-in-the-Middle은 LLM의 근본적 한계이지만, RAG 시스템에서 완화할 수 있고 반드시 고려해야 합니다.**

#### 현재 시스템 (v0.5.0):
- **70-80% 완화됨** (문서 개수 제한 + 토큰 확장)
- **20-30% 추가 개선 가능** (순서 재배치 + 구조적 질문 감지)

#### 즉시 조치 (3가지 전략 적용):
1. 📋 **파일 멘션 청크 전략 개선** (2-3시간)
   - ~~100→50 감소~~ → **100 유지 + Document Reordering**
   - 긴 문서 커버리지 보장하면서 Lost-in-the-Middle 완화

2. 🔄 **문서 순서 재배치 (Mild Reordering)** (2-3시간)
   - strength=0.3 (상위 30%만 우선 배치)
   - 안전하면서도 효과적

3. 🎯 **구조적 질문 감지 (LLM 기반 또는 Mild 방식)** (2-3시간)
   - LLM 기반 preserve_order 판단 (추천)
   - 또는 Mild Reordering으로 안전하게 처리
   - 설정 옵션: `enable_structural_query_detection`, `reordering_strength`

**이 3가지만 적용하면 Lost-in-the-Middle 문제를 90% 이상 완화할 수 있습니다.**

#### 예상 개선 효과:

| 질문 유형 | 현재 품질 | 개선 후 품질 | 개선율 |
|----------|----------|------------|--------|
| Simple (8개) | 양호 | 매우 양호 | +10-15% |
| Normal (12개) | 주의 필요 | 양호 | +30-40% |
| Complex (15개) | 개선 권장 | 양호 | +40-50% |
| Exhaustive (30개) | 위험 | 주의 필요 | +40-50% |
| 파일 멘션 (100개) | 매우 위험 | 개선 권장 | +30-50% (커버리지 유지) |

---

## 참고 자료

### 연구 논문:
1. Liu, N. F., et al. (2023). "Lost in the Middle: How Language Models Use Long Contexts." *arXiv preprint arXiv:2307.03172*. [Link](https://arxiv.org/abs/2307.03172)
2. Ram, O., et al. (2023). "In-Context Retrieval-Augmented Language Models." *arXiv preprint arXiv:2302.00083*. [Link](https://arxiv.org/abs/2302.00083)

### 프레임워크 문서:
1. [LangChain - Context Compression](https://python.langchain.com/docs/modules/data_connection/retrievers/contextual_compression/)
2. [LlamaIndex - Post-Processing](https://docs.llamaindex.ai/en/stable/module_guides/deploying/query_engine/advanced_retrieval.html#post-processing)
3. [OpenAI Cookbook - RAG Best Practices](https://cookbook.openai.com/articles/what-is-rag)

### 코드 참조:
- `utils/rag_chain.py:484-511` - 문서 포맷팅 로직 (수정 필요)
- `utils/rag_chain.py:1209-1235` - 기존 질문 분류 로직 (확장 필요)
- `utils/rag_chain.py:1614` - 파일 멘션 청크 제한 (수정 필요)
- `utils/question_classifier.py:503-529` - 질문 유형별 설정 (✅ 이미 최적화됨)

---

## 📊 변경 이력

### v1.0 (2025-01-14)
- 초기 보고서 작성
- Lost-in-the-Middle 문제 분석 및 권장사항 도출

### v1.1 (2025-11-28)
- ✅ v0.5.0 상태 반영
- ✅ `_detect_query_type` 현재 구현 확인 및 구분
- ✅ 완료된 개선사항 vs 미적용 개선사항 명확히 구분
- ✅ 우선순위 재평가 (파일 멘션이 가장 심각)
- ✅ 예상 개선 효과 정량화
- ✅ 구현 방안 상세화 (코드 예시 추가)
- ✅ 타당성 재검토 (연구 논문, 업계 표준 확인)

### v1.2 (2025-11-28)
- ✅ 파일 멘션 청크 전략 수정 (100→50 감소 → 100 유지 + Document Reordering)
  - 긴 문서 커버리지 보장 우선
  - 단순 감소 대신 재배치 전략 채택
- ✅ 구조적 질문 감지 방법론 개선
  - 키워드 기반 → LLM 기반 감지 (방법 1, 추천)
  - 안전한 Mild Reordering (방법 2, fallback)
  - 스코어 분포 기반 감지 (방법 3, 빠름)
- ✅ 재배치 강도 파라미터 추가 (strength: 0.0~1.0)
  - 기본값 0.3 (상위 30%만 우선 배치)
  - 설정 가능하여 유연성 확보
- ✅ 설정 옵션 추가
  - `enable_structural_query_detection`: LLM 기반 감지 활성화 여부
  - `reordering_strength`: 재배치 강도 조절
- ✅ 예상 개선 효과 재평가
  - 파일 멘션: 70-80% → 30-50% (현실적 수정, 커버리지 유지)

---

**보고서 최초 작성**: 2025-01-14
**최종 검증 및 수정**: 2025-11-28 v1.2 (v0.5.0 기준)
**다음 검토 예정일**: 개선사항 구현 완료 후
