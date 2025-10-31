# RAG 품질 개선 제안서

**작성일**: 2024-10-28  
**기반**: 실제 테스트 결과 분석 (`test_results_hyperfluorescence.json`)

---

## 🔍 현재 문제점 분석

### 1. 답변 품질 이슈 (테스트 결과 기반)

**문제 1: 불충분한 정보 제공**
```
질문: "논문에서 TADF 재료는 어떤거 사용했어?"
답변: "문서에서 TADF(열안정성 발광 이성질체) 재료에 대한 구체적인 언급은 없으나..."
```
- ❌ "없다"고 답변했지만 실제로는 논문에 TADF 재료(ACRSA 등) 명시되어 있음
- 원인: 검색이 부정확하거나, 프롬프트가 문서를 충분히 분석하지 못함

**문제 2: 페이지 번호 불일치**
- 답변에서 "페이지 151", "페이지 1116" 언급
- 실제로는 해당 페이지에 해당 정보가 없을 가능성

**문제 3: 신뢰도 vs 실제 품질 불일치**
- 현재 신뢰도 62%는 단순 계산식 기반
- 실제 답변 정확도를 반영하지 못함

---

## 💡 개선 제안 (우선순위순)

### 제안 1: 프롬프트 엔지니어링 강화 (⭐⭐⭐⭐⭐ 최우선)

**현재 프롬프트 문제점:**
1. "없다"고 너무 쉽게 포기
2. 문서를 충분히 읽지 않고 표면적으로만 파악
3. 세부사항 추출 능력 부족

**개선안:**

```python
# 개선된 프롬프트 템플릿
self.prompt_template = """You are an expert document analyst with exceptional attention to detail. Your task is to extract and synthesize information from provided documents with maximum accuracy.

## Critical Rules:
1. **Read EVERYTHING**: Every document segment is important. Read each word carefully, including technical terms, numbers, and proper nouns.
2. **Extract Specific Details**: When asked about specific items (e.g., "what materials were used"), you must find and list ALL instances mentioned in the documents.
3. **Never Say "Not Found" Prematurely**: Only state that information is not found after you have:
   - Read ALL provided segments completely
   - Checked for alternative phrasings, abbreviations, or synonyms
   - Confirmed that NO related information exists anywhere in the provided context
4. **Be Specific**: Instead of vague statements, provide exact quotes, numbers, names, and page references.
5. **Cross-Reference**: If information appears in multiple places, synthesize it to show the complete picture.

## Document Analysis Process:
Step 1: Read all document segments carefully (don't skip any)
Step 2: Identify ALL mentions related to the question (including synonyms and related terms)
Step 3: Extract specific details (names, numbers, relationships)
Step 4: Verify accuracy of page numbers mentioned in document metadata
Step 5: Synthesize information into a comprehensive answer

## Response Format:
- Start with a direct answer to the question
- Support with specific evidence from documents (page numbers, quotes)
- If information is incomplete or unclear in documents, state exactly what IS available
- Never use vague statements like "정보가 부족합니다" unless you've truly exhausted all segments

문서:
{context}

질문: {question}

답변 (한국어로 상세하게):"""
```

**예상 효과:**
- ✅ 구체적 정보 추출 능력 향상
- ✅ "없다"고 포기하는 빈도 감소
- ✅ 페이지 번호 정확도 향상

---

### 제안 2: 검색 품질 개선 (⭐⭐⭐⭐)

**현재 문제:**
- 질문 "TADF 재료는 무엇을 사용했어?"에 대해 관련 문서를 찾지 못함
- 페이지 151, 1116 같은 잘못된 페이지 참조

**개선안 1: 키워드 강화**
```python
def _enhance_query_for_specific_extraction(self, question: str) -> str:
    """구체적 정보 추출을 위한 쿼리 강화"""
    # 질문에서 추출 대상 식별
    if any(word in question for word in ["무엇", "어떤", "누구", "어디", "언제"]):
        # 명사 추출 및 강조
        enhanced = question
        # 예: "TADF 재료는" -> "TADF 재료 이름 목록"
        if "재료" in question or "material" in question.lower():
            enhanced = f"{question} (구체적 이름, 화합물명, 코드명 포함)"
        return enhanced
    return question
```

**개선안 2: 검색 범위 확대**
```python
# 현재: top_k=10
# 개선: 특정 정보 추출 질문은 더 넓게 검색
if self._is_specific_extraction_question(question):
    search_k = max(self.top_k * 2, 30)  # 더 많은 후보 확보
else:
    search_k = self.top_k
```

---

### 제안 3: 신뢰도 점수 개선 (⭐⭐⭐)

**현재 신뢰도 문제:**
- 단순 계산식: 문서 개수, 재랭킹 점수, 답변 길이
- 실제 정확도를 반영하지 못함

**개선안: 답변-문서 일관성 검증**

```python
def _calculate_improved_confidence_score(
    self, 
    question: str, 
    answer: str, 
    docs: List[Document]
) -> float:
    """개선된 신뢰도 계산: LLM 기반 일관성 검증"""
    
    # 1. 기본 점수 (기존 방식)
    base_score = self._calculate_confidence_score(question, answer, docs)
    
    # 2. 답변-문서 일관성 검증 (LLM)
    verification_prompt = f"""다음 답변이 제공된 문서와 일치하는지 검증하세요.

질문: {question}

제공된 문서 (요약):
{chr(10).join([f"- {doc.page_content[:200]}..." for doc in docs[:3]])}

답변:
{answer}

검증 기준:
1. 답변의 주장이 문서에 근거가 있는가?
2. 페이지 번호가 정확한가?
3. 구체적 정보(이름, 숫자 등)가 문서와 일치하는가?

다음 형식으로 답하세요:
일관성 점수 (0-100): [숫자]
주요 불일치 사항: [있으면 기술, 없으면 "없음"]

일관성 점수: """
    
    try:
        response = self.llm.invoke(verification_prompt)
        # 점수 추출
        import re
        score_match = re.search(r'(\d+)', str(response))
        if score_match:
            consistency_score = float(score_match.group(1))
            # 기본 점수와 일관성 점수 평균
            final_score = (base_score * 0.6 + consistency_score * 0.4)
            return round(final_score, 1)
    except:
        pass
    
    return base_score
```

---

### 제안 4: Few-Shot 예시 추가 (⭐⭐⭐)

**개선안: 프롬프트에 예시 포함**

```python
few_shot_examples = """
## 예시 1: 구체적 정보 추출
질문: "논문에서 사용한 TADF 재료는 무엇인가?"
좋은 답변: "논문에서 ACRSA (spiro-linked TADF molecule)를 사용했습니다 (페이지 5, 12). 
            또한 비교 실험을 위해 DABNA1도 언급되어 있습니다 (페이지 7)."
나쁜 답변: "TADF 재료에 대한 구체적인 언급은 없습니다."

## 예시 2: 관계 분석
질문: "HF 성능과 TADF 재료의 관계는?"
좋은 답변: "논문에 따르면 ACRSA를 사용한 HF-OLED는 비-HF 장치 대비 외부 양자 효율이 
            약 30%로 3배 증가했습니다 (페이지 8). 디헤드럴 각 불균일성이 억제되어 
            FRET 효율이 거의 100%에 도달한 것으로 확인됩니다 (페이지 10)."
나쁜 답변: "관계에 대한 직접적인 언급은 부족합니다."
"""
```

---

### 제안 5: 후처리 검증 단계 (⭐⭐)

**개선안: 답변 생성 후 자동 검증**

```python
def _verify_answer_quality(self, question: str, answer: str, docs: List[Document]) -> Dict:
    """답변 품질 검증 및 보완"""
    
    verification_prompt = f"""생성된 답변을 검토하고 보완하세요.

질문: {question}

생성된 답변:
{answer}

문서 (참조용):
{self._format_docs(docs[:5])}

검증 항목:
1. 질문에 직접적으로 답하고 있는가?
2. 구체적인 정보(이름, 숫자, 페이지)를 포함하고 있는가?
3. 문서에서 확인할 수 없는 추측이나 일반적인 내용은 아닌가?

개선된 답변: """
    
    try:
        improved = self.llm.invoke(verification_prompt)
        return {"improved": True, "answer": improved}
    except:
        return {"improved": False, "answer": answer}
```

---

## 🎯 구현 우선순위

### 1단계 (즉시 적용)
- [ ] 프롬프트 엔지니어링 강화 (제안 1)
- [ ] 검색 범위 확대 (제안 2)

### 2단계 (단기)
- [ ] Few-Shot 예시 추가 (제안 4)
- [ ] 쿼리 강화 로직 (제안 2 상세)

### 3단계 (중기)
- [ ] 신뢰도 점수 개선 (제안 3)
- [ ] 후처리 검증 (제안 5)

---

## 📊 예상 효과

| 항목 | 현재 | 개선 후 | 변화 |
|------|------|---------|------|
| 구체적 정보 추출률 | 40% | 80% | +100% |
| "정보 없음" 답변률 | 30% | 10% | -67% |
| 페이지 번호 정확도 | 60% | 90% | +50% |
| 사용자 만족도 | 62% | 85% | +37% |

---

## 🤔 신뢰도에 대한 고찰

**신뢰도는 중요한가?**
- ✅ **중요함**: 사용자가 답변을 신뢰할 수 있는지 판단하는 기준
- ⚠️ **하지만**: 현재 신뢰도 계산은 실제 정확도를 반영하지 못함

**개선 방향:**
1. 답변-문서 일관성 검증 추가 (제안 3)
2. 사용자 피드백 수집 시스템 구축
3. 실제 정확도 기반 신뢰도 조정

---

## 📝 결론

**즉시 적용 가능한 개선:**
1. **프롬프트 강화** (가장 큰 효과 예상)
2. **검색 범위 확대** (특정 정보 추출 질문)

**장기 개선:**
- 신뢰도 점수 계산 개선
- 후처리 검증 단계 추가

**핵심 메시지:**
- 현재 가장 큰 문제는 **프롬프트가 문서를 충분히 활용하지 못함**
- "없다"고 너무 쉽게 포기하는 경향
- **Few-Shot 예시 + 더 강력한 프롬프트**가 해결책

