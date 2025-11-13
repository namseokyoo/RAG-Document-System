# OC Papers - 프로젝트 정의서

**프로젝트 코드명**: OC Papers  
**현재 버전**: v3.7.0  
**작성일**: 2025-11-12  
**목적**: 프로젝트의 핵심 목적, 기능, 사용 시나리오를 명확히 정의

---

## 🎯 프로젝트 핵심 목적

### 1. 사내망 논문 DB 기반 RAG 챗봇
**목표**: 사내망 환경에서 논문 데이터베이스를 구축하고, 엔지니어들에게 정확하고 신뢰할 수 있는 정보를 제공하는 AI 챗봇 시스템

**핵심 가치**:
- 폐쇄망 최적화: 외부 네트워크 없이 완전히 작동 (로컬 모델 캐시)
- 정확한 인용 시스템: 95% 이상의 citation coverage (NotebookLM 스타일)
- 지능형 검색: 질문 유형 자동 분류 및 exhaustive retrieval
- Vision-Augmented: PPTX 슬라이드 이미지 분석으로 표/그래프 인식
- Dual DB 아키텍처: 개인 DB + 공유 DB 통합 검색

### 2. 엔지니어 보조 에이전트 AI로의 진화
**장기 목표**: 논문뿐만 아니라 다양한 개발결과물(엑셀, 파워포인트, PDF, raw data 등)을 활용하여 엔지니어를 보조하는 자율 에이전트 AI로 발전

---

## 📚 주요 사용 시나리오

### 시나리오 1: 특정 논문에 대한 질문
**사용자 목적**: 특정 논문의 내용을 빠르게 이해하고 요약

**예시 질문**:
- "[논문명]의 주요 내용을 요약해줘"
- "[논문명]에서 제시한 핵심 방법론은?"
- "[논문명]의 실험 결과는?"

**시스템 동작**:
1. 질문에서 논문명/저자명 추출
2. 해당 논문의 모든 청크 검색
3. 관련 내용을 종합하여 답변 생성
4. 정확한 페이지 번호와 함께 Citation 제공

**성공 기준**:
- 논문의 핵심 내용을 정확히 반영
- 주요 섹션(서론, 방법론, 결과, 결론) 포함
- Citation이 해당 논문을 정확히 가리킴

---

### 시나리오 2: 주제/키워드 기반 논문 검색
**사용자 목적**: 특정 주제나 키워드로 관련 논문을 찾고 요약

**예시 질문**:
- "OLED 효율 향상에 대한 논문을 찾아줘"
- "TADF 재료 관련 연구를 찾아줘"
- "모든 OLED 논문을 찾아줘" (Exhaustive Query)

**시스템 동작**:
1. 질문에서 주제/키워드 추출
2. 벡터 검색 + 키워드 검색 (Hybrid Search)
3. 관련 논문 검색 및 Re-ranking
4. 일반 질문: 답변 형식 / Exhaustive Query: 파일 리스트 형식

**성공 기준**:
- 관련 논문을 정확히 찾음
- 여러 논문을 제시 (다양성)
- 각 논문의 관련성을 설명

---

### 시나리오 3: 여러 논문에서 인사이트 추출
**사용자 목적**: 여러 논문의 정보를 종합하여 인사이트를 얻음

**예시 질문**:
- "OLED와 QLED 기술의 차이점을 비교해줘"
- "OLED 효율 향상 기술의 발전 추세는?"
- "여러 논문에서 공통으로 언급하는 OLED 효율 향상 방법은?"

**시스템 동작**:
1. 질문 유형 분류 (비교/분석/트렌드)
2. 여러 논문에서 관련 내용 검색
3. Diversity Penalty 적용하여 다양한 논문 선택
4. 정보를 종합하여 인사이트 제공

**성공 기준**:
- 여러 논문에서 정보를 종합
- 각 논문의 특징을 정확히 비교
- Citation이 여러 논문을 가리킴
- 단순 나열이 아닌 통합적 분석

---

## 🔧 핵심 기능

### 1. 문서 처리 (Document Processing)
- **PDF**: 구조 인식 청킹 (Small-to-Large), Layout-Aware 분석
- **PPTX**: 슬라이드 단위 청킹, Vision 기반 표/그래프 인식
- **XLSX**: 셀 단위 추출 및 구조 보존
- **TXT**: 기본 텍스트 분할

### 2. 검색 및 검색 (Retrieval & Ranking)
- **Hybrid Search**: BM25 (키워드) + Vector (의미) 통합 검색
- **Multi-Query Expansion**: 질문을 여러 쿼리로 확장하여 리콜 향상
- **Re-ranker**: Cross-encoder 기반 정확도 향상
- **Diversity Penalty**: 동일 논문 중복 방지, 다양한 논문 선택

### 3. 답변 생성 (Answer Generation)
- **Question Classifier**: 질문 유형 자동 분류 (simple/normal/complex/exhaustive)
- **Small-to-Large**: 작은 청크 + 큰 컨텍스트로 정확도 향상
- **Citation Generation**: NotebookLM 스타일 인라인 인용 (95% 목표)
- **Answer Verification**: 답변 품질 검증 및 재생성

### 4. 파일 레벨 집계 (File Aggregation)
- **Exhaustive Query 감지**: "모든/전체" 키워드 자동 감지
- **파일 리스트 반환**: 관련 논문을 파일 단위로 집계하여 리스트 제공
- **가중치 기반 점수**: WEIGHTED 전략으로 관련도 계산

---

## 📊 데이터 및 사용자 규모

### 데이터 규모
- **논문 수**: 수백 여건 (단계적 확대)
- **주요 분야**: OLED 소자, 광학, 재료과학
- **DB 용량**: 논문당 평균 10-20MB → 총 5-10GB 예상

### 사용자 규모
- **Phase 1 (네트워크 폴더)**: 약 20명
- **Phase 2 (DB 서버)**: 수백 명 예상
- **동시 접속**: 최대 10-20명 예상

---

## 🏗️ 기술 스택

### Core Framework
- **UI**: PySide6 (Qt6), Streamlit
- **RAG**: LangChain 0.3+ (LCEL)
- **Vector DB**: ChromaDB (persistent local storage)
- **Python**: 3.10+

### LLM & Embedding
- **Ollama**: 로컬 LLM 서버 (gemma3:4b, llama3, etc.)
- **OpenAI**: API 지원 (gpt-4o, gpt-4o-mini)
- **범용 API**: vLLM, FastChat 등 OpenAI 호환
- **Embedding**: mxbai-embed-large (Ollama)

### Document Processing
- **PDF**: PyMuPDF, pdfplumber, pypdf
- **PowerPoint**: python-pptx + Windows COM (Vision 렌더링)
- **Excel**: openpyxl
- **Vision**: Pillow, pywin32 (Windows)

### Retrieval & Ranking
- **Vector Search**: ChromaDB (HNSW)
- **Keyword Search**: BM25 (rank-bm25)
- **Re-ranker**: sentence-transformers (cross-encoder/ms-marco-MiniLM-L-6-v2)
- **Hybrid**: RRF (Reciprocal Rank Fusion)

---

## 🎯 성능 목표

### 품질 지표
- **답변 정확도**: 90% 이상
- **답변 완전성**: 85% 이상
- **출처 다양성**: 평균 2.5개 이상 (다중 논문 질문)
- **Citation Coverage**: 95% 이상
- **인사이트 추출**: 80% 이상 (다중 논문 질문)

### 성능 지표
- **응답 시간**: 질문당 5초 이내 (백엔드 의존)
- **시작 시간**: 3초 이내
- **메모리 사용량**: 500MB 이내

---

## 🔄 개발 원칙

### 1. 코드 재사용
- 백엔드 100% 재사용 (utils/ 폴더)
- Streamlit과 PySide6 동일한 백엔드 사용

### 2. 설정 중심
- config.json으로 모든 동작 제어
- 하드코딩 최소화

### 3. 오프라인 우선
- 외부 네트워크 의존성 최소화
- 로컬 모델 캐시 사용

### 4. 점진적 개발
- Phase별 단계적 구현 및 확장
- 안정성 우선, 기능 추가는 신중하게

### 5. 데이터 기반 의사결정
- 모든 개선 조치에 정량 지표 설정
- 변경 전/후 측정 및 비교
- 문서화 (근거, 조치, 예상 효과)

---

## 📝 프로젝트 상태

### 현재 버전: v3.7.0 (2025-11-12)

**주요 기능**:
- ✅ Phase 1-2: 기본 구조 및 핵심 기능 완료
- ✅ Phase 3: 검색 품질 및 응답 전략 개선 (진행 중)
- ✅ File Aggregation: Exhaustive Query 파일 리스트 반환
- ✅ Diversity Penalty: 다문서 합성 개선
- ✅ Citation System: NotebookLM 스타일 인라인 인용

**다음 단계**:
- ⏳ Phase 3 Day 3: 회귀 테스트 및 성능 벤치마킹
- ⏳ Phase 2.5: PDF/PPTX 개선 및 시스템 최적화
- ⏳ Phase 4: 다양한 문서 형식 지원 확대

---

## 🎓 사용자 가이드

### 기본 사용법
1. **문서 업로드**: PDF, PPTX, XLSX, TXT 파일 업로드
2. **질문 입력**: 자연어로 질문 입력
3. **답변 확인**: Citation과 함께 답변 확인
4. **추가 질문**: 대화 이력을 유지하며 추가 질문 가능

### 질문 유형별 팁
- **특정 논문 질문**: 논문명이나 저자명을 포함
- **주제 검색**: 키워드를 명확히 제시
- **비교/분석**: "비교", "차이", "공통점" 등의 키워드 사용
- **전체 논문 찾기**: "모든", "전체", "리스트" 등의 키워드 사용

---

**작성자**: AI Assistant  
**최종 업데이트**: 2025-11-12

