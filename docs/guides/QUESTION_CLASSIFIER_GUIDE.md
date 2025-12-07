# Question Classifier 사용 가이드

## 📌 개요

**하이브리드 질문 분류기 (Rule-based + LLM)**를 구현했습니다.

### 핵심 기능
- ✅ **규칙 기반 빠른 분류** (80% 이상 신뢰도는 LLM 불필요)
- ✅ **애매한 경우에만 LLM 호출** (30% 미만 비율 목표)
- ✅ **자동 파라미터 최적화** (Multi-Query, Max Tokens 등)
- ✅ **4가지 질문 유형**: Simple, Normal, Complex, Exhaustive

---

## 🎯 질문 유형 분류 기준

### 1. Simple (단순 질문)
**특징**:
- 특정 값, 숫자, 이름을 묻는 질문
- 1-2 문장으로 답변 가능
- 짧고 명확함

**예시**:
```
✅ "kFRET 값은?"
✅ "3페이지 요약해줘"
✅ "얼마인가?"
✅ "무엇인가?"
```

**최적화 파라미터**:
- Multi-Query: **OFF** (불필요)
- Max Results: **10개** (최소)
- Reranker K: **30개** (최소)
- Max Tokens: **512** (짧은 답변)

**예상 응답시간**: 8-15초 (77초 → 85% 개선)

---

### 2. Normal (일반 질문)
**특징**:
- 설명이 필요한 일반적 질문
- 2-3 문단 답변
- 약간의 모호함 가능

**예시**:
```
✅ "OLED 효율은?"
✅ "작동 원리는?"
✅ "제품의 장단점은?"
```

**최적화 파라미터**:
- Multi-Query: **OFF** (기본)
- Max Results: **20개** (표준)
- Reranker K: **60개** (표준)
- Max Tokens: **1024** (표준 답변)

**예상 응답시간**: 25-35초 (77초 → 55% 개선)

---

### 3. Complex (복잡한 질문)
**특징**:
- 비교, 분석, 평가 요청
- 다중 항목 또는 다중 관점
- 긴 답변 필요 (4+ 문단)

**예시**:
```
✅ "OLED와 QLED를 비교해줘"
✅ "효율과 수명의 관계를 분석해줘"
✅ "A와 B의 차이점은?"
✅ "영향을 평가해줘"
```

**최적화 파라미터**:
- Multi-Query: **ON** (필수!)
- Max Results: **30개** (많이)
- Reranker K: **80개** (여유있게)
- Max Tokens: **2048** (긴 답변)

**예상 응답시간**: 40-50초 (82초 → 40% 개선)

---

### 4. Exhaustive (포괄적 질문)
**특징**:
- "모든", "전체", "각각" 등의 전수 조사
- 리스트/목록 형태 답변
- 많은 문서 필요

**예시**:
```
✅ "모든 슬라이드 제목을 나열해줘"
✅ "전체 페이지의 요약"
✅ "각각의 항목 설명"
```

**최적화 파라미터**:
- Multi-Query: **OFF** (불필요, 이미 많은 문서)
- Max Results: **100개** (최대)
- Reranker K: **150개** (여유있게)
- Max Tokens: **2048** (긴 답변)

**예상 응답시간**: 30-40초 (85초 → 55% 개선)

---

## 🚀 사용 방법

### 방법 1: 래퍼 클래스 사용 (권장)

**장점**: 기존 코드 수정 불필요

```python
from utils.rag_chain import RAGChain
from utils.question_classifier_integration import OptimizedRAGChain

# 1. 기존 RAGChain 초기화
rag_chain = RAGChain(config_manager, vector_store)

# 2. OptimizedRAGChain으로 래핑
optimized_rag = OptimizedRAGChain(
    rag_chain=rag_chain,
    use_classifier=True,          # 분류기 사용
    classifier_verbose=True       # 상세 로그 (개발 시)
)

# 3. 사용 (기존과 동일)
answer = optimized_rag.query("질문")

# 4. 통계 확인 (선택)
optimized_rag.print_stats()
```

**출력 예시**:
```
🎯 질문 분류 결과:
   유형: simple
   신뢰도: 90%
   방법: rule
   이유: Simple indicators: short length, value query

⚙️  최적화 파라미터 적용:
   Multi-Query: False
   Max Results: 10
   Reranker K: 30
   Max Tokens: 512

[검색 및 답변 생성...]

=== 질문 분류기 통계 ===
총 질문 수: 10
규칙만 사용: 7 (70%)
LLM 사용: 3 (30%)
LLM 호출 비율: 30% (목표: <30%) ✅
```

---

### 방법 2: RAGChain 직접 수정

**장점**: 더 깊은 통합, 데스크톱 앱에도 적용

**파일**: `utils/rag_chain.py`

```python
from utils.question_classifier import create_classifier

class RAGChain:
    def __init__(self, config_manager, vector_store, ...):
        # 기존 코드...

        # ========== 추가: 질문 분류기 ==========
        self.question_classifier = create_classifier(
            llm=self.llm,
            use_llm=True,
            verbose=self.verbose
        )
        # ========================================

    def _get_context(self, question: str, ...):
        """컨텍스트 검색 (최적화 버전)"""

        # ========== 추가: 질문 분류 및 최적화 ==========
        if hasattr(self, 'question_classifier'):
            classification = self.question_classifier.classify(question)

            if self.verbose:
                print(f"\n🎯 질문 유형: {classification['type']} "
                      f"(신뢰도: {classification['confidence']:.0%})")

            # 파라미터 동적 조정
            self.enable_multi_query = classification['multi_query']
            self.max_num_results = classification['max_results']
            self.reranker_initial_k = classification['reranker_k']
            self.max_tokens = classification['max_tokens']
        # ===============================================

        # 기존 로직 계속...
        if self.enable_multi_query:
            queries = self._generate_multi_query(question)
        else:
            queries = [question]

        # ... 나머지 기존 코드
```

---

## 📊 성능 비교

### 테스트 결과 (7개 질문)

| 질문 | 유형 | 신뢰도 | LLM 사용 | 예상 개선 |
|------|------|--------|---------|----------|
| kFRET 값은? | simple | 90% | ❌ | 85% ⬇️ |
| 3페이지 요약 | normal | 40% | ✅ | 55% ⬇️ |
| OLED 효율은? | normal | 40% | ✅ | 55% ⬇️ |
| 발광 원리 설명 | normal | 40% | ✅ | 55% ⬇️ |
| OLED vs QLED 비교 | complex | 100% | ❌ | 40% ⬇️ |
| 모든 슬라이드 나열 | exhaustive | 100% | ❌ | 55% ⬇️ |
| 제품 장단점 | normal | 40% | ✅ | 55% ⬇️ |

**통계**:
- 규칙만 사용: 3/7 (43%)
- LLM 사용: 4/7 (57%) ⚠️ 목표보다 높음

**원인**: Normal 유형이 많고 신뢰도 낮음 (40%)

---

## 🔧 고급 설정

### 1. 신뢰도 임계값 조정

**파일**: `utils/question_classifier.py`

```python
class QuestionClassifier:
    # 기본값
    HIGH_CONFIDENCE_THRESHOLD = 0.8   # 이상이면 LLM 불필요
    LOW_CONFIDENCE_THRESHOLD = 0.5    # 미만이면 LLM 필수
```

**조정 예시**:
```python
# LLM 호출 줄이기 (규칙 신뢰)
QuestionClassifier.HIGH_CONFIDENCE_THRESHOLD = 0.7
QuestionClassifier.LOW_CONFIDENCE_THRESHOLD = 0.4

# LLM 호출 늘리기 (정확도 우선)
QuestionClassifier.HIGH_CONFIDENCE_THRESHOLD = 0.9
QuestionClassifier.LOW_CONFIDENCE_THRESHOLD = 0.6
```

---

### 2. 규칙 기반만 사용 (LLM 없이)

**빠르지만 덜 정확**:

```python
classifier = QuestionClassifier(
    llm=None,                    # LLM 없음
    use_llm_fallback=False,      # LLM 사용 안 함
    verbose=False
)
```

**용도**:
- 프로토타이핑
- LLM 비용 절감
- 속도 최우선

---

### 3. LLM 항상 사용 (최고 정확도)

**느리지만 가장 정확**:

```python
# 임계값을 매우 높게 설정
QuestionClassifier.HIGH_CONFIDENCE_THRESHOLD = 1.0  # 항상 LLM 사용

classifier = QuestionClassifier(
    llm=llm,
    use_llm_fallback=True,
    verbose=True
)
```

---

### 4. 분류기 없이 사용 (기존 방식)

```python
optimized_rag = OptimizedRAGChain(
    rag_chain=rag_chain,
    use_classifier=False  # 분류기 비활성화
)

# 또는 기존 RAGChain 직접 사용
answer = rag_chain.query(question)
```

---

## 🎓 분류 알고리즘 상세

### Rule-based 점수 계산

#### Simple Score 계산 (0.0-1.0)

```python
점수 = 0.0

# 1. 짧은 길이 (+0.3)
if len(question) < 20:
    점수 += 0.3

# 2. 단순 패턴 (각 +0.25)
if re.search(r"값[은는이가]", question):
    점수 += 0.25
if re.search(r"얼마", question):
    점수 += 0.25
if re.search(r"무엇", question):
    점수 += 0.25
if re.search(r"\d+\s*(페이지|슬라이드)", question):
    점수 += 0.25

# 3. 특정 기술 용어 (+0.2)
if "kFRET" in question or "EQE" in question:
    점수 += 0.2

# 4. 물음표 하나 (+0.15)
if question.count("?") == 1:
    점수 += 0.15

최종 점수 = min(1.0, 점수)

# 판단
if 점수 >= 0.7:
    return "simple"
```

**예시**:
```
"kFRET 값은?"
  → 짧은 길이 (0.3) + 값은 (0.25) + kFRET (0.2) + ?하나 (0.15) = 0.9
  → simple ✅

"3페이지 내용 요약해줘"
  → 0.25 (3페이지) = 0.25
  → 0.7 미만 → simple 아님 ❌
```

---

#### Complex Score 계산 (0.0-1.0)

```python
점수 = 0.0

# 1. 복잡 키워드 (각 +0.3)
키워드 = ["비교", "차이", "분석", "평가", "관계", "영향"]
for 키워드 in 키워드들:
    if 키워드 in question:
        점수 += 0.3

# 2. 다중 항목 패턴 (+0.4)
if re.search(r"[와과]\s*[^\s]+\s*(비교|차이)", question):
    점수 += 0.4

# 3. 긴 질문 (+0.2)
if len(question) > 50:
    점수 += 0.2

# 4. 다중 물음표 (+0.25)
if question.count("?") > 1:
    점수 += 0.25

최종 점수 = min(1.0, 점수)

# 판단
if 점수 >= 0.6:
    return "complex"
```

**예시**:
```
"OLED와 QLED의 효율과 수명을 비교 분석해줘"
  → 비교 (0.3) + 분석 (0.3) + "와...비교" (0.4) = 1.0
  → complex ✅

"OLED 효율은?"
  → 0.0
  → complex 아님 ❌
```

---

### LLM-based 분류

**프롬프트 구조**:
```
다음 질문을 분류하세요:

질문: "{question}"

분류 기준:
1. simple: 단순 사실 질문 (예: "값은?")
2. normal: 일반 질문 (예: "효율은?")
3. complex: 복잡한 질문 (예: "비교")
4. exhaustive: 포괄적 질문 (예: "모든")

추가 분석:
- ambiguity: 모호함 정도 (0.0-1.0)
- multi_query_helpful: Multi-Query 도움 여부

JSON 출력:
{
    "type": "simple",
    "confidence": 0.95,
    "reasoning": "...",
    "ambiguity": 0.1,
    "multi_query_helpful": false
}
```

**LLM의 장점**:
- 맥락 이해 (단순 키워드 넘어)
- 모호함 감지
- 의도 파악

---

## 🐛 문제 해결

### Q1: LLM 호출 비율이 너무 높음 (>50%)

**원인**: Normal 유형이 많고 신뢰도 낮음

**해결**:
```python
# 1. 임계값 완화 (규칙 더 신뢰)
QuestionClassifier.HIGH_CONFIDENCE_THRESHOLD = 0.6
QuestionClassifier.LOW_CONFIDENCE_THRESHOLD = 0.3

# 2. Normal 점수 계산 추가 (현재는 기본값만)
# question_classifier.py에 _calculate_normal_score() 추가
```

---

### Q2: 분류가 부정확함

**원인**: 규칙이 질문 패턴을 커버하지 못함

**해결**:
```python
# question_classifier.py 수정

# 단순 패턴 추가
simple_patterns = [
    (r"값[은는이가]", "..."),
    (r"정의[는]", "정의 질문"),  # 추가
    (r"의미[는]", "의미 질문"),  # 추가
]

# 복잡 키워드 추가
complex_keywords = {
    "비교": "...",
    "상관관계": "correlation",  # 추가
    "트레이드오프": "tradeoff",  # 추가
}
```

---

### Q3: 한글이 깨져 보임

**원인**: Windows 콘솔 인코딩 문제

**해결**:
```python
# 콘솔 인코딩 설정
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 또는 환경변수 설정
# set PYTHONIOENCODING=utf-8
```

---

## 📈 기대 효과

### 전체 시스템 성능

**현재 (분류기 없음)**:
- 모든 질문: 77-82초 (Multi-Query 항상 ON, max_tokens=4096)

**개선 후 (분류기 적용)**:
- Simple 질문 (40%): 8-15초 → **85% 개선** 🎉
- Normal 질문 (30%): 25-35초 → **55% 개선**
- Complex 질문 (20%): 40-50초 → **40% 개선**
- Exhaustive 질문 (10%): 30-40초 → **55% 개선**

**가중 평균**:
```
(0.4 × 12초) + (0.3 × 30초) + (0.2 × 45초) + (0.1 × 35초)
= 4.8 + 9 + 9 + 3.5
= 26.3초

개선율: (79 - 26.3) / 79 = 67% ✅
```

---

### LLM 비용 절감

**LLM 호출 감소**:
- Multi-Query 생성: 100% → 20% (Complex만)
- 카테고리 검출: 100% → 100% (유지)
- 답변 생성: 100% → 100% (유지)

**토큰 사용 감소**:
- Simple: 4096 → 512 (87% 감소)
- Normal: 4096 → 1024 (75% 감소)
- Complex: 4096 → 2048 (50% 감소)

**총 비용 절감**: 약 60-70% ✅

---

## 🎯 다음 단계

### Phase 1: 테스트 및 검증 (1주일)
1. ✅ 분류기 구현 완료
2. ⬜ 100개 질문으로 정확도 테스트
3. ⬜ LLM 호출 비율 측정 (목표: <30%)
4. ⬜ 응답시간 벤치마크

### Phase 2: 통합 (1주일)
5. ⬜ RAGChain에 통합
6. ⬜ Desktop App에 적용
7. ⬜ Config 설정 추가
8. ⬜ UI에 분류 결과 표시

### Phase 3: 최적화 (2주일)
9. ⬜ Normal 점수 계산 개선
10. ⬜ 도메인 특화 패턴 추가
11. ⬜ 사용자 피드백 수집
12. ⬜ 머신러닝 분류기 탐색

---

## 📚 참고 자료

- 구현 코드: [utils/question_classifier.py](../utils/question_classifier.py)
- 통합 예제: [utils/question_classifier_integration.py](../utils/question_classifier_integration.py)
- 프로젝트 분석: [PROJECT_ANALYSIS_REPORT.md](./PROJECT_ANALYSIS_REPORT.md)

---

**작성일**: 2025-11-07
**버전**: v1.0
**상태**: 구현 완료, 테스트 대기
