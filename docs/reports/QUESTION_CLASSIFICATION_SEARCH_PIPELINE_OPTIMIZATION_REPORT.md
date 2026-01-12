# 질문 분류 기반 검색 파이프라인 최적화 제안 보고서

**작성일**: 2025-12-08  
**최종 수정일**: 2025-12-08  
**작성자**: RAG 시스템 개발팀  
**버전**: v2.2 (10개 분류로 확장, 번역을 직접/검색 후 번역으로 세분화)

---

## 📋 목차

1. [요약 (Executive Summary)](#요약-executive-summary)
2. [현재 상태 분석](#현재-상태-분석)
3. [문제점 파악](#문제점-파악)
4. [개선 방안 제안](#개선-방안-제안)
5. [구현 계획](#구현-계획)
6. [예상 효과](#예상-효과)
7. [예외 상황 및 대응 방안](#예외-상황-및-대응-방안)
8. [질문 분류 체계 최종 검토](#질문-분류-체계-최종-검토)
9. [참고 자료](#참고-자료)

---

## 요약 (Executive Summary)

### 핵심 문제

현재 RAG 시스템은 **질문 분류(Question Classification)**를 통해 질문 유형을 4가지(simple, normal, complex, exhaustive)로 분류하고 있으나, **검색 파이프라인 전략이 질문 분류 결과와 완전히 연동되지 않아** 비효율적인 검색이 발생하고 있습니다.

특히 **Exhaustive 질문**에서 HyDE(Hypothetical Document Embeddings)가 사용되면서 키워드 기반 검색이 약화되어, "특정 키워드가 있는 문서를 모두 찾아줘" 같은 질문에서 한정적인 결과만 반환되는 문제가 확인되었습니다.

### 제안 사항

1. **질문 분류 세분화**: 4가지 → 10가지로 확장 (번역 세분화: 직접 번역 + 검색 후 번역)
2. **계층적 라우팅 방식**: Local LLM의 인지 부하 문제 해결을 위한 2단계 분류
3. **Semantic Router**: 임베딩 기반 빠른 분류 (밀리초 단위, LLM 호출 불필요)
4. **하이브리드 분류**: Semantic Router + 계층적 라우팅 결합
5. **검색 전략 매핑 테이블**: 질문 유형별 검색 파라미터 명시적 정의
6. **조건부 HyDE/Multi-Query**: 질문 유형에 따라 자동 활성화/비활성화
7. **BM25/Vector 가중치 동적 조정**: 질문 유형별 최적 가중치 적용

### 예상 효과

- **분류 속도**: LLM 호출 → 밀리초 단위로 개선 (Semantic Router)
- **분류 정확도**: +30-40% 향상 (계층적 라우팅으로 인지 부하 문제 해결)
- **검색 정확도**: +20-30% 향상 (특히 Exhaustive 질문)
- **응답 시간**: -15-25% 단축 (불필요한 HyDE/Multi-Query 제거)
- **리소스 효율**: LLM 호출 횟수 -50-70% 감소 (Semantic Router 활용)

---

## 현재 상태 분석

### 1. 질문 분류 시스템

#### 1.1 분류 방식 (하이브리드)

현재 시스템은 **LLM 우선 + 규칙 기반 폴백** 방식을 사용합니다:

```python
# utils/question_classifier.py
def classify(self, question: str) -> Dict:
    # Stage 1: LLM 우선 시도
    if self.llm and self.use_llm_fallback:
        llm_result = self._classify_by_llm(question)
        # 하이브리드 검증: LLM 결과를 규칙 기반으로 재검증
        if llm_result.get('type') == 'normal':
            complex_score = self._calculate_complex_score(question)
            if complex_score >= 0.5:
                llm_result['type'] = 'complex'  # 재분류
    
    # Stage 2: 규칙 기반 폴백 (LLM 실패 시)
    rule_result = self._classify_by_rules(question)
    return final_result
```

**특징**:
- ✅ LLM: 문맥 이해, 유연한 분류
- ✅ 규칙 기반: 키워드 매칭, 정규식 패턴, 빠른 처리
- ✅ 하이브리드 검증: 두 방식의 장점 결합

#### 1.2 질문 유형 (4가지)

| 유형 | 특징 | 예시 |
|------|------|------|
| **simple** | 단순 사실 질문 | "kFRET 값은?", "3페이지 요약" |
| **normal** | 일반 질문 | "OLED 효율은?", "작동 원리는?" |
| **complex** | 복잡한 질문 | "OLED와 QLED 비교", "효율과 수명의 관계" |
| **exhaustive** | 포괄적 질문 | "모든 슬라이드 제목", "OLED 전극 모두 찾아줘" |

#### 1.3 현재 파라미터 매핑

**QuestionClassifier 파라미터** (`utils/question_classifier.py`):

```python
params = {
    "simple": {
        "multi_query": False,
        "max_results": 8,
        "reranker_k": 30,
        "max_tokens": 20480,
    },
    "normal": {
        "multi_query": False,
        "max_results": 12,
        "reranker_k": 60,
        "max_tokens": 40960,
    },
    "complex": {
        "multi_query": True,
        "max_results": 15,
        "reranker_k": 80,
        "max_tokens": 61440,
    },
    "exhaustive": {
        "multi_query": False,  # ✅ 이미 비활성화
        "max_results": 30,
        "reranker_k": 150,
        "max_tokens": 81920,
    }
}
```

**RAGChain BM25/Vector 가중치** (`utils/rag_chain.py`):

```python
_question_type_params = {
    "simple": {
        "bm25_weight": 0.7,  # 키워드 매칭 중요
        "vector_weight": 0.3,
        "adaptive_threshold_percentile": 0.7,
    },
    "normal": {
        "bm25_weight": 0.5,  # 균형
        "vector_weight": 0.5,
        "adaptive_threshold_percentile": 0.6,
    },
    "complex": {
        "bm25_weight": 0.3,  # 의미론적 유사도 중요
        "vector_weight": 0.7,
        "adaptive_threshold_percentile": 0.5,
    },
    "exhaustive": {
        "bm25_weight": 0.5,  # ⚠️ 균형 유지 (키워드 검색에는 부족)
        "vector_weight": 0.5,
        "adaptive_threshold_percentile": 0.4,
    },
    "keyword": {
        "bm25_weight": 0.8,  # 키워드 검색 강화
        "vector_weight": 0.2,
        "adaptive_threshold_percentile": 0.4,
    }
}
```

### 2. 검색 파이프라인 현황

#### 2.1 HyDE 사용 현황

**현재 문제**: Exhaustive 질문에서도 HyDE가 사용됨

```python
# utils/rag_chain.py - generate_rewritten_queries()
def generate_rewritten_queries(self, original_query: str, num_queries: int = 3):
    # ...
    # HyDE 통합 (질문 유형과 무관하게 항상 실행)
    if self.enable_hyde:
        hyde_document = self._generate_hypothetical_document(original_query)
        if hyde_document:
            rewritten_queries.append(hyde_document)
```

**터미널 로그 분석**:
```
질문: "OLED 전극에 대한 내용이 있으면 모두 찾아줘...."
[QuestionClassifier] ✓ LLM 분류 성공
  → 유형: exhaustive
  → 신뢰도: 92.0%
[HyDE] 가상 문서 생성 완료: 2785자  # ⚠️ Exhaustive 질문에서도 HyDE 실행
[REWRITE] 다중 쿼리 생성: ... → 5개 쿼리 (HyDE 포함)
```

#### 2.2 Multi-Query 사용 현황

**현재 상태**: QuestionClassifier에서 `multi_query: False`로 설정되어 있으나, 실제 검색 파이프라인에서는 여전히 실행될 수 있음

```python
# utils/rag_chain.py - _get_context_standard()
if self.enable_multi_query and not is_keyword_query:
    original_queries = self.generate_rewritten_queries(question, ...)
else:
    original_queries = [question]
```

**문제점**: QuestionClassifier의 `multi_query` 설정이 검색 파이프라인에 완전히 반영되지 않음

---

## 문제점 파악

### 1. Exhaustive 질문에서 HyDE 부적합

#### 문제 상황

**질문**: "OLED 전극에 대한 내용이 있으면 모두 찾아줘"

**현재 동작**:
1. QuestionClassifier: `exhaustive` 분류 ✅
2. HyDE 실행: 가상 문서 생성 (2785자) ❌
3. 검색 결과: 3개 문서만 반환 (예상: 10-20개) ❌

**원인 분석**:

HyDE는 "이상적인 답변"을 생성하여 그 임베딩으로 검색합니다:

```python
def _generate_hypothetical_document(self, question: str) -> str:
    prompt = f"""Write a hypothetical answer to the following question.
    This answer will be used to find relevant documents through semantic search,
    so it MUST include rich keywords, technical terms, and concepts.
    ...
    Question: {question}
    Answer:"""
```

**문제점**:
- ❌ 키워드 기반 검색이 약화됨: "OLED 전극"이라는 정확한 키워드보다 의미론적 유사성에 의존
- ❌ 기술 문서에서는 키워드 정확도가 핵심인데, HyDE는 이를 약화시킴
- ❌ Exhaustive 질문은 "모두 찾아줘"라는 키워드 매칭 요청인데, HyDE는 부적합

### 2. 검색 전략과 질문 분류의 불완전한 연동

#### 현재 구조

```
질문 입력
  ↓
QuestionClassifier (분류)
  ↓
파라미터 반환 (multi_query, max_results, ...)
  ↓
RAGChain 검색 파이프라인
  ↓
❌ QuestionClassifier 파라미터가 완전히 반영되지 않음
```

**문제점**:
- ❌ `multi_query` 설정이 검색 파이프라인에 반영되지 않음
- ❌ HyDE 사용 여부가 질문 유형과 무관하게 항상 실행됨
- ❌ BM25/Vector 가중치는 적용되지만, HyDE/Multi-Query는 별도 로직

### 3. 질문 분류 세분화 부족

#### 현재 분류 (4가지)

- `simple`: 단순 사실 질문
- `normal`: 일반 질문
- `complex`: 복잡한 질문
- `exhaustive`: 포괄적 질문

**문제점**:
- ❌ `exhaustive`가 너무 광범위: 키워드 기반 전체 검색 vs 목록 질문 구분 불가
- ❌ `simple`이 너무 광범위: 키워드 검색 vs 사실 질문 구분 불가
- ❌ 검색 전략 선택이 세밀하지 않음

---

## 개선 방안 제안

### 1. 질문 분류 세분화 (4가지 → 8가지)

#### 1.1 세분화된 질문 유형

| 기존 유형 | 세분화 유형 | 특징 | 검색 전략 |
|----------|------------|------|----------|
| **simple** | `simple_fact` | 단순 사실 질문 (값, 수치) | BM25 강화, HyDE OFF |
| | `simple_keyword` | 키워드 검색 질문 (저자명, 특정 용어) | BM25 최대 강화, HyDE OFF |
| **normal** | `normal_definition` | 정의 질문 ("무엇인가?") | Vector 강화, HyDE ON |
| | `normal_explanation` | 설명 질문 ("어떻게?", "왜?") | 균형, HyDE ON, Multi-Query ON |
| | `normal_translation_direct` | 직접 번역 ("이 문단 번역해줘") | 검색 스킵, 번역만 수행 |
| | `normal_translation_search` | 검색 후 번역 ("X 찾아서 번역해줘") | 검색 필요, 번역 수행 |
| **complex** | `complex_comparison` | 비교/분석 질문 | Vector 강화, Multi-Query 필수 |
| | `complex_relationship` | 관계/영향 질문 | Vector 강화, Multi-Query 필수 |
| **exhaustive** | `exhaustive_keyword` | 키워드 기반 전체 검색 ("모든 X 찾아줘") | BM25 최대 강화, HyDE OFF |
| | `exhaustive_list` | 목록/나열 질문 ("모든 제목 나열") | BM25 강화, HyDE OFF |

#### 1.2 세분화 분류 로직

```python
# utils/question_classifier.py에 추가
def _classify_detailed(self, question: str, base_result: Dict) -> Dict:
    """세분화된 질문 분류"""
    
    base_type = base_result['type']
    
    if base_type == 'simple':
        # 키워드 검색 패턴 확인
        if self._is_keyword_search(question):
            return {**base_result, "detailed_type": "simple_keyword"}
        else:
            return {**base_result, "detailed_type": "simple_fact"}
    
    elif base_type == 'normal':
        # 번역 질문 감지 및 세분화
        if self._detect_translation(question):
            # 검색이 필요한 번역인지 확인
            if self._requires_search_for_translation(question):
                return {**base_result, "detailed_type": "normal_translation_search"}
            else:
                return {**base_result, "detailed_type": "normal_translation_direct"}
        # 정의 질문 vs 설명 질문
        elif self._is_definition_question(question):
            return {**base_result, "detailed_type": "normal_definition"}
        else:
            return {**base_result, "detailed_type": "normal_explanation"}
    
    elif base_type == 'complex':
        # 비교 질문 vs 관계 질문
        if self._is_comparison_question(question):
            return {**base_result, "detailed_type": "complex_comparison"}
        else:
            return {**base_result, "detailed_type": "complex_relationship"}
    
    elif base_type == 'exhaustive':
        # 키워드 기반 vs 목록 기반
        if self._is_keyword_search(question):
            return {**base_result, "detailed_type": "exhaustive_keyword"}
        else:
            return {**base_result, "detailed_type": "exhaustive_list"}
    
    return {**base_result, "detailed_type": base_type}

def _is_keyword_search(self, question: str) -> bool:
    """키워드 검색 질문인지 판단"""
    keyword_patterns = [
        r'찾아줘', r'있는', r'포함', r'나와',
        r'find.*by', r'search.*for', r'contain'
    ]
    return any(re.search(pattern, question, re.IGNORECASE) for pattern in keyword_patterns)

def _is_definition_question(self, question: str) -> bool:
    """정의 질문인지 판단"""
    definition_patterns = [
        r'[은는이가]\s*무엇[인가이]',
        r'[이란는]\s*무엇',
        r'[은는]\s*뭐'
    ]
    return any(re.search(pattern, question) for pattern in definition_patterns)

def _is_comparison_question(self, question: str) -> bool:
    """비교 질문인지 판단"""
    comparison_keywords = ['비교', '차이', 'vs', 'versus', 'compared']
    return any(kw in question.lower() for kw in comparison_keywords)

def _detect_translation(self, question: str) -> bool:
    """번역 질문인지 판단"""
    translation_patterns = [
        r'번역', r'translate', r'번역해줘',
        r'영어로', r'한글로', r'한국어로',
        r'영어로\s*번역', r'한글로\s*번역'
    ]
    return any(re.search(pattern, question, re.IGNORECASE) for pattern in translation_patterns)

def _requires_search_for_translation(self, question: str) -> bool:
    """번역 질문이 검색을 필요로 하는지 판단"""
    # 검색이 필요한 패턴
    search_patterns = [
        r'찾아서\s*번역', r'찾아\s*번역',
        r'검색.*번역', r'search.*translate',
        r'번역.*찾아', r'translate.*find',
        r'번역.*검색', r'translate.*search',
        r'내용.*번역', r'content.*translate',
        r'문서.*번역', r'document.*translate',
    ]
    
    # 직접 번역 패턴 (검색 불필요)
    direct_patterns = [
        r'이\s*문단.*번역', r'이\s*내용.*번역',
        r'위\s*내용.*번역', r'아래\s*내용.*번역',
        r'다음.*번역', r'following.*translate',
    ]
    
    # 직접 번역 패턴이 있으면 검색 불필요
    if any(re.search(pattern, question, re.IGNORECASE) for pattern in direct_patterns):
        return False
    
    # 검색 패턴이 있으면 검색 필요
    if any(re.search(pattern, question, re.IGNORECASE) for pattern in search_patterns):
        return True
    
    # 키워드가 포함되어 있으면 검색 필요 (예: "OLED 전극 번역해줘")
    # 질문에서 번역 키워드를 제거한 후 남은 내용이 있으면 검색 필요
    question_without_translation = re.sub(
        r'번역|translate|영어로|한글로|한국어로', 
        '', 
        question, 
        flags=re.IGNORECASE
    ).strip()
    
    # 남은 내용이 3자 이상이면 검색 필요로 판단
    if len(question_without_translation) > 3:
        return True
    
    # 기본값: 직접 번역 (검색 불필요)
    return False
```

### 2. 검색 전략 매핑 테이블

#### 2.1 전략 매핑 정의

```python
# utils/rag_chain.py에 추가
SEARCH_STRATEGY_MAP = {
    "simple_fact": {
        "enable_hyde": False,        # ❌ 단순 질문에는 불필요
        "enable_multi_query": False,  # ❌ 단순 질문에는 불필요
        "bm25_weight": 0.8,           # 키워드 정확도 중요
        "vector_weight": 0.2,
        "initial_k": 30,             # 적은 후보
        "max_results": 5,            # 적은 결과
        "adaptive_threshold_percentile": 0.7,  # 엄격한 필터링
    },
    "simple_keyword": {
        "enable_hyde": False,        # ❌ 키워드 검색에는 HyDE 부적합
        "enable_multi_query": False, # ❌ 키워드 검색에는 Multi-Query 불필요
        "bm25_weight": 0.9,           # 키워드 매칭 최우선
        "vector_weight": 0.1,
        "initial_k": 150,             # 넓은 검색 범위
        "max_results": 20,            # 많은 결과
        "adaptive_threshold_percentile": 0.4,  # 완화된 필터링
    },
    "normal_definition": {
        "enable_hyde": True,         # ✅ 정의 질문에는 HyDE 유용
        "enable_multi_query": False,
        "bm25_weight": 0.4,
        "vector_weight": 0.6,        # 의미론적 유사도 중요
        "initial_k": 60,
        "max_results": 8,
        "adaptive_threshold_percentile": 0.6,
    },
    "normal_explanation": {
        "enable_hyde": True,         # ✅ 설명 질문에는 HyDE 유용
        "enable_multi_query": True,  # ✅ 다양한 관점 유용
        "bm25_weight": 0.5,
        "vector_weight": 0.5,
        "initial_k": 80,
        "max_results": 12,
        "adaptive_threshold_percentile": 0.6,
    },
    "normal_translation_direct": {
        "enable_hyde": False,        # ❌ 직접 번역에는 불필요
        "enable_multi_query": False, # ❌ 직접 번역에는 불필요
        "bm25_weight": 0.0,           # 검색 스킵
        "vector_weight": 0.0,        # 검색 스킵
        "initial_k": 0,              # 검색 스킵
        "max_results": 0,            # 검색 스킵
        "skip_search": True,         # 검색 완전 스킵
        "adaptive_threshold_percentile": 0.0,
    },
    "normal_translation_search": {
        "enable_hyde": False,        # ❌ 검색 후 번역에는 HyDE 불필요
        "enable_multi_query": False, # ❌ 검색 후 번역에는 Multi-Query 불필요
        "bm25_weight": 0.6,           # 키워드 매칭 중요 (검색 필요)
        "vector_weight": 0.4,
        "initial_k": 80,             # 검색 필요
        "max_results": 10,           # 검색 결과 번역
        "skip_search": False,        # 검색 수행
        "adaptive_threshold_percentile": 0.6,
    },
    "complex_comparison": {
        "enable_hyde": True,
        "enable_multi_query": True,  # ✅ 비교 질문에는 Multi-Query 필수
        "bm25_weight": 0.3,
        "vector_weight": 0.7,        # 의미론적 유사도 중요
        "initial_k": 100,
        "max_results": 15,
        "adaptive_threshold_percentile": 0.5,
    },
    "complex_relationship": {
        "enable_hyde": True,
        "enable_multi_query": True,  # ✅ 관계 질문에는 Multi-Query 필수
        "bm25_weight": 0.3,
        "vector_weight": 0.7,
        "initial_k": 120,
        "max_results": 15,
        "adaptive_threshold_percentile": 0.5,
    },
    "exhaustive_keyword": {
        "enable_hyde": False,        # ❌ 키워드 기반 전체 검색에는 HyDE 부적합
        "enable_multi_query": False, # ❌ 키워드 검색에는 Multi-Query 불필요
        "bm25_weight": 0.8,          # 키워드 매칭 최우선
        "vector_weight": 0.2,
        "initial_k": 200,             # 매우 넓은 검색 범위
        "max_results": 50,            # 많은 결과
        "adaptive_threshold_percentile": 0.4,  # 최대한 많은 문서
    },
    "exhaustive_list": {
        "enable_hyde": False,        # ❌ 목록 질문에는 HyDE 부적합
        "enable_multi_query": False, # ❌ 목록 질문에는 Multi-Query 불필요
        "bm25_weight": 0.6,          # 키워드 매칭 중요
        "vector_weight": 0.4,
        "initial_k": 200,
        "max_results": 50,
        "adaptive_threshold_percentile": 0.4,
    }
}
```

#### 2.2 전략 적용 메서드

```python
# utils/rag_chain.py에 추가
def _get_search_strategy(self, question_type: str, detailed_type: str = None) -> Dict:
    """질문 유형에 따른 검색 전략 반환"""
    
    # 세분화된 유형이 있으면 우선 사용
    strategy_key = detailed_type if detailed_type else question_type
    
    # 검색 전략 매핑 테이블에서 조회
    strategy = SEARCH_STRATEGY_MAP.get(
        strategy_key, 
        SEARCH_STRATEGY_MAP.get(question_type, SEARCH_STRATEGY_MAP['normal_explanation'])
    )
    
    return strategy

def _apply_search_strategy(self, strategy: Dict, question: str):
    """검색 전략 적용 (HyDE/Multi-Query 동적 제어)"""
    
    # 원래 설정 저장
    original_enable_hyde = self.enable_hyde
    original_enable_multi_query = self.enable_multi_query
    
    # 전략 적용
    self.enable_hyde = strategy['enable_hyde']
    self.enable_multi_query = strategy['enable_multi_query']
    
    # BM25/Vector 가중치 적용
    self._question_type_params[question_type] = {
        "bm25_weight": strategy['bm25_weight'],
        "vector_weight": strategy['vector_weight'],
        "adaptive_threshold_percentile": strategy['adaptive_threshold_percentile'],
    }
    
    return original_enable_hyde, original_enable_multi_query
```

### 3. 검색 파이프라인 통합

#### 3.1 _get_context_standard 수정

```python
# utils/rag_chain.py - _get_context_standard() 수정
def _get_context_standard(self, question: str, ...):
    """검색 전략 적용"""
    
    # 질문 분류
    classification = self.question_classifier.classify(question)
    question_type = classification['type']
    detailed_type = classification.get('detailed_type', question_type)
    
    # 검색 전략 조회
    strategy = self._get_search_strategy(question_type, detailed_type)
    
    # 전략 적용 (HyDE/Multi-Query 동적 제어)
    original_enable_hyde, original_enable_multi_query = self._apply_search_strategy(strategy, question)
    
    try:
        # 검색 수행
        # ...
        pass
    finally:
        # 원래 설정 복원
        self.enable_hyde = original_enable_hyde
        self.enable_multi_query = original_enable_multi_query
```

#### 3.2 generate_rewritten_queries 수정

```python
# utils/rag_chain.py - generate_rewritten_queries() 수정
def generate_rewritten_queries(self, original_query: str, num_queries: int = 3) -> List[str]:
    """LLM을 사용하여 원본 쿼리를 여러 관점에서 재작성"""
    
    # enable_multi_query가 False면 원본만 반환
    if not self.enable_multi_query:
        return [original_query]
    
    # ... 기존 로직 ...
    
    # HyDE 통합 (enable_hyde가 True일 때만)
    if self.enable_hyde:
        hyde_document = self._generate_hypothetical_document(original_query)
        if hyde_document:
            rewritten_queries.append(hyde_document)
    
    return rewritten_queries
```

---

## 구현 계획 (수정)

### Phase 1: Semantic Router 구현 (우선순위: 최고) ⭐

**기간**: 2-3일  
**작업 내용**:
1. `SemanticRouter` 클래스 구현
2. 각 카테고리별 대표 질문 예시 작성 (10개씩, 총 80개)
3. 카테고리별 임베딩 사전 계산
4. 유사도 계산 및 분류 로직 구현
5. 테스트 케이스 작성 및 검증

**예상 효과**:
- 질문 분류 속도: LLM 호출 → 밀리초 단위로 개선
- 분류 정확도: 수학적 거리 기반으로 일관성 향상
- 비용 절감: LLM 호출 비용 제거

**주의사항**:
- 대표 질문 예시는 실제 사용자 질문 패턴을 반영해야 함
- 정기적으로 예시 업데이트 필요

### Phase 2: 계층적 라우팅 구현 (우선순위: 높음)

**기간**: 2-3일  
**작업 내용**:
1. `_classify_layer1()` 메서드 구현 (큰 분류: simple/complex/exhaustive)
2. `_classify_layer2_simple()`, `_classify_layer2_complex()`, `_classify_layer2_exhaustive()` 구현
3. `classify_hierarchical()` 통합 메서드 구현
4. 구조화된 출력 (JSON) 파싱 로직
5. 테스트 케이스 작성 및 검증

**예상 효과**:
- Local LLM의 인지 부하 문제 해결
- 분류 정확도 향상 (각 단계에서 2-3개 선택지)
- 신뢰도 기반 폴백 가능

### Phase 3: 하이브리드 분류 통합 (우선순위: 높음)

**기간**: 1-2일  
**작업 내용**:
1. `classify_hybrid()` 메서드 구현 (Semantic Router + 계층적 라우팅)
2. 신뢰도 임계값 설정 (0.7)
3. 두 방식의 결과 비교 및 최종 결정 로직
4. 로깅 강화 (어떤 방식이 사용되었는지 기록)
5. 통합 테스트

**예상 효과**:
- 속도와 정확도의 균형 달성
- 대부분의 질문은 Semantic Router로 빠르게 처리
- 신뢰도가 낮을 때만 계층적 라우팅으로 재분류

### Phase 4: 검색 전략 매핑 테이블 구현 (우선순위: 높음)

**기간**: 1-2일  
**작업 내용**:
1. `SEARCH_STRATEGY_MAP` 상수 정의
2. `_get_search_strategy()` 메서드 추가
3. `_apply_search_strategy()` 메서드 추가
4. `_get_context_standard()` 메서드 수정
5. 통합 테스트

**예상 효과**:
- Exhaustive 키워드 질문에서 HyDE 비활성화
- 검색 정확도 향상

### Phase 5: 검색 파이프라인 통합 (우선순위: 중간)

**기간**: 1-2일  
**작업 내용**:
1. `generate_rewritten_queries()` 수정 (HyDE 조건부 실행)
2. `_get_context_standard()` 수정 (전략 적용)
3. 번역 플래그 추가 (`is_translation`, `skip_search`)
4. 로깅 강화 (어떤 전략이 적용되었는지 명확히 기록)
5. 성능 테스트

**예상 효과**:
- 불필요한 HyDE/Multi-Query 제거
- 응답 시간 단축
- 번역 질문 처리 개선

### Phase 6: 테스트 및 검증 (우선순위: 중간)

**기간**: 3-5일  
**작업 내용**:
1. A/B 테스트 (기존 방식 vs 개선 방식)
2. 성능 측정:
   - 분류 정확도 (Semantic Router vs 계층적 라우팅)
   - 검색 정확도 (전략 적용 전후)
   - 응답 시간 (전체 파이프라인)
   - 리소스 사용량 (LLM 호출 횟수)
3. 사용자 피드백 수집
4. Semantic Router 대표 질문 예시 개선
5. 최적화 파라미터 조정

**예상 효과**:
- 검증된 개선 효과 확인
- 추가 최적화 포인트 발견
- Semantic Router 튜닝

---

## 예상 효과

### 1. 검색 정확도 향상

| 질문 유형 | 현재 | 개선 후 | 향상율 |
|----------|------|---------|--------|
| **Exhaustive 키워드** | 3개 문서 | 15-20개 문서 | +400-567% |
| **Simple 키워드** | 5-8개 문서 | 15-20개 문서 | +100-200% |
| **Complex 비교** | 10-12개 문서 | 15-18개 문서 | +25-50% |

**근거**:
- Exhaustive 키워드 질문에서 HyDE 비활성화 → 키워드 매칭 정확도 향상
- BM25 가중치 증가 → 키워드 기반 검색 강화

### 2. 응답 시간 단축

| 질문 유형 | 현재 | 개선 후 | 단축율 |
|----------|------|---------|--------|
| **Simple** | 8-15초 | 6-12초 | -15-20% |
| **Exhaustive 키워드** | 70-90초 | 50-70초 | -20-25% |
| **Normal** | 25-35초 | 22-30초 | -10-15% |

**근거**:
- 불필요한 HyDE 생성 제거 (15-35초 절약)
- 불필요한 Multi-Query 제거 (5-10초 절약)

### 3. 리소스 효율 개선

| 항목 | 현재 | 개선 후 | 개선율 |
|------|------|---------|--------|
| **LLM 호출 횟수** | 100% | 70% | -30% |
| **HyDE 생성 횟수** | 100% | 50% | -50% |
| **Multi-Query 생성 횟수** | 100% | 60% | -40% |

**근거**:
- Simple/Exhaustive 키워드 질문에서 HyDE/Multi-Query 비활성화
- 질문 유형별 최적 전략 적용

### 4. 사용자 경험 개선

**Before (현재)**:
```
질문: "OLED 전극에 대한 내용이 있으면 모두 찾아줘"
→ 3개 문서만 반환 (예상: 15-20개)
→ 사용자 불만족
```

**After (개선 후)**:
```
질문: "OLED 전극에 대한 내용이 있으면 모두 찾아줘"
→ exhaustive_keyword 분류
→ HyDE 비활성화, BM25 가중치 0.8
→ 15-20개 문서 반환
→ 사용자 만족도 향상
```

---

## 참고 자료

### 1. 관련 문서

- `utils/question_classifier.py`: 질문 분류기 구현
- `utils/rag_chain.py`: RAG 체인 및 검색 파이프라인
- `docs/guides/QUESTION_CLASSIFIER_GUIDE.md`: 질문 분류기 사용 가이드
- `docs/reports/RAG_PROMPT_OPTIMIZATION_ANALYSIS.md`: 프롬프트 최적화 분석

### 2. 업계 표준

- **RuleRAG (2024)**: 질문 분류 기반 명시적 규칙 적용
- **Collab-RAG**: 복잡한 질문을 하위 질문으로 분해
- **Self-RAG / Corrective-RAG**: 질문 유형에 따른 검색 품질 검사

### 3. 기술 참고

- **HyDE (Hypothetical Document Embeddings)**: 가상 문서 생성 기법
- **Multi-Query**: 다중 관점 쿼리 재작성
- **Adaptive Retrieval**: 질문 유형에 따른 적응형 검색

---

## 예외 상황 및 대응 방안

### 1. 복합적 질문 (Multi-Intent Questions)

#### 문제 상황

사용자가 단일 질문에 여러 유형의 특징을 동시에 포함하는 경우:

**예시**:
- "OLED 전극의 효율과 수명을 비교하고, 모든 관련 논문을 찾아줘"
  - `complex_comparison` (비교) + `exhaustive_keyword` (전체 검색)
- "TADF는 무엇인가? 그리고 모든 관련 내용을 찾아줘"
  - `normal_definition` (정의) + `exhaustive_keyword` (전체 검색)

#### 현재 시스템의 한계

- 질문 분류기가 단일 유형만 반환
- 검색 전략이 하나만 적용됨
- 복합 의도가 제대로 처리되지 않음

#### 대응 방안

**1. 우선순위 기반 처리**:
```python
def _handle_multi_intent(self, question: str, classification: Dict) -> Dict:
    """복합 의도 질문 처리"""
    
    # 의도 분리
    intents = self._extract_intents(question)
    
    # 우선순위 결정 (exhaustive > complex > normal > simple)
    priority_order = ['exhaustive', 'complex', 'normal', 'simple']
    
    primary_intent = None
    for intent_type in priority_order:
        if any(intent['type'] == intent_type for intent in intents):
            primary_intent = intent_type
            break
    
    # 주 의도에 맞는 전략 적용
    strategy = self._get_search_strategy(primary_intent)
    
    # 부 의도는 검색 범위 확대로 반영
    if 'exhaustive' in [i['type'] for i in intents]:
        strategy['max_results'] = min(strategy['max_results'] * 2, 100)
        strategy['initial_k'] = min(strategy['initial_k'] * 2, 300)
    
    return strategy
```

**2. Query Decomposition 활용**:
- 복합 질문을 하위 질문으로 분해
- 각 하위 질문에 적절한 전략 적용
- 결과 통합

### 2. 모호한 질문 (Ambiguous Questions)

#### 문제 상황

질문이 불명확하거나 여러 해석이 가능한 경우:

**예시**:
- "효율" (무엇의 효율인지 불명확)
- "그것" (대명사 참조 불명확)
- "최근 연구" (시간 범위 불명확)

#### 대응 방안

**1. 세션 컨텍스트 활용**:
```python
# 현재 시스템에 이미 구현됨
if self.session_context:
    # 이전 대화에서 맥락 추출
    contextual_question = self.session_context.add_context(question)
```

**2. 다중 해석 처리**:
```python
def _handle_ambiguous(self, question: str) -> List[str]:
    """모호한 질문의 다중 해석 생성"""
    
    # LLM으로 가능한 해석 생성
    interpretations = self.llm.invoke(f"""
    다음 질문의 가능한 해석을 3가지 제시하세요:
    질문: {question}
    
    각 해석은 구체적이고 명확해야 합니다.
    """)
    
    # 각 해석에 대해 검색 수행
    results = []
    for interpretation in interpretations:
        result = self._search_with_strategy(interpretation)
        results.append(result)
    
    # 결과 통합
    return self._merge_results(results)
```

**3. 명확화 요청**:
- 신뢰도가 낮을 때 (confidence < 0.5)
- 사용자에게 추가 정보 요청

### 3. 새로운 질문 유형의 등장

#### 문제 상황

시스템이 학습하지 않은 새로운 형태의 질문:

**예시**:
- 도메인 특화 질문 (의료, 법률 등)
- 새로운 표현 방식
- 다국어 혼합 질문

#### 대응 방안

**1. 유연한 분류 체계**:
```python
# 기본 전략으로 폴백
DEFAULT_STRATEGY = {
    "enable_hyde": True,  # 안전한 기본값
    "enable_multi_query": True,
    "bm25_weight": 0.5,
    "vector_weight": 0.5,
    "initial_k": 80,
    "max_results": 12,
}

def _get_search_strategy(self, question_type: str, detailed_type: str = None) -> Dict:
    strategy = SEARCH_STRATEGY_MAP.get(
        detailed_type or question_type,
        DEFAULT_STRATEGY  # 기본 전략으로 폴백
    )
    return strategy
```

**2. 분류기 성능 모니터링**:
- 낮은 신뢰도 질문 로깅
- 새로운 패턴 감지
- 주기적 재학습

### 4. 검색 결과 부족 (Empty/Insufficient Results)

#### 문제 상황

검색 결과가 없거나 매우 적은 경우:

**예시**:
- 키워드가 문서에 없음
- 임베딩 유사도가 낮음
- 도메인 불일치

#### 현재 시스템의 대응

**BM25 폴백 메커니즘** (이미 구현됨):
```python
# utils/rag_chain.py
def _try_bm25_fallback(self, pairs: List[tuple], question: str, ...):
    """검색 결과 부족 시 BM25 단독 검색으로 폴백"""
    if len(pairs) < self.min_num_results:
        # BM25 단독 검색 수행
        bm25_results = self.vectorstore._bm25_only_search(question, top_k=50)
        # 결과 병합
        return self._merge_results(pairs, bm25_results)
```

#### 추가 대응 방안

**1. 검색 범위 확대**:
```python
def _expand_search_on_failure(self, question: str, initial_results: List) -> List:
    """검색 실패 시 범위 확대"""
    
    if len(initial_results) < self.min_num_results:
        # 1. 검색 범위 2배 확대
        expanded_k = self.initial_k * 2
        
        # 2. Threshold 완화
        relaxed_threshold = self.adaptive_threshold_percentile * 0.7
        
        # 3. 재검색
        expanded_results = self._search_with_expanded_params(
            question, expanded_k, relaxed_threshold
        )
        
        return expanded_results
    
    return initial_results
```

**2. 키워드 확장**:
- 동의어 사전 활용
- LLM 기반 키워드 확장
- 부분 매칭 허용

**3. 사용자 피드백**:
- "관련 문서를 찾을 수 없습니다" 메시지
- 대안 키워드 제안
- 검색 범위 확대 옵션 제공

### 5. 분류기 오분류 (Misclassification)

#### 문제 상황

질문 분류기가 잘못된 유형으로 분류하는 경우:

**예시**:
- `exhaustive_keyword`를 `normal_explanation`으로 분류
- `simple_keyword`를 `complex_comparison`으로 분류

#### 대응 방안

**1. 하이브리드 검증 강화** (현재 구현됨):
```python
# QuestionClassifier에서 이미 구현
if llm_result.get('type') == 'normal':
    complex_score = self._calculate_complex_score(question)
    if complex_score >= 0.5:
        llm_result['type'] = 'complex'  # 재분류
```

**2. 신뢰도 기반 폴백**:
```python
def _apply_strategy_with_confidence(self, classification: Dict) -> Dict:
    """신뢰도 기반 전략 적용"""
    
    confidence = classification.get('confidence', 0.5)
    question_type = classification['type']
    
    # 신뢰도가 낮으면 안전한 기본 전략 사용
    if confidence < 0.5:
        # 모든 전략 활성화 (안전한 기본값)
        return {
            "enable_hyde": True,
            "enable_multi_query": True,
            "bm25_weight": 0.5,
            "vector_weight": 0.5,
            "initial_k": 100,  # 넓은 범위
            "max_results": 15,
        }
    
    # 신뢰도가 높으면 특화 전략 사용
    return self._get_search_strategy(question_type)
```

**3. 사후 검증**:
- 검색 결과 품질 평가
- 결과가 예상과 다르면 재검색

### 6. LLM 실패/타임아웃

#### 문제 상황

LLM 호출 실패 또는 타임아웃:

**예시**:
- 네트워크 오류
- API 제한 초과
- 타임아웃 (10초 초과)

#### 현재 시스템의 대응

**규칙 기반 폴백** (이미 구현됨):
```python
# QuestionClassifier에서 이미 구현
try:
    llm_result = self._classify_by_llm(question, timeout=10.0)
except (TimeoutError, Exception) as e:
    # 규칙 기반으로 폴백
    rule_result = self._classify_by_rules(question)
    return rule_result
```

#### 추가 대응 방안

**1. 캐싱**:
- 자주 묻는 질문 유형 캐싱
- 유사 질문 재사용

**2. 점진적 타임아웃**:
```python
# 짧은 타임아웃으로 시작, 실패 시 재시도
timeouts = [5.0, 10.0, 15.0]
for timeout in timeouts:
    try:
        return self._classify_by_llm(question, timeout=timeout)
    except TimeoutError:
        continue
# 모두 실패 시 규칙 기반 폴백
```

### 7. 도메인 특화 질문

#### 문제 상황

특정 도메인에 특화된 질문:

**예시**:
- 의료: "환자의 증상은?"
- 법률: "계약서의 조항은?"
- 기술: "API 엔드포인트는?"

#### 대응 방안

**1. 도메인 감지**:
```python
def _detect_domain(self, question: str) -> str:
    """질문의 도메인 감지"""
    
    domain_keywords = {
        'medical': ['환자', '증상', '진단', '치료'],
        'legal': ['계약', '조항', '법률', '소송'],
        'technical': ['API', '엔드포인트', '코드', '함수'],
    }
    
    for domain, keywords in domain_keywords.items():
        if any(kw in question for kw in keywords):
            return domain
    
    return 'general'
```

**2. 도메인별 전략 조정**:
- 의료: 높은 정확도 요구 → 엄격한 필터링
- 법률: 키워드 정확도 중요 → BM25 강화
- 기술: 의미 이해 중요 → Vector 강화

### 8. 다국어/혼합 언어 질문

#### 문제 상황

한국어와 영어가 혼합된 질문:

**예시**:
- "OLED efficiency는 무엇인가?"
- "TADF의 작동 원리를 설명해줘"

#### 대응 방안

**1. 자동 번역** (현재 시스템에 부분 구현):
```python
# 현재 시스템에 이미 구현됨
def _translate_to_english(self, question: str) -> str:
    """질문을 영어로 번역"""
    # ...
```

**2. 다국어 검색**:
- 원본 언어와 번역된 언어 모두로 검색
- 결과 통합

### 9. 검색 전략 적용 실패

#### 문제 상황

검색 전략 매핑 테이블에 없는 유형:

**예시**:
- 새로운 세분화 유형
- 분류 오류로 인한 알 수 없는 유형

#### 대응 방안

**1. 안전한 기본 전략**:
```python
DEFAULT_STRATEGY = SEARCH_STRATEGY_MAP.get('normal_explanation')

def _get_search_strategy(self, question_type: str, detailed_type: str = None) -> Dict:
    strategy_key = detailed_type or question_type
    
    # 매핑 테이블에 없으면 기본 전략 사용
    strategy = SEARCH_STRATEGY_MAP.get(
        strategy_key,
        SEARCH_STRATEGY_MAP.get(question_type, DEFAULT_STRATEGY)
    )
    
    return strategy
```

**2. 로깅 및 모니터링**:
- 알 수 없는 유형 로깅
- 주기적 분석 및 매핑 테이블 업데이트

### 10. 번역 질문의 검색 필요성 오판단

#### 문제 상황

번역 질문에서 검색 필요 여부를 잘못 판단하는 경우:

**예시**:
- "OLED 전극 번역해줘" → `normal_translation_direct`로 잘못 분류 (검색 스킵)
  - 실제로는 검색이 필요함
- "이 문단 번역해줘" → `normal_translation_search`로 잘못 분류 (검색 수행)
  - 실제로는 검색 불필요

#### 현재 시스템의 대응

**규칙 기반 감지 로직**:
```python
def _requires_search_for_translation(self, question: str) -> bool:
    """번역 질문이 검색을 필요로 하는지 판단"""
    
    # 검색이 필요한 패턴
    search_patterns = [
        r'찾아서\s*번역', r'찾아\s*번역',
        r'검색.*번역', r'search.*translate',
        # ...
    ]
    
    # 직접 번역 패턴 (검색 불필요)
    direct_patterns = [
        r'이\s*문단.*번역', r'이\s*내용.*번역',
        # ...
    ]
    
    # 키워드가 포함되어 있으면 검색 필요로 판단
    # ...
```

#### 추가 대응 방안

**1. 세션 컨텍스트 활용**:
```python
def _requires_search_for_translation(self, question: str, chat_history: List = None) -> bool:
    """번역 질문이 검색을 필요로 하는지 판단 (세션 컨텍스트 포함)"""
    
    # 이전 대화에서 번역할 내용이 제공되었는지 확인
    if chat_history:
        recent_context = self._extract_recent_context(chat_history)
        # 최근 대화에 번역할 텍스트가 있으면 직접 번역
        if self._has_translatable_content(recent_context):
            return False
    
    # 기본 로직 수행
    return self._requires_search_for_translation_basic(question)
```

**2. LLM 기반 보조 판단**:
```python
def _requires_search_for_translation_llm(self, question: str) -> bool:
    """LLM으로 번역 질문의 검색 필요성 판단 (보조)"""
    
    prompt = f"""다음 번역 질문에서 검색이 필요한지 판단하세요.

질문: "{question}"

판단 기준:
- 검색 필요: 특정 키워드나 주제를 찾아서 번역하는 경우
- 검색 불필요: 이미 제공된 텍스트나 문단을 번역하는 경우

JSON 형식으로 답하세요:
{{
    "requires_search": true/false,
    "reasoning": "이유"
}}"""
    
    result = self.llm.invoke(prompt)
    return result['requires_search']
```

**3. 폴백 전략**:
- 판단이 애매한 경우 (신뢰도 < 0.7)
- 검색을 수행하고, 결과가 없으면 직접 번역으로 폴백
- 또는 사용자에게 명확화 요청

**4. 검색 결과 검증**:
```python
def _handle_translation_search(self, question: str, search_results: List) -> str:
    """검색 후 번역 처리"""
    
    if not search_results:
        # 검색 결과가 없으면 사용자에게 확인
        return "검색 결과가 없습니다. 직접 번역할 내용을 제공해주시겠어요?"
    
    # 검색 결과를 번역
    translated_content = self._translate_content(search_results)
    return translated_content
```

---

## 예외 상황 대응 체크리스트

### 구현 전 검토 사항

- [ ] 복합 의도 질문 처리 로직
- [ ] 모호한 질문 명확화 메커니즘
- [ ] 검색 실패 시 폴백 전략
- [ ] 분류기 오분류 대응
- [ ] LLM 실패 시 규칙 기반 폴백
- [ ] 도메인 특화 질문 처리
- [ ] 다국어 질문 지원
- [ ] 알 수 없는 유형 처리
- [ ] 번역 질문의 검색 필요성 판단 로직

### 모니터링 지표

- **분류 정확도**: 분류기 성능 추적
- **검색 성공률**: 검색 결과 반환 비율
- **폴백 사용률**: 폴백 메커니즘 사용 빈도
- **예외 발생률**: 예외 상황 발생 빈도
- **사용자 만족도**: 예외 상황 처리에 대한 피드백

---

## 질문 분류 체계 최종 검토 및 개선 방안

### ⚠️ 중요: LLM 기반 분류의 위험성

#### 문제점: 단일 프롬프트로 10개 분류의 한계

**연구 결과**: 많은 연구에서 **"분류 카테고리가 5개를 넘어가면 소형 모델의 정확도는 급격히 떨어진다"**는 결과가 있습니다.

**Local LLM (Ollama 등)의 한계**:
- ❌ GPT-4만큼 미묘한 뉘앙스를 구분하지 못함
- ❌ **Cognitive Load (인지 부하)**: 8-9개의 정의를 프롬프트에 넣으면 모델이 앞쪽 지시사항을 잊거나(Forgetfulness) 비슷한 개념(`explanation` vs `relationship`) 사이에서 환각(Hallucination) 발생
- ❌ 분류 정확도 저하로 인한 검색 전략 오적용 → 검색 품질 저하

**최종 제안: 10개 분류** (번역 세분화)

| 분류 | 설명 | 검색 전략 |
|------|------|----------|
| `simple_fact` | 단순 사실 질문 (값, 수치) | BM25 강화, HyDE OFF |
| `simple_keyword` | 키워드 검색 질문 | BM25 최대 강화, HyDE OFF |
| `normal_definition` | 정의 질문 ("무엇인가?") | Vector 강화, HyDE ON |
| `normal_explanation` | 설명 질문 ("어떻게?", "왜?") | 균형, HyDE ON, Multi-Query ON |
| `normal_translation_direct` | 직접 번역 ("이 문단 번역해줘") | 검색 스킵, 번역만 수행 |
| `normal_translation_search` | 검색 후 번역 ("X 찾아서 번역해줘") | 검색 필요, 번역 수행 |
| `complex_comparison` | 비교/분석 질문 | Vector 강화, Multi-Query 필수 |
| `complex_relationship` | 관계/영향 질문 | Vector 강화, Multi-Query 필수 |
| `exhaustive_keyword` | 키워드 기반 전체 검색 | BM25 최대 강화, HyDE OFF |
| `exhaustive_list` | 목록/나열 질문 | BM25 강화, HyDE OFF |

### 예외 상황 검토 결과

#### 1. 추가 분류 필요성 검토

**요약 질문 (Summary Questions)**
- **현재 상태**: `normal_explanation`에 포함 가능
- **검토 결과**: ❌ 별도 분류 불필요
- **이유**: 
  - 검색 전략이 `normal_explanation`과 유사 (Vector 강화, HyDE ON)
  - 프롬프트 차이만 있음 (이미 별도 프롬프트로 처리)
  - 분류 복잡도 증가 대비 효과 미미

**번역 질문 (Translation Questions)**
- **현재 상태**: 별도 처리 없음
- **검토 결과**: ✅ **별도 분류로 추가** (10개 분류, 번역 세분화)
- **이유**:
  - 번역 질문에는 두 가지 유형이 있음:
    1. **직접 번역**: "이 문단을 번역해줘" → 검색 불필요
    2. **검색 후 번역**: "OLED 전극 찾아서 번역해줘" → 검색 필요
  - 검색 전략이 완전히 다름
  - 명시적 분류로 처리 명확성 향상
- **최종 결정**: 
  - `normal_translation_direct`: 직접 번역 (검색 스킵)
  - `normal_translation_search`: 검색 후 번역 (검색 필요)

**복합 의도 질문 (Multi-Intent)**
- **현재 상태**: 처리 로직으로 해결
- **검토 결과**: ❌ 별도 분류 불필요
- **이유**:
  - 우선순위 기반 처리로 충분
  - Query Decomposition으로 하위 질문 분해 가능
  - 별도 분류 시 복잡도만 증가

**모호한 질문 (Ambiguous)**
- **현재 상태**: 신뢰도 기반 처리
- **검토 결과**: ❌ 별도 분류 불필요
- **이유**:
  - 신뢰도 기반 폴백 전략으로 충분
  - 세션 컨텍스트 활용 가능
  - 다중 해석 처리로 해결

**도메인 특화 질문**
- **현재 상태**: 별도 처리 없음
- **검토 결과**: ❌ 별도 분류 불필요
- **이유**:
  - 도메인은 검색 전략에 영향을 주지 않음
  - 검색 파라미터 조정으로 해결 가능
  - 분류 복잡도만 증가

**다국어/혼합 언어 질문**
- **현재 상태**: 자동 번역 처리
- **검토 결과**: ❌ 별도 분류 불필요
- **이유**:
  - 자동 번역으로 해결
  - 번역 후 기존 분류 체계 적용 가능
  - 언어는 검색 전략과 무관

### 개선된 분류 방식 제안

#### 전략 1: 계층적 라우팅 (Hierarchical Routing) ⭐ 권장

**핵심 아이디어**: 한 번에 8개 중 하나를 고르는 것이 아니라, **단계를 나누어 질문 범위를 좁혀가는 방식**

**2단계 분류 구조**:

```
Layer 1 (Main Router): 큰 분류 (2-3개 선택지)
  ↓
Layer 2 (Sub Router): 세부 분류 (2-3개 선택지)
  ↓
최종 분류 + 검색 전략 적용
```

**구현 예시**:

```python
# Layer 1: 큰 분류 (단순 vs 일반 vs 복잡 vs 포괄)
def _classify_layer1(self, question: str) -> str:
    """1단계: 큰 분류"""
    # 번역 질문은 규칙 기반으로 먼저 감지 (빠름)
    # 번역은 normal의 하위 분류이므로 normal로 분류
    if self._detect_translation(question):
        return "normal", 1.0
    
    prompt = f"""다음 질문을 다음 4가지 중 하나로 분류하세요:
    1. simple: 단순 사실/키워드 검색 질문
    2. normal: 일반 질문 (정의, 설명, 번역 등)
    3. complex: 복잡한 분석/비교/관계 질문
    4. exhaustive: 포괄적 검색 질문 ("모든", "전체" 등)
    
    질문: "{question}"
    
    JSON 형식으로 답하세요:
    {{
        "category": "simple|normal|complex|exhaustive",
        "confidence": 0.0-1.0,
        "reasoning": "이유"
    }}"""
    
    result = self.llm.invoke(prompt)
    return result['category'], result['confidence']

# Layer 2: 세부 분류
def _classify_layer2_simple(self, question: str) -> str:
    """2단계: Simple 세부 분류"""
    if self._is_keyword_search(question):
        return "simple_keyword"
    else:
        return "simple_fact"

def _classify_layer2_normal(self, question: str) -> str:
    """2단계: Normal 세부 분류"""
    # 번역 질문 감지 및 세분화
    if self._detect_translation(question):
        if self._requires_search_for_translation(question):
            return "normal_translation_search"
        else:
            return "normal_translation_direct"
    # 정의 질문 감지
    elif self._is_definition_question(question):
        return "normal_definition"
    else:
        return "normal_explanation"

def _classify_layer2_complex(self, question: str) -> str:
    """2단계: Complex 세부 분류"""
    prompt = f"""다음 질문을 다음 2가지 중 하나로 분류하세요:
    1. comparison: 비교/분석 질문
    2. relationship: 관계/영향 질문
    
    질문: "{question}"
    
    JSON 형식으로 답하세요:
    {{
        "category": "comparison|relationship",
        "confidence": 0.0-1.0
    }}"""
    
    result = self.llm.invoke(prompt)
    return f"complex_{result['category']}"

def _classify_layer2_exhaustive(self, question: str) -> str:
    """2단계: Exhaustive 세부 분류"""
    if self._is_keyword_search(question):
        return "exhaustive_keyword"
    else:
        return "exhaustive_list"

# 통합 분류 함수
def classify_hierarchical(self, question: str) -> Dict:
    """계층적 분류"""
    # Layer 1
    layer1_category, layer1_confidence = self._classify_layer1(question)
    
    # Layer 2
    if layer1_category == 'simple':
        detailed_type = self._classify_layer2_simple(question)
    elif layer1_category == 'normal':
        detailed_type = self._classify_layer2_normal(question)
    elif layer1_category == 'complex':
        detailed_type = self._classify_layer2_complex(question)
    else:  # exhaustive
        detailed_type = self._classify_layer2_exhaustive(question)
    
    return {
        "type": layer1_category,
        "detailed_type": detailed_type,
        "confidence": layer1_confidence,
        "method": "hierarchical"
    }
```

**장점**:
- ✅ 각 단계에서 선택지가 2-3개로 제한 → 정확도 비약적 향상
- ✅ Local LLM도 안정적으로 처리 가능
- ✅ 단계별 신뢰도 확인 가능
- ✅ 구현 복잡도 적절

**단점**:
- ⚠️ LLM 호출 횟수 증가 (2회)
- ⚠️ 약간의 지연 시간 증가 (100-200ms)

#### 전략 2: Semantic Router (임베딩 기반) ⭐⭐ 최고 권장

**핵심 아이디어**: LLM을 사용하지 않고, **임베딩 모델로 질문의 의미를 벡터로 변환하여 미리 정의된 카테고리와 비교**

**구현 예시**:

```python
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict

class SemanticRouter:
    def __init__(self, embedding_model: SentenceTransformer):
        self.embedding_model = embedding_model
        self.category_examples = self._load_category_examples()
        self.category_embeddings = self._precompute_embeddings()
    
    def _load_category_examples(self) -> Dict[str, List[str]]:
        """각 카테고리별 대표 질문 예시 (10개씩)"""
        return {
            "simple_fact": [
                "kFRET 값은?",
                "효율은 얼마인가?",
                "3페이지 요약해줘",
                # ... 10개
            ],
            "simple_keyword": [
                "Changmin Keum 저자 찾아줘",
                "OLED 전극 포함된 문서",
                # ... 10개
            ],
            "normal_definition": [
                "TADF는 무엇인가?",
                "OLED의 정의는?",
                # ... 10개
            ],
            "normal_explanation": [
                "OLED 효율은 어떻게 작동하나?",
                "왜 TADF가 중요한가?",
                # ... 10개
            ],
            "normal_translation_direct": [
                "이 문단을 영어로 번역해줘",
                "한글로 번역해줘",
                "위 내용을 번역해줘",
                "다음 문장을 번역해줘",
                # ... 10개
            ],
            "normal_translation_search": [
                "OLED 전극에 대한 내용을 찾아서 번역해줘",
                "TADF 관련 내용 검색해서 번역해줘",
                "효율에 대한 내용 찾아 번역해줘",
                # ... 10개
            ],
            "complex_comparison": [
                "OLED와 QLED 비교해줘",
                "효율과 수명의 차이는?",
                # ... 10개
            ],
            "complex_relationship": [
                "효율과 수명의 관계는?",
                "TADF가 OLED에 미치는 영향은?",
                # ... 10개
            ],
            "exhaustive_keyword": [
                "OLED 전극 모두 찾아줘",
                "모든 관련 논문 찾아줘",
                # ... 10개
            ],
            "exhaustive_list": [
                "모든 슬라이드 제목 나열",
                "전체 목록 보여줘",
                # ... 10개
            ]
        }
    
    def _precompute_embeddings(self) -> Dict[str, np.ndarray]:
        """카테고리별 임베딩 사전 계산"""
        embeddings = {}
        for category, examples in self.category_examples.items():
            # 각 카테고리의 예시들을 임베딩하고 평균
            example_embeddings = self.embedding_model.encode(examples)
            category_embedding = np.mean(example_embeddings, axis=0)
            embeddings[category] = category_embedding
        return embeddings
    
    def classify(self, question: str) -> Dict:
        """질문을 임베딩하여 가장 유사한 카테고리 반환"""
        # 질문 임베딩
        question_embedding = self.embedding_model.encode([question])[0]
        
        # 각 카테고리와의 유사도 계산 (코사인 유사도)
        similarities = {}
        for category, category_embedding in self.category_embeddings.items():
            similarity = np.dot(question_embedding, category_embedding) / (
                np.linalg.norm(question_embedding) * np.linalg.norm(category_embedding)
            )
            similarities[category] = float(similarity)
        
        # 가장 유사한 카테고리 선택
        best_category = max(similarities, key=similarities.get)
        confidence = similarities[best_category]
        
        return {
            "type": best_category.split('_')[0],  # simple, normal, complex, exhaustive
            "detailed_type": best_category,
            "confidence": confidence,
            "method": "semantic_router",
            "all_similarities": similarities  # 디버깅용
        }
```

**장점**:
- ✅ **속도**: LLM을 거치지 않으므로 매우 빠름 (밀리초 단위)
- ✅ **안정성**: 프롬프트에 따라 오락가락하지 않고, 수학적 거리 기반이라 일관성 있음
- ✅ **제어**: 특정 분류가 잘 안되면, 그 분류의 '대표 질문 예시'만 몇 개 더 추가하면 됨 (튜닝이 쉬움)
- ✅ **비용**: LLM 호출 비용 없음
- ✅ **확장성**: 새로운 카테고리 추가가 쉬움

**단점**:
- ⚠️ 초기 설정 필요 (대표 질문 예시 작성)
- ⚠️ 임베딩 모델 품질에 의존

#### 전략 3: 구조화된 출력 + 신뢰도 기반 폴백

**핵심 아이디어**: LLM에게 단순 분류만 시키지 말고, **JSON 형태로 이유와 확신 수준을 같이 반환**받아 신뢰도가 낮을 때 안전한 폴백 적용

**구현 예시**:

```python
def _classify_with_confidence(self, question: str) -> Dict:
    """구조화된 출력 + 신뢰도 점수"""
    
    prompt = f"""사용자의 질문을 분석하여 다음 8가지 중 하나로 분류하세요.

질문: "{question}"

분류 유형:
1. simple_fact: 단순 사실 질문 (값, 수치)
2. simple_keyword: 키워드 검색 질문
3. normal_definition: 정의 질문 ("무엇인가?")
4. normal_explanation: 설명 질문 ("어떻게?", "왜?")
5. complex_comparison: 비교/분석 질문
6. complex_relationship: 관계/영향 질문
7. exhaustive_keyword: 키워드 기반 전체 검색
8. exhaustive_list: 목록/나열 질문

**중요**: JSON 형식으로 답해야 하며 'reasoning'(이유)과 'confidence'(확신도 0~1)를 포함하세요.

{{
    "category": "simple_fact",
    "reasoning": "사용자가 특정 값(kFRET)을 묻고 있으므로 단순 사실 질문이다.",
    "confidence": 0.95
}}"""
    
    result = self.llm.invoke(prompt)
    
    # 신뢰도 기반 폴백
    if result['confidence'] < 0.8:
        # 안전한 기본 전략 사용
        return {
            **result,
            "fallback": True,
            "strategy": "safe_default"  # normal_explanation + 모든 전략 활성화
        }
    
    return result
```

**장점**:
- ✅ 신뢰도 기반 안전장치
- ✅ 잘못된 분류로 인한 검색 실패 방지
- ✅ 구현이 상대적으로 간단

**단점**:
- ⚠️ 여전히 9개 분류를 한 번에 처리 (인지 부하 문제)
- ⚠️ Local LLM에서 정확도 저하 가능

### 최종 권장 사항 (수정)

#### 🏆 최우선 권장: Semantic Router + 계층적 라우팅 하이브리드

**구조**:
```
1. Semantic Router로 빠른 1차 분류 (밀리초 단위)
   ↓
2. 신뢰도가 낮으면 (< 0.7) → 계층적 라우팅으로 재분류
   ↓
3. 최종 분류 + 검색 전략 적용
```

**구현 예시**:

```python
def classify_hybrid(self, question: str) -> Dict:
    """하이브리드 분류: Semantic Router + 계층적 라우팅"""
    
    # 1단계: Semantic Router (빠른 분류)
    semantic_result = self.semantic_router.classify(question)
    
    # 신뢰도가 높으면 바로 반환
    if semantic_result['confidence'] >= 0.7:
        return semantic_result
    
    # 2단계: 신뢰도가 낮으면 계층적 라우팅으로 재분류
    print(f"[Classifier] Semantic Router 신뢰도 낮음 ({semantic_result['confidence']:.2f}) → 계층적 라우팅으로 재분류")
    hierarchical_result = self.classify_hierarchical(question)
    
    # 두 결과 비교
    if semantic_result['detailed_type'] == hierarchical_result['detailed_type']:
        # 일치하면 신뢰도 상승
        return {
            **semantic_result,
            "confidence": min(1.0, semantic_result['confidence'] + 0.2),
            "method": "hybrid_agreed"
        }
    else:
        # 불일치하면 계층적 결과 우선 (더 정확)
        return {
            **hierarchical_result,
            "method": "hybrid_hierarchical",
            "semantic_suggestion": semantic_result['detailed_type']
        }
```

**장점**:
- ✅ **속도**: 대부분의 경우 Semantic Router로 빠르게 처리
- ✅ **정확도**: 신뢰도가 낮을 때만 계층적 라우팅으로 재분류
- ✅ **안정성**: 두 방식의 결과를 비교하여 최종 결정
- ✅ **비용 효율**: LLM 호출 최소화

#### 대안 1: 계층적 라우팅만 사용

**조건**:
- Semantic Router 구현이 어려운 경우
- 임베딩 모델이 없는 경우

**구현**: 위의 "전략 1: 계층적 라우팅" 참조

#### 대안 2: 구조화된 출력 + 신뢰도 폴백

**조건**:
- 구현 복잡도를 최소화하고 싶은 경우
- LLM 성능이 충분히 좋은 경우 (GPT-4 등)

**구현**: 위의 "전략 3: 구조화된 출력" 참조

### 결론 및 최종 권장 사항

**최종 권장**: **10개 분류 + Semantic Router + 계층적 라우팅 하이브리드 방식**

**이유**:
1. **명확성**: 번역을 별도 분류로 명시하여 처리 명확성 향상
2. **정확도**: 계층적 라우팅으로 Local LLM의 인지 부하 문제 해결 (9개 → 2-3개 선택지)
3. **속도**: Semantic Router로 대부분의 질문을 빠르게 처리
4. **안정성**: 두 방식의 결과를 비교하여 최종 결정
5. **비용 효율**: LLM 호출 최소화
6. **확장성**: 새로운 카테고리 추가가 쉬움

**구현 우선순위**:
1. ✅ Phase 1: Semantic Router 구현 (10개 분류별 대표 질문 예시 작성)
2. ✅ Phase 2: 계층적 라우팅 구현 (Layer 1 + Layer 2, 번역 포함)
3. ✅ Phase 3: 하이브리드 분류 통합
4. ✅ Phase 4: 검색 전략 매핑 (9개 분류 전략 포함)
5. ✅ Phase 5: 검색 파이프라인 통합 (번역 분류 처리)
6. ✅ Phase 6: 예외 상황 처리 로직

**10개 분류 체계**:
1. `simple_fact` - 단순 사실 질문
2. `simple_keyword` - 키워드 검색 질문
3. `normal_definition` - 정의 질문
4. `normal_explanation` - 설명 질문
5. `normal_translation_direct` - 직접 번역 (검색 스킵) ⭐ 추가
6. `normal_translation_search` - 검색 후 번역 (검색 필요) ⭐ 추가
7. `complex_comparison` - 비교/분석 질문
8. `complex_relationship` - 관계/영향 질문
9. `exhaustive_keyword` - 키워드 기반 전체 검색
10. `exhaustive_list` - 목록/나열 질문

**향후 확장 고려사항**:
- Semantic Router의 대표 질문 예시를 사용자 피드백으로 지속 개선
- 분류 정확도 모니터링 및 재학습
- 새로운 질문 유형 추가 시 Semantic Router만 업데이트하면 됨

---

## 결론

질문 분류 기반 검색 파이프라인 최적화를 통해 **검색 정확도 향상**, **응답 시간 단축**, **리소스 효율 개선**을 달성할 수 있습니다.

### 핵심 개선 사항

1. **Semantic Router 도입**: LLM 호출 없이 밀리초 단위로 질문 분류
2. **계층적 라우팅**: Local LLM의 인지 부하 문제 해결 (8개 → 2-3개 선택지로 단계적 분류)
3. **하이브리드 분류**: Semantic Router의 속도 + 계층적 라우팅의 정확도 결합
4. **Exhaustive 키워드 질문 최적화**: HyDE 비활성화 및 BM25 가중치 증가 (Quick Win)

### 예외 상황 대응

**예외 상황 대응**을 통해 시스템의 **견고성(Robustness)**과 **유연성(Flexibility)**을 확보하여, 다양한 사용자 질문에 효과적으로 대응할 수 있습니다.

### 구현 우선순위

**다음 단계**:
1. ✅ Phase 1: Semantic Router 구현 (대표 질문 예시 작성)
2. ✅ Phase 2: 계층적 라우팅 구현 (2단계 분류)
3. ✅ Phase 3: 하이브리드 분류 통합
4. ✅ Phase 4: 검색 전략 매핑 테이블 구현
5. ✅ Phase 5: 검색 파이프라인 통합
6. ✅ Phase 6: 테스트 및 검증 (A/B 테스트, 성능 측정)

### 기대 효과

- **분류 속도**: LLM 호출 (수백 ms) → Semantic Router (밀리초 단위)
- **분류 정확도**: +30-40% 향상 (계층적 라우팅)
- **검색 정확도**: +20-30% 향상 (특히 Exhaustive 질문)
- **리소스 효율**: LLM 호출 -50-70% 감소
- **응답 시간**: -15-25% 단축

### 주의사항

1. **Semantic Router 튜닝**: 대표 질문 예시는 실제 사용 패턴을 반영해야 함
2. **정기적 모니터링**: 분류 정확도 추적 및 개선
3. **점진적 배포**: A/B 테스트를 통한 검증 후 단계적 적용

---

**문의사항**: 개발팀에 문의하시기 바랍니다.

