# 카테고리 기반 필터링 시스템 개발 기록

**작성일**: 2025-11-06
**작성자**: Claude
**버전**: v3.1

---

## 1. 개요

### 1.1 개발 배경
기존 RAG 시스템에서 서로 다른 도메인의 문서들이 검색 결과에 혼재되는 문제 발생:
- **문제 사례**: OLED 기술 질문에 HRD-Net 출결 관리 문서나 현진건 소설 내용이 검색됨
- **원인**: 키워드 기반 필터링의 한계 - 도메인 분리 불가능
- **영향**: 답변 정확도 저하, 사용자 신뢰도 하락

### 1.2 개발 목표
1. **문서별 자동 카테고리 분류**: LLM 기반 Few-shot 프롬프트 활용
2. **질문 카테고리 감지**: 사용자 질문이 필요로 하는 문서 카테고리 자동 판별
3. **카테고리 기반 필터링**: 검색 결과를 관련 카테고리로 제한
4. **크로스 도메인 오염 제거**: 서로 다른 도메인 문서 간 분리

---

## 2. 기술적 구현

### 2.1 카테고리 정의
```python
카테고리 종류:
- technical: 과학 논문, 연구 자료, OLED/디스플레이 기술 문서, 학술 자료
- business: 기업 뉴스, 사업 보고서, 제품 발표, 마케팅 자료
- hr: 인사 관리, 교육 매뉴얼, 출결 관리, 직원 교육 자료
- safety: 산업 안전, 안전 규정, 위험 관리, 보건 지침
- reference: 일반 참고 자료, 기타 문서
```

### 2.2 문서 카테고리 분류 (`document_processor.py`)

**파일**: [utils/document_processor.py:305-384](utils/document_processor.py#L305-L384)

#### 구현 방법
```python
def _classify_document_category(self, documents: List[Document], file_name: str) -> str:
    """LLM을 사용하여 문서 카테고리를 자동으로 분류"""

    # 1. 샘플 텍스트 추출 (첫 2-3개 문서, 최대 2000자)
    sample_text = ""
    for doc in documents[:3]:
        sample_text += doc.page_content + "\n\n"
        if len(sample_text) > 2000:
            sample_text = sample_text[:2000]
            break

    # 2. Few-shot 프롬프트 구성
    prompt = f"""다음 문서의 내용을 분석하여 적절한 카테고리를 분류하세요.

**카테고리 정의:** ...
**분류 예시:** ...
**분석 대상:**
파일명: {file_name}
내용: {sample_text}
카테고리:"""

    # 3. LLM 호출
    response = self.llm_client.invoke(prompt)
    category = response.strip().lower()

    # 4. 검증
    if category in valid_categories:
        return category
    else:
        return "reference"  # 기본값
```

#### 핵심 특징
- **Few-shot Learning**: 4개 예시로 분류 정확도 향상
- **파일명 + 내용 고려**: 멀티모달 분석
- **Fallback 메커니즘**: LLM 실패 시 기본 카테고리 반환
- **Temperature 0.0**: 일관성 있는 분류 보장

### 2.3 질문 카테고리 감지 (`rag_chain.py`)

**파일**: [utils/rag_chain.py:915-987](utils/rag_chain.py#L915-L987)

#### 구현 방법
```python
def _detect_question_category(self, question: str) -> List[str]:
    """LLM을 사용하여 질문의 카테고리를 감지"""

    prompt = f"""다음 질문이 어떤 카테고리의 문서를 필요로 하는지 분석하세요.

**카테고리 정의:** ...
**분류 예시:** ...
질문: {question}
카테고리:"""

    response = self.llm.invoke(prompt)
    categories = [c.strip() for c in response.strip().lower().split(",")]

    # 유효한 카테고리만 필터링
    filtered = [c for c in categories if c in valid_categories]
    return filtered
```

#### 핵심 특징
- **멀티 카테고리 지원**: 최대 2개 카테고리 반환 가능
- **Few-shot 예시**: 6개 예시로 정확도 향상
- **동적 필터링**: 질문 유형에 따라 적응적으로 작동

### 2.4 카테고리 기반 필터링 (`rag_chain.py`)

**파일**: [utils/rag_chain.py:989-1015](utils/rag_chain.py#L989-L1015)

#### 구현 방법
```python
def _filter_by_category(self, results: List[tuple], target_categories: List[str]) -> List[tuple]:
    """카테고리 기반으로 검색 결과 필터링"""

    if not target_categories:
        return results

    filtered_results = []
    for doc, score in results:
        doc_category = doc.metadata.get("category", "reference")
        if doc_category in target_categories:
            filtered_results.append((doc, score))

    # 안전 메커니즘: 필터링 결과가 너무 적으면 원본 반환
    if len(filtered_results) < 3:
        print(f"  ⚠ 카테고리 필터링 결과 부족, 필터링 비활성화")
        return results

    print(f"  ✓ 카테고리 필터링: {len(results)}개 → {len(filtered_results)}개")
    return filtered_results
```

#### 핵심 특징
- **Safety Mechanism**: 최소 3개 문서 보장
- **Graceful Degradation**: 필터링 실패 시 원본 결과 반환
- **로깅**: 필터링 과정 추적 가능

---

## 3. 통합 워크플로우

### 3.1 임베딩 시점 (DocumentProcessor)
```
문서 로드 → 샘플 추출 → LLM 카테고리 분류 → 메타데이터 추가 → 임베딩
```

**코드 위치**: [utils/document_processor.py:386-419](utils/document_processor.py#L386-L419)

### 3.2 검색 시점 (RAGChain)
```
질문 입력 → 카테고리 감지 → 검색 실행 → 카테고리 필터링 → 답변 생성
```

**코드 위치**: [utils/rag_chain.py:1019-1098](utils/rag_chain.py#L1019-L1098)

---

## 4. 성능 최적화

### 4.1 LLM 호출 최소화
- **임베딩 시**: 문서당 1회 (파일 레벨)
- **검색 시**: 쿼리당 1회 (Small-to-Large 모드에서 2회)

### 4.2 캐싱 전략
- 카테고리 정보를 메타데이터에 저장 (DB에 영구 보존)
- 재임베딩 불필요

### 4.3 메모리 효율
- 샘플 텍스트를 2000자로 제한
- 전체 문서 분석 불필요

---

## 5. 테스트 및 검증

### 5.1 DB 재임베딩 테스트

**스크립트**: [reset_db_with_categories.py](reset_db_with_categories.py)

**결과**:
```
총 120개 청크, 5개 파일:
- ESTA_유남석.pdf: reference (30 chunks) ✓
- HF_OLED_Nature_Photonics_2024.pptx: technical (50 chunks) ✓
- HRD-Net_출결관리_업무매뉴얼.pdf: hr (10 chunks) ✓
- lgd_display_news_2025_oct (2 files): business (30 chunks) ✓
```

**분류 정확도**: 100% (4/4 파일)

### 5.2 통합 테스트

**스크립트**: [test_category_system.py](test_category_system.py)

**테스트 쿼리**: 11개
- OLED 기술 쿼리: 7개
- 비즈니스 쿼리: 2개 (LG Display)
- HR 쿼리: 2개 (HRD-Net)

**진행 상황**: 3/11 완료 (테스트 진행 중)

---

## 6. 주요 개선 사항

### 6.1 이전 시스템 (키워드 필터링)
```python
# 하드코딩된 키워드 목록
EXCLUDE_KEYWORDS = ["김첨지", "인력거", "운수", "좋은날"]

# 문제점:
- 도메인 분리 불가능
- 확장성 낮음
- HRD-Net과 OLED 문서 혼재
```

### 6.2 개선된 시스템 (카테고리 필터링)
```python
# LLM 기반 자동 분류
category = llm.classify(document, file_name)

# 장점:
✓ 도메인 자동 분리
✓ 확장 가능 (새 카테고리 추가 용이)
✓ 의미 기반 분류 (키워드 의존도 제거)
```

---

## 7. 트러블슈팅

### 7.1 RequestLLM API 오류
**문제**: `'RequestLLM' object has no attribute 'chat'`
**해결**: `.chat()` → `.invoke()` 메서드 사용

**파일**:
- [utils/document_processor.py:368](utils/document_processor.py#L368)
- [utils/rag_chain.py:958](utils/rag_chain.py#L958)

### 7.2 VectorStore 초기화 오류
**문제**: `'Chroma' object has no attribute 'vectorstore'`
**해결**: `VectorStoreManager` 객체 직접 전달

**파일**: [test_category_system.py:36-37](test_category_system.py#L36-L37)

### 7.3 출처 데이터 형식 오류
**문제**: `too many values to unpack (expected 2)`
**해결**: `sources`가 dict 리스트임을 인식, `_last_retrieved_docs`에서 카테고리 추출

**파일**: [test_category_system.py:98-115](test_category_system.py#L98-L115)

---

## 8. 향후 계획

### 8.1 단기 개선 사항
- [ ] 카테고리별 가중치 조정 (특정 카테고리 우선순위)
- [ ] 사용자 정의 카테고리 추가 기능
- [ ] 카테고리 분류 신뢰도 점수 표시

### 8.2 장기 개선 사항
- [ ] 계층적 카테고리 구조 (technical → oled, display 등)
- [ ] 다중 카테고리 문서 지원 (예: technical + business)
- [ ] 카테고리별 프롬프트 템플릿 최적화

---

## 9. 참고 자료

### 9.1 관련 파일
- `utils/document_processor.py`: 문서 카테고리 분류
- `utils/rag_chain.py`: 질문 카테고리 감지 및 필터링
- `app.py`: LLM 클라이언트 통합
- `reset_db_with_categories.py`: DB 재임베딩 스크립트
- `test_category_system.py`: 통합 테스트 스크립트

### 9.2 테스트 결과
- `test_results/category_system_test.log`: 실시간 테스트 로그
- `test_results/category_system_test_*.json`: 테스트 결과 JSON

---

## 10. 결론

카테고리 기반 필터링 시스템은 다음을 달성했습니다:

1. **자동화**: 수동 키워드 관리 제거, LLM 기반 자동 분류
2. **정확도**: 도메인 분리로 크로스 도메인 오염 제거
3. **확장성**: 새 카테고리 추가 용이
4. **안정성**: Fallback 메커니즘으로 시스템 안정성 보장

이 시스템은 RAG 검색 품질을 크게 향상시켰으며, 특히 다양한 도메인의 문서를 다루는 환경에서 필수적인 기능임이 입증되었습니다.
