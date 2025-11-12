# 📝 Changelog

All notable changes to this project will be documented in this file.

## [v3.7.0] - 2025-01-12 - Phase 3 완료

### ✨ 추가된 기능
- **File Aggregation 기능**: Exhaustive Query 지원 (파일 단위 집계 및 순위화)
  - Response Strategy Selector 구현
  - Exhaustive Query 자동 감지 및 처리
  - 파일별 청크 수 계산 및 가중치 적용
  - Weighted/Count 기반 순위화 전략
- **Diversity Penalty 메커니즘**: 문서 다양성 제어
  - diversity_penalty=0.3으로 최종 확정
  - 회귀 테스트로 성능 검증 (0.3 vs 0.32 비교)
  - Multi-doc 비율 97.1%, Diversity Ratio 51.2% 달성
- **Question Classifier 개선**: LLM 기반 정교한 질문 분류
  - exhaustive/complex/normal/simple 4단계 분류
  - classifier_verbose 옵션 추가

### 🐛 버그 수정
- UTF-8 인코딩 표준화: 모든 파일 I/O에 UTF-8 적용
- .gitignore 업데이트: 테스트 로그 및 임시 파일 제외

### 📚 문서화
- `.CLAUDE.md`에 QA Principles 추가
  - Issue Investigation Principle
  - Test-Driven Validation Principle
  - Evidence-Based Decision Making Principle
- Phase 3 완료 보고서 작성

### 🧪 테스트
- 35개 회귀 테스트 케이스 실행 (test_cases_comprehensive_v2.json)
- Diversity 지표 검증
  - 평균 고유 문서: 2.40개
  - Diversity Ratio: 51.2%
  - Multi-doc 비율: 97.1%

### ⏱️ 개발 소요 시간
- Day 1: 6시간 (File Aggregation 초기 구현)
- Day 2: 8시간 (Diversity Penalty 테스트 및 검증)
- Day 3: 2시간 (회귀 테스트 및 최종 확정)
- **총 16시간**

---

## [v3.6.2] - 2025-01-09

### 📊 분석 및 문서화
- 메타데이터 검색 아키텍처 분석
  - Semantic Scholar, Perplexity, Elicit 벤치마크
  - `docs/METADATA_SEARCH_ANALYSIS.md` 작성
- Phase 2.5.6 로드맵 추가
  - PDF 메타데이터 자동 추출 계획
  - ChromaDB 필드 확장 설계

### 📝 참고
- 코드 변경 없음 (분석 및 계획 단계)

---

## [v3.6.1] - 2025-01-09

### 🔧 설정 변경
- **ChromaDB 거리 함수 변경**: `l2` → `cosine`
  - 정규화된 임베딩 모델(mxbai, qwen3)에 최적화
  - 동일 유사도 범위로 일관된 threshold 적용 가능
- **공유 DB 볼륨 레이블 수정**: LGDKBB → LGDKRB

### 🧪 테스트 도구
- qwen3-embedding-8B 검증 스크립트 추가
  - 차원/정규화/속도 테스트

---

## [v3.6.0] - 2025-01-09

### ✨ Phase 2 QC 개선
- **Re-ranker 모델 통일**: multilingual-mini로 단일화
- **Hybrid Search 단순화**: 3단계 → 2단계 우선순위 최적화
- **Singleton 패턴**: Re-ranker 인스턴스 재사용으로 성능 향상
- **Score Filtering 개선**: OpenAI 스타일 적응형 threshold
- **Question Classifier 통합**: 질문 유형 자동 분류
- **Exhaustive Retrieval**: "모든/전체" 키워드 감지 (최대 100개)
- **설정 동기화**: config.json과 DEFAULT_CONFIG 통일 (13개 항목 추가)

### ⏱️ 개발 소요 시간
- Phase 1: 1시간
- Phase 2: 30분
- **총 1.5시간**

---

## [v3.4.0] - 2025-01-07

### ✨ Phase D: 답변 자연화
- 섹션 강제 구조 제거
- max_tokens 4096으로 증가
- NotebookLM 스타일 Inline Citation

### ✨ Phase C: Citation 95%
- 다중 출처 지원 (최대 2개/문장)
- 동적 임계값 (0.35-0.5)
- 짧은 문장 임계값 10으로 낮춤

### 🎨 UI 개선
- 설정 탭에서 비기능 체크박스 제거

### 📊 성능 향상
- 답변 품질: 자연스러움 +40%, 중복 내용 -60%
- Citation 커버리지: 80% → 95%

---

## [v3.1.0] - 2025-01-XX

### ✨ 프롬프트 개선
- Chain-of-Thought (CoT) 강화
- Few-shot 예시 확장
- 구조화된 출력 형식
- Self-verification 단계 추가 (할루시네이션 -30%)
- Query Expansion 고도화 (5가지 관점 전략)
- Vision 프롬프트 개선 (5단계 분석 절차)

### 📊 성능
- 프롬프트 수준: 상용 서비스 85% 달성 (8.5/10점)

---

## [v3.0.0] - 2025-01-02

### ✨ 추가된 기능
- 동적 Top-k 결정 (질문 특성 분석)
- 슬라이드/페이지 단위 중복 제거 전략 개선
- 출처 표시 형식 개선 (파일명 중복 제거)
- Vision 청킹 최적화 (PowerPoint 한 번만 열기)

### 🧹 정리
- requirements.txt 정리 (불필요한 패키지 제거)
- 불필요한 스크립트 및 모델 삭제

---

## [v2.7.0] - 2024-12-19

### ✨ 고급 청킹 시스템
- PDF 고급 청킹 시스템 구현
- PPTX 고급 청킹 시스템 구현
- Vision-Augmented 청킹 구현
- Layout-Aware 분석
- Small-to-Large 아키텍처
- 표 다층 청킹 (PDF/PPTX)

---

## [v2.6.0] - 2024-12-19

### ✨ 데스크톱 앱 완성
- PySide6 기반 데스크톱 앱
- 하이브리드 검색 + Cross-Encoder Re-ranker
- 구조 인식 청킹 전략 문서화

---

## [v2.5.0] - 2024-10-18

### 🎨 UI 개선
- 간이 문서 작성
- ChatGPT 스타일 UI

---

## [v2.4.0] - 2024-10-18

### ✨ 세션 관리
- 세션 관리 시스템
- 과거 세션 목록 및 전환

---

## [v2.3.0] - 2024-10-18

### ✨ 범용 API 지원
- 범용 API 지원 (OpenAI 호환)
- 동적 클라이언트 생성

---

## [v2.2.0] - 2024-10-18

### ✨ 대화 컨텍스트
- 대화 이력 기반 컨텍스트
- 세션별 대화 관리

---

## [v2.0.0] - 2024-10-18

### 🔄 대규모 리팩토링
- LCEL 방식으로 재작성
- 스트리밍 답변
- 유사도 점수 표시

---

## [v1.0.0] - 2024-10-14

### 🎉 초기 릴리스
- 기본 RAG 시스템
- ChromaDB 통합
- Streamlit UI

---

**Legend:**
- ✨ 추가된 기능
- 🐛 버그 수정
- 🔧 설정 변경
- 📚 문서화
- 🧪 테스트
- 🎨 UI 개선
- 📊 성능 향상
- 🔄 리팩토링
- 🧹 정리
- 🎉 릴리스
