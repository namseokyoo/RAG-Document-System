# RAG 품질 벤치마크 및 테스트 계획 (v0.1)

## 1. 상용 RAG 서비스 품질 기준
- **Perplexity / Glean / NotebookLM** 등은 다음을 공통 제공
  - 질문 의도 분류 + 적절한 검색 경로 선택 (웹 / 내부 DB / 메타데이터)
  - Top-k 문서에서 **정확한 문장 단위 인용**을 삽입하며, 문장마다 근거 제공
  - 다양한 문서에서 근거를 결합하여 **인사이트** 제공 (단순 요약 X)
  - 질문이 요구하는 형식(표/리스트/정의)을 자연스럽게 맞춤
  - 답변 불가 시 근거 기반으로 “왜 불가한지” 설명

> **평가 포인트**: 검색 적합성, 응답 정확도/완전성, 다양성, 인용 정확도, 응답 형식 준수, 실패 처리 품질

## 2. 현재 시스템 진단 (2025-11-12 Round 2 기준)
- **Retrieval**: 카테고리별 문서 매칭은 정상화 (MicroLED/QLED 등)
- **Answering**: 관련 문서가 있어도 "정보 없음" 안내 빈도 높음 → 컨텍스트 요약/증류 미흡
- **Diversity**: multi-doc 질문에서 고유 문서 수 2~3개 확보 (목표 3~4개 필요)
- **형식**: 표/상세 요약, 비교 포맷은 미구현 → 대부분 서술형 단일 단락
- **실패 응답**: “문서에 없다” 안내만 존재, 대체 자료/다른 접근 제안 부족

## 3. 테스트 목표
1. **검색 품질 최적화**
   - Top-k 문서에 실제 정답이 포함되는지 확인 (Precision@k, Recall@k)
   - 카테고리 미스매치 / 불필요한 문서 혼입 여부 측정
2. **응답 품질 향상**
   - 필수 정보 포함 여부, 잘못된 추론 방지
   - 인사이트/비교 질문에서 최소 3개 이상의 근거를 활용
   - 원하는 형식(목록, 표, 요약) 준수
3. **인용/출처 정확도**
   - 문장별 인용/페이지 일치율 95%+ 목표
4. **다양성·탈중복**
   - 동일 문서 반복 인용률 40% 이하 (multi-doc 질문 기준)
5. **실패 처리 품질**
   - 근거 기반의 “답변 불가” 메시지 및 다음 행동 제안

## 4. 테스트 스위트 구성

| 스위트 | 목적 | 질문 수 | 주요 검증항목 |
|--------|------|---------|----------------|
| **Retrieval Core** | 질의→문서 매칭 | 30 | Precision@5, Recall@10, 카테고리 정확도 |
| **Answer Accuracy** | 단일 문서 사실 질의 | 20 | 핵심 정보 포함, 단문/수치 응답 |
| **Insight & Comparison** | 다문서 종합/비교 | 20 | 다양성, 비교 구조, 인사이트 여부 |
| **Format & Style** | 출력 형식 준수 | 10 | 표/리스트/요약 프롬프트에 대한 대응 |
| **Failure & Robustness** | 모호/불가 질의 | 10 | 실패 대응, 안전 필터 |
| **Regression Set** | 변경 후 회귀 테스트 | 30 | 과거 실패 케이스 재검증 |

### 예시 카테고리별 질문분포
- OLED/QLED/MicroLED: 최신 연구, 효율 수치, 제조 공정 비교
- Perovskite: 시뮬레이션/실험 결합 사례, 재료 특성 변화
- Graphene: THz 안테나 설계, 재료 물성 예측
- Display/Immersive: VR/AR 데이터셋, 3D 디스플레이 벤치마크

## 5. 평가 지표 및 도구
- **Retrieval**: Precision@k, Recall@k, Hit@k, MRR, Category Accuracy
- **Answering**
  - 정답 스크립트 대비 Rouge/BERTScore
  - LLM 기반 평가(GPT-4/Claude)로 정확도/완전성/인용 일치 여부 자동 평가
  - 내부 규칙 기반 체크(예: “정보 없음” 문구 포함 시 실패)
- **다양성**: 고유 문서 수 / 전체 인용 수, Shannon Diversity Index
- **형식 준수**: 정규식 기반 포맷 검사 + LLM 가이드라인 평가
- **실패 대응**: 수동 리뷰 리스트 (False Positive/Negative 기록)

## 6. 실행 프로세스 제안
1. **질문 풀 관리**
   - `tests/data/benchmark_questions.json` 생성
   - 각 항목에 “기대 문서/핵심 키워드/정답 템플릿” 기재
2. **실행 스크립트**
   - `scripts/run_benchmark.py` 작성: 질문 → RAG → 결과 저장(`test_logs/benchmark_roundX.json`)
   - Retrieval 단계에서 top 문서/점수/카테고리 기록
   - Answer 단계는 preview + 인용/다양성 수치 기록
3. **평가 & 리포트**
   - `scripts/analyze_benchmark.py`: 정량 지표 계산, 실패 케이스 추출
   - 워크플로우: 실행 → 자동 분석 → manual spot-check
4. **회귀 테스트**
   - 주요 변경(프롬프트, reranker, chunk 전략) 후 Regression Set 필수 실행
   - 히스토리 남기기 (`test_logs/benchmark_history/`)

## 7. 품질 개선 로드맵과 연결
- **검색 튜닝**: BM25 가중치, 메타데이터 필터, 카테고리별 초기 k 조정
- **응답 생성**: 프롬프트 템플릿(포맷 지시), Self-RAG 혹은 Answer Structuring 단계 도입 검토
- **Citation 강화**: 문장 길이별 임계값 최적화, 출처 중복 방지 로직 개선
- **실패 대응 강화**: “근거 없음” 시 대안 문서/재검색 안내, 사용자 액션 제안

## 8. 산출물 & 추적
- `docs/rag_quality_benchmark_plan.md` (본 문서)
- `tests/data/benchmark_questions.json` (예정)
- `scripts/run_benchmark.py`, `scripts/analyze_benchmark.py` (예정)
- `test_logs/benchmark_round*.json` (실행 결과)
- `reports/benchmark_summary_YYYYMMDD.md` (자동 분석 보고서)

---
**다음 단계**
1. 질문 풀 초안 작성 (카테고리별 5~10개)  
2. Benchmark 실행 스크립트 구현  
3. Round 0 실행 → 문제 케이스 선별  
4. 품질 개선 작업 후 Round 1~N 반복
