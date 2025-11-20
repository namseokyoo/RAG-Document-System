# RAG System v0.4.0 종합 테스트 계획

**버전**: v0.4.0 (2025-11-20)
**목적**: Phase 3.5 완료 후 전체 시스템의 안정성, 통합성, 성능 검증
**테스트 범위**: 기존 기능 회귀 + 신규 기능 + 통합 시나리오 + 성능 + Edge Cases

---

## 📋 테스트 개요

### 테스트 목표
1. ✅ 기존 기능이 Phase 3.5 추가 후에도 정상 작동하는지 확인 (회귀 테스트)
2. ✅ 새로운 SessionContext + Intent Detection 기능의 실제 사용성 검증
3. ✅ 전체 시스템의 end-to-end 통합성 검증
4. ✅ 성능 저하 없는지 확인 (응답 시간, 메모리)
5. ✅ Edge case 처리 확인 (에러 핸들링, fallback)

### 테스트 분류
| 카테고리 | 테스트 수 | 자동화 | 우선순위 |
|---------|----------|--------|---------|
| 회귀 테스트 | 8개 | 가능 | HIGH |
| Phase 3.5 기능 테스트 | 6개 | 완료 (41개) | HIGH |
| 통합 시나리오 | 7개 | 일부 | HIGH |
| 성능 벤치마크 | 4개 | 가능 | MEDIUM |
| Edge Cases | 6개 | 일부 | MEDIUM |
| **합계** | **31개** | **부분** | - |

---

## 🔄 Part 1: 회귀 테스트 (Regression Tests)

**목적**: Phase 3.5 추가로 기존 기능이 영향받지 않았는지 확인

### Test 1.1: Vision Chunking - PDF 차트 인식
**파일**: `test_vision_pdf_regression.py`

**테스트 케이스**:
```python
def test_pdf_chart_recognition():
    """PDF 내 차트 이미지를 Vision으로 인식하는지 확인"""
    # 1. PDF with chart 업로드
    pdf_path = "data/test_documents/chart_sample.pdf"

    # 2. Vision 청킹 수행
    chunks = process_pdf_with_vision(pdf_path)

    # 3. 차트 설명 청크 존재 확인
    chart_chunks = [c for c in chunks if 'chart' in c.page_content.lower()]

    assert len(chart_chunks) > 0, "Chart not recognized"
    assert any('bar chart' in c.page_content.lower() for c in chart_chunks)
```

**통과 기준**: Vision으로 차트 설명 텍스트 생성됨

---

### Test 1.2: Vision Chunking - PPTX 이미지 인식
**파일**: `test_vision_pptx_regression.py`

**테스트 케이스**:
```python
def test_pptx_image_recognition():
    """PPTX 슬라이드 이미지를 Vision으로 인식하는지 확인"""
    # 1. PPTX with images 업로드
    pptx_path = "data/test_documents/image_sample.pptx"

    # 2. Vision 청킹 수행
    chunks = process_pptx_with_vision(pptx_path)

    # 3. 이미지 설명 청크 존재 확인
    image_chunks = [c for c in chunks if c.metadata.get('has_vision_content')]

    assert len(image_chunks) > 0, "Images not recognized"
```

**통과 기준**: PPTX 슬라이드 이미지 Vision 처리 성공

---

### Test 1.3: File Mention (@filename)
**파일**: `test_file_mention_regression.py`

**테스트 케이스**:
```python
def test_file_mention_priority():
    """@파일명 멘션이 최우선 검색되는지 확인"""
    # 1. 여러 PDF 업로드
    upload_multiple_pdfs(['doc1.pdf', 'doc2.pdf', 'doc3.pdf'])

    # 2. @doc2.pdf 멘션으로 질문
    response = rag_chain.query("@doc2.pdf 요약해줘", chat_history=[])

    # 3. doc2.pdf에서만 검색되었는지 확인
    sources = response['sources']
    assert all('doc2.pdf' in str(s) for s in sources), "Wrong file searched"
```

**통과 기준**: @멘션 파일만 검색됨 (Priority 1 작동)

---

### Test 1.4: Hybrid Search (BM25 + Vector)
**파일**: `test_hybrid_search_regression.py`

**테스트 케이스**:
```python
def test_hybrid_search_enabled():
    """Hybrid search가 정상 작동하는지 확인"""
    # 1. config.json에서 enable_hybrid_search=true 확인
    config = load_config()
    assert config['enable_hybrid_search'] == True

    # 2. BM25 가중치 확인
    assert config['hybrid_bm25_weight'] == 0.5

    # 3. 키워드 질문으로 BM25 활용 확인
    response = rag_chain.query("OLED device efficiency", chat_history=[])

    # 검색 로그에서 BM25 사용 확인
    assert "Hybrid search" in captured_logs
```

**통과 기준**: Hybrid search 활성화 및 BM25 가중치 적용

---

### Test 1.5: Re-ranker (Cross-Encoder)
**파일**: `test_reranker_regression.py`

**테스트 케이스**:
```python
def test_reranker_scoring():
    """Re-ranker가 문서 재순위화를 수행하는지 확인"""
    # 1. 초기 검색 k=30
    # 2. Re-ranker로 재순위화
    # 3. top_k=5로 필터링

    response = rag_chain.query("chromatic function", chat_history=[])

    # 최종 문서가 5개인지 확인
    assert len(response['sources']) <= 5

    # 검색 로그에서 Re-ranker 사용 확인
    assert "Re-ranker" in captured_logs
```

**통과 기준**: Re-ranker 재순위화 수행됨

---

### Test 1.6: Citation System (Inline References)
**파일**: `test_citation_regression.py`

**테스트 케이스**:
```python
def test_inline_citations():
    """답변에 inline citation이 포함되는지 확인"""
    response = rag_chain.query("What is OLED?", chat_history=[])
    answer = response['answer']

    # [1], [2] 같은 citation 존재 확인
    import re
    citations = re.findall(r'\[\d+\]', answer)

    assert len(citations) > 0, "No citations found"
    assert len(response['sources']) > 0, "No sources"
```

**통과 기준**: 답변에 [1], [2] 형식의 citation 포함

---

### Test 1.7: Multi-Query Expansion
**파일**: `test_multi_query_regression.py`

**테스트 케이스**:
```python
def test_multi_query_generation():
    """Multi-query expansion이 작동하는지 확인"""
    # config에서 enable_multi_query=true 확인
    config = load_config()

    if config.get('enable_multi_query'):
        response = rag_chain.query("OLED materials", chat_history=[])

        # 로그에서 multi-query 생성 확인
        assert "multi-query" in captured_logs.lower()
```

**통과 기준**: Multi-query 생성 및 검색 수행

---

### Test 1.8: Question Classifier
**파일**: `test_question_classifier_regression.py`

**테스트 케이스**:
```python
def test_question_classification():
    """질문 분류기가 작동하는지 확인"""
    # 1. Simple 질문
    result = classify_question("OLED이 뭐야?")
    assert result in ['simple', 'normal', 'complex', 'exhaustive']

    # 2. Exhaustive 질문
    result = classify_question("모든 문서에서 OLED 찾아줘")
    assert result == 'exhaustive'
```

**통과 기준**: 질문 유형 정확히 분류

---

## 🆕 Part 2: Phase 3.5 기능 테스트

**이미 완료된 테스트 (41개)**:
- ✅ SessionContext 단위 테스트 (15개) - `test_session_context.py`
- ✅ IntentDetector 단위 테스트 (23개) - `test_intent_detector.py`
- ✅ 통합 시나리오 테스트 (3개) - `test_session_integration.py`

### Test 2.1: SessionContext Timeout
**상태**: ✅ 이미 테스트됨 ([test_session_context.py:210](test_session_context.py#L210))

### Test 2.2: Intent Detection - Korean Patterns
**상태**: ✅ 이미 테스트됨 ([test_intent_detector.py:88](test_intent_detector.py#L88))

### Test 2.3: Intent Detection - English Patterns
**상태**: ✅ 이미 테스트됨 ([test_intent_detector.py:118](test_intent_detector.py#L118))

### Test 2.4: Search Priority - File Mention
**상태**: ✅ 이미 테스트됨 (통합 테스트 Scenario 1)

### Test 2.5: Search Priority - Session Context
**상태**: ✅ 이미 테스트됨 (통합 테스트 Scenario 2)

### Test 2.6: Search Priority - Auto Session
**상태**: ✅ 이미 테스트됨 (통합 테스트 Scenario 3)

---

## 🔗 Part 3: 통합 시나리오 테스트 (End-to-End)

**목적**: 실제 사용자 워크플로우 시뮬레이션

### Scenario 3.1: PDF 업로드 → 지시대명사 질문
**파일**: `test_e2e_scenario_1.py`

**사용자 스토리**:
```
1. 사용자가 "research_paper.pdf" 업로드 (개인 DB)
2. 업로드 완료 후 1분 이내
3. 채팅에서 "이 논문 요약해줘" 입력
4. 시스템이 업로드한 PDF에서 답변 생성
```

**검증 포인트**:
- [ ] PDF 업로드 성공
- [ ] SessionContext에 문서 기록됨
- [ ] Intent Detection이 "이 논문" 감지 (confidence >= 0.7)
- [ ] 세션 문서 우선 검색 수행
- [ ] 답변이 업로드한 PDF 기반
- [ ] Sources에 올바른 파일명 표시

---

### Scenario 3.2: PPTX 업로드 → 시간 기반 참조
**파일**: `test_e2e_scenario_2.py`

**사용자 스토리**:
```
1. 사용자가 "presentation.pptx" 업로드 (개인 DB)
2. 업로드 완료 후 30초 이내
3. 채팅에서 "방금 올린 파일에서 표 찾아줘" 입력
4. 시스템이 PPTX에서 표 내용 검색
```

**검증 포인트**:
- [ ] PPTX 업로드 및 Vision 처리 성공
- [ ] "방금 올린" 패턴 감지
- [ ] 세션 문서 우선 검색
- [ ] 표 내용 포함된 답변 생성

---

### Scenario 3.3: 다중 문서 업로드 → 우선순위
**파일**: `test_e2e_scenario_3.py`

**사용자 스토리**:
```
1. 사용자가 3개 PDF 업로드: A.pdf, B.pdf, C.pdf
2. 5분 이내에 "이 문서들에서 키워드 찾아줘" 입력
3. 시스템이 3개 모두에서 검색
```

**검증 포인트**:
- [ ] 3개 문서 모두 세션에 기록
- [ ] "이 문서들" 패턴 감지
- [ ] 세션 내 3개 문서에서 검색
- [ ] Sources에 3개 파일 포함 가능

---

### Scenario 3.4: 타임아웃 후 Fallback
**파일**: `test_e2e_scenario_4.py`

**사용자 스토리**:
```
1. 사용자가 PDF 업로드
2. **6분 대기** (타임아웃 5분 초과)
3. "이 문서 요약해줘" 입력
4. 세션 비활성 → 전체 DB 검색으로 fallback
```

**검증 포인트**:
- [ ] 세션 타임아웃 확인 (is_active() = False)
- [ ] Intent Detection은 감지하지만 세션 비활성
- [ ] 전체 DB 검색 수행 (fallback)
- [ ] 여전히 답변 생성 가능

---

### Scenario 3.5: Vision + Session 통합
**파일**: `test_e2e_scenario_5.py`

**사용자 스토리**:
```
1. 차트가 포함된 PDF 업로드
2. Vision으로 차트 설명 생성
3. "이 문서의 차트 설명해줘" 질문
4. Vision 생성 청크에서 답변
```

**검증 포인트**:
- [ ] Vision 청킹 성공 (차트 설명 텍스트)
- [ ] 세션 문서 우선 검색
- [ ] Vision 생성 청크가 검색됨
- [ ] 차트 내용 기반 답변

---

### Scenario 3.6: @멘션 + 세션 혼용
**파일**: `test_e2e_scenario_6.py`

**사용자 스토리**:
```
1. A.pdf, B.pdf 업로드 (둘 다 세션 활성)
2. "@B.pdf 요약해줘" 질문
3. 세션보다 @멘션 우선순위가 높음
4. B.pdf만 검색
```

**검증 포인트**:
- [ ] Priority 1 (@멘션)이 Priority 3 (세션)보다 우선
- [ ] B.pdf만 검색됨
- [ ] A.pdf는 검색 안 됨

---

### Scenario 3.7: 공유 DB는 세션 추적 안 함
**파일**: `test_e2e_scenario_7.py`

**사용자 스토리**:
```
1. PDF를 **공유 DB**로 업로드
2. "이 문서 요약해줘" 질문
3. 공유 DB 업로드는 세션에 기록 안 됨
4. 전체 DB 검색
```

**검증 포인트**:
- [ ] 공유 DB 업로드 시 세션 기록 안 됨
- [ ] Intent 감지는 되지만 세션 비활성
- [ ] 전체 DB 검색 수행

---

## ⚡ Part 4: 성능 벤치마크

### Test 4.1: 응답 시간 측정
**파일**: `test_performance_response_time.py`

**측정 항목**:
```python
def test_response_time():
    # 1. 일반 질문 (전체 DB 검색)
    start = time.time()
    response = rag_chain.query("OLED materials", chat_history=[])
    normal_time = time.time() - start

    # 2. 세션 우선 검색
    upload_pdf("test.pdf")  # 세션 활성화
    start = time.time()
    response = rag_chain.query("이 문서 요약해줘", chat_history=[])
    session_time = time.time() - start

    print(f"Normal search: {normal_time:.2f}s")
    print(f"Session search: {session_time:.2f}s")

    # 세션 검색이 더 빠르거나 비슷해야 함
    assert session_time <= normal_time * 1.5, "Session search too slow"
```

**통과 기준**: 세션 검색이 전체 DB 검색보다 1.5배 이상 느리지 않음

---

### Test 4.2: 메모리 사용량
**파일**: `test_performance_memory.py`

**측정 항목**:
```python
import psutil
import os

def test_memory_usage():
    process = psutil.Process(os.getpid())

    # 1. 초기 메모리
    mem_before = process.memory_info().rss / 1024 / 1024  # MB

    # 2. 100개 질문 처리
    for i in range(100):
        rag_chain.query(f"Question {i}", chat_history=[])

    # 3. 최종 메모리
    mem_after = process.memory_info().rss / 1024 / 1024

    mem_increase = mem_after - mem_before
    print(f"Memory increase: {mem_increase:.2f} MB")

    # 메모리 증가가 500MB 이하여야 함
    assert mem_increase < 500, "Memory leak suspected"
```

**통과 기준**: 메모리 증가 < 500MB

---

### Test 4.3: 대규모 DB 검색 성능
**파일**: `test_performance_large_db.py`

**측정 항목**:
```python
def test_large_db_search():
    # 공유 DB (963개 문서) 검색
    start = time.time()
    response = rag_chain.query(
        "OLED quantum efficiency",
        chat_history=[],
        target_db="shared"
    )
    elapsed = time.time() - start

    print(f"Large DB search time: {elapsed:.2f}s")

    # 10초 이내 응답
    assert elapsed < 10, "Large DB search too slow"
```

**통과 기준**: 대규모 DB 검색 < 10초

---

### Test 4.4: SessionContext 메모리 오버헤드
**파일**: `test_performance_session_overhead.py`

**측정 항목**:
```python
def test_session_memory_overhead():
    import sys

    # SessionContext 객체 크기 측정
    session = SessionContext(timeout_seconds=300)

    # 100개 문서 추가
    for i in range(100):
        session.add_upload(
            document_id=f"doc_{i}",
            file_name=f"file_{i}.pdf",
            num_chunks=50
        )

    # 객체 크기
    size = sys.getsizeof(session) / 1024  # KB
    print(f"SessionContext size (100 docs): {size:.2f} KB")

    # 1MB 이하여야 함
    assert size < 1024, "SessionContext too large"
```

**통과 기준**: 100개 문서 추적 시 < 1MB

---

## 🔍 Part 5: Edge Cases 테스트

### Test 5.1: 빈 세션 (업로드 없이 질문)
**파일**: `test_edge_empty_session.py`

**테스트 케이스**:
```python
def test_empty_session_reference():
    # 1. 업로드 없이 세션만 생성
    session = SessionContext(timeout_seconds=300)
    rag_chain = RAGChain(..., session_context=session)

    # 2. "이 문서" 질문
    response = rag_chain.query("이 문서 요약해줘", chat_history=[])

    # 3. Intent 감지는 되지만 세션 비활성 → 전체 DB 검색
    assert response['answer'] != "", "Should fallback to full DB"
```

**통과 기준**: 에러 없이 전체 DB 검색으로 fallback

---

### Test 5.2: 여러 파일 동시 업로드
**파일**: `test_edge_multiple_upload.py`

**테스트 케이스**:
```python
def test_concurrent_upload():
    # 동시에 5개 파일 업로드
    files = ['a.pdf', 'b.pdf', 'c.pdf', 'd.pdf', 'e.pdf']

    for f in files:
        session.add_upload(
            document_id=f"id_{f}",
            file_name=f,
            num_chunks=10
        )

    # 모두 세션에 기록되었는지 확인
    active = session.get_active_documents()
    assert len(active) == 5
```

**통과 기준**: 모든 파일 정상 추적

---

### Test 5.3: 중복 파일명
**파일**: `test_edge_duplicate_filename.py`

**테스트 케이스**:
```python
def test_duplicate_filename():
    # 같은 파일명, 다른 document_id
    session.add_upload("id_1", "report.pdf", 10)
    session.add_upload("id_2", "report.pdf", 20)

    # 둘 다 세션에 있어야 함
    active = session.get_active_documents()
    assert len(active) == 2

    # "이 문서" 질문 시 둘 다 검색
    response = rag_chain.query("이 문서 요약해줘", chat_history=[])
    # (둘 다 검색되는지는 document_id로 확인)
```

**통과 기준**: 중복 파일명 모두 추적

---

### Test 5.4: 특수문자 파일명
**파일**: `test_edge_special_chars.py`

**테스트 케이스**:
```python
def test_special_characters_filename():
    # 한글, 공백, 특수문자
    filenames = [
        "보고서 (최종).pdf",
        "2024-11-20_분석.pdf",
        "논문[ver2].docx"
    ]

    for fname in filenames:
        detector = IntentDetector()
        result = detector.detect_document_reference(f'"{fname}" 요약해줘')

        assert result['has_reference'] == True
        assert result['mentioned_filename'] == fname
```

**통과 기준**: 특수문자 파일명 정확히 추출

---

### Test 5.5: 매우 긴 질문
**파일**: `test_edge_long_question.py`

**테스트 케이스**:
```python
def test_long_question_with_reference():
    # 500자 질문에 "이 문서" 포함
    long_question = "이 문서에서 " + "OLED " * 200 + "에 대해 설명해줘"

    detector = IntentDetector()
    result = detector.detect_document_reference(long_question)

    # 여전히 패턴 감지되어야 함
    assert result['has_reference'] == True
```

**통과 기준**: 긴 질문에서도 패턴 감지

---

### Test 5.6: 세션 타임아웃 경계 테스트
**파일**: `test_edge_timeout_boundary.py`

**테스트 케이스**:
```python
def test_timeout_boundary():
    session = SessionContext(timeout_seconds=300)

    # 4분 59초 후
    session.add_upload("id_1", "test.pdf", 10)
    time.sleep(299)

    # 아직 활성
    assert session.is_active() == True

    # 2초 더 대기 (총 5분 1초)
    time.sleep(2)

    # 비활성
    assert session.is_active() == False
```

**통과 기준**: 정확히 5분에 타임아웃

---

## 📊 테스트 실행 계획

### Phase 1: 회귀 테스트 (우선순위 HIGH)
```bash
# 1일차: 회귀 테스트 스크립트 작성 및 실행
venv/Scripts/python.exe test_regression_suite.py
```

**예상 소요**: 2시간

---

### Phase 2: 통합 시나리오 (우선순위 HIGH)
```bash
# 2일차: End-to-End 시나리오 테스트
venv/Scripts/python.exe test_e2e_all_scenarios.py
```

**예상 소요**: 3시간

---

### Phase 3: 성능 벤치마크 (우선순위 MEDIUM)
```bash
# 3일차: 성능 측정
venv/Scripts/python.exe test_performance_suite.py
```

**예상 소요**: 2시간

---

### Phase 4: Edge Cases (우선순위 MEDIUM)
```bash
# 3일차: Edge case 테스트
venv/Scripts/python.exe test_edge_cases_suite.py
```

**예상 소요**: 1시간

---

## 📝 테스트 결과 보고서 형식

### 각 테스트 후 생성할 문서
```
COMPREHENSIVE_TEST_RESULTS.md
├── Part 1: 회귀 테스트 결과 (8/8 PASS)
├── Part 2: Phase 3.5 기능 테스트 (6/6 PASS)
├── Part 3: 통합 시나리오 (7/7 PASS)
├── Part 4: 성능 벤치마크 (응답시간, 메모리)
├── Part 5: Edge Cases (6/6 PASS)
└── 종합 결론 및 권장사항
```

---

## ✅ 성공 기준

### 전체 테스트 통과 조건
- [ ] 회귀 테스트: 8/8 통과 (100%)
- [ ] Phase 3.5 기능: 41/41 통과 (이미 완료)
- [ ] 통합 시나리오: 7/7 통과 (100%)
- [ ] 성능 벤치마크: 모든 항목 기준치 이내
- [ ] Edge Cases: 6/6 통과 (100%)

### Production 배포 기준
- ✅ 전체 테스트 통과율 >= 95%
- ✅ 크리티컬 버그 0개
- ✅ 응답 시간 < 10초 (대규모 DB)
- ✅ 메모리 누수 없음
- ✅ 모든 fallback 정상 작동

---

## 🚀 다음 단계

1. **즉시 시작**: 회귀 테스트 스크립트 작성
2. **1일차 완료 후**: 통합 시나리오 테스트
3. **2일차 완료 후**: 성능 벤치마크
4. **전체 완료 후**: 종합 결과 보고서 작성

---

**작성일**: 2025-11-20
**작성자**: Claude Code
**문서 버전**: 1.0
