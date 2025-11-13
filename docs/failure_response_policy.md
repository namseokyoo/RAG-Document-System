# 실패 대응 템플릿 & 분기 조건 정의 (Draft)

## 1. 분기 조건 정의
1. **Retrieval 결과 부족**
   - `self._last_retrieved_docs` 길이 < `min_num_results` (현재 3) 이고 top-1 score < 0.5.
   - Hybrid 검색 시 BM25/Vector 모두 빈 리스트인 경우.
2. **품질 검증 실패**
   - `_verify_answer_quality` 결과에서 `no_forbidden_phrases == 0.0` 또는 `content_match` < 0.2.
   - must_include 체크 후 누락된 키워드가 존재.
3. **Failure 카테고리**
   - Question classifier가 `failure` 또는 `unsupported`로 분류.
   - 테스트 모드(`benchmark_questions`)에서 `expected_sources`가 빈 배열.

조건 중 하나라도 만족하면 안전 응답 경로로 전환한다.

## 2. 안전 응답 템플릿 초안
```
죄송하지만 제공된 문서에서 "<요청 주제>"와 직접적으로 관련된 근거를 찾을 수 없습니다.
- 검색 범위를 늘리거나 다른 키워드(예: <추천 키워드 2~3개>)로 다시 시도해보세요.
- 최신 수치나 외부 데이터가 필요하다면 사내 데이터베이스 또는 공개 보고서를 확인하십시오.

필요하시면 추가로 조사할 방향을 알려주시면 다시 도와드리겠습니다.
```
- `추천 키워드`: 질문에서 명사 추출 또는 도메인별 기본 키워드 리스트 사용.
- Citation은 붙이지 않는다.
- 안전 응답 발생 시 `success=False`로 표기하여 후속 처리 용이하게 한다.

## 3. 로깅 항목
- `failure_reason`: retrieval_insufficient / forbidden_phrase / must_include_missing / classifier_failure.
- `top_scores`: 상위 3개 score 기록.
- `must_include_missing_terms`: 누락된 키워드 리스트.
- `retry_recommended`: Bool (사용자에게 재질문 제안 여부).

## 4. 추가 가이드
- 안전 응답 발생 시 LLM 재호출 금지 → 낭비 방지.
- 추후 Self-RAG 도입 시 이 경로에서 재검색/재생성 옵션을 실험.
- UI에서는 안전 응답을 별도 스타일로 표시하여 오탐 인지 지원.
