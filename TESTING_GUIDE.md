# RAG 시스템 종합 테스트 가이드

**작성일**: 2025-11-11
**목적**: 시스템 품질 평가 및 개선 방향 도출

---

## 📋 개요

현재 RAG 시스템(v3.6.2)의 실제 성능을 종합적으로 평가하고, 개선 가능성을 파악하기 위한 테스트 프레임워크입니다.

### 핵심 특징
- ✅ **중간 단계 상세 로깅**: 모든 파이프라인 단계의 파라미터, 시간, 결과 기록
- ✅ **다양한 질문 유형**: 29개 테스트 케이스 (Simple/Normal/Complex/Exhaustive/Edge)
- ✅ **자동 분석**: 응답 시간, 비용, 병목 구간 자동 분석
- ✅ **개선 제안**: 데이터 기반 최적화 방향 제시

---

## 🗂️ 파일 구조

```
RAG_for_OC_251014/
├── docs/
│   ├── COMPREHENSIVE_TEST_PLAN.md          # 상세 테스트 계획
│   ├── RAG_SYSTEM_EVOLUTION_ANALYSIS.md    # 시스템 진화 분석
│   └── TESTING_GUIDE.md                    # 이 문서
│
├── utils/
│   └── detailed_logger.py                  # 상세 로깅 시스템
│
├── test_cases_comprehensive.json           # 테스트 케이스 (29개)
├── run_comprehensive_test.py               # 테스트 실행 스크립트
├── analyze_comprehensive_test.py           # 결과 분석 스크립트
│
└── test_logs/                              # 로그 출력 디렉토리
    ├── test_001_*.json                     # 개별 테스트 로그
    ├── test_002_*.json
    ├── ...
    └── test_summary.json                   # 전체 요약
```

---

## 🚀 실행 방법

### 1단계: 시뮬레이션 테스트 (현재 가능)

더미 데이터로 테스트 프레임워크를 검증합니다.

```bash
# 시뮬레이션 테스트 실행
python run_comprehensive_test.py

# 결과 분석
python analyze_comprehensive_test.py --input test_logs/test_summary.json
```

**출력:**
- `test_logs/*.json`: 개별 테스트 상세 로그
- `test_logs/test_summary.json`: 전체 요약
- `TEST_ANALYSIS.md`: 분석 보고서

---

### 2단계: 실제 RAGChain 통합 (다음 작업)

실제 RAG 시스템과 연동하여 진짜 데이터를 수집합니다.

**필요 작업:**

#### A. ChromaDB 오류 해결
```bash
# DB 상태 확인
python check_db_status.py

# 오류 발생 시 재구축
python re_embed_documents.py
```

#### B. RAGChain에 상세 로깅 통합

`run_comprehensive_test.py`의 `run_single_test` 함수를 수정:

```python
# 현재: 시뮬레이션
def run_single_test(test_case, rag_chain, logger):
    # === 더미 데이터 ===
    ...

# 변경: 실제 RAGChain 사용
def run_single_test(test_case, rag_chain, logger):
    test_id = test_case['test_id']
    question = test_case['question']

    # 로그 시작
    log = logger.start_test(test_id, question)

    try:
        # 실제 RAG 실행 (로깅 포함)
        answer = rag_chain.invoke(
            question,
            detailed_logger=logger  # 로거 전달
        )

        # 로그 완료
        log = logger.finalize(answer)
        return log

    except Exception as e:
        logger.log_error(str(e), "rag_execution")
        log = logger.finalize("ERROR")
        return log
```

#### C. RAGChain 수정 (선택적)

더 상세한 로깅을 위해 `utils/rag_chain.py` 수정:

```python
class RAGChain:
    def __init__(self, ..., detailed_logger=None):
        self.detailed_logger = detailed_logger
        ...

    def invoke(self, question, **kwargs):
        logger = kwargs.get('detailed_logger', self.detailed_logger)

        # 1. Classification
        if logger:
            start = time.time()
        classification = self.classify_question(question)
        if logger:
            logger.log_classification(
                q_type=classification['type'],
                confidence=classification['confidence'],
                ...
                elapsed_time=time.time() - start
            )

        # 2. Query Expansion
        if logger:
            start = time.time()
        expanded_queries = self.expand_query(question)
        if logger:
            logger.log_query_expansion(...)

        # ... (이하 각 단계마다 로깅)

        return answer
```

---

### 3단계: 전체 테스트 실행

```bash
# 전체 테스트 (약 30분 소요)
python run_comprehensive_test.py \
    --test-cases test_cases_comprehensive.json \
    --output-dir test_logs \
    --summary test_summary.json

# 결과 분석
python analyze_comprehensive_test.py \
    --input test_logs/test_summary.json \
    --output TEST_ANALYSIS.md
```

---

## 📊 테스트 케이스 구성

### Phase 1: 질문 유형별 (10개)
- Simple (3개): 단순 정의 질문
- Normal (3개): 일반적인 방법 질문
- Complex (2개): 비교 분석 질문
- Exhaustive (2개): 전체 요약 질문

### Phase 2: 검색 기능별 (5개)
- Hybrid Search (3개): 영어/한국어/혼합
- Citation (2개): 인용 정확도

### Phase 3: 에지 케이스 (4개)
- Ambiguous (1개): 모호한 질문
- No Info (2개): 정보 없는 질문
- Multi-condition (1개): 복합 조건

### Phase 4: 성능 테스트 (4개)
- 각 질문 유형별 1개씩

**총 29개 테스트 케이스**

---

## 📈 분석 지표

### 1. 응답 시간
- 평균, 중앙값, 표준편차
- P95, P99 (95%, 99% 백분위수)
- 질문 유형별 분류

### 2. 질문 분류
- 분류 분포 (Simple/Normal/Complex/Exhaustive)
- 분류 신뢰도 (평균, 최소, 최대)

### 3. 검색 품질
- 검색된 문서 수
- Vector/BM25/Reranker 점수
- Top-k 정확도

### 4. 비용
- LLM 호출 횟수
- 토큰 사용량
- 예상 비용 ($)

### 5. 파이프라인 단계별
- 각 단계별 시간 분석
- 병목 구간 식별
- 최적화 제안

### 6. 실패 분석
- 실패율
- 단계별 실패
- 실패 케이스 예시

---

## 🎯 성공 기준

### Tier 1: 기본 품질
- ✅ Simple 질문 정확도 > 90%
- ✅ Normal 질문 정확도 > 80%
- ✅ 인용 정확도 > 90%
- ✅ 응답 시간 P95 < 60초

### Tier 2: 고급 품질
- ✅ Complex 질문 정확도 > 70%
- ✅ Hallucination 비율 < 5%
- ✅ 응답 시간 P95 < 45초
- ✅ 비용 < $0.05/query

### Tier 3: 최적화 품질
- ✅ 분류기 정확도 > 85%
- ✅ Reranker 효과 > 15% 향상
- ✅ 병목 구간 < 30% (단일 단계)

---

## 🔍 로그 구조 예시

```json
{
  "test_id": "normal_001",
  "timestamp": "2025-11-11T10:30:00",
  "question": "OLED 디바이스의 효율을 향상시키는 방법은?",

  "classification": {
    "type": "normal",
    "confidence": 0.85,
    "method": "rule-based",
    "elapsed_time": 0.05
  },

  "query_expansion": {
    "enabled": true,
    "original_query": "OLED 디바이스의 효율을 향상시키는 방법은?",
    "expanded_queries": [
      "OLED 발광 효율을 개선하는 기술은?",
      "유기 발광 다이오드 성능 최적화 방법은?"
    ],
    "elapsed_time": 2.3,
    "llm_calls": 1
  },

  "search": {
    "vector_search": {
      "query": "...",
      "k": 60,
      "results": 58,
      "elapsed_time": 1.2,
      "top_scores": [0.9, 0.85, 0.8]
    },
    "bm25_search": {...},
    "fusion": {...}
  },

  "reranking": {
    "input_docs": 58,
    "output_docs": 18,
    "score_threshold": 0.5,
    "elapsed_time": 3.5
  },

  "context_expansion": {
    "initial_chunks": 18,
    "expanded_chunks": 36,
    "elapsed_time": 0.2
  },

  "generation": {
    "llm_model": "gemma3:4b",
    "context_tokens_estimate": 1800,
    "output_tokens_estimate": 350,
    "elapsed_time": 12.5
  },

  "citation": {
    "sources_count": 3,
    "sources": [...]
  },

  "total": {
    "elapsed_time": 23.5,
    "llm_calls": 2,
    "total_tokens_estimate": 2300,
    "estimated_cost": 0.023
  },

  "answer": "OLED 효율을 향상시키는 방법은..."
}
```

---

## 🛠️ 커스터마이징

### 테스트 케이스 추가

`test_cases_comprehensive.json` 수정:

```json
{
  "test_id": "custom_001",
  "category": "normal",
  "question": "새로운 질문",
  "expected_classification": "normal",
  "expected_response_time": 35,
  "expected_doc_count": [10, 30],
  "evaluation_criteria": ["기준1", "기준2"]
}
```

### 로깅 항목 추가

`utils/detailed_logger.py`의 `DetailedLog` 클래스에 필드 추가:

```python
@dataclass
class DetailedLog:
    ...
    custom_metric: float = 0.0  # 새 필드
```

---

## 📚 참고 문서

- [COMPREHENSIVE_TEST_PLAN.md](docs/COMPREHENSIVE_TEST_PLAN.md): 상세 테스트 계획
- [RAG_SYSTEM_EVOLUTION_ANALYSIS.md](docs/RAG_SYSTEM_EVOLUTION_ANALYSIS.md): 시스템 분석 및 발전 방향
- [PHASE2_COMPLETION_SUMMARY.md](docs/PHASE2_COMPLETION_SUMMARY.md): Phase 2 완료 보고서

---

## 🚧 현재 상태

### ✅ 완료
1. 종합 테스트 계획 수립
2. 상세 로깅 시스템 구현
3. 테스트 케이스 작성 (29개)
4. 테스트 실행 스크립트 작성
5. 결과 분석 스크립트 작성

### ⚠️ 진행 중
1. ChromaDB 오류 해결
2. 실제 RAGChain 통합

### ⬜ 대기 중
1. 전체 테스트 실행
2. 결과 분석
3. 개선 사항 구현
4. 재테스트

---

## 🎯 다음 단계

### 즉시 실행 가능
```bash
# 1. 시뮬레이션 테스트
python run_comprehensive_test.py

# 2. 결과 확인
python analyze_comprehensive_test.py --input test_logs/test_summary.json
```

### 실제 테스트 준비
1. ChromaDB 오류 해결
2. RAGChain 로깅 통합
3. 전체 테스트 실행
4. 결과 분석 및 개선

---

**작성자**: Claude Code
**버전**: 1.0
**상태**: ✅ 프레임워크 준비 완료
