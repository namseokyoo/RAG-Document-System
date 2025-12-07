# 📊 메타데이터 기반 검색 아키텍처 분석

**작성일**: 2025-01-09
**목적**: 상용 RAG 서비스의 메타데이터 검색 전략 분석 및 현재 프로젝트 적용 방안

---

## 🎯 문제 정의

### 현재 시스템의 한계

현재 시스템은 **벡터 임베딩 기반 의미론적 검색(Semantic Search)**에 최적화되어 있어, 다음과 같은 메타데이터 기반 쿼리에 취약합니다:

**문제 사례**:
```
사용자: "김철수 저자가 쓴 논문을 찾아서 요약해줘"

[현재 시스템의 동작]
1. "김철수 저자가 쓴 논문" → 벡터 임베딩 생성
2. 유사도 검색 → 본문에 "김철수"가 많이 등장하는 청크 검색
3. 문제: 저자명은 주로 첫 페이지에만 나오므로 검색 누락 발생
4. 문제: 논문이 20개 청크로 나뉘어 있을 때, 3개 청크만 반환 → 불완전한 요약
```

### 메타데이터 쿼리의 특성

사용자가 알고 있는 **구조화된 정보**로 검색하는 경우:
- **저자명**: "김철수", "이영희"
- **파일명**: "OLED_efficiency_2024.pdf"
- **제목**: "고효율 OLED 소자 개발"
- **저널명**: "Nature Photonics", "Applied Physics Letters"
- **소속 기관**: "LG Display", "서울대학교"
- **연도**: 2023, 2024

**기존 벡터 검색의 한계**:
- ❌ 정확한 문자열 매칭(Exact Match) 불가
- ❌ 메타데이터는 본문에 등장 빈도가 낮아 유사도 낮음
- ❌ 논문 전체를 대표하는 정보이지만, 청크 단위 검색에서 손실

---

## 🏢 상용 서비스 벤치마크

### 1. Semantic Scholar (학술 검색 엔진)

**아키텍처**: 3-Index 병렬 검색

```
┌──────────────────────────────────────────────────┐
│              Query Router (LLM)                  │
│  "김철수의 OLED 연구" → [Metadata] + [Vector]     │
└─────────────┬────────────────────────────────────┘
              │
     ┌────────┴────────┬─────────────┐
     ▼                 ▼             ▼
┌─────────┐     ┌─────────┐   ┌─────────┐
│Metadata │     │Full-text│   │ Vector  │
│ Index   │     │ Index   │   │ Index   │
│(Elastic)│     │ (BM25)  │   │(SPECTER)│
└────┬────┘     └────┬────┘   └────┬────┘
     │               │             │
     └───────────────┴─────────────┘
                     │
              [Fusion Ranking]
                     │
              [Final Results]
```

**핵심 전략**:
1. **Elasticsearch 메타데이터 인덱스**: 저자, 제목, 기관, 연도 등 구조화된 필드
2. **BM25 키워드 검색**: 전문 검색 (용어 정확도 중요)
3. **SPECTER 벡터 검색**: 논문 임베딩 (의미론적 유사도)
4. **Reciprocal Rank Fusion (RRF)**: 3개 결과 종합 순위화

**메타데이터 필드**:
```json
{
  "paperId": "abc123",
  "title": "High-Efficiency OLED Devices",
  "authors": [
    {
      "authorId": "1234",
      "name": "김철수",
      "affiliation": "LG Display"
    }
  ],
  "year": 2024,
  "venue": "Nature Photonics",
  "citationCount": 42,
  "influentialCitationCount": 15,
  "references": ["paper_id_1", "paper_id_2"]
}
```

---

### 2. Perplexity AI (대화형 검색)

**아키텍처**: Query Decomposition + Multi-step Retrieval

```
User Query: "LG Display 소속 저자들의 OLED 연구를 요약해줘"
      │
      ▼
┌──────────────────────────────────────┐
│   LLM Query Decomposition            │
│   (쿼리를 실행 가능한 단계로 분해)       │
└──────────┬───────────────────────────┘
           │
           ▼
   ┌───────────────────────┐
   │ Step 1: Metadata 필터링│
   │   WHERE affiliation    │
   │   = "LG Display"       │
   │   AND topic = "OLED"   │
   └───────┬───────────────┘
           │
           ▼
   ┌───────────────────────┐
   │ Step 2: Document Load │
   │   식별된 논문의        │
   │   전체 내용 로드       │
   └───────┬───────────────┘
           │
           ▼
   ┌───────────────────────┐
   │ Step 3: Synthesis     │
   │   모든 논문 종합 요약  │
   └───────────────────────┘
```

**핵심 전략**:
- **Query Planning**: LLM이 복잡한 쿼리를 다단계 실행 계획으로 변환
- **Tool Use**: 검색, 필터링, 요약 등 각 단계별 도구 사용
- **Context Aggregation**: 필터링된 문서의 모든 청크를 컨텍스트에 포함

---

### 3. Elicit (AI Research Assistant)

**아키텍처**: Paper-centric Structured Extraction

```
User Query: "OLED 효율 향상 방법 비교"
      │
      ▼
┌─────────────────────────────────────┐
│  Semantic Scholar API 호출           │
│  논문 메타데이터 검색                │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  GROBID PDF Parsing                 │
│  - Abstract                         │
│  - Methods                          │
│  - Results                          │
│  - Discussion                       │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Section-wise Summarization         │
│  각 섹션별 요약 추출                 │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Structured Table Output            │
│  저자│연도│방법론│주요 발견│인용     │
└─────────────────────────────────────┘
```

**핵심 전략**:
- **논문 구조 인식**: GROBID로 섹션 자동 추출
- **구조화된 출력**: 표 형태로 비교 가능한 정보 제공
- **메타데이터 중심**: 저자, 연도, 방법론 등 필드별 검색

---

### 4. ChatGPT Enterprise (File Upload)

**아키텍처**: Hybrid RAG with Automatic Metadata Extraction

```
File Upload (PDF)
      │
      ▼
┌─────────────────────────────────────┐
│  Automatic Metadata Extraction      │
│  - Title, Authors (from PDF props)  │
│  - Content Analysis (keywords)      │
│  - Entity Recognition (NER)         │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Dual Index Creation                │
│  - Metadata Index                   │
│  - Vector Index (chunks)            │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Query Analysis & Strategy Selection│
│  - Metadata Query → Exact Filter    │
│  - Content Query → Vector Search    │
│  - Hybrid Query → Both              │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  LLM Generation (GPT-4)             │
│  최대 100개 청크 컨텍스트 포함 가능  │
└─────────────────────────────────────┘
```

**핵심 전략**:
- **자동 메타데이터 추출**: 파일 업로드 시 자동 파싱
- **쿼리 타입 자동 감지**: LLM이 쿼리 특성 분석
- **Large Context Window**: GPT-4 Turbo 128K 컨텍스트 활용

---

## 🛠️ 공통 핵심 기술

### 1. 메타데이터 자동 추출 파이프라인

**GROBID (GeneRation Of BIbliographic Data)**:
```python
def extract_metadata_with_grobid(pdf_path: str) -> dict:
    """GROBID를 사용한 메타데이터 추출"""
    # GROBID 서버 호출 (로컬 또는 원격)
    response = requests.post(
        "http://localhost:8070/api/processHeaderDocument",
        files={"input": open(pdf_path, "rb")}
    )

    # XML 응답 파싱
    xml_data = response.text
    soup = BeautifulSoup(xml_data, "xml")

    # 메타데이터 추출
    metadata = {
        "title": soup.find("title").text,
        "authors": [
            {
                "name": author.find("persName").text,
                "affiliation": author.find("affiliation").text if author.find("affiliation") else ""
            }
            for author in soup.find_all("author")
        ],
        "abstract": soup.find("abstract").text if soup.find("abstract") else "",
        "journal": soup.find("title", {"level": "j"}).text if soup.find("title", {"level": "j"}) else "",
        "year": soup.find("date").get("when") if soup.find("date") else ""
    }

    return metadata
```

**대안: PyPDF2 + Regex (오프라인)**:
```python
def extract_metadata_simple(pdf_path: str) -> dict:
    """PyPDF2 기본 정보 + 정규식 추출"""
    import PyPDF2
    import re

    with open(pdf_path, "rb") as f:
        pdf = PyPDF2.PdfReader(f)

        # PDF 메타데이터 (파일 속성)
        info = pdf.metadata

        # 첫 2페이지 텍스트 추출
        first_pages = ""
        for i in range(min(2, len(pdf.pages))):
            first_pages += pdf.pages[i].extract_text()

        # 정규식으로 저자/소속 추출 (논문마다 형식 상이)
        authors = re.findall(r"([A-Z][a-z]+ [A-Z][a-z]+)", first_pages)  # 영문 이름
        affiliations = re.findall(r"(University|Institute|Display|Laboratory)", first_pages)

        return {
            "title": info.get("/Title", ""),
            "authors": authors[:5],  # 최대 5명
            "affiliations": list(set(affiliations)),
            "creation_date": info.get("/CreationDate", "")
        }
```

---

### 2. ChromaDB 메타데이터 필터링

**Chroma의 `where` 절 활용**:
```python
# 저자명으로 필터링
results = collection.get(
    where={"authors": {"$contains": "김철수"}},
    include=["metadatas", "documents", "embeddings"]
)

# 복합 조건 (저자 + 연도)
results = collection.get(
    where={
        "$and": [
            {"authors": {"$contains": "김철수"}},
            {"year": {"$gte": 2020}}
        ]
    }
)

# OR 조건 (여러 저자)
results = collection.get(
    where={
        "$or": [
            {"authors": {"$contains": "김철수"}},
            {"authors": {"$contains": "이영희"}}
        ]
    }
)
```

**메타데이터 스키마 설계**:
```python
# 현재 (v3.6.1)
metadata = {
    "source": "paper.pdf",
    "page": 1,
    "chunk_id": "paper_chunk_001"
}

# 확장 버전 (Phase 2.5.6)
metadata = {
    "source": "paper.pdf",
    "page": 1,
    "chunk_id": "paper_chunk_001",

    # 논문 메타데이터 (문서 레벨)
    "document_id": "doc_12345",  # 논문 고유 ID
    "title": "고효율 OLED 소자 개발",
    "authors": ["김철수", "이영희"],
    "author_affiliations": ["LG Display", "서울대학교"],
    "journal": "Nature Photonics",
    "year": 2024,
    "doi": "10.1038/nphoton.2024.123",

    # 청크 메타데이터 (청크 레벨)
    "section": "Results",  # Introduction, Methods, Results, Discussion
    "has_table": True,
    "has_figure": True
}
```

---

### 3. Query Router (쿼리 분류기)

**LLM 기반 쿼리 타입 분류**:
```python
def classify_query(query: str, llm) -> dict:
    """쿼리 타입을 분류하고 검색 전략 결정"""

    prompt = f"""다음 사용자 쿼리를 분석하여 검색 전략을 결정하세요.

쿼리: "{query}"

분류 기준:
1. metadata_search: 저자명, 제목, 기관 등 메타데이터로 검색
2. semantic_search: 내용 기반 의미론적 검색
3. hybrid_search: 메타데이터 + 내용 모두 필요

출력 형식 (JSON):
{{
    "type": "metadata_search" | "semantic_search" | "hybrid_search",
    "metadata_filters": {{
        "authors": ["김철수"],
        "year": {{"$gte": 2020}}
    }},
    "semantic_query": "재구성된 의미론적 쿼리",
    "needs_full_document": true | false
}}
"""

    response = llm.invoke(prompt)
    return json.loads(response)
```

**현재 프로젝트 적용 (Question Classifier 확장)**:
```python
# utils/question_classifier.py 확장
QUERY_TYPES = {
    "metadata_search": {
        "description": "저자명, 제목, 기관 등으로 논문 검색",
        "keywords": ["저자", "작성자", "소속", "제목", "저널", "발표", "논문"],
        "examples": [
            "김철수가 쓴 논문 찾아줘",
            "LG Display 소속 연구자의 OLED 논문",
            "Nature에 실린 최신 연구"
        ],
        "search_strategy": "metadata_filter_then_load_full_document"
    },
    # 기존 타입들...
}
```

---

### 4. 2단계 검색 전략 (Metadata → Full Document)

**구현 패턴**:
```python
def metadata_based_search(query: str, metadata_filter: dict, vectorstore, llm):
    """메타데이터 기반 2단계 검색"""

    # Stage 1: 메타데이터 필터링으로 논문 식별
    filtered_papers = vectorstore.get(
        where=metadata_filter,
        include=["metadatas"]
    )

    # 논문 ID 추출 (중복 제거)
    paper_ids = set()
    for meta in filtered_papers["metadatas"]:
        paper_ids.add(meta["document_id"])

    print(f"[Stage 1] {len(paper_ids)}개 논문 식별됨")

    # Stage 2: 각 논문의 모든 청크 로드
    all_chunks = []
    for paper_id in paper_ids:
        chunks = vectorstore.get(
            where={"document_id": paper_id},
            include=["documents", "metadatas"]
        )
        all_chunks.extend(zip(chunks["documents"], chunks["metadatas"]))

    print(f"[Stage 2] {len(all_chunks)}개 청크 로드됨")

    # Stage 3: LLM에 전달하여 요약
    # (컨텍스트 크기 제한 고려 - 필요시 섹션별 요약 후 병합)
    if len(all_chunks) > 50:
        # 논문별로 먼저 요약
        paper_summaries = []
        for paper_id in paper_ids:
            paper_chunks = [c for c in all_chunks if c[1]["document_id"] == paper_id]
            summary = llm.summarize(paper_chunks)
            paper_summaries.append(summary)

        # 전체 요약 병합
        final_summary = llm.synthesize(paper_summaries)
    else:
        # 직접 요약
        final_summary = llm.summarize(all_chunks)

    return final_summary
```

---

## 📋 현재 프로젝트 적용 로드맵

### Phase 1: 빠른 구현 (1-2일) ✅ 우선순위 High

**목표**: 저자명 검색 기본 기능 구현

1. **Question Classifier 확장**:
   - `metadata_search` 타입 추가
   - 키워드: ["저자", "작성자", "파일명"]
   - 기존 LLM 기반 분류기 활용

2. **RAG Chain에 메타데이터 검색 로직 추가**:
   ```python
   # utils/rag_chain.py
   def _handle_metadata_search(self, query, metadata_filter):
       # 현재는 source(파일명)만 필터링 가능
       papers = self.vectorstore.get(
           where={"source": {"$contains": metadata_filter["filename"]}}
       )
       # 전체 청크 로드 및 요약
   ```

3. **테스트**:
   - "Balkenhol 논문 요약해줘" (파일명 검색)
   - "cosmology 파일 찾아줘" (파일명 검색)

**제약사항**: 현재는 `source` 필드(파일명)만 사용 가능

---

### Phase 2: 메타데이터 추출 (3-4일) ✅ 우선순위 Medium

**목표**: PDF에서 저자, 제목, 저널 자동 추출

1. **PyPDF2 기반 간단한 추출기 작성**:
   ```python
   # utils/pdf_metadata_extractor.py
   def extract_metadata(pdf_path: str) -> dict:
       # PDF 속성 읽기
       # 첫 2페이지 정규식 매칭
       # 저자명 추출 (영문 이름 패턴)
   ```

2. **문서 처리 파이프라인 수정**:
   ```python
   # utils/document_processor.py
   def process_pdf(self, pdf_path):
       # 기존 청킹 로직
       chunks = self._split_text(text)

       # NEW: 메타데이터 추출
       doc_metadata = extract_metadata(pdf_path)

       # 각 청크에 문서 메타데이터 추가
       for chunk in chunks:
           chunk.metadata.update({
               "document_id": generate_doc_id(pdf_path),
               "title": doc_metadata.get("title", ""),
               "authors": doc_metadata.get("authors", [])
           })
   ```

3. **DB 재구축**:
   - 기존 DB 백업
   - 새 메타데이터 포함하여 재임베딩

**한계**: 정규식 기반이라 정확도 제한적 (60-70% 예상)

---

### Phase 3: GROBID 통합 (선택 사항, 1주) ⚠️ 우선순위 Low

**목표**: 높은 정확도의 메타데이터 추출

1. **GROBID 서버 설치** (Docker 권장):
   ```bash
   docker pull lfoppiano/grobid:0.8.0
   docker run -t --rm -p 8070:8070 lfoppiano/grobid:0.8.0
   ```

2. **GROBID API 연동**:
   ```python
   def extract_metadata_grobid(pdf_path: str) -> dict:
       # GROBID API 호출
       # XML 파싱
       # 저자, 소속, 제목, 초록, 참고문헌 추출
   ```

3. **정확도 검증**:
   - 샘플 100개 논문으로 테스트
   - PyPDF2 방식과 비교

**장점**: 90% 이상 정확도
**단점**: 외부 서버 의존성, 설치 복잡도

---

### Phase 4: 고급 검색 (장기, Phase 3-4) 🚀 우선순위 Future

**목표**: Knowledge Graph + Agentic RAG

1. **Knowledge Graph 구축**:
   - Neo4j 또는 NetworkX
   - 논문-저자-기관-주제 관계 매핑
   - 인용 관계 분석

2. **Agentic RAG (LangGraph)**:
   ```python
   from langgraph.graph import StateGraph

   # Agent가 자동으로 검색 전략 수립
   graph = StateGraph()
   graph.add_node("plan", plan_search_strategy)
   graph.add_node("metadata_search", metadata_search_tool)
   graph.add_node("semantic_search", semantic_search_tool)
   graph.add_node("synthesize", synthesize_results)
   ```

3. **Multi-hop Reasoning**:
   - "김철수와 공저자가 많은 사람의 최신 연구"
   - Graph query + Vector search 결합

---

## ✅ 권장 사항

### 현재 프로젝트에 즉시 적용 (Phase 1)

1. ✅ **Question Classifier에 `metadata_search` 타입 추가**
   - 기존 인프라 활용
   - 구현 시간: 4-6시간

2. ✅ **파일명 기반 검색 먼저 구현**
   - 현재 `source` 필드 활용 가능
   - 사용자: "Balkenhol 논문 요약해줘"

3. ✅ **2단계 검색 로직 추가**
   - 메타데이터 필터 → 전체 청크 로드 → 요약
   - 기존 RAG Chain 확장

### 중기 목표 (Phase 2.5.6)

1. **PyPDF2 기반 메타데이터 추출**
   - 저자, 제목 기본 추출
   - 정확도 60-70%로 시작

2. **DB 재구축 스크립트**
   - 기존 PDF 재처리
   - 메타데이터 추가

3. **테스트 및 검증**
   - 샘플 20개 논문으로 정확도 확인
   - 사용자 피드백 수집

### 장기 목표 (Phase 4)

1. **GROBID 도입 검토** (정확도 중요시)
2. **Knowledge Graph** (관계 기반 검색)
3. **Agentic RAG** (복잡한 멀티스텝 쿼리)

---

## 📚 참고 자료

- **Semantic Scholar API**: https://api.semanticscholar.org/
- **GROBID**: https://github.com/kermitt2/grobid
- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **ChromaDB Metadata Filtering**: https://docs.trychroma.com/usage-guide#filtering-by-metadata
- **Perplexity AI Blog**: https://www.perplexity.ai/hub/blog
- **Elicit Research**: https://elicit.com/

---

**작성자**: Claude Code + OC Papers Team
**마지막 업데이트**: 2025-01-09
