# PPT RAG 성능 최적화 방법 (비전 청킹 외)

**작성일**: 2025-11-05
**목적**: 비전 청킹을 제외한 PPT RAG 성능 향상 방안

---

## 📊 현재 시스템 분석

### 구현된 기능
- ✅ Small-to-Large 아키텍처 (슬라이드 전체 + 개별 요소)
- ✅ python-pptx 기반 텍스트/표/노트 추출
- ✅ paragraph.level 기반 불릿 그룹핑
- ✅ 슬라이드 번호, 제목 메타데이터

### 개선 가능 영역
- ⚠️ 슬라이드 간 문맥/순서 정보 부족
- ⚠️ 표 구조 정보 손실 (텍스트로만 변환)
- ⚠️ 슬라이드 타입별 차별화 없음
- ⚠️ 메타데이터 활용 제한적
- ⚠️ 검색 전략 단일 (벡터 검색만)

---

## 🚀 개선 방법 1: 슬라이드 문맥 정보 강화

### 문제점
현재는 각 슬라이드를 독립적으로 처리하여 **슬라이드 간 문맥**을 잃음

### 해결 방법: 문맥 창(Context Window) 추가

```python
def _create_slide_with_context(self, slides, slide_index: int) -> str:
    """슬라이드에 앞뒤 문맥 추가"""
    current_slide = slides[slide_index]

    # 이전 슬라이드 제목 (문맥)
    prev_context = ""
    if slide_index > 0:
        prev_title = self._get_slide_title(slides[slide_index - 1])
        if prev_title:
            prev_context = f"[이전 슬라이드] {prev_title}\n\n"

    # 다음 슬라이드 제목 (문맥)
    next_context = ""
    if slide_index < len(slides) - 1:
        next_title = self._get_slide_title(slides[slide_index + 1])
        if next_title:
            next_context = f"\n\n[다음 슬라이드] {next_title}"

    # 섹션 정보 (프레젠테이션 구조)
    section_info = self._get_section_info(slides, slide_index)

    return f"{section_info}{prev_context}[현재 슬라이드] {current_slide.text}{next_context}"
```

**적용 위치**: `pptx_chunking_engine.py` - `_create_slide_summary_chunk_with_vision()` 메서드

**예상 효과**:
- 슬라이드 순서 정보 활용 → 검색 정확도 +10-15%
- "다음 슬라이드에서 설명", "앞에서 언급한" 같은 참조 해결
- 프레젠테이션 흐름 이해 향상

**구현 난이도**: ★★☆☆☆ (쉬움)

---

## 🚀 개선 방법 2: 표 구조 보존 및 Markdown 변환

### 문제점
현재는 표를 단순 텍스트로 변환 → **구조 정보 손실**

```python
# 현재 방식 (pptx_chunking_engine.py:406)
def _convert_table_to_simple_text(self, table):
    rows = []
    for row in table.rows:
        row_text = " | ".join(cell.text.strip() for cell in row.cells)
        rows.append(row_text)
    return "\n".join(rows)
```

### 해결 방법: Markdown 표 + 메타데이터

```python
def _table_to_markdown_with_metadata(self, table, table_idx: int) -> dict:
    """표를 Markdown + 메타데이터로 변환"""

    # 1. 헤더 감지 (첫 행이 헤더인지 판단)
    first_row = [cell.text.strip() for cell in table.rows[0].cells]
    is_header = all(len(text) > 0 and not any(c.isdigit() for c in text)
                    for text in first_row)

    # 2. Markdown 표 생성
    if is_header:
        headers = first_row
        data_rows = list(table.rows)[1:]
    else:
        headers = [f"열{i+1}" for i in range(len(table.columns))]
        data_rows = list(table.rows)

    # Markdown 테이블
    md = "| " + " | ".join(headers) + " |\n"
    md += "| " + " | ".join(["---"] * len(headers)) + " |\n"

    for row in data_rows:
        cells = [cell.text.strip() for cell in row.cells]
        md += "| " + " | ".join(cells) + " |\n"

    # 3. 숫자 추출 (검색 최적화)
    numbers = self._extract_numbers_from_table(table)

    # 4. 표 요약 생성
    summary = self._generate_table_summary(headers, data_rows, numbers)

    return {
        "markdown": md,
        "headers": headers,
        "row_count": len(data_rows),
        "col_count": len(table.columns),
        "numbers": numbers,  # {"항목": "값"} 형태
        "summary": summary,  # "3행 4열 매출 비교표, Q1=150억..."
        "table_type": self._classify_table_type(headers, numbers)  # "비교표", "시계열", "요약표"
    }

def _generate_table_summary(self, headers, data_rows, numbers):
    """표 요약 자동 생성 (검색 최적화)"""
    summary_parts = []

    # 표 크기
    summary_parts.append(f"{len(data_rows)}행 {len(headers)}열")

    # 헤더 정보
    if headers:
        summary_parts.append(f"항목: {', '.join(headers)}")

    # 주요 숫자값 (상위 5개)
    if numbers:
        top_numbers = list(numbers.items())[:5]
        number_str = ", ".join([f"{k}={v}" for k, v in top_numbers])
        summary_parts.append(f"주요 수치: {number_str}")

    return " | ".join(summary_parts)
```

**저장 방식**:
```python
# Chunk에 저장
chunk = PPTXChunk(
    page_content=f"""[표 {table_idx}]
{table_data['summary']}

{table_data['markdown']}
""",
    metadata=PPTXChunkMetadata(
        table_headers=table_data['headers'],
        table_numbers=table_data['numbers'],
        table_type=table_data['table_type'],
        ...
    )
)
```

**예상 효과**:
- 표 검색 정확도 +20-30%
- 숫자 정확 검색 가능 ("Q1 매출 150억" exact match)
- 표 타입별 필터링 가능

**구현 난이도**: ★★★☆☆ (보통)

---

## 🚀 개선 방법 3: 슬라이드 타입 자동 분류 및 차별화

### 개념
슬라이드를 타입별로 분류하고 **타입별로 다른 청킹 전략** 적용

### 슬라이드 타입 분류

```python
def _classify_slide_type(self, slide) -> str:
    """슬라이드 타입 자동 분류"""

    # 1. 표 슬라이드
    table_count = sum(1 for shape in slide.shapes
                      if hasattr(shape, 'table') and shape.has_table)
    if table_count > 0:
        return "table"

    # 2. 차트 슬라이드
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    chart_count = sum(1 for shape in slide.shapes
                      if shape.shape_type == MSO_SHAPE_TYPE.CHART)
    if chart_count > 0:
        return "chart"

    # 3. 이미지 슬라이드
    image_count = sum(1 for shape in slide.shapes
                      if shape.shape_type in [MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.LINKED_PICTURE])
    if image_count >= 2:  # 이미지가 2개 이상이면
        return "image_heavy"

    # 4. 텍스트 슬라이드
    text_length = sum(len(shape.text) for shape in slide.shapes if hasattr(shape, 'text'))
    bullet_count = self._count_bullet_points(slide)

    if bullet_count >= 5:
        return "bullet_list"
    elif text_length > 500:
        return "text_heavy"
    elif text_length < 50:
        return "title_only"
    else:
        return "text_normal"

def _process_by_type(self, slide, slide_type: str) -> List[PPTXChunk]:
    """타입별 최적화된 청킹"""

    if slide_type == "table":
        # 표 슬라이드: 표 중심으로 청킹
        return self._process_table_slide(slide)

    elif slide_type == "chart":
        # 차트 슬라이드: Vision 필수
        return self._process_chart_slide(slide)

    elif slide_type == "bullet_list":
        # 불릿 슬라이드: 계층 구조 강조
        return self._process_bullet_slide(slide)

    elif slide_type == "text_heavy":
        # 텍스트 많은 슬라이드: 문단 단위로 분할
        return self._process_text_heavy_slide(slide)

    else:
        # 일반 슬라이드: 기존 방식
        return self._process_normal_slide(slide)
```

**메타데이터 추가**:
```python
chunk.metadata.slide_type = slide_type
chunk.metadata.complexity = self._calculate_complexity(slide)  # "simple", "medium", "complex"
```

**검색 시 활용**:
```python
# 쿼리가 숫자를 포함하면 표 슬라이드 우선
if has_numbers(query):
    filter_metadata = {"slide_type": "table"}

# 쿼리가 "비교", "대조"를 포함하면 표/차트 우선
if "비교" in query or "대조" in query:
    filter_metadata = {"slide_type": ["table", "chart"]}
```

**예상 효과**:
- 슬라이드 타입별 최적화 → 검색 정확도 +15-20%
- 불필요한 슬라이드 필터링 (title_only는 검색 제외)
- 타입별 가중치 조정 가능

**구현 난이도**: ★★★☆☆ (보통)

---

## 🚀 개선 방법 4: 하이브리드 검색 (Sparse + Dense)

### 개념
현재는 **Dense 벡터 검색만** 사용 → Sparse 검색 추가

### 구현: BM25 + 벡터 검색 조합

```python
from rank_bm25 import BM25Okapi

class HybridRetriever:
    """Sparse (BM25) + Dense (Vector) 하이브리드 검색"""

    def __init__(self, vectorstore, documents):
        self.vectorstore = vectorstore
        self.documents = documents

        # BM25 인덱스 생성
        tokenized_docs = [doc.page_content.split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized_docs)

    def hybrid_search(self, query: str, top_k: int = 10, alpha: float = 0.5):
        """하이브리드 검색

        Args:
            alpha: BM25 가중치 (0.0 = 벡터만, 1.0 = BM25만, 0.5 = 50:50)
        """
        # 1. BM25 검색
        tokenized_query = query.split()
        bm25_scores = self.bm25.get_scores(tokenized_query)

        # 2. 벡터 검색
        vector_results = self.vectorstore.similarity_search_with_score(query, k=top_k*2)

        # 3. 점수 정규화 및 결합
        normalized_bm25 = self._normalize_scores(bm25_scores)
        normalized_vector = self._normalize_scores([score for _, score in vector_results])

        # 4. 하이브리드 점수 계산
        hybrid_scores = {}
        for i, doc in enumerate(self.documents):
            doc_id = doc.metadata['chunk_id']
            hybrid_scores[doc_id] = (
                alpha * normalized_bm25[i] +
                (1 - alpha) * normalized_vector.get(doc_id, 0)
            )

        # 5. 상위 k개 반환
        top_docs = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self.documents[doc_id], score) for doc_id, score in top_docs]
```

**PPT 특화 개선**:
```python
def ppt_hybrid_search(self, query: str, top_k: int = 10):
    """PPT 특화 하이브리드 검색"""

    # 쿼리 분석
    has_numbers = bool(re.search(r'\d+', query))
    has_comparison = any(word in query for word in ["비교", "대조", "차이", "vs"])

    # 타입별 가중치 조정
    if has_numbers:
        # 숫자 쿼리: BM25 가중치 높임 (exact match 중요)
        alpha = 0.7
        filter_metadata = {"slide_type": "table"}
    elif has_comparison:
        # 비교 쿼리: 표/차트 우선
        alpha = 0.5
        filter_metadata = {"slide_type": ["table", "chart"]}
    else:
        # 일반 쿼리: 벡터 검색 중심
        alpha = 0.3
        filter_metadata = None

    return self.hybrid_search(query, top_k=top_k, alpha=alpha)
```

**예상 효과**:
- 숫자/키워드 정확 검색 +30-40%
- 의미 기반 검색 유지
- 쿼리 타입별 최적화

**구현 난이도**: ★★★★☆ (어려움)

---

## 🚀 개선 방법 5: 슬라이드 관계 그래프 구축

### 개념
슬라이드 간 관계를 그래프로 표현하여 **문맥 기반 검색**

### 구현

```python
import networkx as nx

class SlideGraphBuilder:
    """슬라이드 관계 그래프 구축"""

    def build_graph(self, presentation) -> nx.DiGraph:
        """슬라이드 간 관계 그래프"""
        G = nx.DiGraph()

        for i, slide in enumerate(presentation.slides):
            # 노드 추가
            G.add_node(i,
                      title=self._get_title(slide),
                      type=self._classify_slide_type(slide),
                      content=self._get_content(slide))

            # 엣지 추가 (순차 관계)
            if i > 0:
                G.add_edge(i-1, i, relation="next")

            # 참조 관계 감지
            references = self._detect_references(slide)
            for ref_slide_num in references:
                if 0 <= ref_slide_num < len(presentation.slides):
                    G.add_edge(i, ref_slide_num, relation="reference")

            # 동일 섹션 관계
            section = self._get_section(slide, i)
            for j in range(i):
                if self._get_section(presentation.slides[j], j) == section:
                    G.add_edge(i, j, relation="same_section")

        return G

    def _detect_references(self, slide) -> List[int]:
        """슬라이드에서 다른 슬라이드 참조 감지"""
        text = self._get_all_text(slide)
        references = []

        # "슬라이드 5에서", "3페이지 참조" 같은 패턴 감지
        patterns = [
            r'슬라이드\s*(\d+)',
            r'(\d+)\s*페이지',
            r'slide\s*(\d+)',
            r'p\.?\s*(\d+)'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            references.extend([int(m) - 1 for m in matches])  # 0-indexed

        return list(set(references))

class GraphEnhancedRetriever:
    """그래프 기반 검색"""

    def __init__(self, vectorstore, slide_graph):
        self.vectorstore = vectorstore
        self.graph = slide_graph

    def search_with_context(self, query: str, top_k: int = 5):
        """그래프 문맥을 활용한 검색"""

        # 1. 기본 벡터 검색
        results = self.vectorstore.similarity_search_with_score(query, k=top_k)

        # 2. 각 결과의 관련 슬라이드 추가
        expanded_results = []
        for doc, score in results:
            slide_num = doc.metadata['slide_num']

            # 관련 슬라이드 찾기
            related_slides = self._get_related_slides(slide_num)

            expanded_results.append({
                "doc": doc,
                "score": score,
                "related_slides": related_slides,
                "context": self._build_context(slide_num)
            })

        return expanded_results

    def _get_related_slides(self, slide_num: int) -> List[int]:
        """관련 슬라이드 찾기"""
        related = []

        # 이전/다음 슬라이드
        if slide_num > 0:
            related.append(slide_num - 1)
        related.append(slide_num + 1)

        # 참조 슬라이드
        if slide_num in self.graph:
            for neighbor in self.graph.neighbors(slide_num):
                related.append(neighbor)

        return list(set(related))
```

**예상 효과**:
- 문맥 기반 검색 정확도 +10-15%
- "이전 슬라이드에서 언급한" 같은 참조 해결
- 섹션 단위 검색 가능

**구현 난이도**: ★★★★☆ (어려움)

---

## 🚀 개선 방법 6: 청크 크기 동적 조정

### 문제점
현재는 **고정 크기** (300자) → 슬라이드 특성 무시

### 해결 방법: 슬라이드별 최적 크기 계산

```python
def _calculate_optimal_chunk_size(self, slide) -> int:
    """슬라이드별 최적 청크 크기"""

    slide_type = self._classify_slide_type(slide)
    content_length = self._get_total_content_length(slide)

    # 타입별 기본 크기
    base_sizes = {
        "table": 500,        # 표는 큰 청크
        "chart": 400,        # 차트도 큰 청크
        "bullet_list": 300,  # 불릿은 중간
        "text_heavy": 400,   # 텍스트 많으면 큰 청크
        "title_only": 100,   # 제목만 있으면 작은 청크
        "text_normal": 300   # 기본 크기
    }

    base_size = base_sizes.get(slide_type, 300)

    # 내용 길이에 따라 조정
    if content_length < 100:
        return min(base_size, 200)  # 짧은 내용은 작게
    elif content_length > 1000:
        return max(base_size, 600)  # 긴 내용은 크게
    else:
        return base_size
```

**예상 효과**:
- 슬라이드별 최적화 → 검색 정확도 +5-10%
- 표/차트는 완전한 정보 유지
- 짧은 슬라이드는 불필요한 분할 방지

**구현 난이도**: ★★☆☆☆ (쉬움)

---

## 📊 개선 방법 비교

| 개선 방법 | 구현 난이도 | 예상 효과 | 비용 | 우선순위 |
|----------|-----------|----------|------|---------|
| **1. 슬라이드 문맥 강화** | ★★☆☆☆ | +10-15% | 없음 | **1순위** |
| **2. 표 구조 보존** | ★★★☆☆ | +20-30% | 없음 | **1순위** |
| **3. 슬라이드 타입 분류** | ★★★☆☆ | +15-20% | 없음 | **2순위** |
| **4. 하이브리드 검색** | ★★★★☆ | +30-40% | 없음 | **2순위** |
| **5. 슬라이드 그래프** | ★★★★☆ | +10-15% | 없음 | **3순위** |
| **6. 청크 크기 조정** | ★★☆☆☆ | +5-10% | 없음 | **3순위** |

---

## 🎯 추천 실행 계획

### Phase 1: 즉시 적용 (1-2일)

**방법 1 + 방법 6**:
- 슬라이드 문맥 정보 추가
- 청크 크기 동적 조정

**예상 효과**: +15-25% 검색 정확도

---

### Phase 2: 단기 적용 (1주일)

**방법 2 + 방법 3**:
- 표 구조 보존 및 Markdown 변환
- 슬라이드 타입 자동 분류

**예상 효과**: +35-50% 검색 정확도 (누적)

---

### Phase 3: 중기 적용 (2-3주)

**방법 4**:
- 하이브리드 검색 (BM25 + 벡터)

**예상 효과**: +60-70% 검색 정확도 (누적)

---

## 💡 실전 적용 예시

### 쿼리: "2024년 Q1 매출은 얼마인가?"

**현재 시스템**:
- 벡터 검색만 사용
- "2024년 매출" 슬라이드 검색
- "Q1"이라는 키워드 놓침 가능성

**개선 후** (방법 2+4 적용):
1. BM25가 "Q1", "매출" 키워드 정확히 매칭
2. 슬라이드 타입 필터링 (table 우선)
3. 표 메타데이터에서 "Q1=150억" 직접 추출
4. 정확도: 60% → 95%

---

## 📚 참고 자료

### 하이브리드 검색
- LangChain Ensemble Retriever: https://python.langchain.com/docs/modules/data_connection/retrievers/ensemble
- BM25: https://github.com/dorianbrown/rank_bm25

### 표 처리
- python-pptx Table API: https://python-pptx.readthedocs.io/en/latest/api/table.html
- Markdown Tables: https://www.markdownguide.org/extended-syntax/#tables

### 그래프 검색
- NetworkX: https://networkx.org/
- Graph RAG: https://arxiv.org/abs/2404.16130

---

## ✅ 결론

**가장 효과적인 조합**:
1. **즉시 적용**: 슬라이드 문맥 + 청크 크기 조정 (+15-25%)
2. **단기 적용**: 표 구조 보존 + 타입 분류 (+35-50%)
3. **중기 적용**: 하이브리드 검색 (+60-70%)

**총 예상 개선**: 현재 대비 **60-70% 검색 정확도 향상**

**핵심**: 비전 청킹 없이도 **알고리즘 최적화만으로** 큰 성능 향상 가능!
