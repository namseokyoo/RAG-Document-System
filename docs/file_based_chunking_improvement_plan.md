# 파일별 청킹 전략 개선 진행플랜

## 📋 개요

현재 프로젝트의 문서 처리 시스템을 PDF 고급 청킹 전략에 따라 단계적으로 개선하는 플랜입니다. 각 파일 타입별로 특화된 전략을 적용하여 검색 성능을 크게 향상시킵니다.

## 🎯 전체 목표

- **Small-to-Large 아키텍처** 도입으로 정확성과 컨텍스트 동시 확보
- **Layout-Aware 분석**으로 문서의 시각적 구조 보존
- **계층적 메타데이터** 시스템으로 검색 품질 향상
- **파일 타입별 최적화** 전략 적용

---

## 📄 Phase 1: PDF 고급 청킹 전략 구현

### 1.1 핵심 데이터 구조 구현

#### 파일: `utils/pdf_chunking.py` (신규 생성)
```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import uuid

@dataclass
class ChunkMetadata:
    """PDF 청크의 풍부한 메타데이터"""
    document_id: str
    page_number: int
    parent_chunk_id: Optional[str] = None  # Small-to-Large용
    section_title: str = ""
    chunk_type_weight: float = 1.0
    font_size: float = 12.0
    is_bold: bool = False
    coordinates: Optional[tuple] = None  # (x1, y1, x2, y2)
    word_count: int = 0
    char_count: int = 0

@dataclass
class Chunk:
    """PDF 청크의 최종 형태"""
    id: str
    content: str
    chunk_type: str  # title, paragraph, table, list, page_summary
    metadata: ChunkMetadata
```

### 1.2 Layout-Aware PDF 분석기 구현

#### 파일: `utils/pdf_layout_analyzer.py` (신규 생성)
```python
import pdfplumber
import fitz  # PyMuPDF
from typing import List, Dict, Any

class PDFLayoutAnalyzer:
    """PDF의 시각적 레이아웃을 분석하는 클래스"""
    
    def __init__(self):
        self.title_font_threshold = 18.0
        self.bold_threshold = 0.7
    
    def analyze_page_elements(self, page) -> List[Dict[str, Any]]:
        """페이지의 시각적 요소를 분석하여 구조화된 리스트 반환"""
        elements = []
        
        # 1. 텍스트 블록과 폰트 정보 추출
        text_blocks = self._extract_text_blocks_with_font(page)
        
        # 2. 폰트 크기 통계 계산
        font_stats = self._calculate_font_statistics(text_blocks)
        
        # 3. 요소 유형 분류
        for block in text_blocks:
            element_type = self._classify_element_type(block, font_stats)
            elements.append({
                "type": element_type,
                "content": block["text"],
                "properties": {
                    "font_size": block["font_size"],
                    "is_bold": block["is_bold"],
                    "coordinates": block["coordinates"]
                }
            })
        
        # 4. 테이블 추출
        tables = self._extract_tables(page)
        for table in tables:
            elements.append({
                "type": "table",
                "data": table["data"],
                "properties": {"coordinates": table["coordinates"]}
            })
        
        # 5. 시각적 순서로 정렬
        return self._sort_elements_by_position(elements)
    
    def _extract_text_blocks_with_font(self, page):
        """텍스트 블록과 폰트 정보 추출"""
        # pdfplumber 또는 PyMuPDF 사용
        pass
    
    def _calculate_font_statistics(self, text_blocks):
        """폰트 크기 통계 계산"""
        font_sizes = [block["font_size"] for block in text_blocks]
        return {
            "mean": sum(font_sizes) / len(font_sizes),
            "std": self._calculate_std(font_sizes),
            "threshold": max(font_sizes) * 0.8  # 상위 20%를 제목으로 간주
        }
    
    def _classify_element_type(self, block, font_stats):
        """요소 유형 분류"""
        text = block["text"].strip()
        
        # 제목 판별
        if (block["font_size"] > font_stats["threshold"] and 
            block["is_bold"] and 
            len(text.split()) <= 10):
            return "title"
        
        # 리스트 판별
        if (text.startswith("•") or 
            text.startswith("-") or 
            text.startswith("*") or
            re.match(r'^\d+\.', text)):
            return "list_item"
        
        # 문단
        return "paragraph"
```

### 1.3 Small-to-Large 청킹 엔진 구현

#### 파일: `utils/pdf_chunking_engine.py` (신규 생성)
```python
from typing import List, Dict, Any
import uuid

class PDFChunkingEngine:
    """PDF 고급 청킹 엔진"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.layout_analyzer = PDFLayoutAnalyzer()
    
    def process_pdf_document(self, pdf_path: str) -> List[Chunk]:
        """PDF 문서를 레이아웃을 인식하여 계층적으로 청킹"""
        all_chunks = []
        document_id = str(uuid.uuid4())
        
        with pdfplumber.open(pdf_path) as pdf:
            current_section_title = "문서 서두"
            
            for page_num, page in enumerate(pdf.pages, 1):
                # 1. Large 청크 생성 (페이지 전체)
                page_chunk = self._create_page_summary_chunk(
                    page, document_id, page_num, current_section_title
                )
                all_chunks.append(page_chunk)
                
                # 2. Small 청크 생성 (Layout-Aware)
                elements = self.layout_analyzer.analyze_page_elements(page)
                small_chunks = self._process_page_elements(
                    elements, document_id, page_num, 
                    page_chunk.id, current_section_title
                )
                all_chunks.extend(small_chunks)
                
                # 3. 섹션 제목 업데이트
                current_section_title = self._update_section_title(
                    elements, current_section_title
                )
        
        return all_chunks
    
    def _create_page_summary_chunk(self, page, document_id, page_num, section_title):
        """페이지 전체 텍스트를 부모 청크로 생성"""
        page_id = f"{document_id}_page_{page_num}"
        page_text = page.extract_text()
        
        return Chunk(
            id=page_id,
            content=page_text,
            chunk_type="page_summary",
            metadata=ChunkMetadata(
                document_id=document_id,
                page_number=page_num,
                parent_chunk_id=None,  # 최상위 부모
                section_title=section_title,
                chunk_type_weight=1.0,
                word_count=len(page_text.split()),
                char_count=len(page_text)
            )
        )
    
    def _process_page_elements(self, elements, document_id, page_num, parent_id, section_title):
        """페이지 요소들을 Small 청크로 처리"""
        chunks = []
        current_list_buffer = []
        
        for elem in elements:
            # 리스트 항목 버퍼링
            if elem["type"] == "list_item":
                current_list_buffer.append(elem["content"])
                continue
            
            # 리스트 버퍼 비우기
            if current_list_buffer:
                list_chunks = self._create_list_chunks(
                    current_list_buffer, document_id, page_num, 
                    parent_id, section_title
                )
                chunks.extend(list_chunks)
                current_list_buffer.clear()
            
            # 다른 요소 처리
            if elem["type"] == "title":
                chunk = self._create_title_chunk(elem, document_id, page_num, parent_id, section_title)
                chunks.append(chunk)
            elif elem["type"] == "paragraph":
                para_chunks = self._create_paragraph_chunks(
                    elem, document_id, page_num, parent_id, section_title
                )
                chunks.extend(para_chunks)
            elif elem["type"] == "table":
                table_chunks = self._create_table_chunks(
                    elem, document_id, page_num, parent_id, section_title
                )
                chunks.extend(table_chunks)
        
        # 마지막 리스트 버퍼 처리
        if current_list_buffer:
            list_chunks = self._create_list_chunks(
                current_list_buffer, document_id, page_num, 
                parent_id, section_title
            )
            chunks.extend(list_chunks)
        
        return chunks
```

### 1.4 Fallback 메커니즘 구현

#### 파일: `utils/chunking_fallback.py` (신규 생성)
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Dict, Any

class ChunkingFallback:
    """의미론적 청킹 실패 시 Fallback 처리"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.get("max_size", 500),
            chunk_overlap=config.get("overlap_size", 100),
            separators=["\n\n", "\n", " ", ""]
        )
    
    def chunk_element_with_fallback(self, content: str, element_type: str, 
                                  base_metadata: ChunkMetadata) -> List[Chunk]:
        """요소가 max_size를 초과할 경우 Fallback 적용"""
        chunks = []
        
        if len(content) <= self.config.get("max_size", 500):
            # 단일 청크로 충분
            chunk = Chunk(
                id=str(uuid.uuid4()),
                content=content,
                chunk_type=element_type,
                metadata=base_metadata
            )
            chunks.append(chunk)
        else:
            # Fallback: 강제 분할
            sub_contents = self.text_splitter.split_text(content)
            
            for i, sub_content in enumerate(sub_contents):
                chunk = Chunk(
                    id=str(uuid.uuid4()),
                    content=sub_content,
                    chunk_type=f"{element_type}_segment",
                    metadata=base_metadata
                )
                chunks.append(chunk)
        
        return chunks
```

---

## 📊 Phase 2: PPTX 슬라이드 중심 청킹 구현

### 2.1 슬라이드 구조 분석기

#### 파일: `utils/pptx_chunking.py` (신규 생성)
```python
from pptx import Presentation
from typing import List, Dict, Any

class PPTXChunkingEngine:
    """PPTX 슬라이드 중심 청킹 엔진"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def process_pptx_document(self, pptx_path: str) -> List[Chunk]:
        """PPTX 문서를 슬라이드 단위로 청킹"""
        all_chunks = []
        document_id = str(uuid.uuid4())
        
        prs = Presentation(pptx_path)
        
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_chunks = self._process_slide(
                slide, document_id, slide_num
            )
            all_chunks.extend(slide_chunks)
        
        return all_chunks
    
    def _process_slide(self, slide, document_id, slide_num):
        """개별 슬라이드 처리"""
        chunks = []
        
        # 1. 슬라이드 제목 (가중치 2.0)
        title = self._extract_slide_title(slide)
        if title:
            chunks.append(self._create_title_chunk(
                title, document_id, slide_num, weight=2.0
            ))
        
        # 2. 슬라이드 본문 내용
        content = self._extract_slide_content(slide)
        if content:
            content_chunks = self._chunk_content_by_bullets(
                content, document_id, slide_num
            )
            chunks.extend(content_chunks)
        
        # 3. 슬라이드 노트 (가중치 1.5)
        notes = self._extract_slide_notes(slide)
        if notes:
            chunks.append(self._create_notes_chunk(
                notes, document_id, slide_num, weight=1.5
            ))
        
        return chunks
```

---

## 📈 Phase 3: XLSX 워크시트 중심 청킹 구현

### 3.1 워크시트 구조 분석기

#### 파일: `utils/xlsx_chunking.py` (신규 생성)
```python
import openpyxl
from typing import List, Dict, Any

class XLSXChunkingEngine:
    """XLSX 워크시트 중심 청킹 엔진"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def process_xlsx_document(self, xlsx_path: str) -> List[Chunk]:
        """XLSX 문서를 워크시트 단위로 청킹"""
        all_chunks = []
        document_id = str(uuid.uuid4())
        
        wb = openpyxl.load_workbook(xlsx_path)
        
        for ws_name in wb.sheetnames:
            ws = wb[ws_name]
            ws_chunks = self._process_worksheet(
                ws, document_id, ws_name
            )
            all_chunks.extend(ws_chunks)
        
        return all_chunks
    
    def _process_worksheet(self, worksheet, document_id, ws_name):
        """개별 워크시트 처리"""
        chunks = []
        
        # 1. 워크시트 헤더 (가중치 2.0)
        headers = self._extract_headers(worksheet)
        if headers:
            chunks.append(self._create_header_chunk(
                headers, document_id, ws_name, weight=2.0
            ))
        
        # 2. 데이터 행들을 그룹으로 청킹
        data_rows = self._extract_data_rows(worksheet)
        if data_rows:
            row_groups = self._group_rows_by_size(data_rows)
            for group_num, group in enumerate(row_groups):
                chunks.append(self._create_data_group_chunk(
                    group, document_id, ws_name, group_num
                ))
        
        # 3. 수식 설명 (가중치 1.5)
        formulas = self._extract_formulas(worksheet)
        if formulas:
            chunks.append(self._create_formula_chunk(
                formulas, document_id, ws_name, weight=1.5
            ))
        
        return chunks
```

---

## 📝 Phase 4: Text 구조 인식 청킹 구현

### 4.1 텍스트 구조 분석기

#### 파일: `utils/text_chunking.py` (신규 생성)
```python
import re
from typing import List, Dict, Any

class TextChunkingEngine:
    """Text 구조 인식 청킹 엔진"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def process_text_document(self, text_content: str) -> List[Chunk]:
        """Text 문서를 구조 인식하여 청킹"""
        all_chunks = []
        document_id = str(uuid.uuid4())
        
        # 1. 섹션 단위 분할
        sections = self._split_by_sections(text_content)
        
        for section_num, section in enumerate(sections):
            section_chunks = self._process_section(
                section, document_id, section_num
            )
            all_chunks.extend(section_chunks)
        
        return all_chunks
    
    def _split_by_sections(self, text):
        """섹션 구분자로 분할"""
        section_patterns = [
            r'\n(?:제?\d+[장절]|Chapter|Section)',
            r'\n#{1,6}\s',  # Markdown 헤더
            r'\n={3,}$',    # 등호 구분선
            r'\n-{3,}$',    # 대시 구분선
        ]
        
        # 패턴으로 분할
        sections = [text]
        for pattern in section_patterns:
            new_sections = []
            for section in sections:
                parts = re.split(pattern, section)
                new_sections.extend(parts)
            sections = new_sections
        
        return [s.strip() for s in sections if s.strip()]
```

---

## 🔧 Phase 5: 통합 시스템 구현

### 5.1 통합 청킹 매니저

#### 파일: `utils/integrated_chunking_manager.py` (신규 생성)
```python
from typing import List, Dict, Any, Union
import os

class IntegratedChunkingManager:
    """모든 문서 타입을 통합 관리하는 청킹 매니저"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pdf_engine = PDFChunkingEngine(config)
        self.pptx_engine = PPTXChunkingEngine(config)
        self.xlsx_engine = XLSXChunkingEngine(config)
        self.text_engine = TextChunkingEngine(config)
    
    def process_document(self, file_path: str) -> List[Chunk]:
        """파일 타입에 따라 적절한 청킹 엔진 선택"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.pdf':
            return self.pdf_engine.process_pdf_document(file_path)
        elif file_ext in ['.ppt', '.pptx']:
            return self.pptx_engine.process_pptx_document(file_path)
        elif file_ext in ['.xls', '.xlsx']:
            return self.xlsx_engine.process_xlsx_document(file_path)
        elif file_ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.text_engine.process_text_document(content)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {file_ext}")
```

### 5.2 Small-to-Large 검색 시스템

#### 파일: `utils/small_to_large_search.py` (신규 생성)
```python
from typing import List, Dict, Any
from langchain.schema import Document

class SmallToLargeSearch:
    """Small-to-Large 아키텍처 검색 시스템"""
    
    def __init__(self, vectorstore):
        self.vectorstore = vectorstore
    
    def search_with_context_expansion(self, query: str, top_k: int = 5) -> List[Document]:
        """정확한 검색 후 컨텍스트 확장"""
        # 1단계: Small 청크로 정확한 검색
        small_results = self.vectorstore.similarity_search_with_score(
            query, k=top_k * 2  # 더 많은 후보 확보
        )
        
        # 2단계: 부모 청크로 컨텍스트 확장
        expanded_results = []
        processed_parents = set()
        
        for doc, score in small_results:
            # Small 청크 추가
            expanded_results.append((doc, score))
            
            # 부모 청크 확장
            parent_id = doc.metadata.get("parent_chunk_id")
            if parent_id and parent_id not in processed_parents:
                parent_doc = self._get_parent_chunk(parent_id)
                if parent_doc:
                    expanded_results.append((parent_doc, score * 0.8))  # 부모는 약간 낮은 점수
                    processed_parents.add(parent_id)
        
        # 3단계: 상위 결과 반환
        expanded_results.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, score in expanded_results[:top_k]]
    
    def _get_parent_chunk(self, parent_id: str) -> Document:
        """부모 청크 조회"""
        # 벡터스토어에서 parent_id로 검색
        results = self.vectorstore.similarity_search(
            f"parent_chunk_id:{parent_id}", k=1
        )
        return results[0] if results else None
```

---

## 📅 구현 일정

### Week 1: PDF 고급 청킹 구현
- [ ] `utils/pdf_chunking.py` - 핵심 데이터 구조
- [ ] `utils/pdf_layout_analyzer.py` - Layout-Aware 분석기
- [ ] `utils/pdf_chunking_engine.py` - Small-to-Large 엔진
- [ ] `utils/chunking_fallback.py` - Fallback 메커니즘

### Week 2: PPTX 슬라이드 중심 청킹
- [ ] `utils/pptx_chunking.py` - 슬라이드 구조 분석기
- [ ] 슬라이드 제목/노트/본문 구분 처리
- [ ] 불릿 포인트 버퍼링 전략

### Week 3: XLSX 워크시트 중심 청킹
- [ ] `utils/xlsx_chunking.py` - 워크시트 구조 분석기
- [ ] 헤더/데이터/수식 구분 처리
- [ ] 행 그룹화 전략

### Week 4: Text 구조 인식 청킹
- [ ] `utils/text_chunking.py` - 텍스트 구조 분석기
- [ ] 섹션/문단/코드블록 구분 처리
- [ ] Markdown 헤더 인식

### Week 5: 통합 시스템 및 최적화
- [ ] `utils/integrated_chunking_manager.py` - 통합 매니저
- [ ] `utils/small_to_large_search.py` - 검색 시스템
- [ ] `utils/document_processor.py` 통합
- [ ] 성능 테스트 및 최적화

---

## 🎯 예상 효과

### 검색 성능 향상
- **정확도**: 40-60% 향상 (Small-to-Large 아키텍처)
- **컨텍스트 품질**: 완전한 답변 제공
- **구조 보존**: 문서의 시각적 레이아웃 반영

### 사용자 경험 개선
- **관련성**: 더 정확한 문서 검색
- **완전성**: 컨텍스트가 풍부한 답변
- **신뢰성**: 출처 정보의 정확성 향상

### 시스템 확장성
- **모듈화**: 파일 타입별 독립적 처리
- **확장성**: 새로운 문서 타입 쉽게 추가
- **유지보수**: 명확한 책임 분리

---

**문서 버전**: 1.0  
**최종 수정일**: 2024-12-19  
**작성자**: RAG Development Team
