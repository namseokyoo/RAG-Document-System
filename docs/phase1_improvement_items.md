# Phase 1 개선 사항 정리

**날짜**: 2025-11-05
**Phase 1 결과**: 27/31 테스트 통과 (87.1%)

---

## 우선순위별 개선 사항

### 1. 필수 (Phase 2에서 구현)

#### 1.1 Re-ranker 메서드 통합
**문제**: `RAGChain.rerank_documents()` 메서드가 없음

**영향**: Phase 1.3 통합 테스트 실패 (1/8)

**해결 방안**:
```python
# utils/rag_chain.py에 추가 필요
def rerank_documents(self, query: str, docs: List[Tuple]) -> List[Tuple]:
    """Re-ranking 수행"""
    if not self.use_reranker or not self.reranker:
        return docs

    # CrossEncoder를 사용한 Re-ranking
    # 1. docs에서 문서 추출
    # 2. query와 각 문서의 유사도 계산
    # 3. 점수 기준 정렬
    # 4. 상위 K개 반환

    return reranked_docs
```

**테스트 방법**: `test_integration_basic.py` 시나리오 B 재실행


#### 1.2 Content-based 필터링 구현 (Solution #1, #2)

**문제**: 도메인 외 문서가 Smart Filtering을 통과함

**Phase 1.2 테스트 결과**:
- 입력: 물리 5개 (0.85~0.95) + 경영 3개 (0.64~0.68) + 생물 2개 (0.40~0.42)
- 출력: 물리 5개 + 경영 3개 = 8개
- 물리/화학 비율: 62.5% < 70% (기준 미달)

**해결 방안**:

**Solution #1: Semantic Similarity Filtering**
```python
def _semantic_similarity_filter(
    self,
    query: str,
    candidates: List[Tuple[Document, float]],
    threshold: float = 0.7
) -> List[Tuple[Document, float]]:
    """
    쿼리와 각 문서의 의미론적 유사도 계산
    - Embedding 기반 코사인 유사도 측정
    - threshold 이하 문서 제거
    """
    pass
```

**Solution #2: Keyword/Topic-based Filtering**
```python
def _keyword_based_filter(
    self,
    query: str,
    candidates: List[Tuple[Document, float]],
    min_keyword_overlap: float = 0.3
) -> List[Tuple[Document, float]]:
    """
    쿼리와 문서의 키워드 중복도 측정
    - TF-IDF 또는 키워드 추출
    - 중복도 기준 필터링
    """
    pass
```

**테스트 방법**: `test_smart_filtering.py`의 통합 시나리오 수정


### 2. 권장 (Phase 2에서 구현)

#### 2.1 파라미터 튜닝

**현재 설정**:
```python
# Gap-based Cutoff
gap_threshold = 2.0 * np.mean(gaps)  # 평균의 2.0배

# Statistical Outlier Removal
mad_threshold = 3.0  # MAD 기준
```

**개선 방안**:
- Gap threshold: 2.0 → 1.5로 조정 테스트
- MAD threshold: 3.0 → 2.5로 조정 테스트
- 실제 데이터셋으로 Grid Search 수행

**테스트 방법**: 다양한 파라미터 조합으로 성능 측정


#### 2.2 sentence_transformers 명시적 포함

**문제**: `dist/RAG_Document_System/_internal/sentence_transformers/` 디렉토리 누락

**영향**: 낮음 (transformers 라이브러리로 대체 가능)

**해결 방안**:
```python
# RAG_Document_System_custom.spec
hiddenimports=[
    # ... 기존 imports ...
    'sentence_transformers',  # 이미 있음
    'sentence_transformers.cross_encoder',  # 이미 있음
    'sentence_transformers.SentenceTransformer',  # 추가
    'sentence_transformers.models',  # 이미 있음
    'sentence_transformers.util',  # 이미 있음
]
```

**검증 방법**: 빌드 후 `test_build_verification.py` 재실행


### 3. 선택적 (Phase 3 이후)

#### 3.1 ChromaDB 파일 잠금 문제

**문제**: 테스트 종료 시 ChromaDB 파일이 잠겨 임시 디렉토리 삭제 실패

**영향**: 매우 낮음 (임시 파일만 남음)

**해결 방안**:
```python
# test_integration_basic.py의 teardown()
def teardown(self):
    # ChromaDB 명시적 종료
    if self.vector_manager and hasattr(self.vector_manager, 'vectorstore'):
        if hasattr(self.vector_manager.vectorstore, '_client'):
            try:
                self.vector_manager.vectorstore._client.close()
            except:
                pass

    # 디렉토리 삭제
    time.sleep(1)  # Windows 파일 잠금 해제 대기
    shutil.rmtree(self.temp_dir)
```


#### 3.2 실행 파일 크기 최적화

**현재 크기**: 1.07GB (7,296개 파일)

**최적화 방안**:
- PyTorch CPU 버전 사용 (GPU 버전은 크기가 큼)
- 불필요한 언어 모델 제외
- UPX 압축 강화

---

## Phase 2 실행 계획

### Phase 2.1: Re-ranker 통합 (우선순위 1)
1. `utils/rag_chain.py`에 `rerank_documents()` 메서드 구현
2. 기존 Re-ranker 로직 통합
3. `test_integration_basic.py` 재실행
4. 통합 테스트 통과 확인

### Phase 2.2: Content-based 필터링 (우선순위 2)
1. Semantic Similarity Filtering 구현
2. Keyword-based Filtering 구현
3. `test_smart_filtering.py` 통합 시나리오 업데이트
4. 70% 도메인 순도 달성 확인

### Phase 2.3: 파라미터 최적화 (우선순위 3)
1. Gap threshold 튜닝 (2.0 → 1.5)
2. MAD threshold 튜닝 (3.0 → 2.5)
3. 다양한 시나리오로 성능 측정
4. 최적 파라미터 선정

### Phase 2.4: 빌드 업데이트 (우선순위 4)
1. sentence_transformers hiddenimport 추가
2. PyInstaller 재빌드
3. `test_build_verification.py` 재실행
4. 18/18 통과 확인

---

## 성공 기준

### Phase 2 완료 조건
- [ ] Re-ranker 통합 테스트 통과 (8/8)
- [ ] Content-based 필터링으로 도메인 순도 70% 이상
- [ ] 파라미터 최적화로 필터링 정확도 향상
- [ ] 빌드 검증 테스트 18/18 통과

### Phase 2 목표 통과율
- 최소: 90% (28/31 테스트)
- 목표: 95% (29/31 테스트)
- 이상적: 100% (31/31 테스트)

---

## 참고 문서

- [Phase 1 Test Report](phase1_test_report.md)
- [System Weakness Analysis](system_weakness_analysis_and_solutions.md)
- [Domain Filtering Validation](domain_filtering_validation_report.md)
