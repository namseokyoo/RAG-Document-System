# 질문 유형별 프롬프트/포맷/키워드 전략 설계 (Draft)

## 1. 입력 메타데이터 정리
- `validation.must_include`: 질문 큐레이션 단계에서 제공되는 키워드 리스트.
- `expected_format`: `paragraph`, `list`, `table`, `safe` 등.
- `question.category`: single_paper / topic_search / insight / format / failure / regression.
- 추가 신호: `answer.classification` (RAGChain 내부)와 프론트에서 전달 가능한 사용자 옵션.

## 2. 프롬프트 전송 방식
- `RAGChain.query` 호출 시 `extra_instructions` 사전을 받아 템플릿에 삽입하는 훅 추가.
- 기본 구조: System 메시지 상단에 "핵심 용어" 섹션, "요구 포맷" 섹션을 조건부로 삽입.

### 2.1 must_include 처리
- 텍스트 예시: `핵심 용어: 양자, 자기장, 스핀 → 각 용어를 최소 한 번 이상 자연스럽게 언급하세요.`
- LLM에 과도한 강제를 주지 않기 위해 "가능하면 그대로"/"정보가 없으면 근거와 함께 부재를 설명" 문구 추가.

### 2.2 포맷 요구 사항
- `expected_format == "list"`: Markdown 불릿 예시 제공 (`- 항목: 설명[1]`).
- `expected_format == "table"`: 2~3열 기본 구조 예시, 근거 부족 시 "표로 제시할 근거 없음" 문구 지침.
- `expected_format == "safe"`: "관련 정보 없음" 템플릿과 후속 제안 인스트럭션 제공.
- 기타: 기본 paragraph 지침 유지.

### 2.3 공통 지시
- Citation 규칙 유지.
- 키워드 누락 시 "정보 부재"를 명확히 표기하도록 지시.
- 포맷 지키기 어려울 경우 대체 메시지 안내.

## 3. 템플릿 구조 초안
```
[시스템 메시지 헤더]
- 역할 정의 + 문서 기반 원칙
- (옵션) 핵심 용어 섹션
- (옵션) 요구 포맷 섹션
- (옵션) 안전 응답 지침
- 공통 Citation/추측 금지 규칙
```

### 3.1 카테고리별 추가 메시지
- `single_paper`: "특정 문서 기반" 강조, 실험 조건/수치 우선.
- `topic_search`: 복수 문서 종합, 동향/과제 요약 지침.
- `insight`: 비교/공통점/차이점 명시 지시, 최소 3개 근거 활용.
- `format`: 포맷 섹션을 최우선으로 재차 강조.
- `failure`: 안전 템플릿 우선 (근거 없음 + 제안).

## 4. 구현 영향도 메모
- `RAGChain` 내 프롬프트 선택 로직 개선 필요 (`_select_prompt_template` 유사 함수 도입 예정).
- `tests/data/benchmark_questions.json` 같은 외부 테스트용 메타 데이터는 운영 코드에서는 직접 사용하지 않으므로, 실제 질문 입력 시 적용할 규칙은 Question Classifier 결과 + 프런트엔드 옵션으로 추론.
- PromptTemplate 변경 시 unit/regression 테스트 필요 (LLM 호출 mock 기준).

## 5. 향후 확장 포인트
- must_include를 post-processing 검증으로 활용해 1차 실패 시 재생성(Self-RAG) 고려.
- 포맷 검증을 위한 간단한 문법 검사기 개발.
- 안전 응답 템플릿 다국어 지원.
