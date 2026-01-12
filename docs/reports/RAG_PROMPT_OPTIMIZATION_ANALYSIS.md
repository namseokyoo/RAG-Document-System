# RAG 시스템 프롬프트 최적화 비교 분석 보고서

**작성일**: 2025-12-07  
**목적**: 현재 시스템의 프롬프트를 웹 검색 기반 최적화 사례와 비교하여 개선 방안 제시

---

## 목차

1. [개요](#개요)
2. [파이프라인 노드별 프롬프트 분석](#파이프라인-노드별-프롬프트-분석)
3. [최적화 사례 비교](#최적화-사례-비교)
4. [개선 방안](#개선-방안)
5. [구현 우선순위](#구현-우선순위)

---

## 개요

### 현재 시스템 프롬프트 구조

현재 시스템은 다음 6가지 주요 프롬프트를 사용합니다:

1. **답변 생성 프롬프트** (`base_prompt_template` + 질문 타입별 템플릿)
2. **질문 분류 프롬프트** (`question_classifier`)
3. **Multi-Query 생성 프롬프트** (`generate_rewritten_queries`)
4. **HyDE 프롬프트** (`_generate_hypothetical_document`)
5. **Query Decomposition 프롬프트** (`_decompose_question`)
6. **번역 프롬프트** (`_translate_to_english`)

---

## 파이프라인 노드별 프롬프트 분석

### 1. 답변 생성 프롬프트 (Response Generation)

#### 현재 프롬프트 구조

**위치**: `utils/rag_chain.py::base_prompt_template` (라인 261-311)

**특징**:
- ✅ Few-shot 예시 포함 (5개)
- ✅ 수식/기호 정확 인용 지시
- ✅ 언어 일치 지시 (한/영)
- ✅ 출처 표시 가이드라인
- ✅ 문서 기반 답변 강제
- ❌ 단계별 추론(Chain of Thought) 미포함
- ❌ 명확한 답변 절차 지시 부족

**현재 프롬프트**:
```
You are a document-based AI assistant. Provide accurate and useful answers based on the provided documents.

Provided documents:
{context}

Previous conversation:
{chat_history}

Question:
{question}

---

Answer guidelines:

1. **Natural format**: ...
2. **Source indication**: ...
3. **Examples**: ...
4. **Important**: ...
```

#### 최적화 사례 비교

**웹 검색 결과 - 최적화된 프롬프트 패턴**:

1. **단계별 추론 유도**:
   ```
   "질문에 답하기 전에 다음 단계를 순서대로 수행하세요:
   1. 질문의 의미를 분석합니다.
   2. 관련된 문맥을 찾습니다.
   3. 답변을 작성합니다."
   ```

2. **문서 우선 원칙 강화**:
   ```
   "⚠️ 중요 규칙:
   1. **문서 우선 원칙**: 반드시 제공된 문서에서 정보를 찾아 답변하세요.
   2. **일반 지식 금지**: 문서에 없는 내용은 절대 추측하거나 일반 지식으로 답변하지 마세요.
   3. **금지 표현**: 다음 표현은 절대 사용하지 마세요:
      ❌ "정보를 찾을 수 없습니다"
      ❌ "문서에 없습니다"
   ```

3. **NotebookLM 스타일 출처 표시**:
   ```
   "According to the provided document [파일명, 페이지], [구체적 정보]..."
   ```

#### 비교 분석

| 항목 | 현재 시스템 | 최적화 사례 | 개선 필요도 |
|------|------------|------------|------------|
| 단계별 추론 | ❌ 없음 | ✅ 명확한 3단계 절차 | 🔴 높음 |
| 문서 우선 강조 | ⚠️ 보통 | ✅ 매우 강조 (금지 표현 명시) | 🟡 중간 |
| 출처 표시 형식 | ✅ 자연스러운 언급 | ✅ NotebookLM 스타일 (페이지 번호 포함) | 🟡 중간 |
| Few-shot 예시 | ✅ 5개 | ✅ 3-5개 (일반적) | ✅ 적절 |
| 수식 정확도 | ✅ 강조 | ⚠️ 명시적 지시 없음 | ✅ 우수 |

---

### 2. 질문 분류 프롬프트 (Question Classification)

#### 현재 프롬프트 구조

**위치**: `utils/question_classifier.py::_classify_by_llm` (라인 399-445)

**특징**:
- ✅ JSON 출력 형식 명시
- ✅ 4가지 질문 타입 정의 (simple, normal, complex, exhaustive)
- ✅ Few-shot 예시 포함
- ✅ 모호도 분석 포함
- ✅ Multi-Query 필요성 판단 포함
- ❌ 분류 기준이 다소 추상적
- ❌ 도메인별 특화 부족

**현재 프롬프트**:
```
Classify the following question and translate it to English if it's not already in English:

Question: "{question}"

Classification criteria:
1. **simple** (simple fact question) ...
2. **normal** (general question) ...
3. **complex** (complex question) ...
4. **exhaustive** (exhaustive question) ...

**Output ONLY in JSON format** (no other text):
{
    "type": "simple",
    "confidence": 0.95,
    ...
}
```

#### 최적화 사례 비교

**웹 검색 결과 - 질문 분석 프롬프트**:

1. **핵심 키워드 추출 강조**:
   ```
   "사용자가 입력한 질문에서 핵심 키워드를 추출하고, 
   이를 기반으로 검색에 적합한 쿼리 문장을 생성하세요."
   ```

2. **다중 질문 분리**:
   ```
   "만약 여러 개의 질문이 포함되어 있다면 각각을 별도의 질문으로 분리하여 처리하세요."
   ```

#### 비교 분석

| 항목 | 현재 시스템 | 최적화 사례 | 개선 필요도 |
|------|------------|------------|------------|
| 키워드 추출 | ⚠️ 간접적 (번역 포함) | ✅ 명시적 지시 | 🟡 중간 |
| 다중 질문 분리 | ❌ 없음 | ✅ 명시적 지시 | 🔴 높음 |
| JSON 출력 | ✅ 명확 | ✅ 일반적 | ✅ 적절 |
| 질문 타입 분류 | ✅ 상세 | ⚠️ 기본적 | ✅ 우수 |

---

### 3. Multi-Query 생성 프롬프트

#### 현재 프롬프트 구조

**위치**: `utils/rag_chain.py::generate_rewritten_queries` (라인 3163-3186)

**특징**:
- ✅ 5가지 관점 명시 (Technical, Conceptual, Application, Comparative, Problem-solving)
- ✅ Few-shot 예시 포함
- ✅ JSON 출력 형식
- ❌ 관점별 가이드라인이 다소 추상적
- ❌ 원본 쿼리와의 차별화 지시 부족

**현재 프롬프트**:
```
You are a search optimization expert. Rewrite the original query from various perspectives to improve search recall.

**Original query**: "{original_query}"

**Rewriting strategies** (generate 1 for each):
1. **Technical perspective**: Focus on specific technical terms and methodologies
2. **Conceptual perspective**: Focus on abstract concepts and theories
3. **Application perspective**: Focus on real-world use cases and applications
4. **Comparative perspective**: Comparative analysis question format (if applicable)
5. **Problem-solving perspective**: Focus on problem definition and solutions (if applicable)

**Few-shot examples**: ...
**Output format**: JSON list
["query1", "query2", "query3"]
```

#### 최적화 사례 비교

**웹 검색 결과 - 쿼리 변환 프롬프트**:

1. **명확한 변환 목표**:
   ```
   "사용자의 질문을 효과적인 검색 쿼리로 변환하세요.
   검색 효율성을 높이기 위해 핵심 키워드를 포함하세요."
   ```

2. **동의어/유사어 활용**:
   ```
   "기술 용어의 동의어나 유사어를 포함하여 검색 범위를 확장하세요."
   ```

#### 비교 분석

| 항목 | 현재 시스템 | 최적화 사례 | 개선 필요도 |
|------|------------|------------|------------|
| 관점 다양성 | ✅ 5가지 관점 | ⚠️ 기본적 | ✅ 우수 |
| 키워드 확장 | ⚠️ 간접적 | ✅ 명시적 (동의어) | 🟡 중간 |
| Few-shot 예시 | ✅ 포함 | ⚠️ 일반적 | ✅ 적절 |
| 출력 형식 | ✅ JSON | ✅ 일반적 | ✅ 적절 |

---

### 4. HyDE 프롬프트 (Hypothetical Document Embeddings)

#### 현재 프롬프트 구조

**위치**: `utils/rag_chain.py::_generate_hypothetical_document` (라인 3254-3260)

**특징**:
- ✅ 간결하고 명확
- ✅ 키워드 포함 지시
- ❌ 전문성 강조 부족
- ❌ 구체적인 길이 지시 부족
- ❌ 검색 최적화 키워드 강조 부족

**현재 프롬프트**:
```
Write an answer to the following question.
The answer should be professional and specific, and include keywords and concepts useful for search.
Write the answer in 2-3 paragraphs.

Question: {question}

Answer:
```

#### 최적화 사례 비교

**HyDE 논문 기반 최적화**:

1. **검색 최적화 강조**:
   ```
   "질문에 대한 가상의 답변을 작성하세요. 
   이 답변은 검색 시스템에서 관련 문서를 찾는 데 사용되므로,
   핵심 키워드와 전문 용어를 풍부하게 포함해야 합니다."
   ```

2. **구체적 형식 지시**:
   ```
   "답변은 다음 형식을 따르세요:
   - 전문 용어와 기술 개념 명시
   - 수치와 데이터 포함 (가능한 경우)
   - 관련 개념 간의 관계 설명"
   ```

#### 비교 분석

| 항목 | 현재 시스템 | 최적화 사례 | 개선 필요도 |
|------|------------|------------|------------|
| 간결성 | ✅ 우수 | ⚠️ 다소 장황 | ✅ 적절 |
| 검색 최적화 강조 | ⚠️ 보통 | ✅ 매우 강조 | 🟡 중간 |
| 키워드 포함 | ✅ 지시 | ✅ 강조 | ✅ 적절 |
| 전문성 | ⚠️ 간접적 | ✅ 명시적 | 🟡 중간 |

---

### 5. Query Decomposition 프롬프트

#### 현재 프롬프트 구조

**위치**: `utils/rag_chain.py::_decompose_question` (라인 3440-3454)

**특징**:
- ✅ 분해 규칙 명시 (4가지)
- ✅ JSON 출력 형식
- ✅ 하위 질문 수 제한 (2-4개)
- ❌ 분해 기준이 다소 추상적
- ❌ 예시 부족

**현재 프롬프트**:
```
Decompose the following question into independent sub-questions.
Each sub-question should focus on a single topic and maintain the core of the original question.

Original question: {question}

**Decomposition rules**:
1. Each sub-question must be answerable independently
2. Must include all core concepts from the original question
3. Minimize duplication
4. 2-4 sub-questions are appropriate

**Output format**: JSON format
{"sub_questions": ["sub-question 1", "sub-question 2", "sub-question 3"]}
```

#### 최적화 사례 비교

**웹 검색 결과 - 질문 분해 프롬프트**:

1. **Few-shot 예시 포함**:
   ```
   "예시:
   원본: 'OLED 효율과 TADF 재료의 관계는?'
   분해:
   1. OLED 효율이란 무엇인가?
   2. TADF 재료의 특성은?
   3. TADF 재료가 OLED 효율에 미치는 영향은?"
   ```

2. **의존성 명시**:
   ```
   "각 하위 질문은 독립적으로 답변 가능해야 하며,
   원본 질문의 핵심 개념을 모두 포함해야 합니다."
   ```

#### 비교 분석

| 항목 | 현재 시스템 | 최적화 사례 | 개선 필요도 |
|------|------------|------------|------------|
| 분해 규칙 | ✅ 명확 | ✅ 유사 | ✅ 적절 |
| Few-shot 예시 | ❌ 없음 | ✅ 포함 | 🔴 높음 |
| 출력 형식 | ✅ JSON | ✅ 일반적 | ✅ 적절 |
| 하위 질문 수 제한 | ✅ 명시 | ⚠️ 일반적 | ✅ 우수 |

---

### 6. 번역 프롬프트

#### 현재 프롬프트 구조

**위치**: `utils/rag_chain.py::_translate_to_english` (라인 3312-3318)

**특징**:
- ✅ 간결하고 명확
- ✅ 전문 용어 보존 지시
- ✅ 영어면 그대로 반환
- ❌ 번역 품질 지시 부족
- ❌ 컨텍스트 고려 부족

**현재 프롬프트**:
```
Translate the following question to English. 
If the question is already in English, return it as is.
If the question contains technical terms or proper nouns, keep them in their original form.

Question: "{question}"

Translated question (English only, no explanation):
```

#### 최적화 사례 비교

**웹 검색 결과 - 번역 프롬프트**:

1. **의미 보존 강조**:
   ```
   "질문의 의미를 정확히 보존하면서 영어로 번역하세요.
   전문 용어와 고유명사는 원문 그대로 유지하세요."
   ```

2. **자연스러운 표현**:
   ```
   "번역된 질문은 자연스러운 영어 표현이어야 하며,
   검색에 적합한 형식이어야 합니다."
   ```

#### 비교 분석

| 항목 | 현재 시스템 | 최적화 사례 | 개선 필요도 |
|------|------------|------------|------------|
| 간결성 | ✅ 우수 | ⚠️ 다소 장황 | ✅ 적절 |
| 전문 용어 보존 | ✅ 명시 | ✅ 강조 | ✅ 적절 |
| 의미 보존 | ⚠️ 간접적 | ✅ 명시적 | 🟡 중간 |
| 검색 적합성 | ❌ 없음 | ✅ 명시 | 🟡 중간 |

---

## 최적화 사례 비교

### 종합 비교표

| 프롬프트 유형 | 현재 상태 | 최적화 수준 | 주요 개선점 |
|-------------|----------|------------|-----------|
| **답변 생성** | 🟡 양호 | 🔴 개선 필요 | Chain of Thought 추가, 문서 우선 강화 |
| **질문 분류** | 🟢 우수 | 🟡 보완 필요 | 다중 질문 분리, 키워드 추출 강화 |
| **Multi-Query** | 🟢 우수 | 🟡 보완 필요 | 동의어 확장 명시 |
| **HyDE** | 🟡 양호 | 🟡 보완 필요 | 검색 최적화 강조, 전문성 강화 |
| **Query Decomposition** | 🟡 양호 | 🔴 개선 필요 | Few-shot 예시 추가 |
| **번역** | 🟢 우수 | 🟡 보완 필요 | 의미 보존, 검색 적합성 강조 |

---

## 개선 방안

### 1. 답변 생성 프롬프트 개선 (최우선)

#### 개선안 1: Chain of Thought 추가

**현재**:
```
Answer guidelines:
1. **Natural format**: ...
2. **Source indication**: ...
3. **Examples**: ...
4. **Important**: ...
```

**개선안**:
```
Answer guidelines:

**Step-by-step reasoning process** (MUST follow):
1. **Question Analysis**: Analyze what the user is asking for
   - Identify key concepts, entities, and relationships
   - Determine the type of answer needed (factual, explanatory, comparative, etc.)

2. **Context Review**: Review the provided documents
   - Identify which documents contain relevant information
   - Extract specific facts, numbers, formulas, and relationships
   - Note any contradictions or complementary information

3. **Information Integration**: Synthesize information from multiple sources
   - Combine related information logically
   - Prioritize information by relevance to the question
   - Identify gaps where information is missing

4. **Answer Generation**: Write the final answer
   - Use only information from the provided documents
   - Include exact formulas, numbers, and symbols as they appear
   - Cite sources naturally (e.g., "According to Display_1801.pdf, page 5...")
   - Respond in the same language as the question

1. **Natural format**: ...
2. **Source indication**: ...
3. **Examples**: ...
4. **Important**: ...
```

**기대 효과**:
- ✅ 더 체계적인 답변 생성
- ✅ 문서 분석 과정 명확화
- ✅ 정보 누락 방지

#### 개선안 2: 문서 우선 원칙 강화

**추가할 내용**:
```
⚠️ **CRITICAL RULES** (MUST follow):

1. **Document-First Principle**: 
   - ALWAYS answer based ONLY on the provided documents
   - NEVER use general knowledge or assumptions
   - If information is not in the documents, explicitly state: "Not available in the provided documents"

2. **Forbidden Phrases** (DO NOT use):
   ❌ "정보를 찾을 수 없습니다" / "Information not found"
   ❌ "문서에 없습니다" / "Not in the documents"
   ❌ "
   ✅ Instead use: "The provided documents do not contain specific information about [topic]"

3. **Source Attribution Format**:
   - Use: "According to [filename], [specific information]..."
   - Include page/slide numbers when available: "According to Display_1801.pdf (page 5)..."
   - Do NOT use numbered citations: [1], [2], etc.
```

**기대 효과**:
- ✅ 환각(Hallucination) 감소
- ✅ 일관된 출처 표시
- ✅ 사용자 신뢰도 향상

---

### 2. 질문 분류 프롬프트 개선

#### 개선안: 다중 질문 분리 및 키워드 추출 강화

**추가할 내용**:
```
**Pre-processing** (before classification):
1. **Multiple Question Detection**: 
   - If the input contains multiple questions (separated by "?", "and", "또한", etc.), 
     identify each question separately
   - Example: "What is TADF? And how does it work?" → 2 separate questions

2. **Keyword Extraction**:
   - Extract core keywords and technical terms
   - Identify entities (names, places, concepts)
   - Note: Keywords will be used for search optimization

**Classification criteria**: ...
```

**기대 효과**:
- ✅ 복합 질문 처리 개선
- ✅ 검색 정확도 향상

---

### 3. Query Decomposition 프롬프트 개선

#### 개선안: Few-shot 예시 추가

**추가할 내용**:
```
**Few-shot examples**:

Example 1:
Original: "What is the relationship between OLED efficiency and TADF materials?"
Decomposed:
{
  "sub_questions": [
    "What is OLED efficiency?",
    "What are TADF materials?",
    "How do TADF materials affect OLED efficiency?"
  ]
}

Example 2:
Original: "Compare ACRSA and DABNA1 in terms of structure and performance"
Decomposed:
{
  "sub_questions": [
    "What is the structure of ACRSA?",
    "What is the structure of DABNA1?",
    "What is the performance of ACRSA?",
    "What is the performance of DABNA1?"
  ]
}

**Decomposition rules**: ...
```

**기대 효과**:
- ✅ 분해 품질 향상
- ✅ 일관된 형식 유지

---

### 4. HyDE 프롬프트 개선

#### 개선안: 검색 최적화 강조

**개선안**:
```
Write a hypothetical answer to the following question.
This answer will be used to find relevant documents through semantic search,
so it MUST include rich keywords, technical terms, and concepts.

**Requirements**:
1. **Keyword Density**: Include core keywords and their synonyms
2. **Technical Terms**: Use domain-specific terminology
3. **Concepts**: Mention related concepts and relationships
4. **Format**: Write in 2-3 paragraphs, professional and specific

**Example**:
Question: "What is TADF?"
Hypothetical Answer: "TADF (Thermally Activated Delayed Fluorescence) is a 
luminescence mechanism in organic light-emitting diodes (OLEDs) that enables 
100% internal quantum efficiency. It works by thermally activating triplet 
excitons and converting them back to singlet states through reverse intersystem 
crossing (RISC). Key characteristics include small singlet-triplet energy gap 
(ΔEST), delayed fluorescence, and high efficiency in OLED devices..."

Question: {question}

Answer:
```

**기대 효과**:
- ✅ 검색 정확도 향상
- ✅ 관련 문서 발견률 증가

---

### 5. Multi-Query 프롬프트 개선

#### 개선안: 동의어 확장 명시

**추가할 내용**:
```
**Rewriting strategies** (generate 1 for each):
1. **Technical perspective**: 
   - Focus on specific technical terms and methodologies
   - Include synonyms and related technical terms
   - Example: "efficiency" → "efficacy", "performance", "output"

2. **Conceptual perspective**: 
   - Focus on abstract concepts and theories
   - Use broader conceptual terms
   - Example: "OLED efficiency" → "light emission optimization", "quantum efficiency"

3. **Application perspective**: 
   - Focus on real-world use cases and applications
   - Include practical terminology
   - Example: "OLED efficiency" → "display brightness optimization", "device performance"

4. **Comparative perspective**: 
   - Comparative analysis question format (if applicable)
   - Include comparison keywords: "vs", "compared to", "difference"

5. **Problem-solving perspective**: 
   - Focus on problem definition and solutions (if applicable)
   - Include problem-solution keywords: "improvement", "optimization", "enhancement"
```

**기대 효과**:
- ✅ 검색 범위 확장
- ✅ 다양한 표현 방식 포착

---

### 6. 번역 프롬프트 개선

#### 개선안: 의미 보존 및 검색 적합성 강조

**개선안**:
```
Translate the following question to English while preserving its exact meaning.
The translated question will be used for semantic search, so it must be:
- Natural and fluent in English
- Suitable for search (include key terms)
- Preserve technical terms and proper nouns in original form

**Translation guidelines**:
1. **Meaning Preservation**: Maintain the exact intent and scope of the original question
2. **Technical Terms**: Keep technical terms, proper nouns, and acronyms unchanged
3. **Search Optimization**: Use natural English that is suitable for semantic search
4. **If already in English**: Return the question as-is

Question: "{question}"

Translated question (English only, no explanation):
```

**기대 효과**:
- ✅ 번역 품질 향상
- ✅ 검색 정확도 개선

---

## 구현 우선순위

### Phase 1: 핵심 개선 (즉시 적용)

1. **답변 생성 프롬프트 - Chain of Thought 추가** 🔴
   - 영향도: 매우 높음
   - 구현 난이도: 낮음
   - 예상 효과: 답변 품질 20-30% 향상

2. **답변 생성 프롬프트 - 문서 우선 원칙 강화** 🔴
   - 영향도: 매우 높음
   - 구현 난이도: 낮음
   - 예상 효과: 환각 감소, 신뢰도 향상

### Phase 2: 중요 개선 (1주 내)

3. **Query Decomposition - Few-shot 예시 추가** 🟡
   - 영향도: 높음
   - 구현 난이도: 낮음
   - 예상 효과: 분해 품질 15-20% 향상

4. **HyDE 프롬프트 - 검색 최적화 강조** 🟡
   - 영향도: 중간
   - 구현 난이도: 낮음
   - 예상 효과: 검색 정확도 10-15% 향상

### Phase 3: 보완 개선 (2주 내)

5. **질문 분류 - 다중 질문 분리** 🟢
   - 영향도: 중간
   - 구현 난이도: 중간
   - 예상 효과: 복합 질문 처리 개선

6. **Multi-Query - 동의어 확장 명시** 🟢
   - 영향도: 중간
   - 구현 난이도: 낮음
   - 예상 효과: 검색 범위 확장

7. **번역 프롬프트 - 의미 보존 강조** 🟢
   - 영향도: 낮음
   - 구현 난이도: 낮음
   - 예상 효과: 번역 품질 개선

---

## 예상 효과

### 정량적 개선 목표

| 지표 | 현재 (예상) | Phase 1 후 | Phase 2 후 | Phase 3 후 |
|------|------------|-----------|-----------|-----------|
| 답변 정확도 | 75% | 85% | 88% | 90% |
| 환각 발생률 | 15% | 8% | 5% | 3% |
| 검색 정확도 | 80% | 82% | 85% | 87% |
| 사용자 만족도 | 4.0/5.0 | 4.3/5.0 | 4.5/5.0 | 4.6/5.0 |

### 정성적 개선 효과

1. **답변 품질**:
   - 더 체계적이고 논리적인 답변
   - 문서 기반 답변 강화로 신뢰도 향상
   - 출처 표시 일관성 개선

2. **검색 성능**:
   - Multi-Query 다양성 증가
   - HyDE 검색 정확도 향상
   - Query Decomposition 품질 개선

3. **사용자 경험**:
   - 복합 질문 처리 개선
   - 일관된 답변 형식
   - 명확한 출처 표시

---

## 결론

현재 시스템의 프롬프트는 전반적으로 잘 구성되어 있으나, 다음과 같은 개선이 필요합니다:

1. **답변 생성 프롬프트**: Chain of Thought와 문서 우선 원칙 강화가 가장 중요
2. **Query Decomposition**: Few-shot 예시 추가로 분해 품질 향상
3. **HyDE**: 검색 최적화 강조로 검색 정확도 개선
4. **기타 프롬프트**: 점진적 보완으로 전체 시스템 성능 향상

**권장 사항**:
- Phase 1 개선을 즉시 적용하여 핵심 성능 향상
- A/B 테스트를 통해 개선 효과 검증
- 사용자 피드백 수집 및 지속적 개선

---

## 참고 자료

- 현재 시스템 프롬프트 위치:
  - `utils/rag_chain.py` (라인 261-500)
  - `utils/question_classifier.py` (라인 399-445)
- 웹 검색 기반 최적화 사례 (2024-2025)
- RAG 프롬프트 엔지니어링 베스트 프랙티스

