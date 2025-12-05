# 하이브리드 검색 최적화 계획 (개선안)

## 현재 상태 분석

### 1. BM25 토크나이저 (`_tokenize`)

**현재 구현:**
- 위치: `utils/vector_store.py` 917줄
- 기본 기능: 한글/영문 토큰화, stopwords 제거, 숫자/단위 보존
- 문제점:
  1. 한글/영문 혼용 처리 미흡
  2. 고유명사(저자 이름, 약어 등) 처리 부족
  3. 대소문자 변형 처리 없음 (예: "Duan Lian" vs "duan lian")
  4. 형태소 분석 미사용 (한국어 특성 미반영)

**현재 코드:**
```python
def _tokenize(self, text: str, preserve_numbers: bool = True) -> List[str]:
    # 토큰화: 영문, 한글, 숫자 모두 포함
    tokens = re.findall(r'[\w가-힣]+|\d+\.?\d*[%°C℃℉kmhmgdlnmlμΩVAmWkg]*', text.lower())
    # stopwords 제거
    # ...
```

### 2. 키워드 확장 (`expand_query_with_synonyms`)

**현재 구현:**
- 위치: `utils/rag_chain.py` 2175줄
- 방식: LLM 기반 동의어/연관어 생성
- 문제점:
  1. 고유명사(저자 이름, 약어 등)의 변형어 처리 부족
  2. LLM 호출로 인한 지연 시간
  3. 이름의 다양한 표기법 처리 미흡
  4. Fuzzy matching 미사용

## 웹 검색 기반 표준 기법 분석

### 일반적으로 사용되는 기법들

#### 1. **형태소 분석기 활용** (한국어)
- **KoNLPy의 Okt 또는 MeCab**: 한국어 형태소 분석에 특화
- **장점**: 어미, 접사 분리로 정확한 토큰화
- **단점**: 설치 복잡도, 성능 오버헤드

#### 2. **언어별 토크나이저 적용**
- **방법**: 텍스트에서 언어를 감지하여 각 언어에 적합한 토크나이저 적용
- **한국어**: 형태소 분석기
- **영어**: 공백 기반 토크나이저 + 스테밍(stemming)

#### 3. **개체명 인식 (NER)**
- **목적**: 인명, 지명 등 고유명사를 일관된 형태로 처리
- **방법**: spaCy, NLTK 등 라이브러리 활용
- **장점**: 저자 이름뿐만 아니라 모든 고유명사 처리 가능

#### 4. **Fuzzy Matching / Levenshtein Distance**
- **목적**: 오타, 변형어 처리
- **방법**: `fuzzywuzzy`, `rapidfuzz` 라이브러리
- **장점**: 정확한 키워드 매칭 실패 시에도 검색 가능

#### 5. **N-그램 토크나이저**
- **목적**: 부분 단어 일치 지원
- **장점**: 복합어, 약어 처리에 유용

#### 6. **동의어 사전 구축**
- **방법**: 도메인 특화 동의어 사전
- **장점**: LLM 호출 없이 빠른 처리

## 개선된 개선 방안 (표준 기법 기반)

### 1. BM25 토크나이저 개선

#### 1.1 언어별 토크나이저 적용 (권장)

**표준 방법:**
```python
def _tokenize(self, text: str, preserve_numbers: bool = True) -> List[str]:
    """언어별 토크나이저 적용 (표준 기법)"""
    if not text:
        return []
    
    # 1. 언어 감지
    languages = self._detect_languages(text)
    
    tokens = []
    
    # 2. 언어별 토크나이저 적용
    for lang, segment in self._split_by_language(text):
        if lang == 'ko':
            # 한국어: 형태소 분석기 사용 (선택적)
            if self.use_morphological_analyzer:
                ko_tokens = self._tokenize_korean(segment)
            else:
                # 폴백: 기존 방식
                ko_tokens = self._tokenize_simple(segment)
            tokens.extend(ko_tokens)
        elif lang == 'en':
            # 영어: 공백 기반 + 스테밍
            en_tokens = self._tokenize_english(segment)
            tokens.extend(en_tokens)
        else:
            # 기타: 기본 토크나이저
            tokens.extend(self._tokenize_simple(segment))
    
    # 3. 정규화 및 stopwords 제거
    cleaned_tokens = self._clean_tokens(tokens, preserve_numbers)
    
    return cleaned_tokens

def _detect_languages(self, text: str) -> List[str]:
    """텍스트에서 언어 감지"""
    # 간단한 휴리스틱: 한글이 있으면 'ko', 영문이 있으면 'en'
    has_korean = bool(re.search(r'[가-힣]', text))
    has_english = bool(re.search(r'[a-zA-Z]', text))
    
    languages = []
    if has_korean:
        languages.append('ko')
    if has_english:
        languages.append('en')
    
    return languages if languages else ['unknown']

def _split_by_language(self, text: str) -> List[Tuple[str, str]]:
    """언어별로 텍스트 분할"""
    # 한글/영문 혼용 텍스트를 언어별로 분할
    segments = []
    current_lang = None
    current_text = ""
    
    for char in text:
        if re.match(r'[가-힣]', char):
            lang = 'ko'
        elif re.match(r'[a-zA-Z]', char):
            lang = 'en'
        else:
            lang = current_lang  # 기호는 현재 언어 유지
        
        if lang == current_lang:
            current_text += char
        else:
            if current_text:
                segments.append((current_lang, current_text))
            current_lang = lang
            current_text = char
    
    if current_text:
        segments.append((current_lang, current_text))
    
    return segments

def _tokenize_english(self, text: str) -> List[str]:
    """영어 토크나이저 (스테밍 포함)"""
    # 1. 기본 토큰화
    tokens = re.findall(r'\b\w+\b', text.lower())
    
    # 2. 스테밍 (간단한 버전)
    stemmed = []
    for token in tokens:
        # 간단한 스테밍 규칙
        if token.endswith('ing'):
            stemmed.append(token[:-3])
        elif token.endswith('ed'):
            stemmed.append(token[:-2])
        elif token.endswith('s') and len(token) > 3:
            stemmed.append(token[:-1])
        else:
            stemmed.append(token)
    
    return stemmed
```

#### 1.2 형태소 분석기 통합 (선택적, 고급)

**방법:**
```python
# KoNLPy 사용 (선택적)
try:
    from konlpy.tag import Okt
    self.okt = Okt()
    self.use_morphological_analyzer = True
except ImportError:
    self.use_morphological_analyzer = False
    print("[WARN] KoNLPy 미설치: 형태소 분석기 비활성화")

def _tokenize_korean(self, text: str) -> List[str]:
    """한국어 형태소 분석"""
    if not self.use_morphological_analyzer:
        return self._tokenize_simple(text)
    
    # 형태소 분석
    morphs = self.okt.morphs(text)
    
    # 명사, 동사, 형용사만 추출 (선택적)
    nouns = self.okt.nouns(text)
    
    # 결합
    tokens = list(set(morphs + nouns))
    
    return tokens
```

#### 1.3 대소문자 정규화 (표준 기법)

**방법:**
```python
def _normalize_case(self, text: str) -> str:
    """대소문자 정규화 (표준 기법)"""
    # 1. 전체 소문자 변환
    normalized = text.lower()
    
    # 2. 고유명사 패턴 복원 (대문자로 시작하는 단어)
    # 예: "duan lian" → "Duan Lian" (2단어 패턴)
    words = normalized.split()
    if len(words) == 2 and all(len(w) > 2 for w in words):
        # 2단어 패턴은 고유명사 가능성 높음
        normalized = ' '.join([w.capitalize() for w in words])
    
    return normalized
```

### 2. 키워드 확장 개선

#### 2.1 Fuzzy Matching 적용 (표준 기법)

**방법:**
```python
from rapidfuzz import fuzz, process

def _expand_with_fuzzy_matching(self, query: str, corpus: List[str], threshold: int = 80) -> List[str]:
    """Fuzzy matching으로 유사 키워드 찾기"""
    # corpus에서 유사한 키워드 찾기
    matches = process.extract(query, corpus, limit=5, scorer=fuzz.token_sort_ratio)
    
    # threshold 이상인 것만 반환
    similar_terms = [term for term, score, _ in matches if score >= threshold]
    
    return similar_terms
```

#### 2.2 개체명 인식 (NER) 활용 (표준 기법)

**방법:**
```python
# spaCy 또는 NLTK 사용
try:
    import spacy
    self.nlp = spacy.load("en_core_web_sm")  # 영어용
    # 한국어는 KoNLPy의 NER 사용
except ImportError:
    self.nlp = None

def _extract_entities(self, text: str) -> Dict[str, List[str]]:
    """개체명 추출 (인명, 지명, 기관명 등)"""
    entities = {
        'PERSON': [],  # 인명
        'ORG': [],     # 기관명
        'GPE': [],     # 지명
    }
    
    if self.nlp:
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in entities:
                entities[ent.label_].append(ent.text)
    
    return entities
```

#### 2.3 통합 키워드 확장 (표준 기법 조합)

**방법:**
```python
def expand_query_with_synonyms(self, original_query: str) -> str:
    """통합 키워드 확장 (표준 기법 조합)"""
    if not self.enable_synonym_expansion:
        return original_query
    
    expanded_terms = []
    
    # 1. 개체명 추출 (NER)
    entities = self._extract_entities(original_query)
    for entity_type, entity_list in entities.items():
        for entity in entity_list:
            # 개체명의 변형어 생성
            variations = self._generate_entity_variations(entity)
            expanded_terms.extend(variations)
    
    # 2. Fuzzy matching (기존 corpus에서 유사 키워드 찾기)
    if hasattr(self, 'bm25_corpus') and self.bm25_corpus:
        fuzzy_matches = self._expand_with_fuzzy_matching(original_query, self.bm25_corpus)
        expanded_terms.extend(fuzzy_matches)
    
    # 3. 동의어 사전 조회
    synonym_matches = self._lookup_synonyms(original_query)
    expanded_terms.extend(synonym_matches)
    
    # 4. LLM 기반 확장 (기존 로직, 선택적)
    if self.enable_llm_expansion:
        llm_expanded = self._expand_with_llm(original_query)
        expanded_terms.extend(llm_expanded)
    
    # 5. 중복 제거 및 결합
    unique_terms = list(set(expanded_terms))
    if unique_terms:
        expanded_query = f"{original_query} ({' '.join(unique_terms[:10])})"
        return expanded_query
    
    return original_query

def _generate_entity_variations(self, entity: str) -> List[str]:
    """개체명 변형어 생성 (일반적 방법)"""
    variations = [entity]
    
    # 1. 대소문자 변형
    variations.append(entity.lower())
    variations.append(entity.title())
    variations.append(entity.upper())
    
    # 2. 공백/하이픈 변형
    if ' ' in entity:
        variations.append(entity.replace(' ', '-'))
        variations.append(entity.replace(' ', ''))
    
    # 3. 순서 변형 (2단어인 경우)
    words = entity.split()
    if len(words) == 2:
        variations.append(f"{words[1]} {words[0]}")
    
    return list(set(variations))
```

### 3. BM25 검색 최적화

#### 3.1 쿼리 정규화 (표준 기법)

**방법:**
```python
def _normalize_query(self, query: str) -> str:
    """BM25 검색을 위한 쿼리 정규화"""
    # 1. 대소문자 정규화
    normalized = self._normalize_case(query)
    
    # 2. 개체명 변형어 추가
    entities = self._extract_entities(query)
    entity_variations = []
    for entity_list in entities.values():
        for entity in entity_list:
            entity_variations.extend(self._generate_entity_variations(entity))
    
    # 3. 쿼리와 변형어 결합
    all_terms = [normalized] + entity_variations
    
    return ' '.join(all_terms[:5])  # 최대 5개
```

#### 3.2 BM25 검색 시 정규화 적용

**위치:** `utils/vector_store.py`의 `similarity_search_hybrid` 메서드

```python
def similarity_search_hybrid(self, query: str, ...):
    # 1. 쿼리 정규화
    normalized_query = self._normalize_query(query)
    
    # 2. 정규화된 쿼리로 토큰화
    query_tokens = self._tokenize(normalized_query)
    
    # 3. BM25 검색
    bm25_scores = self.bm25.get_scores(query_tokens)
    # ...
```

## 구현 우선순위 (표준 기법 기반)

### Phase 1: 빠른 개선 (1-2일) - 표준 기법 적용

1. **대소문자 정규화 추가**
   - `_normalize_case` 메서드 구현
   - BM25 검색 전 쿼리 정규화

2. **개체명 변형어 생성**
   - `_generate_entity_variations` 메서드 구현
   - 저자 이름뿐만 아니라 모든 개체명 처리

3. **언어별 토크나이저 기본 구조**
   - 언어 감지 및 분할 로직
   - 영어 스테밍 기본 구현

### Phase 2: 중기 개선 (3-5일) - 고급 기법

4. **Fuzzy Matching 통합**
   - `rapidfuzz` 라이브러리 사용
   - 기존 corpus에서 유사 키워드 찾기

5. **동의어 사전 구축**
   - 도메인 특화 동의어 사전
   - 파일 기반 또는 DB 기반 저장

6. **형태소 분석기 통합 (선택적)**
   - KoNLPy 설치 및 통합
   - 성능 테스트 후 활성화 여부 결정

### Phase 3: 장기 개선 (1-2주) - 최적화

7. **NER 통합**
   - spaCy 또는 KoNLPy NER 사용
   - 개체명 일관성 보장

8. **학습 기반 쿼리 확장**
   - 사용자 검색 패턴 분석
   - 자동 동의어 학습

## 표준 기법 vs 제안한 방법 비교

| 항목 | 제안한 방법 | 표준 기법 | 권장 |
|------|-----------|----------|------|
| **고유명사 처리** | 정규화 함수 | NER (개체명 인식) | ✅ NER |
| **변형어 생성** | 하드코딩 규칙 | Fuzzy Matching | ✅ Fuzzy Matching |
| **한국어 처리** | 기본 토크나이저 | 형태소 분석기 | ⚠️ 선택적 (성능 고려) |
| **영어 처리** | 기본 토크나이저 | 스테밍 | ✅ 스테밍 |
| **동의어 확장** | LLM 기반 | 동의어 사전 + LLM | ✅ 하이브리드 |

## 최종 권장 사항

### 즉시 적용 (표준 기법)

1. **대소문자 정규화**: 간단하고 효과적
2. **개체명 변형어 생성**: 일반적인 방법
3. **영어 스테밍**: 표준 기법
4. **Fuzzy Matching**: 오타/변형어 처리

### 선택적 적용 (성능 고려)

5. **형태소 분석기**: 성능 오버헤드 vs 정확도 트레이드오프
6. **NER**: 설치 복잡도 vs 정확도 향상

### 장기 적용

7. **동의어 사전 구축**: 도메인 특화
8. **학습 기반 확장**: 사용자 패턴 분석

## 예상 효과

- **고유명사 검색 정확도**: +25-35% (NER + 변형어)
- **오타/변형어 처리**: +30-40% (Fuzzy Matching)
- **한글/영문 혼용 처리**: +20-30% (언어별 토크나이저)
- **전체 검색 Recall**: +10-15% (통합 개선)
