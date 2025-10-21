"""
PDF 고급 청킹 엔진
Small-to-Large 아키텍처와 Layout-Aware 분석을 통한 PDF 청킹
"""
from typing import List, Dict, Any, Optional
import pdfplumber
import uuid
from .pdf_chunking import Chunk, ChunkMetadata, ChunkFactory, CHUNK_TYPE_WEIGHTS
from .pdf_layout_analyzer import PDFLayoutAnalyzer
from .chunking_fallback import ChunkingFallback


class PDFChunkingEngine:
    """PDF 고급 청킹 엔진"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.layout_analyzer = PDFLayoutAnalyzer()
        self.fallback = ChunkingFallback(config)
        
        # 설정값들
        self.max_size = config.get("max_size", 500)
        self.overlap_size = config.get("overlap_size", 100)
        self.enable_small_to_large = config.get("enable_small_to_large", True)
        self.enable_layout_analysis = config.get("enable_layout_analysis", True)
    
    def process_pdf_document(self, pdf_path: str) -> List[Chunk]:
        """PDF 문서를 레이아웃을 인식하여 계층적으로 청킹"""
        all_chunks = []
        document_id = str(uuid.uuid4())
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                current_section_title = "문서 서두"
                
                for page_num, page in enumerate(pdf.pages, 1):
                    print(f"페이지 {page_num} 처리 중...")
                    
                    # 1. Large 청크 생성 (페이지 전체) - Small-to-Large 아키텍처
                    if self.enable_small_to_large:
                        page_chunk = self._create_page_summary_chunk(
                            page, document_id, page_num, current_section_title
                        )
                        all_chunks.append(page_chunk)
                        parent_id = page_chunk.id
                    else:
                        parent_id = None
                    
                    # 2. Small 청크 생성 (Layout-Aware)
                    if self.enable_layout_analysis:
                        elements = self.layout_analyzer.analyze_page_elements(page)
                        small_chunks = self._process_page_elements(
                            elements, document_id, page_num, 
                            parent_id, current_section_title
                        )
                        all_chunks.extend(small_chunks)
                        
                        # 3. 섹션 제목 업데이트
                        current_section_title = self._update_section_title(
                            elements, current_section_title
                        )
                    else:
                        # 폴백: 기본 텍스트 추출
                        basic_text = page.extract_text()
                        if basic_text:
                            basic_chunks = self._create_basic_chunks(
                                basic_text, document_id, page_num, parent_id, current_section_title
                            )
                            all_chunks.extend(basic_chunks)
        
        except Exception as e:
            print(f"PDF 처리 중 오류 발생: {e}")
            # 최종 폴백: 기본 텍스트 추출
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    all_text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            all_text += page_text + "\n\n"
                    
                    if all_text:
                        basic_chunks = self._create_basic_chunks(
                            all_text, document_id, 1, None, "문서 전체"
                        )
                        all_chunks.extend(basic_chunks)
            except Exception as fallback_error:
                print(f"폴백 처리도 실패: {fallback_error}")
        
        print(f"총 {len(all_chunks)}개 청크 생성 완료")
        return all_chunks
    
    def _create_page_summary_chunk(self, page, document_id: str, page_num: int, 
                                 section_title: str) -> Chunk:
        """페이지 전체 텍스트를 부모 청크로 생성"""
        page_text = page.extract_text() or ""
        
        return ChunkFactory.create_page_summary_chunk(
            page_text=page_text,
            document_id=document_id,
            page_num=page_num,
            section_title=section_title
        )
    
    def _process_page_elements(self, elements: List[Dict[str, Any]], 
                             document_id: str, page_num: int, 
                             parent_id: Optional[str], section_title: str) -> List[Chunk]:
        """페이지 요소들을 Small 청크로 처리"""
        chunks = []
        current_list_buffer = []
        
        for elem in elements:
            elem_type = elem.get("type", "paragraph")
            elem_content = elem.get("content", "")
            elem_props = elem.get("properties", {})
            
            # 빈 내용은 건너뛰기
            if not elem_content or not elem_content.strip():
                continue
            
            # 리스트 항목 버퍼링
            if elem_type == "list_item":
                current_list_buffer.append(elem_content)
                continue
            
            # 리스트 버퍼 비우기
            if current_list_buffer:
                list_chunks = self._create_list_chunks(
                    current_list_buffer, document_id, page_num, 
                    parent_id, section_title, elem_props
                )
                chunks.extend(list_chunks)
                current_list_buffer.clear()
            
            # 다른 요소 처리
            if elem_type == "title":
                chunk = self._create_title_chunk(
                    elem_content, document_id, page_num, parent_id, section_title, elem_props
                )
                chunks.append(chunk)
            elif elem_type == "paragraph":
                para_chunks = self._create_paragraph_chunks(
                    elem_content, document_id, page_num, parent_id, section_title, elem_props
                )
                chunks.extend(para_chunks)
            elif elem_type == "table":
                table_chunks = self._create_table_chunks(
                    elem, document_id, page_num, parent_id, section_title
                )
                chunks.extend(table_chunks)
        
        # 마지막 리스트 버퍼 처리
        if current_list_buffer:
            list_chunks = self._create_list_chunks(
                current_list_buffer, document_id, page_num, 
                parent_id, section_title, {}
            )
            chunks.extend(list_chunks)
        
        return chunks
    
    def _create_title_chunk(self, title_text: str, document_id: str, page_num: int,
                          parent_id: Optional[str], section_title: str, 
                          elem_props: Dict[str, Any]) -> Chunk:
        """제목 청크 생성"""
        font_size = elem_props.get("font_size", 18.0)
        is_bold = elem_props.get("is_bold", True)
        
        return ChunkFactory.create_title_chunk(
            title_text=title_text,
            document_id=document_id,
            page_num=page_num,
            parent_id=parent_id,
            section_title=section_title,
            font_size=font_size,
            is_bold=is_bold
        )
    
    def _create_paragraph_chunks(self, para_text: str, document_id: str, page_num: int,
                               parent_id: Optional[str], section_title: str,
                               elem_props: Dict[str, Any]) -> List[Chunk]:
        """문단 청크 생성 (Fallback 포함)"""
        font_size = elem_props.get("font_size", 12.0)
        
        base_metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=CHUNK_TYPE_WEIGHTS.get("paragraph", 1.0),
            font_size=font_size
        )
        
        return self.fallback.chunk_element_with_fallback(
            content=para_text,
            element_type="paragraph",
            base_metadata=base_metadata
        )
    
    def _create_list_chunks(self, list_items: List[str], document_id: str, page_num: int,
                          parent_id: Optional[str], section_title: str,
                          elem_props: Dict[str, Any]) -> List[Chunk]:
        """리스트 청크 생성 (버퍼링 전략)"""
        font_size = elem_props.get("font_size", 12.0)
        
        base_metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=CHUNK_TYPE_WEIGHTS.get("list", 1.2),
            font_size=font_size
        )
        
        return self.fallback.chunk_list_with_fallback(
            list_items=list_items,
            base_metadata=base_metadata
        )
    
    def _create_table_chunks(self, table_elem: Dict[str, Any], document_id: str, 
                           page_num: int, parent_id: Optional[str], 
                           section_title: str) -> List[Chunk]:
        """테이블 청크 생성"""
        table_data = table_elem.get("data", [])
        
        # 테이블 데이터가 비어있으면 빈 리스트 반환
        if not table_data:
            return []
        
        base_metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=CHUNK_TYPE_WEIGHTS.get("table", 1.3)
        )
        
        return self.fallback.chunk_table_with_fallback(
            table_data=table_data,
            base_metadata=base_metadata
        )
    
    def _create_basic_chunks(self, text: str, document_id: str, page_num: int,
                           parent_id: Optional[str], section_title: str) -> List[Chunk]:
        """기본 텍스트 청킹 (폴백)"""
        base_metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=1.0
        )
        
        return self.fallback.chunk_element_with_fallback(
            content=text,
            element_type="paragraph",
            base_metadata=base_metadata
        )
    
    def _update_section_title(self, elements: List[Dict[str, Any]], 
                            current_title: str) -> str:
        """섹션 제목 업데이트"""
        for elem in elements:
            if elem["type"] == "title":
                return elem["content"]
        return current_title
    
    def get_chunk_statistics(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """청크 통계 정보 반환"""
        if not chunks:
            return {}
        
        stats = {
            "total_chunks": len(chunks),
            "chunk_types": {},
            "avg_word_count": 0,
            "avg_char_count": 0,
            "pages_covered": set(),
            "sections": set()
        }
        
        total_words = 0
        total_chars = 0
        
        for chunk in chunks:
            # 청크 타입별 카운트
            chunk_type = chunk.chunk_type
            stats["chunk_types"][chunk_type] = stats["chunk_types"].get(chunk_type, 0) + 1
            
            # 단어/문자 수 누적
            total_words += chunk.metadata.word_count
            total_chars += chunk.metadata.char_count
            
            # 페이지 및 섹션 정보
            stats["pages_covered"].add(chunk.metadata.page_number)
            if chunk.metadata.section_title:
                stats["sections"].add(chunk.metadata.section_title)
        
        stats["avg_word_count"] = total_words / len(chunks)
        stats["avg_char_count"] = total_chars / len(chunks)
        stats["pages_covered"] = len(stats["pages_covered"])
        stats["sections"] = len(stats["sections"])
        
        return stats
