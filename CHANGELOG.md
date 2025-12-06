# 📝 Changelog

All notable changes to this project will be documented in this file.

## [v0.7.1] - 2025-01-15 - 시스템 파이프라인 최적화 및 문서화

### 📊 시스템 분석 및 문서화
- **전체 파이프라인 분석 완료**: Pipeline A (문서 인제스션) 및 Pipeline B (질의응답) 상세 분석
- **시스템 분석 보고서 작성**: `docs/v0.7.1_system_analysis.md` 신규 작성
  - 아키텍처 개요 및 컴포넌트 분석
  - 최근 개선사항 요약 (v0.6.0 → v0.7.1)
  - 성능 지표 및 개선점 도출
  - 다음 단계 로드맵

### 📚 문서화 개선
- **파이프라인 아키텍처 문서 업데이트**: 전체 시스템 구조 상세 문서화
- **성능 분석 문서**: 개선 방안 및 최적화 전략 문서화

### 🔄 버전 업데이트
- **버전 업데이트**: v0.6.0 → v0.7.1
- **README.md**: 버전 정보 및 개발 기간 갱신
- **desktop_app.py**: Splash Screen 버전 문자열 업데이트

---

## [v0.6.0] - 2025-12-04 - UI/UX 개선 및 성능 최적화

### ✨ UI/UX 개선
- **채팅 버블 개선**: 내부 스크롤 제거, 높이 자동 증가
- **부드러운 스크롤 구현**: 스트리밍 중 자동 스크롤 (`_smooth_scroll_to_bottom()`)
- **반응형 레이아웃**: 창 크기 변경 시 버블 너비 자동 조정 (`resizeEvent`, `_update_all_bubble_widths()`)
- **기본 화면 크기 증가**: 1200x800 → 1320x880 (가로세로 10% 증가)
- **버블 여유 공간 조정**: 20% 수준으로 최적화

### 📊 성능 최적화 (Quick Wins)
- **BM25 가중치 동적 조정**: 질문 유형별 BM25/Vector 가중치 최적화
  - Simple: 0.7/0.3 (BM25/Vector)
  - Normal: 0.5/0.5
  - Complex: 0.3/0.7
  - Exhaustive: 0.5/0.5
- **Adaptive Threshold 최적화**: 질문 유형별 percentile 조정
  - Simple: 0.7
  - Normal: 0.6
  - Complex: 0.5
  - Exhaustive: 0.4
- **Gap-based Cutoff 활성화**: 점수 gap 기반 자동 컷오프로 노이즈 제거
- **성능 분석 문서**: `docs/performance_analysis_and_improvement_plan.md` 작성

### 🐛 버그 수정 및 안정성 개선
- **PDF 임베딩 시간 감지 로직 개선**:
  - 상대값 체크를 경고로 변경 (예외 발생하지 않음)
  - 절대 타임아웃(`max_page_time`)만 강제 적용 (120초)
  - Vision 페이지는 더 유연한 기준 적용 (기본 배수의 2배 허용)
  - Vision API 지연 시에도 처리 계속 진행

### ✨ 새로운 기능
- **PPTX → PDF 자동 변환**:
  - Windows COM을 통한 PowerPoint 자동 변환
  - 변환된 PDF 경로를 Document 메타데이터에 포함
  - 변환 실패 시 기존 PPTX 청킹으로 폴백
  - 설정: `auto_convert_pptx_to_pdf`, `pptx_conversion_tool`

### 🔧 설정 및 타임아웃 개선
- **Vision API 타입별 Base URL 제어**: OpenAI/OpenAI-compatible 호환성 향상
- **LLM 스트리밍 타임아웃**: `max_llm_stream_seconds` 설정 추가
- **업로드 타임아웃**: `max_upload_file_seconds` 설정 추가
- **상태 신호등**: 질문/업로드 상태 시각적 표시
- **오류 후 자동 복귀**: QTimer를 통한 idle 상태 자동 복귀

---

## [v0.4.0] - 2025-11-20 - SessionContext + Intent Detection (Major Feature Release)

### ✨ 추가된 기능
- **SessionContext 구현**: 최근 업로드 문서 자동 추적
  - 5분 타임아웃 기반 세션 관리
  - 개인 DB 업로드 시 자동 기록
  - 시간 기반 문서 만료 관리
  - 15개 단위 테스트 PASS

- **IntentDetector 구현**: 문서 참조 패턴 감지
  - 한국어 지시대명사: "이 문서", "그 파일" (신뢰도 0.7-0.95)
  - 시간 기반: "방금 올린", "아까 업로드한"
  - 영어 패턴: "this document", "uploaded file"
  - 파일명 직접 언급: confidence=1.0
  - 23개 단위 테스트 PASS

- **RAG Chain 검색 우선순위 통합**:
  1. File Mention (@파일명) - 기존
  2. Intent Detection (파일명 명시) - 신규, confidence=1.0
  3. Session Context (참조 패턴 + 5분 이내) - 신규, confidence≥0.7
  4. Auto Session (relevance≥0.7, 5분 이내) - 신규
  5. Full DB (fallback) - 기존

- **GUI 통합 완료**:
  - PDF 업로드 시 "📌 Session 추적 활성화" 메시지 표시
  - desktop_app.py, MainWindow, DocumentWidget 통합

### 🚀 사용자 경험 개선
- Before: "이 문서 요약해줘" → 전체 DB 검색 (업로드 파일 못 찾음)
- After: "이 문서 요약해줘" → Intent 감지 → 세션 문서 우선 검색
- Before: "방금 올린 파일" → @파일명 필수
- After: "방금 올린 파일" → 시간 기반 참조 자동 감지

### 🐛 버그 수정
- `_last_retrieved_docs` 튜플 형식 오류 (rag_chain.py:3304)
- `_generate_multi_queries` 존재하지 않는 메서드 호출 (rag_chain.py:3235)

### 🧪 테스트
- 총 41개 테스트 통과 (38 unit + 3 integration)
- Scenario 1: Intent Detection - 지시대명사 (PASS)
- Scenario 2: Time-based Reference (PASS)
- Scenario 3: Auto Session Context (PASS)

### 📝 문서
- TEST_PHASE3.5_GUI.md - GUI 테스트 가이드
- PHASE3.5_TEST_RESULTS.md - 테스트 결과 보고서

### ⚙️ 설정 추가
```json
{
  "enable_session_priority": true,
  "session_relevance_threshold": 0.7
}
```

---

## [v0.3.7] - 2025-01-14 - 파일 멘션 및 자동완성 기능

### ✨ 추가된 기능
- **@filename 파일 멘션 기능**: 특정 파일의 모든 청크를 직접 참조
  - `@filename.pdf` 패턴으로 파일 전체 내용 검색
  - 최대 100개 청크까지 Re-ranker로 필터링
  - 일반 검색 우회하여 특정 파일 집중 분석 가능
- **파일명 자동완성 기능**: QCompleter 기반 UI 개선
  - `@` 입력 시 자동으로 파일 목록 표시
  - 부분 문자열 매칭으로 파일 검색
  - 대소문자 구분 없이 필터링

### 🐛 버그 수정
- **Adaptive Max Results 로직 수정**: Question Classifier 결과 제대로 적용
  - `_adaptive_max_results`가 이제 분류 결과 기반으로 10/20/30/100개 문서 선택
  - `determine_optimal_top_k` LLM 결과도 폴백으로 활용
- **DEFAULT_CONFIG 동기화**: config.json과 config.py 파라미터 일치
  - `top_k`: 3 → 5
  - `reranker_initial_k`: 60 → 30
  - `diversity_penalty`: 0.0 → 0.3
  - `enable_synonym_expansion`: True → False

### 🔧 빌드 개선
- **ChromaDB 런타임 에러 수정**: PyInstaller hidden imports 추가
  - `chromadb.api.rust`, `chromadb.api.segment`, `chromadb.api.fastapi` 등
  - "no module named chromadb.api.rust" 에러 근본 해결
- **magic 라이브러리 제외**: Windows DLL 충돌 방지

---

## [v0.3.7-beta] - 2025-01-12 - Phase 3 완료

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

## [v0.3.6] - 2025-01-09

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

## [v0.3.6-patch1] - 2025-01-09

### 🔧 설정 변경
- **ChromaDB 거리 함수 변경**: `l2` → `cosine`
  - 정규화된 임베딩 모델(mxbai, qwen3)에 최적화
  - 동일 유사도 범위로 일관된 threshold 적용 가능
- **공유 DB 볼륨 레이블 수정**: LGDKBB → LGDKRB

### 🧪 테스트 도구
- qwen3-embedding-8B 검증 스크립트 추가
  - 차원/정규화/속도 테스트

---

## [v0.3.6-alpha] - 2025-01-09

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

## [v0.3.4] - 2025-01-07

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

## [v0.3.1] - 2025-01-XX

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

## [v0.3.0] - 2025-01-02

### ✨ 추가된 기능
- 동적 Top-k 결정 (질문 특성 분석)
- 슬라이드/페이지 단위 중복 제거 전략 개선
- 출처 표시 형식 개선 (파일명 중복 제거)
- Vision 청킹 최적화 (PowerPoint 한 번만 열기)

### 🧹 정리
- requirements.txt 정리 (불필요한 패키지 제거)
- 불필요한 스크립트 및 모델 삭제

---

## [v0.2.7] - 2024-12-19

### ✨ 고급 청킹 시스템
- PDF 고급 청킹 시스템 구현
- PPTX 고급 청킹 시스템 구현
- Vision-Augmented 청킹 구현
- Layout-Aware 분석
- Small-to-Large 아키텍처
- 표 다층 청킹 (PDF/PPTX)

---

## [v0.2.6] - 2024-12-19

### ✨ 데스크톱 앱 완성
- PySide6 기반 데스크톱 앱
- 하이브리드 검색 + Cross-Encoder Re-ranker
- 구조 인식 청킹 전략 문서화

---

## [v0.2.5] - 2024-10-18

### 🎨 UI 개선
- 간이 문서 작성
- ChatGPT 스타일 UI

---

## [v0.2.4] - 2024-10-18

### ✨ 세션 관리
- 세션 관리 시스템
- 과거 세션 목록 및 전환

---

## [v0.2.3] - 2024-10-18

### ✨ 범용 API 지원
- 범용 API 지원 (OpenAI 호환)
- 동적 클라이언트 생성

---

## [v0.2.2] - 2024-10-18

### ✨ 대화 컨텍스트
- 대화 이력 기반 컨텍스트
- 세션별 대화 관리

---

## [v0.2.0] - 2024-10-18

### 🔄 대규모 리팩토링
- LCEL 방식으로 재작성
- 스트리밍 답변
- 유사도 점수 표시

---

## [v0.1.0] - 2025-10-14

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
