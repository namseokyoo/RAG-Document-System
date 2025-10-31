# RAG 시스템 개선 플랜
## 테스트 결과 분석 및 개선 방안 (2024-10-28)

### 📊 테스트 결과 요약
- **테스트 질문 수**: 15개
- **평균 품질 점수**: 1.53/4.0 (38%)
- **평균 응답 시간**: 15.24초
- **출처 반환률**: 0% (0/15) ⚠️ **심각한 문제**
- **품질 점수 1점 이하**: 7개 질문 (47%)

---

## 🔴 심각한 문제점 (Critical Issues)

### 1. 출처 반환 실패 (Sources Not Returned)
**증상**: 모든 질문에서 `sources_count: 0`

**원인 분석**:
1. `get_source_documents()` 메서드가 빈 리스트 반환
2. `_last_retrieved_docs` 캐시가 제대로 업데이트되지 않음
3. `query()` 메서드와 RAG chain의 불일치

**해결 방안**:
```python
# utils/rag_chain.py 수정
def query(self, question: str, chat_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    try:
        formatted_history = self._format_chat_history(chat_history or [])
        
        # 컨텍스트 가져오기 (이미 _last_retrieved_docs 캐시됨)
        context = self._get_context(question)
        
        answer = self.chain.invoke({
            "question": question,
            "chat_history": formatted_history
        })
        
        # 캐시된 문서 사용
        sources = self.get_source_documents(question)
        
        return {
            "answer": answer,
            "sources": sources,
            "context_length": len(context)
        }
```

### 2. 검색 결과 부족
**증상**: 답변에서 "정보를 찾을 수 없다"는 메시지 지속

**원인 분석**:
1. `reranker_initial_k`가 20으로 너무 작음
2. 임계값 필터링으로 유효한 문서가 제외됨
3. 다국어 검색이 제대로 작동하지 않음

**해결 방안**:
```json
// config.json 수정
{
  "reranker_initial_k": 60,  // 20 → 60
  "top_k": 10,  // 20 → 10 (너무 크면 노이즈)
}
```

### 3. Page Summary 조회 실패
**증상**: `Expected include item to be one of documents, embeddings...`

**원인**: ChromaDB API 호출 형식 오류

**해결 방안**:
```python
# utils/rag_chain.py - _get_context_for_summarization 수정
all_data = collection.get(
    where={"chunk_type": "page_summary"},
    include=["documents", "metadatas"]  # "ids" 제거
)
```

---

## 🟡 중간 우선순위 문제

### 4. 요약 품질 개선
**현재**: 평균 2.0/4.0
**개선 목표**: 3.0/4.0

**개선 방안**:
1. 요약 전용 프롬프트 템플릿 추가
2. 구조화된 요약 형식 적용:
   - 연구 목적
   - 핵심 발견사항
   - 실험 방법 요약
   - 결론

### 5. 복합 질문 처리 개선
**예시**: "HF 성능은 TADF 재료에 따라 어떤 경향성이있어?"
**현재 품질**: 1.0/4.0

**개선 방안**:
1. 질문 유형 감지 (비교, 분석, 요약 등)
2. 관계형 질문은 여러 청크 수집 강화
3. 비교 분석 전용 프롬프트 추가

### 6. 응답 시간 최적화
**현재**: 15.24초 (목표: <10초)

**개선 방안**:
1. 불필요한 LLM 호출 제거 (번역, 재작성 등)
2. 캐싱 추가
3. 병렬 검색 최적화

---

## 🟢 낮은 우선순위 (Nice to Have)

### 7. 다국어 검색 강화
- 쿼리 번역 품질 향상
- 영어 동의어 확장 개선

### 8. 시각화 데이터 검색
- 그래프/표 캡션 인식
- 수치 데이터 추출

---

## 📋 개선 작업 체크리스트

### Phase 1: 긴급 수정 (즉시)
- [ ] `get_source_documents()` 메서드 수정
- [ ] `query()` 메서드에서 소스 반환 보장
- [ ] Page summary 조회 오류 수정
- [ ] `reranker_initial_k` 증가 (20 → 60)

### Phase 2: 검색 품질 개선 (1주일)
- [ ] 하이브리드 검색 가중치 조정
- [ ] 임계값 필터링 완화
- [ ] 다국어 검색 디버깅
- [ ] 요약 프롬프트 개선

### Phase 3: 성능 최적화 (2주일)
- [ ] 응답 시간 최적화
- [ ] 캐싱 시스템 추가
- [ ] 불필요한 LLM 호출 제거

### Phase 4: 고급 기능 (1개월)
- [ ] 질문 유형 감지
- [ ] 관계형 질문 처리
- [ ] 비교 분석 프롬프트

---

## 🎯 목표 지표

| 지표 | 현재 | 목표 (1주일) | 목표 (1개월) |
|------|------|------------|------------|
| 평균 품질 점수 | 1.53/4.0 | 2.5/4.0 | 3.0/4.0 |
| 출처 반환률 | 0% | 80% | 95% |
| 평균 응답 시간 | 15.24초 | 12초 | 8초 |
| 품질 1점 이하 비율 | 47% | 20% | <10% |

---

## 📝 테스트 케이스 우선순위

1. **TADF 재료 검색** (현재 1점) - 가장 중요
2. **HF 성능 경향성 분석** (현재 1점) - 관계 분석 테스트
3. **논문 요약** (현재 2점) - 요약 품질 테스트
4. **실험 방법론** (현재 1점) - 구체적 정보 검색 테스트

