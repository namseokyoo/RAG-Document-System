# 품질 개선 실행 로드맵 (2025-11-13)

## 1. 구현 순서
1. **프롬프트 훅 추가** (`utils/rag_chain.py`)
   - `query()` 입력에 `answer_constraints` 파라미터 도입
   - must_include / expected_format / category 기반으로 system 메시지 조합
   - 템플릿 구성 함수 `_build_system_message()` 작성
2. **형식별 응답 로직**
   - list/table 요청 시 LLM 출력 검증 및 fallback 메시지 처리
   - safe 요청 시 안전 템플릿 반환
3. **실패 분기 적용**
   - Retrieval/품질 검증 결과 기반으로 `failure_response_policy` 적용
   - 로깅 필드 추가 (`failure_reason`, `missing_terms`, `top_scores`)
4. **후처리 검사**
   - must_include 누락 시 재시도 or 안전 응답 전환 정책 결정
   - Citation 누락/포맷 미준수 시 경고 로깅

## 2. 테스트 계획
- `scripts/run_benchmark.py` Round1 재실행 → `test_logs/benchmark_round1.json`
- `scripts/analyze_benchmark.py`로 키워드/포맷 통과율 비교
- 실패 케이스 수동 검증 (safe 응답 문구 확인)
- 필요 시 소규모 단위 테스트: `_build_system_message()` 함수 입력/출력 검증

## 3. 문서 & 로그 업데이트
- `docs/rag_quality_benchmark_plan.md`: Round1 추적 섹션 추가 예정
- `docs/benchmark_round0_failure_analysis.md`: 개선 후 결과 비교 테이블 갱신
- `development_log.md`: 구현 및 테스트 타임라인 기록

## 4. 주의 사항
- 프롬프트 길이 증가에 따른 토큰 사용량 모니터링
- 안전 응답이 과도하게 발생하지 않도록 threshold 조정값 로그화
- Self-RAG / 재생성 로직 도입 시 본 계획 확장.
