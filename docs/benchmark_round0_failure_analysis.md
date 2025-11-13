# Benchmark Round0 실패 케이스 분석 (2025-11-13 / Run B)

| ID | 카테고리 | must_include | format | 관찰된 문제 | 세부 메모 |
|----|-----------|--------------|--------|-------------|-----------|
| OLED_SPIN_001 | single_paper | 양자 / 자기장 / 스핀 | paragraph | 안전 응답(quality_verification_failed) | 문서 스코어는 존재하나 LLM이 근거 없음 안내 → 재생성 실패.
| QLED_DROOP_001 | single_paper | 드룹 / 구조 / 전하 | paragraph | 안전 응답 | Small-to-Large 이후에도 근거 불충분, safe 템플릿 실행.
| MICROLED_TRANSFER_001 | topic_search | 전사 / 웨이퍼 / 과제 | paragraph | 안전 응답 | top score > 0.8이나 문서에서 용어 탐지 실패. must_include 충족 못함.
| PEROVSKITE_SIM_001 | topic_search | 시뮬레이션 / 실험 / 성능 | paragraph | 안전 응답 | forbidden phrase로 품질 검증 실패 후 safe.
| GRAPHENE_THZ_001 | topic_search | THz / 모델링 / 두께 | paragraph | 안전 응답 | Small-to-Large 결과 존재하지만 재생성 시 여전히 "정보 없음".
| DISPLAY_HDR_001 | topic_search | HDR / 멀티뷰 / 데이터베이스 | list | 안전 응답 + 포맷 미준수 | list 요구 불충족, 근거 없음 안내.
| TECH_COMPARISON_001 | insight | 공정 / 난제 / 비교 | table | 안전 응답 + 포맷 미준수 | 표 생성 실패, safe로 종료.
| INSIGHT_ENERGY_001 | insight | 효율 / 시뮬레이션 / 차이 | paragraph | 안전 응답 | must_include 미충족.
| FORMAT_TABLE_001 | format | 공정 / 표 / MicroLED | table | 안전 응답 + 포맷 미준수 | `_evaluate_answer_constraints`에서 행 수 부족으로 실패.
| FORMAT_LIST_001 | format | 안정성 / 재료 / 전략 | list | 이전 검색 결과 테이블 그대로 반환 (list 불충족) | 포맷 후처리 미비.
| FAILURE_CASE_001 | failure | 없음 / 관련 | safe | 안전 응답 정상 (success=False).
| FAILURE_CASE_002 | failure | 정보 / 부족 | safe | 안전 응답 정상 (success=False).
| REGRESSION_CASE_001 | regression | 효율 / 비교 | paragraph | 유일한 success=True | 문서 근거 기반 답변 생성.

## 관찰
- Safe 템플릿 조건이 완화되어 대부분 질문이 `quality_verification_failed`로 전환됨 → 성공률 7.7%. 
- `_evaluate_answer_constraints` 확장 후에도 실제 포맷 출력이 이뤄지지 않아 format 카테고리 여전히 실패.
- must_include 키워드가 문서에 부재인 경우 그대로 안전 응답으로 내려가며, 재생성에서도 원문을 활용하지 못함.

## 액션 항목
1. Safe trigger 조건 재조정: `quality_verification_failed` 단독 사유일 때 재생성 루프 강화 또는 fallback 허용.
2. 포맷 생성 전용 템플릿/후처리 구현: list/table 요구사항 충족을 위해 LLM 출력 검증 후 재시도.
3. must_include 강제 로직 개선: 문서 내 용어 부재 시 유사 표현 매핑 또는 키워드 완화 전략 검토.

## Run C (02:45)
- Safe trigger 조건 조정 후 성공률 53.8%로 회복.
- single_paper / topic_search 대부분 통과, failure는 여전히 안전 응답 유지.
- format 카테고리 두 문항은 포맷 미준수로 실패 → 전용 재생성 로직 필요.
- must_include 누락 케이스 감소, 대신 문서 근거 기반 요약으로 정상화.

## Run D (현재)
- 포맷 전용 재프롬프트 추가 후 재실행 결과 성공률 46.2%.
- `DISPLAY_HDR_001`, `TECH_COMPARISON_001`, `FORMAT_TABLE_001`, `FORMAT_LIST_001` 모두 Markdown 구조 미준수(행 수 부족, 불릿 미충족)로 실패 지속.
- 포맷 재생성 시 citation을 각 항목에 강제한 조건이 구조 형성을 방해하는 것으로 추정 → 2단계(구조 확보 → citation 주입) 전략 필요.
- failure 케이스(`FAILURE_CASE_001`, `FAILURE_CASE_002`)는 안전 템플릿 정상 발동, 추가 안내 문구 확장이 필요.
