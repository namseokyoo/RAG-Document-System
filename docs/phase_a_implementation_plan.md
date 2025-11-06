# Phase A 구현 계획서 (즉시 적용)

**작성일**: 2025-11-06
**목표**: NotebookLM 수준의 Source Citation 및 검증 강화
**예상 완료**: 1-2주
**우선순위**: 최고

---

## 📋 목차

1. [개요](#개요)
2. [A-1: Standard 모드 카테고리 필터링](#a-1-standard-모드-카테고리-필터링)
3. [A-2: Source Citation 강화](#a-2-source-citation-강화)
4. [A-3: Answer Verification 개선](#a-3-answer-verification-개선)
5. [테스트 계획](#테스트-계획)
6. [예상 성과](#예상-성과)

---

## 개요

### 목표

Phase A는 **즉시 적용 가능한 핵심 개선사항**으로, NotebookLM의 강점을 흡수하면서 현재 시스템의 약점을 보완합니다.

### 핵심 개선 사항

1. **A-1**: Standard 모드 카테고리 필터링 (30분)
   - 크로스 도메인 오염 완전 제거 (4.5% → 0%)

2. **A-2**: Source Citation 강화 (3일)
   - NotebookLM 수준 출처 표시 (95% 정확도)

3. **A-3**: Answer Verification 개선 (2일)
   - 재생성 빈도 50% 감소, 응답 시간 10-15초 단축

### 예상 성과

| 지표 | Before (v3.1) | After (Phase A) | 개선 |
|------|--------------|----------------|------|
| **크로스 도메인 오염** | 4.5% | 0% | -100% |
| **출처 정확도** | ~60% | 95% | +58% |
| **재생성 빈도** | ~20% | ~10% | -50% |
| **사용자 신뢰도** | - | - | +30% |
| **응답 시간** | 평균 92초 | 평균 77-82초 | -10-15초 |

**총 정확도 향상**: +15-25%

---

## A-1: Standard 모드 카테고리 필터링

### 문제 정의

**현재 상황**:
```python
# Small-to-Large 모드: 카테고리 필터링 ✓ 적용됨
# Standard 모드 (Hybrid Search): 카테고리 필터링 ✗ 미적용

결과:
Query: "FRET 에너지 전달 효율은?"
출처: technical (4/5), hr (1/5) ← HRD-Net 문서 혼입 (오염)
```

**영향**:
- 크로스 도메인 오염 4.5% (1/22 출처)
- 검색 품질 저하
- 사용자 혼란

### 구현 계획

#### 1. 파일 위치
- **수정 파일**: `utils/rag_chain.py`
- **수정 메서드**: `_get_context_standard()`
- **라인 위치**: 약 450-550 라인

#### 2. 구현 내용

**Before**:
```python
def _get_context_standard(self, question: str, initial_k: int = 60):
    """Standard 검색 모드 (Hybrid Search)"""

    # Phase 4: Hybrid Search 사용
    if self.enable_hybrid_search and self.hybrid_retriever:
        print(f"  🔍 [Phase 4] Hybrid Search (BM25+Vector) 사용 (top_k={initial_k})")
        hybrid_results = self.hybrid_retriever.search(question, top_k=initial_k)
        candidates = [(doc, score) for doc, score in hybrid_results]
    else:
        # Fallback: Vector Search only
        results = self.retriever.get_relevant_documents(question)
        candidates = [(doc, 1.0) for doc in results[:initial_k]]

    # Re-ranking
    if self.use_reranker and self.reranker and len(candidates) > 0:
        docs_only = [doc for doc, score in candidates]
        reranked_docs = self.reranker.compress_documents(
            documents=docs_only,
            query=question
        )
        candidates = [(doc, 1.0) for doc in reranked_docs[:self.top_k]]

    return candidates  # 카테고리 필터링 없음!
```

**After**:
```python
def _get_context_standard(self, question: str, initial_k: int = 60):
    """Standard 검색 모드 (Hybrid Search)"""

    # 1. 질문 카테고리 감지
    detected_categories = self._detect_question_category(question)

    # Phase 4: Hybrid Search 사용
    if self.enable_hybrid_search and self.hybrid_retriever:
        print(f"  🔍 [Phase 4] Hybrid Search (BM25+Vector) 사용 (top_k={initial_k})")
        hybrid_results = self.hybrid_retriever.search(question, top_k=initial_k)
        candidates = [(doc, score) for doc, score in hybrid_results]
    else:
        # Fallback: Vector Search only
        results = self.retriever.get_relevant_documents(question)
        candidates = [(doc, 1.0) for doc in results[:initial_k]]

    # 2. 카테고리 필터링 적용 (NEW!)
    if detected_categories:
        print(f"  🔍 카테고리 필터링 적용: {', '.join(detected_categories)}")
        original_count = len(candidates)
        candidates = self._filter_by_category(candidates, detected_categories)
        print(f"  ✓ 필터링 완료: {original_count}개 → {len(candidates)}개 문서")

    # 3. Re-ranking
    if self.use_reranker and self.reranker and len(candidates) > 0:
        docs_only = [doc for doc, score in candidates]
        reranked_docs = self.reranker.compress_documents(
            documents=docs_only,
            query=question
        )
        candidates = [(doc, 1.0) for doc in reranked_docs[:self.top_k]]

    return candidates
```

#### 3. 구현 단계

**Step 1**: 코드 수정 (10분)
- `_get_context_standard()` 메서드에 카테고리 감지 및 필터링 추가
- 기존 `_detect_question_category()` 및 `_filter_by_category()` 메서드 재사용

**Step 2**: 단위 테스트 (10분)
```python
# test_phase_a1.py
def test_standard_mode_category_filtering():
    """Standard 모드에서 카테고리 필터링 확인"""

    # OLED 기술 질문
    question = "FRET 에너지 전달 효율은?"

    # Standard 모드로 검색
    result = rag_chain.generate_answer(question)

    # 출처 카테고리 확인
    sources = result['sources']
    categories = [s.metadata.get('category') for s in sources]

    # HR 문서가 없어야 함
    assert 'hr' not in categories, f"HR 문서 혼입 감지: {categories}"

    # technical 또는 business만 있어야 함
    valid_categories = ['technical', 'business']
    assert all(c in valid_categories for c in categories), \
        f"잘못된 카테고리 포함: {categories}"
```

**Step 3**: 통합 테스트 (10분)
- 실제 문서 세트로 테스트
- OLED 기술 질문 5개 → HR 문서 혼입 0% 확인
- HR 질문 3개 → OLED 문서 혼입 0% 확인

#### 4. 검증 기준

**성공 조건**:
- ✅ 크로스 도메인 오염 0% (0/N 출처)
- ✅ 정상 검색 유지 (검색 실패 없음)
- ✅ 응답 시간 변화 없음 (±5% 이내)

**테스트 케이스**:
1. OLED 기술 질문 10개 → HR 문서 혼입 0개
2. HR 시스템 질문 5개 → OLED 문서 혼입 0개
3. 비즈니스 질문 5개 → 올바른 카테고리만

#### 5. 예상 소요 시간

- 코드 수정: 10분
- 단위 테스트: 10분
- 통합 테스트: 10분
- **총 소요 시간**: **30분**

---

## A-2: Source Citation 강화

### 문제 정의

**현재 상황**:
```
## 참조 정보
- [kFRET 값]: 문서 #4, 페이지 4 / 섹션 "본문"

문제점:
1. 출처 표시 일관성 부족 (때때로 누락)
2. 페이지/섹션 정보 부정확
3. 출처 신뢰도 점수 미표시
4. 문장 단위 출처 매핑 없음
```

**목표 (NotebookLM 스타일)**:
```
제공된 문서에 따르면, kFRET 값은 87.8%입니다 [HF_OLED_Nature_Photonics_2024.pptx, slide 5, 신뢰도: 826.2].

또한 ACRSA 재료를 사용했습니다 [HF_OLED_Nature_Photonics_2024.pptx, slide 3, 신뢰도: 792.8].
```

### 구현 계획

#### 1. 파일 위치
- **수정 파일**: `utils/rag_chain.py`
- **새 메서드들**:
  - `_generate_source_citations()`
  - `_find_best_source_for_sentence()`
  - `_format_citation()`
  - `_split_sentences()`
  - `_embed_text()`
  - `_cosine_similarity()`

#### 2. 구현 내용

**핵심 로직**:
```python
def _generate_source_citations(self, answer: str, sources: List[Document]) -> str:
    """NotebookLM 스타일 출처 인라인 표시

    Args:
        answer: 생성된 답변
        sources: 사용된 출처 문서들

    Returns:
        출처가 인라인으로 표시된 답변
    """

    # 1. 답변을 문장 단위로 분리
    sentences = self._split_sentences(answer)

    cited_sentences = []
    for sentence in sentences:
        # 2. 문장과 가장 관련된 출처 찾기
        best_source = self._find_best_source_for_sentence(sentence, sources)

        if best_source:
            # 3. 인라인 출처 생성
            citation = self._format_citation(best_source)
            cited_sentence = f"{sentence.strip()} {citation}"
        else:
            cited_sentence = sentence.strip()

        cited_sentences.append(cited_sentence)

    return " ".join(cited_sentences)
```

**문장 분리**:
```python
def _split_sentences(self, text: str) -> List[str]:
    """답변을 문장 단위로 분리

    한글/영문 문장 구분 고려:
    - 마침표(.), 물음표(?), 느낌표(!)
    - 단, "Dr.", "Mr.", "etc." 등은 제외
    """

    # 간단한 정규식 기반 분리
    # 향후 KSS(Korean Sentence Splitter) 또는 NLTK 사용 고려

    # 1. 특수 케이스 보호 (Dr., Mr. 등)
    text = re.sub(r'(Dr|Mr|Ms|Mrs|etc)\.', r'\1<DOT>', text)

    # 2. 문장 분리 (., ?, !)
    sentences = re.split(r'([.!?])\s+', text)

    # 3. 재조합
    result = []
    for i in range(0, len(sentences)-1, 2):
        sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else '')
        result.append(sentence)

    # 마지막 문장 추가
    if len(sentences) % 2 == 1:
        result.append(sentences[-1])

    # 4. <DOT> 복원
    result = [s.replace('<DOT>', '.') for s in result]

    return [s.strip() for s in result if s.strip()]
```

**출처 찾기 (Semantic Similarity)**:
```python
def _find_best_source_for_sentence(self, sentence: str, sources: List[Document]) -> Optional[Document]:
    """문장과 가장 관련된 출처 찾기

    방법:
    1. 문장과 각 출처의 코사인 유사도 계산
    2. 가장 유사도가 높은 출처 선택
    3. 유사도가 임계값(0.5) 이하면 None 반환
    """

    if not sources:
        return None

    # 1. 문장 임베딩
    sentence_embedding = self._embed_text(sentence)

    # 2. 각 출처와 유사도 계산
    best_source = None
    best_similarity = 0.0

    for source in sources:
        # 출처 텍스트 임베딩
        source_text = source.page_content[:500]  # 처음 500자만 (성능 최적화)
        source_embedding = self._embed_text(source_text)

        # 코사인 유사도
        similarity = self._cosine_similarity(sentence_embedding, source_embedding)

        if similarity > best_similarity and similarity > 0.5:  # 임계값
            best_similarity = similarity
            best_source = source

    return best_source
```

**임베딩 및 유사도**:
```python
def _embed_text(self, text: str) -> np.ndarray:
    """텍스트를 임베딩 벡터로 변환

    기존 vectorstore의 임베딩 모델 재사용
    """

    # VectorStoreManager의 임베딩 모델 사용
    embedding_model = self.vectorstore.embeddings

    try:
        # 텍스트 임베딩
        embedding = embedding_model.embed_query(text)
        return np.array(embedding)
    except Exception as e:
        print(f"    ⚠️ 임베딩 실패: {e}")
        return np.zeros(1024)  # 기본 차원 (mxbai-embed-large)

def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
    """코사인 유사도 계산"""

    # 영벡터 체크
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    # 코사인 유사도
    similarity = np.dot(vec1, vec2) / (norm1 * norm2)

    return float(similarity)
```

**출처 포맷팅**:
```python
def _format_citation(self, source: Document) -> str:
    """출처를 NotebookLM 스타일로 포맷

    형식: [파일명, p.페이지, 신뢰도: 점수]
    """

    # 메타데이터 추출
    file_name = source.metadata.get('file_name', 'Unknown')
    page = source.metadata.get('page', '?')
    score = source.metadata.get('score', 0.0)

    # 짧은 파일명 추출 (확장자 제거)
    short_name = file_name.rsplit('.', 1)[0]

    # 너무 길면 자르기 (30자 제한)
    if len(short_name) > 30:
        short_name = short_name[:27] + "..."

    # 출처 포맷
    citation = f"[{short_name}, p.{page}, 신뢰도: {score:.1f}]"

    return citation
```

#### 3. 구현 단계

**Day 1: 핵심 로직 구현** (4-5시간)
- ✅ `_split_sentences()` 구현 및 테스트
- ✅ `_embed_text()` 구현 (기존 모델 활용)
- ✅ `_cosine_similarity()` 구현
- ✅ `_find_best_source_for_sentence()` 구현
- ✅ 단위 테스트 작성

**Day 2: 출처 생성 및 포맷팅** (4-5시간)
- ✅ `_format_citation()` 구현
- ✅ `_generate_source_citations()` 구현
- ✅ 기존 `generate_answer()` 메서드에 통합
- ✅ 단위 테스트 작성

**Day 3: 통합 테스트 및 최적화** (4-5시간)
- ✅ 전체 플로우 테스트
- ✅ 출처 정확도 측정 (목표: 95%)
- ✅ 성능 최적화 (캐싱, 배치 처리)
- ✅ 문서화

#### 4. 검증 기준

**정량적 지표**:
- ✅ 출처 정확도: 95% 이상
  - 100개 문장 샘플 테스트
  - 사람이 수동으로 출처 검증
  - 일치율 계산

- ✅ 출처 커버리지: 90% 이상
  - 답변의 90% 이상 문장에 출처 표시
  - 나머지 10%는 연결어, 일반 문장 등

- ✅ 성능 영향: +20% 이내
  - 출처 생성으로 인한 추가 시간
  - 임베딩 캐싱으로 최소화

**정성적 지표**:
- ✅ 사용자 만족도: 설문조사 (Phase A 완료 후)
- ✅ Hallucination 감지: 출처 없는 문장 쉽게 식별

#### 5. 예상 소요 시간

- Day 1: 4-5시간
- Day 2: 4-5시간
- Day 3: 4-5시간
- **총 소요 시간**: **3일** (12-15시간)

---

## A-3: Answer Verification 개선

### 문제 정의

**현재 상황**:
```
Query: "kFRET 값은?"
1차 답변 생성: "정보를 찾을 수 없습니다" (금지 구문 사용)
→ 검증 실패
→ 2차 재생성 (10-15초 추가 소요)
→ 성공

문제점:
1. 재생성 빈도 ~20% (5개 중 1개)
2. 추가 LLM 호출 비용
3. 응답 시간 증가
```

**목표**:
- 재생성 빈도 50% 감소 (20% → 10%)
- 응답 시간 10-15초 단축

### 구현 계획

#### 1. 개선안 1: Prompt Engineering 강화

**파일 위치**: `utils/rag_chain.py`
**수정 대상**: `base_prompt_template`

**Before** (현재):
```python
⚠️ 중요 규칙:
1. **문서 우선 원칙**: 반드시 제공된 문서에서 정보를 찾아 답변하세요.
2. **일반 지식 금지**: 문서에 없는 내용은 절대 추측하거나 일반 지식으로 답변하지 마세요.
3. **정보 없음 금지**: 문서가 제공된 경우 "정보를 찾을 수 없습니다"는 절대 사용하지 마세요.
4. **문서 인용 의무**: 답변할 때 반드시 문서의 구체적 내용을 인용하세요.
```

**After** (개선):
```python
⚠️ 핵심 규칙 (반드시 준수):

1. **문서 기반 답변**: 제공된 문서 내용만 사용하여 답변하세요.

2. **금지 표현** (절대 사용 금지):
   ❌ "정보를 찾을 수 없습니다"
   ❌ "문서에 없습니다"
   ❌ "확인할 수 없습니다"
   ❌ "제공된 문서에서는 해당 정보를 찾을 수 없습니다"

3. **권장 표현** (대신 사용):
   ✅ "제공된 문서에 따르면, [구체적 정보]..."
   ✅ "문서 #1의 5페이지에서 [내용]을 확인할 수 있습니다"
   ✅ "직접적인 수치는 명시되어 있지 않지만, 관련 정보로는 [내용]이 있습니다"
   ✅ "[문서]에서 [내용]을 언급하고 있습니다"

4. **NotebookLM 스타일 답변 예시**:
   "According to the provided document (HF_OLED.pptx, slide 5), the kFRET value is approximately 87.8%."
   → "제공된 문서(HF_OLED.pptx, 슬라이드 5)에 따르면, kFRET 값은 약 87.8%입니다."

5. **출처 명시 의무**:
   - 모든 사실에 출처 표시: [파일명, 페이지, 신뢰도]
   - 추측이나 일반 지식 절대 금지
```

**구현 시간**: 30분

#### 2. 개선안 2: Self-Consistency Check

**파일 위치**: `utils/rag_chain.py`
**새 메서드**: `_generate_with_self_consistency()`

**핵심 아이디어**:
- 같은 질문에 대해 N회(기본 3회) 독립적으로 답변 생성
- 답변들 간 일관성 점수 계산
- 일관성 높으면 → 신뢰도 높음, 가장 상세한 답변 선택
- 일관성 낮으면 → 신뢰도 낮음, 경고 표시

**구현 코드**:
```python
def _generate_with_self_consistency(self, question: str, context: str, n: int = 3) -> Dict[str, Any]:
    """여러 번 생성 후 일관성 검증

    Args:
        question: 사용자 질문
        context: 검색된 문맥
        n: 생성 횟수 (기본 3회)

    Returns:
        {
            'answer': 최종 답변,
            'consistency': 일관성 점수 (0-1),
            'variants': 생성된 답변들
        }
    """

    print(f"  🔄 Self-consistency check: {n}회 생성 중...")

    # 1. N번 독립적으로 답변 생성
    original_temp = self.temperature
    self.temperature = 0.5  # 약간 다양성 추가

    answers = []
    for i in range(n):
        answer = self._generate_answer_internal(question, context)
        answers.append(answer)
        print(f"    ✓ {i+1}번째 생성 완료 ({len(answer)} chars)")

    self.temperature = original_temp

    # 2. 답변 간 일관성 점수 계산
    consistency_score = self._calculate_answer_consistency(answers)
    print(f"  📊 일관성 점수: {consistency_score:.2%}")

    # 3. 일관성에 따라 처리
    if consistency_score > 0.8:
        # 높은 일관성: 가장 상세한 답변 선택
        best_answer = max(answers, key=lambda a: len(a))
        print(f"  ✅ 높은 일관성: 최상 답변 선택")

    elif consistency_score > 0.5:
        # 중간 일관성: 공통 정보 추출
        best_answer = self._extract_common_info(answers)
        best_answer = f"⚠️ 중간 신뢰도 (일관성: {consistency_score:.1%})\n\n{best_answer}"
        print(f"  ⚠️ 중간 일관성: 공통 정보 추출")

    else:
        # 낮은 일관성: 경고와 함께 첫 번째 답변
        best_answer = f"⚠️ 낮은 신뢰도 (일관성: {consistency_score:.1%})\n제공된 문서에서 명확한 답변을 찾기 어렵습니다.\n\n{answers[0]}"
        print(f"  ⚠️ 낮은 일관성: 경고 표시")

    return {
        'answer': best_answer,
        'consistency': consistency_score,
        'variants': answers
    }

def _calculate_answer_consistency(self, answers: List[str]) -> float:
    """답변들 간의 일관성 점수 계산 (Jaccard 유사도)"""

    from itertools import combinations

    if len(answers) < 2:
        return 1.0

    # 모든 쌍의 유사도 계산
    similarities = []
    for ans1, ans2 in combinations(answers, 2):
        # 단어 기반 Jaccard 유사도
        words1 = set(ans1.lower().split())
        words2 = set(ans2.lower().split())

        if len(words1) == 0 and len(words2) == 0:
            similarity = 1.0
        elif len(words1) == 0 or len(words2) == 0:
            similarity = 0.0
        else:
            intersection = words1 & words2
            union = words1 | words2
            similarity = len(intersection) / len(union)

        similarities.append(similarity)

    return sum(similarities) / len(similarities)

def _extract_common_info(self, answers: List[str]) -> str:
    """여러 답변에서 공통 정보 추출 (빈도 기반)"""

    # 각 답변을 문장 단위로 분리
    all_sentences = []
    for answer in answers:
        sentences = [s.strip() for s in answer.split('.') if s.strip()]
        all_sentences.extend(sentences)

    # 가장 빈번한 문장들 선택
    from collections import Counter
    sentence_counts = Counter(all_sentences)

    # 2개 이상 답변에 등장하거나, 50% 이상 답변에 등장
    common_sentences = [
        sentence for sentence, count in sentence_counts.items()
        if count >= 2 or count >= len(answers) * 0.5
    ]

    if common_sentences:
        return '. '.join(common_sentences[:5]) + '.'
    else:
        # 공통 정보가 없으면 첫 번째 답변 반환
        return answers[0]
```

**사용 방법**:
```python
# RAGChain __init__에 설정 추가
self.enable_self_consistency = config.get('enable_self_consistency', False)
self.self_consistency_n = config.get('self_consistency_n', 3)

# generate_answer()에서 옵션으로 사용
if self.enable_self_consistency:
    result = self._generate_with_self_consistency(question, context, n=self.self_consistency_n)
    answer = result['answer']
    # 일관성 점수를 메타데이터로 저장
    self._last_consistency_score = result['consistency']
else:
    answer = self._generate_answer_internal(question, context)
```

**트레이드오프**:
- ✅ 장점: 재생성 빈도 50% 감소, 신뢰도 향상
- ❌ 단점: 응답 시간 N배 증가 (3회 생성 시 3배)
- 💡 해결: **선택적 적용** (모호한 질문에만)

**선택적 적용 로직**:
```python
def _should_use_self_consistency(self, question: str, context: str) -> bool:
    """Self-consistency가 필요한지 판단"""

    # 1. 질문 복잡도가 높으면
    complexity = self._analyze_question_complexity(question)
    if complexity > 0.7:
        return True

    # 2. 검색 결과 점수가 낮으면 (애매한 검색 결과)
    if hasattr(self, '_last_retrieved_docs'):
        avg_score = np.mean([doc.metadata.get('score', 0) for doc in self._last_retrieved_docs])
        if avg_score < 500:  # 임계값
            return True

    # 3. 질문에 "정확히", "확실히" 등 키워드 포함 시
    precision_keywords = ["정확히", "확실히", "명확히", "구체적으로"]
    if any(kw in question for kw in precision_keywords):
        return True

    return False
```

#### 3. 구현 단계

**Day 1: Prompt 개선** (2시간)
- ✅ 새 프롬프트 템플릿 작성
- ✅ A/B 테스트 (기존 vs 개선)
- ✅ 재생성 빈도 측정

**Day 2: Self-Consistency 구현** (6-7시간)
- ✅ `_generate_with_self_consistency()` 구현
- ✅ `_calculate_answer_consistency()` 구현
- ✅ `_extract_common_info()` 구현
- ✅ `_should_use_self_consistency()` 구현 (선택적 적용)
- ✅ 단위 테스트 작성

**Day 3: 통합 및 최적화** (3-4시간)
- ✅ 전체 플로우 테스트
- ✅ 성능 측정 (응답 시간, 재생성 빈도)
- ✅ 최적화 (병렬 생성 고려)
- ✅ 문서화

#### 4. 검증 기준

**정량적 지표**:
- ✅ 재생성 빈도: 20% → 10% (50% 감소)
- ✅ 평균 응답 시간: 92초 → 77-82초 (10-15초 단축)
  - Prompt 개선: -5-8초
  - Self-consistency (선택적 적용): -5-7초 (재생성 감소)

**정성적 지표**:
- ✅ 금지 구문 사용 빈도: 80% 감소
- ✅ 답변 품질: 사용자 만족도 조사

#### 5. 예상 소요 시간

- Day 1: 2시간
- Day 2: 6-7시간
- **총 소요 시간**: **2일** (11-12시간)

---

## 테스트 계획

### 1. 단위 테스트

**파일**: `tests/test_phase_a.py`

```python
import pytest
from utils.rag_chain import RAGChain

class TestPhaseA:
    """Phase A 개선사항 단위 테스트"""

    @pytest.fixture
    def rag_chain(self):
        """RAGChain 인스턴스 생성"""
        # 테스트용 설정
        config = {...}
        return RAGChain(vectorstore, **config)

    # A-1: Standard 모드 카테고리 필터링
    def test_standard_mode_category_filtering(self, rag_chain):
        """Standard 모드에서 카테고리 필터링 확인"""
        question = "FRET 에너지 전달 효율은?"
        result = rag_chain.generate_answer(question)

        # HR 문서 혼입 없음
        categories = [s.metadata.get('category') for s in result['sources']]
        assert 'hr' not in categories

    # A-2: Source Citation
    def test_source_citation_accuracy(self, rag_chain):
        """출처 표시 정확도 확인"""
        question = "kFRET 값은?"
        result = rag_chain.generate_answer(question)
        answer = result['answer']

        # 출처 포맷 확인
        assert '[' in answer and ']' in answer  # 인라인 출처 존재
        assert '신뢰도:' in answer or 'confidence:' in answer.lower()

        # 출처 개수 확인 (최소 1개)
        citation_count = answer.count('[')
        assert citation_count >= 1

    def test_sentence_source_mapping(self, rag_chain):
        """문장-출처 매핑 정확도 확인"""
        # 샘플 답변과 출처
        answer = "TADF는 열 활성화 지연 형광입니다. OLED에 사용됩니다."
        sources = [...]  # 테스트 출처

        # 출처 생성
        cited_answer = rag_chain._generate_source_citations(answer, sources)

        # 각 문장에 출처 표시 확인
        sentences = cited_answer.split('.')
        citation_count = sum(1 for s in sentences if '[' in s and ']' in s)
        assert citation_count >= 1

    # A-3: Answer Verification
    def test_prompt_improvement_no_forbidden_phrases(self, rag_chain):
        """개선된 프롬프트로 금지 구문 감소 확인"""
        # 모호한 질문 10개로 테스트
        questions = [
            "kFRET 값은?",
            "양자 효율은?",
            # ... 8개 more
        ]

        forbidden_count = 0
        for q in questions:
            result = rag_chain.generate_answer(q)
            answer = result['answer']

            # 금지 구문 체크
            forbidden_phrases = ["정보를 찾을 수 없습니다", "문서에 없습니다"]
            if any(phrase in answer for phrase in forbidden_phrases):
                forbidden_count += 1

        # 금지 구문 사용 빈도 < 10% (10개 중 1개 미만)
        assert forbidden_count < 1

    def test_self_consistency(self, rag_chain):
        """Self-consistency 기능 확인"""
        question = "TADF의 양자 효율은?"
        context = "..."

        result = rag_chain._generate_with_self_consistency(question, context, n=3)

        # 결과 구조 확인
        assert 'answer' in result
        assert 'consistency' in result
        assert 'variants' in result

        # 일관성 점수 범위 확인 (0-1)
        assert 0 <= result['consistency'] <= 1

        # 변형 개수 확인
        assert len(result['variants']) == 3
```

### 2. 통합 테스트

**파일**: `tests/test_phase_a_integration.py`

```python
class TestPhaseAIntegration:
    """Phase A 통합 테스트"""

    def test_full_pipeline_with_phase_a(self):
        """Phase A 적용된 전체 파이프라인 테스트"""

        # 1. 질문 준비
        test_queries = [
            # OLED 기술 질문 (technical)
            "TADF 재료의 양자 효율은?",
            "FRET 에너지 전달 효율은?",
            "kFRET 값은?",

            # 비즈니스 질문 (business)
            "LG디스플레이의 OLED 시장 동향은?",

            # HR 질문 (hr)
            "HRD-Net 출결 관리 방법은?",
        ]

        # 2. 각 질문 테스트
        for question in test_queries:
            result = rag_chain.generate_answer(question)

            # A-1: 카테고리 필터링 확인
            categories = [s.metadata.get('category') for s in result['sources']]
            assert len(set(categories)) <= 2  # 최대 2개 카테고리

            # A-2: 출처 표시 확인
            assert '[' in result['answer']  # 인라인 출처

            # A-3: 금지 구문 없음
            forbidden_phrases = ["정보를 찾을 수 없습니다", "문서에 없습니다"]
            assert not any(phrase in result['answer'] for phrase in forbidden_phrases)

    def test_cross_domain_contamination_zero(self):
        """크로스 도메인 오염 0% 확인"""

        # OLED 기술 질문 20개
        oled_queries = [...]  # 20개 질문

        hr_contamination = 0
        total_sources = 0

        for q in oled_queries:
            result = rag_chain.generate_answer(q)
            sources = result['sources']

            for s in sources:
                total_sources += 1
                if s.metadata.get('category') == 'hr':
                    hr_contamination += 1

        # 오염률 0%
        contamination_rate = hr_contamination / total_sources
        assert contamination_rate == 0.0
```

### 3. 성능 테스트

**파일**: `tests/test_phase_a_performance.py`

```python
import time

class TestPhaseAPerformance:
    """Phase A 성능 테스트"""

    def test_response_time_improvement(self):
        """응답 시간 개선 확인"""

        questions = [...]  # 테스트 질문 20개

        # Before Phase A (v3.1 baseline)
        baseline_times = []
        for q in questions:
            start = time.time()
            rag_chain_baseline.generate_answer(q)
            elapsed = time.time() - start
            baseline_times.append(elapsed)

        # After Phase A
        phase_a_times = []
        for q in questions:
            start = time.time()
            rag_chain_phase_a.generate_answer(q)
            elapsed = time.time() - start
            phase_a_times.append(elapsed)

        # 평균 응답 시간 비교
        avg_baseline = sum(baseline_times) / len(baseline_times)
        avg_phase_a = sum(phase_a_times) / len(phase_a_times)

        # 10-15초 단축 확인
        improvement = avg_baseline - avg_phase_a
        assert improvement >= 10, f"응답 시간 개선: {improvement:.1f}초 (목표: 10초 이상)"

    def test_source_citation_overhead(self):
        """Source Citation 오버헤드 측정"""

        # Without citation
        start = time.time()
        result_no_citation = rag_chain.generate_answer(question, enable_citation=False)
        time_no_citation = time.time() - start

        # With citation
        start = time.time()
        result_with_citation = rag_chain.generate_answer(question, enable_citation=True)
        time_with_citation = time.time() - start

        # 오버헤드 20% 이내
        overhead = (time_with_citation - time_no_citation) / time_no_citation
        assert overhead <= 0.2, f"Citation 오버헤드: {overhead:.1%} (목표: 20% 이내)"
```

### 4. Baseline 테스트

**목적**: Phase A 적용 전후 비교를 위한 Baseline 성능 측정

**파일**: `test_phase_a_baseline.py`

```python
"""
Phase A Baseline 테스트
Phase A 구현 전 현재 성능 측정
"""
import json
import time
from datetime import datetime

def run_baseline_test():
    """Baseline 성능 측정"""

    # 테스트 쿼리 (다양한 난이도)
    test_queries = {
        "easy": [
            "TADF란 무엇인가?",
            "LG디스플레이 본사는 어디인가?",
            "HRD-Net이란?"
        ],
        "medium": [
            "TADF 재료의 양자 효율은 얼마인가?",
            "FRET 에너지 전달 효율은?",
            "LG디스플레이의 OLED 시장 동향은?"
        ],
        "hard": [
            "TADF와 OLED 효율의 관계를 설명해줘",
            "분자 구조와 성능의 관계는?",
            "8.6세대 IT OLED 생산라인의 특징과 LG디스플레이 전략을 연결해서 설명해줘"
        ]
    }

    results = {
        "timestamp": datetime.now().isoformat(),
        "version": "v3.1 (before Phase A)",
        "metrics": {}
    }

    # 각 난이도별 테스트
    for difficulty, queries in test_queries.items():
        print(f"\n{'='*60}")
        print(f"난이도: {difficulty.upper()}")
        print(f"{'='*60}")

        difficulty_results = []

        for i, query in enumerate(queries, 1):
            print(f"\n[Query {i}/{len(queries)}] {query}")

            # 성능 측정
            start_time = time.time()
            result = rag_chain.generate_answer(query)
            elapsed_time = time.time() - start_time

            # 메트릭 수집
            sources = result.get('sources', [])
            answer = result.get('answer', '')

            # 카테고리 오염 체크
            categories = [s.metadata.get('category', 'unknown') for s in sources]
            category_purity = calculate_category_purity(query, categories)

            # 출처 표시 확인
            has_inline_citation = '[' in answer and ']' in answer
            citation_count = answer.count('[')

            # 금지 구문 체크
            forbidden_phrases = ["정보를 찾을 수 없습니다", "문서에 없습니다", "확인할 수 없습니다"]
            has_forbidden_phrase = any(phrase in answer for phrase in forbidden_phrases)

            # 재생성 여부 (로그에서 확인 필요)
            # 실제로는 RAGChain에 카운터 추가 필요

            query_result = {
                "query": query,
                "elapsed_time": elapsed_time,
                "num_sources": len(sources),
                "categories": categories,
                "category_purity": category_purity,
                "has_inline_citation": has_inline_citation,
                "citation_count": citation_count,
                "has_forbidden_phrase": has_forbidden_phrase,
                "answer_length": len(answer)
            }

            difficulty_results.append(query_result)

            # 출력
            print(f"  시간: {elapsed_time:.2f}초")
            print(f"  출처: {len(sources)}개")
            print(f"  카테고리: {categories}")
            print(f"  카테고리 순도: {category_purity:.1%}")
            print(f"  인라인 출처: {'✓' if has_inline_citation else '✗'}")
            print(f"  금지 구문: {'✗ 발견' if has_forbidden_phrase else '✓'}")

        results["metrics"][difficulty] = {
            "queries": difficulty_results,
            "avg_time": sum(r["elapsed_time"] for r in difficulty_results) / len(difficulty_results),
            "avg_sources": sum(r["num_sources"] for r in difficulty_results) / len(difficulty_results),
            "avg_purity": sum(r["category_purity"] for r in difficulty_results) / len(difficulty_results),
            "inline_citation_rate": sum(r["has_inline_citation"] for r in difficulty_results) / len(difficulty_results),
            "forbidden_phrase_rate": sum(r["has_forbidden_phrase"] for r in difficulty_results) / len(difficulty_results)
        }

    # 결과 저장
    output_file = f"test_results/phase_a_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Baseline 테스트 완료!")
    print(f"결과 저장: {output_file}")
    print(f"{'='*60}")

    return results

def calculate_category_purity(query: str, categories: List[str]) -> float:
    """질문에 맞는 카테고리 순도 계산"""

    # 질문 타입 추정
    if any(kw in query.lower() for kw in ['tadf', 'oled', 'fret', 'quantum', '양자', '효율']):
        expected = ['technical', 'business']
    elif any(kw in query.lower() for kw in ['lg디스플레이', '시장', '뉴스']):
        expected = ['business', 'technical']
    elif any(kw in query.lower() for kw in ['hrd', '출결', '교육']):
        expected = ['hr']
    else:
        expected = []  # 모름

    if not expected:
        return 1.0  # 판단 불가능

    # 순도 계산
    match_count = sum(1 for c in categories if c in expected)
    return match_count / len(categories) if categories else 0.0

if __name__ == "__main__":
    run_baseline_test()
```

---

## 예상 성과

### Phase A 완료 후 목표

| 지표 | Before (v3.1) | Target (Phase A) | 개선 |
|------|--------------|-----------------|------|
| **크로스 도메인 오염** | 4.5% (1/22) | **0%** (0/N) | -100% |
| **출처 정확도** | ~60% | **95%** | +58% |
| **출처 커버리지** | ~30% | **90%** | +200% |
| **재생성 빈도** | ~20% | **10%** | -50% |
| **금지 구문 사용** | ~20% | **4%** | -80% |
| **평균 응답 시간** | 92초 | **77-82초** | -10-15초 |
| **사용자 신뢰도** | - | - | **+30%** |

### NotebookLM 비교 (Phase A 후)

| 항목 | NotebookLM | Phase A 목표 | 비고 |
|------|-----------|------------|------|
| **출처 정확도** | 95% | **95%** | 동등 |
| **Hallucination 방지** | 강함 | **강함** | 동등 |
| **크로스 도메인 분리** | - | **100%** | 우위 |
| **대량 문서** | ❌ 약함 | ✅ **강함** | 우위 |

**결론**: Phase A 완료 시 NotebookLM의 핵심 강점(Source Citation) 수준 도달

---

## 다음 단계

### Phase A 완료 후

1. **성능 측정 및 분석** (1일)
   - Before/After 비교
   - 목표 달성 여부 확인
   - 추가 최적화 필요 사항 파악

2. **문서화** (반나절)
   - Phase A 구현 완료 보고서 작성
   - 코드 주석 정리
   - 사용자 가이드 업데이트

3. **Phase B 준비** (1일)
   - Phase B 상세 구현 계획 작성
   - Query Rewriting 설계
   - Confidence Score 설계

---

**작성일**: 2025-11-06
**예상 완료**: 2025-11-13 ~ 2025-11-20
**다음**: Phase B 구현 계획서
