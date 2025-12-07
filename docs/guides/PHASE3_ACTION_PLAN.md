# Phase 3 실행 계획: File-level Retrieval & Response

## 🎯 Phase 3 목표

"OLED ETL 재료 평가 논문을 모두 찾아줘" 같은 **Exhaustive Query**에 대해 **파일 리스트**를 반환하는 시스템 구축

### 핵심 요구사항
1. ✅ Chunk 검색 → File aggregation 작동 (Spike 검증 완료)
2. ⏳ Exhaustive query 자동 감지 → File list 반환
3. ⏳ Normal query는 기존 방식 유지 (역호환성)
4. ⏳ 파일별 관련도, 매칭 청크 수, 페이지 정보 제공

---

## 📅 3일 Sprint 계획 (총 12시간)

### Day 1: Reranker 통합 + Config (3시간)

#### 작업 1.1: Reranker 출력으로 재테스트 (1.5시간)
**목표**: 실제 reranked chunks (score 0.0~1.0)로 전략 비교

**구현:**
```python
# test_file_aggregation_with_reranker.py
# Reranking 포함 전체 파이프라인 테스트

from utils.rag_chain import RAGChain
from utils.file_aggregator import FileAggregator

rag = RAGChain(...)
chunks = rag.retrieve_and_rerank(query, k=50)  # Reranked chunks

aggregator = FileAggregator(strategy="weighted")
files = aggregator.aggregate_chunks_to_files(chunks, top_n=15)
```

**예상 결과**:
- Score 분포: 0.3 ~ 0.95 (reranker 출력)
- MAX vs. WEIGHTED 차이 명확
- WEIGHTED 전략이 균형잡힌 순위 제공

#### 작업 1.2: Config 파라미터 추가 (1시간)
**파일**: [config.py](config.py), [config.json](config.json), [config_test.json](config_test.json)

```python
# config.py DEFAULT_CONFIG에 추가
"enable_file_aggregation": False,  # 기본 비활성화 (안정성 우선)
"file_aggregation_strategy": "weighted",  # max | mean | weighted | count
"file_aggregation_top_n": 20,  # 반환할 최대 파일 수
"file_aggregation_min_chunks": 1,  # 최소 매칭 청크 수
```

#### 작업 1.3: 최적 전략 선택 (0.5시간)
**방법**: 5개 exhaustive query로 A/B 테스트

**테스트 케이스**:
1. "OLED ETL 재료 논문 모두"
2. "Hyperfluorescence 기술 전체"
3. "LTPO 디스플레이 관련 문서"
4. "유기 발광 재료 모든 연구"
5. "Quantum dot 전체 자료"

**평가 기준**:
- Top-5 파일이 모두 관련 있는가?
- 순위가 직관적인가?
- COUNT vs. WEIGHTED 중 선택

**예상 결정**: WEIGHTED (precision + coverage 균형)

---

### Day 2: RAGChain 통합 (6시간)

#### 작업 2.1: FileAggregator 통합 (2시간)
**파일**: [utils/rag_chain.py](utils/rag_chain.py)

```python
class RAGChain:
    def __init__(self, ..., enable_file_aggregation=False, file_aggregation_strategy="weighted"):
        # ...
        self.enable_file_aggregation = enable_file_aggregation

        if enable_file_aggregation:
            from utils.file_aggregator import FileAggregator
            self.file_aggregator = FileAggregator(strategy=file_aggregation_strategy)
```

#### 작업 2.2: Response Strategy Selector (2시간)
```python
def query(self, query: str):
    # 1. Classify query
    classification = self.classifier.classify(query)

    # 2. Route to appropriate handler
    if classification.type == "exhaustive" and self.enable_file_aggregation:
        return self._handle_exhaustive_query(query, classification)
    else:
        return self._handle_normal_query(query, classification)

def _handle_exhaustive_query(self, query, classification):
    """Exhaustive query → File list"""
    # Retrieve many chunks
    chunks = self.retrieve(query, k=100)

    # Rerank
    reranked_chunks = self.reranker.rerank(query, chunks)

    # Aggregate to files
    file_results = self.file_aggregator.aggregate_chunks_to_files(
        reranked_chunks,
        top_n=self.config.get("file_aggregation_top_n", 20)
    )

    # Format as file list
    return self._format_file_list_response(file_results)

def _format_file_list_response(self, file_results):
    """Generate Markdown table + summary"""
    table = self.file_aggregator.format_as_markdown_table(file_results)

    # Add summary statistics
    stats = self.file_aggregator.get_statistics(file_results)
    summary = f"\n\n**통계**: {stats['total_files']}개 파일, 평균 관련도 {stats['avg_score']:.0%}"

    return table + summary
```

#### 작업 2.3: Entry Point 업데이트 (1시간)
**파일**: [app.py](app.py), [desktop_app.py](desktop_app.py)

```python
# RAGChain 초기화 시 file aggregation 활성화
rag_chain = RAGChain(
    # ...기존 파라미터...
    enable_file_aggregation=config.get("enable_file_aggregation", False),
    file_aggregation_strategy=config.get("file_aggregation_strategy", "weighted")
)
```

#### 작업 2.4: End-to-end 테스트 (1시간)
**파일**: test_file_list_e2e.py

```python
# 5개 exhaustive query로 전체 파이프라인 테스트
test_queries = [
    "OLED ETL 재료 논문 모두",
    "Hyperfluorescence 기술 전체",
    # ...
]

for query in test_queries:
    response = rag_chain.query(query)
    assert "검색 결과:" in response  # File list 형식
    assert "|" in response  # Markdown table
```

---

### Day 3: 테스트 & 문서화 (3시간)

#### 작업 3.1: Regression 테스트 (1.5시간)
**목표**: 기존 normal query가 정상 작동하는지 확인

**방법**:
1. 기존 68개 테스트 재실행 (config.json: `enable_file_aggregation=false`)
2. 응답 시간, 품질 비교
3. 모든 테스트 통과 확인

**허용 기준**:
- Exit code 0
- 응답 시간 증가 <5%
- 답변 품질 유지

#### 작업 3.2: 성능 벤치마크 (0.5시간)
**측정 항목**:
- Normal query: 응답 시간 (기존 vs. 신규)
- Exhaustive query: 응답 시간 (chunk-level vs. file-level)
- Aggregation overhead

**목표**:
- Normal query 성능 저하 <5%
- Exhaustive query 응답 시간 <10초

#### 작업 3.3: 사용자 가이드 작성 (1시간)
**파일**: PHASE3_USER_GUIDE.md

**내용**:
1. File aggregation이란?
2. 언제 사용하나?
3. Config 설정 방법
4. 예시 query 및 결과
5. Troubleshooting

---

## 🎯 Phase 3 성공 기준

### 필수 (MUST)
- [ ] Exhaustive query → File list 반환
- [ ] Normal query 정상 작동 (역호환성)
- [ ] 응답 시간 <10초
- [ ] Config로 on/off 가능

### 권장 (SHOULD)
- [ ] 파일별 관련도 점수 표시
- [ ] 페이지 번호 정보 포함
- [ ] Markdown 테이블 가독성

### 선택 (COULD)
- [ ] 파일별 1-line 요약 (LLM 생성)
- [ ] 카테고리별 그룹화
- [ ] Export to CSV/JSON

---

## 📊 리스크 관리

### 리스크 1: Reranker 통합 이슈
**증상**: Reranked chunks의 score가 예상과 다름
**완화**: Spike test 1.1에서 조기 발견 및 수정
**Fallback**: Score 대신 COUNT 전략 사용

### 리스크 2: 응답 시간 초과
**증상**: File list 생성에 10초 이상 소요
**완화**: Aggregation은 0.001초 확인됨 (Spike 결과)
**Fallback**: top_n을 20 → 10으로 감소

### 리스크 3: Normal query 성능 저하
**증상**: 기존 query 응답 시간 증가
**완화**: `enable_file_aggregation=False`로 기본 비활성화
**Fallback**: 조건부 import로 overhead 제거

---

## 📁 산출물 체크리스트

### 코드
- [x] utils/file_aggregator.py (Spike 완료)
- [ ] utils/rag_chain.py 수정
- [ ] config.py 업데이트
- [ ] app.py, desktop_app.py 업데이트

### 테스트
- [x] test_file_aggregation_spike.py (Spike 완료)
- [ ] test_file_aggregation_with_reranker.py
- [ ] test_file_list_e2e.py
- [ ] Regression test (기존 68개)

### 문서
- [x] SPIKE_DECISION_FILE_AGGREGATION.md
- [x] PHASE3_ACTION_PLAN.md (본 문서)
- [ ] PHASE3_USER_GUIDE.md
- [ ] PHASE3_COMPLETION_REPORT.md

---

## 🚀 다음 Phase 미리보기

### Phase 4: 파일별 요약 생성 (Optional)
- LLM으로 각 파일의 1-line 요약 생성
- Caching으로 중복 방지
- Trade-off: +30초, +$0.02

### Phase 5: 메타데이터 필터링
- 연도, 키워드, 저자 필터
- 구조화된 쿼리 분해
- Post-retrieval verification

---

## 💡 핵심 원칙

### 1. 역호환성 최우선
- Normal query는 변경 없음
- File aggregation은 선택적 기능
- Config로 on/off 가능

### 2. 점진적 개선
- Spike → Config → 통합 → 테스트 → 최적화
- 각 단계별 검증
- 문제 발생 시 롤백 가능

### 3. 사용자 중심
- "파일 리스트"라는 명확한 목표
- 가독성 높은 Markdown 테이블
- 직관적인 순위

---

**작성일**: 2025-11-12
**예상 완료일**: 2025-11-15 (3일)
**담당**: Claude Code
**버전**: Phase 3 v1.0
