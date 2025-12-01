"""
PDF 고급 청킹 엔진
Small-to-Large 아키텍처와 Layout-Aware 분석을 통한 PDF 청킹

Phase 2: Vision 기본 지원 추가
Phase 3: Hybrid 모드 (텍스트 페이지 Vision 스킵)
"""
from typing import List, Dict, Any, Optional
import pdfplumber
import uuid
import os
import base64
from io import BytesIO
import requests
import time

# Phase 2: Vision 라이브러리
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

try:
    from PyPDF2 import PdfReader
except ImportError:
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None

from .pdf_chunking import Chunk, ChunkMetadata, ChunkFactory, CHUNK_TYPE_WEIGHTS
from .pdf_layout_analyzer import PDFLayoutAnalyzer
from .chunking_fallback import ChunkingFallback


class CancelledException(Exception):
    """업로드가 취소되었을 때 발생하는 예외"""
    pass


class PartialUploadException(Exception):
    """부분 업로드 발생 시 발생하는 예외 (전체 롤백용)"""
    def __init__(self, message: str, failed_page: int):
        super().__init__(message)
        self.failed_page = failed_page


class PDFChunkingEngine:
    """PDF 고급 청킹 엔진 (Vision 지원)"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.layout_analyzer = PDFLayoutAnalyzer()
        self.fallback = ChunkingFallback(config)

        # 설정값들
        self.max_size = config.get("max_size", 500)
        self.overlap_size = config.get("overlap_size", 100)
        self.enable_small_to_large = config.get("enable_small_to_large", True)
        self.enable_layout_analysis = config.get("enable_layout_analysis", True)

        # Phase 2: Vision 설정
        self.enable_vision = config.get("enable_vision_chunking", True)
        self.poppler_path = config.get("poppler_path", None)
        self.pdf_dpi = config.get("pdf_dpi", 150)
        self.pdf_vision_detail = config.get("pdf_vision_detail", "high")

        # Vision API 설정 (LLM과 별개)
        self.vision_api_type = config.get("vision_api_type", "openai")
        self.vision_base_url = config.get("vision_base_url", "https://api.openai.com/v1")
        self.vision_model = config.get("vision_model", "gpt-4o-mini")
        self.vision_api_key = config.get("vision_api_key", "")

        # Phase 3: Hybrid 설정
        self.enable_hybrid = config.get("enable_pdf_hybrid", True)
    
    def process_pdf_document(self,
                            pdf_path: str,
                            enable_vision: Optional[bool] = None,
                            enable_hybrid: Optional[bool] = None,
                            llm_api_type: Optional[str] = None,
                            llm_base_url: Optional[str] = None,
                            llm_model: Optional[str] = None,
                            llm_api_key: Optional[str] = None,
                            cancel_callback=None,
                            progress_callback=None) -> List[Chunk]:
        """
        PDF 문서를 레이아웃을 인식하여 계층적으로 청킹

        Phase 2: Vision 모드 추가
        - enable_vision=True: PDF → 이미지 → Vision API 분석
        - enable_vision=False: 기존 pdfplumber 텍스트 추출

        Phase 3: Hybrid 모드 추가
        - enable_hybrid=True: Smart Decision (표/차트만 Vision)
        - enable_hybrid=False: Phase 2 동작 (모든 페이지 Vision)

        Args:
            pdf_path: PDF 파일 경로
            enable_vision: Vision 사용 여부 (None이면 config 값 사용)
            enable_hybrid: Hybrid 모드 사용 여부 (None이면 config 값 사용)
            llm_api_type: LLM API 타입
            llm_base_url: LLM Base URL
            llm_model: LLM 모델명
            llm_api_key: LLM API 키

        Returns:
            Chunk 리스트
        """
        # Vision 모드 결정
        use_vision = enable_vision if enable_vision is not None else self.enable_vision
        use_hybrid = enable_hybrid if enable_hybrid is not None else self.enable_hybrid

        # Vision 모드면 Vision 처리 호출
        if use_vision:
            # Phase 4: PPTX 변환 PDF 감지 (Hybrid 모드 무시하고 Full Vision)
            is_pptx_converted = self._is_pptx_converted_pdf(pdf_path)
            if is_pptx_converted:
                print(f"[PDFChunkingEngine] PPTX 변환 PDF 감지 → Full Vision 모드 강제 적용")
                return self._process_pdf_with_vision(
                    pdf_path=pdf_path,
                    llm_api_type=llm_api_type or self.config.get("llm_api_type", "openai"),
                    llm_base_url=llm_base_url or self.config.get("llm_base_url", ""),
                    llm_model=llm_model or self.config.get("llm_model", "gpt-4o-mini"),
                    llm_api_key=llm_api_key or self.config.get("llm_api_key", ""),
                    cancel_callback=cancel_callback,
                    progress_callback=progress_callback
                )

            # Phase 3: Hybrid 모드 (일반 문서)
            elif use_hybrid:
                return self._process_pdf_with_hybrid(
                    pdf_path=pdf_path,
                    llm_api_type=llm_api_type or self.config.get("llm_api_type", "openai"),
                    llm_base_url=llm_base_url or self.config.get("llm_base_url", ""),
                    llm_model=llm_model or self.config.get("llm_model", "gpt-4o-mini"),
                    llm_api_key=llm_api_key or self.config.get("llm_api_key", ""),
                    cancel_callback=cancel_callback,
                    progress_callback=progress_callback
                )
            # Phase 2: 모든 페이지 Vision
            else:
                return self._process_pdf_with_vision(
                    pdf_path=pdf_path,
                    llm_api_type=llm_api_type or self.config.get("llm_api_type", "openai"),
                    llm_base_url=llm_base_url or self.config.get("llm_base_url", ""),
                    llm_model=llm_model or self.config.get("llm_model", "gpt-4o-mini"),
                    llm_api_key=llm_api_key or self.config.get("llm_api_key", ""),
                    cancel_callback=cancel_callback,
                    progress_callback=progress_callback
                )

        # 기존 텍스트 모드 (pdfplumber)
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
        
        # 상용 서비스 수준: 최종 청크 필터링 및 통계
        filtered_chunks = self._filter_invalid_chunks(all_chunks)
        
        print(f"총 {len(all_chunks)}개 청크 생성 → {len(filtered_chunks)}개 유효 청크")
        return filtered_chunks
    
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
        table_idx = 0  # 페이지별 표 인덱스 추적
        
        for elem in elements:
            elem_type = elem.get("type", "paragraph")
            elem_content = elem.get("content", "")
            elem_props = elem.get("properties", {})
            
            # 빈 내용은 건너뛰기 (상용 서비스 수준 필터링)
            if not elem_content or not elem_content.strip():
                continue
            
            # 의미 없는 매우 짧은 내용 필터링 (1-3자 구두점/단일 문자)
            cleaned = elem_content.strip()
            if len(cleaned) <= 3:
                # 알파벳/숫자가 포함되어 있지 않으면 스킵
                if not any(c.isalnum() for c in cleaned):
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
            
            # 다른 요소 처리 (Phase 3: heading, caption, section 추가)
            if elem_type == "heading":
                chunk = self._create_heading_chunk(
                    elem_content, document_id, page_num, parent_id, section_title, elem
                )
                chunks.append(chunk)
                # 제목 감지 시 section_title 업데이트
                section_title = elem_content.strip()
            elif elem_type == "caption":
                chunk = self._create_caption_chunk(
                    elem_content, document_id, page_num, parent_id, section_title, elem
                )
                chunks.append(chunk)
            elif elem_type == "section":
                chunk = self._create_section_chunk(
                    elem_content, document_id, page_num, parent_id, section_title, elem
                )
                chunks.append(chunk)
                # 섹션 번호 감지 시 section_title 업데이트
                section_title = elem_content.strip()
            elif elem_type == "title":
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
                    elem, document_id, page_num, parent_id, section_title, table_idx
                )
                chunks.extend(table_chunks)
                table_idx += 1  # 다음 표를 위해 인덱스 증가
        
        # 마지막 리스트 버퍼 처리
        if current_list_buffer:
            list_chunks = self._create_list_chunks(
                current_list_buffer, document_id, page_num, 
                parent_id, section_title, {}
            )
            chunks.extend(list_chunks)
        
        return chunks
    
    def _create_heading_chunk(self, heading_text: str, document_id: str, page_num: int,
                            parent_id: Optional[str], section_title: str,
                            elem: Dict[str, Any]) -> Chunk:
        """Heading 청크 생성 (Phase 3)"""
        elem_props = elem.get("properties", {})
        font_size = elem_props.get("font_size", 18.0)
        is_bold = elem_props.get("is_bold", True)
        heading_level = elem.get("heading_level", "H3")
        
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=CHUNK_TYPE_WEIGHTS.get("heading", 2.5),
            font_size=font_size,
            is_bold=is_bold,
            heading_level=heading_level
        )
        
        return ChunkFactory.create_chunk(
            content=heading_text,
            chunk_type="heading",
            metadata=metadata
        )
    
    def _create_caption_chunk(self, caption_text: str, document_id: str, page_num: int,
                            parent_id: Optional[str], section_title: str,
                            elem: Dict[str, Any]) -> Chunk:
        """Caption 청크 생성 (Phase 3)"""
        elem_props = elem.get("properties", {})
        font_size = elem_props.get("font_size", 12.0)
        caption_type = elem.get("caption_type", "figure")
        
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=CHUNK_TYPE_WEIGHTS.get("caption", 1.8),
            font_size=font_size,
            caption_type=caption_type
        )
        
        return ChunkFactory.create_chunk(
            content=caption_text,
            chunk_type="caption",
            metadata=metadata
        )
    
    def _create_section_chunk(self, section_text: str, document_id: str, page_num: int,
                            parent_id: Optional[str], section_title: str,
                            elem: Dict[str, Any]) -> Chunk:
        """Section 청크 생성 (Phase 3)"""
        elem_props = elem.get("properties", {})
        font_size = elem_props.get("font_size", 16.0)
        is_bold = elem_props.get("is_bold", True)
        section_number = elem.get("section_number", "")
        
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=CHUNK_TYPE_WEIGHTS.get("section", 2.2),
            font_size=font_size,
            is_bold=is_bold,
            section_number=section_number
        )
        
        return ChunkFactory.create_chunk(
            content=section_text,
            chunk_type="section",
            metadata=metadata
        )
    
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
                           section_title: str, table_idx: int = 0) -> List[Chunk]:
        """Phase 1-3: 표 다층 청킹 - 전체/행/열/키-값 청크 생성"""
        table_data = table_elem.get("data", [])
        
        # 테이블 데이터가 비어있으면 빈 리스트 반환
        if not table_data or len(table_data) == 0:
            return []
        
        chunks = []
        
        try:
            # 표 기본 정보 추출 (페이지별 표 인덱스 사용)
            table_id = f"{document_id}_page_{page_num}_table_{table_idx}"
            num_rows = len(table_data)
            num_cols = len(table_data[0]) if num_rows > 0 else 0
            
            # 헤더 행 추출
            header_row = []
            if num_rows > 0:
                header_row = [str(cell).strip() if cell else "" for cell in table_data[0]]
            
            # 표 제목 추출
            table_title = section_title or header_row[0] if header_row else None
            
            # 항목 번호 추출 (Phase 2)
            item_map = self._extract_item_numbers_from_table_data(table_data, header_row)
            
            # 데이터 타입 감지 (Phase 3)
            data_type = self._detect_table_data_type(header_row, table_data)
            
            # 1. 전체 표 청크 생성 (컨텍스트용)
            full_table_chunk = self._create_full_table_chunk_pdf(
                table_data, document_id, page_num, parent_id, section_title,
                table_id, table_title, header_row, num_rows, num_cols, data_type
            )
            if full_table_chunk:  # None이 아닐 때만 추가
                chunks.append(full_table_chunk)
            
            # 2. 각 행을 개별 청크로 생성
            for row_idx, row in enumerate(table_data):
                row_chunk = self._create_table_row_chunk_pdf(
                    row, row_idx, header_row, document_id, page_num, parent_id,
                    section_title, table_id, table_title, num_cols, item_map, data_type
                )
                chunks.append(row_chunk)
            
            # 3. 각 열을 개별 청크로 생성 (열별 집계 검색용)
            if num_cols > 0:
                for col_idx in range(num_cols):
                    col_chunk = self._create_table_column_chunk_pdf(
                        table_data, col_idx, header_row, document_id, page_num, parent_id,
                        section_title, table_id, table_title, num_rows, data_type
                    )
                    if col_chunk:
                        chunks.append(col_chunk)
            
            # 4. 키-값 쌍 청크 생성 (항목 번호 검색용, Phase 2)
            kv_chunks = self._create_table_key_value_chunks_pdf(
                table_data, header_row, document_id, page_num, parent_id,
                section_title, table_id, table_title, item_map, data_type
            )
            chunks.extend(kv_chunks)
        
        except Exception as e:
            print(f"PDF 테이블 청킹 중 오류: {e}")
            import traceback
            traceback.print_exc()
            # 폴백: 기존 방식 사용
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
        
        return chunks
    
    def _create_full_table_chunk_pdf(self, table_data: List[List[str]], document_id: str,
                                     page_num: int, parent_id: Optional[str],
                                     section_title: str, table_id: str,
                                     table_title: Optional[str], header_row: List[str],
                                     num_rows: int, num_cols: int,
                                     data_type: Optional[str]) -> Optional[Chunk]:
        """전체 표 청크 생성 (컨텍스트용)"""
        markdown_table = self._convert_table_data_to_markdown(table_data)
        
        # 빈 표는 생성하지 않음
        if not markdown_table or not markdown_table.strip():
            return None
        
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=1.2,  # 전체 표는 높은 가중치 (집계 질문에 중요)
            has_table=True,
            table_id=table_id,
            table_title=table_title,
            header_row=header_row,
            table_row_count=num_rows,
            table_col_count=num_cols,
            data_type=data_type
        )
        
        return Chunk(
            id=f"{table_id}_full",
            content=markdown_table,
            chunk_type="table_full",
            metadata=metadata
        )
    
    def _create_table_row_chunk_pdf(self, row: List[str], row_idx: int,
                                    header_row: List[str], document_id: str,
                                    page_num: int, parent_id: Optional[str],
                                    section_title: str, table_id: str,
                                    table_title: Optional[str], num_cols: int,
                                    item_map: Dict[str, Dict],
                                    data_type: Optional[str]) -> Chunk:
        """행 단위 청크 생성"""
        cells = [str(cell).strip() if cell else "" for cell in row]
        is_header = (row_idx == 0)
        
        # 행 데이터를 텍스트로 변환
        if is_header:
            row_text = f"헤더: {' | '.join(cells)}"
        else:
            # 헤더와 함께 키-값 쌍 형식으로 변환
            row_pairs = []
            for col_idx, cell_text in enumerate(cells):
                if col_idx < len(header_row):
                    row_pairs.append(f"{header_row[col_idx]}: {cell_text}")
            row_text = " | ".join(row_pairs)
        
        # 항목 번호 추출 (Phase 2)
        item_number = None
        if cells and not is_header:
            first_cell = cells[0]
            # "항목 1", "항목 2" 등 추출
            import re
            if match := re.search(r'항목\s*(\d+)', first_cell):
                item_number = f"항목 {match.group(1)}"
        
        # 셀 참조 생성 (Phase 3) - 모든 셀에 대해 생성
        cell_references = []
        if not is_header:
            for col_idx in range(len(cells)):
                cell_ref = f"R{row_idx + 1}C{col_idx + 1}"
                cell_references.append(cell_ref)
            cell_reference = cell_references[0] if cell_references else None  # 첫 번째 셀 참조를 메인으로
        else:
            cell_reference = None
        
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=1.3,  # 행 단위는 높은 가중치
            has_table=True,
            table_id=table_id,
            table_title=table_title,
            row_index=row_idx,
            cell_reference=cell_reference,
            header_row=header_row,
            is_header_row=is_header,
            item_number=item_number,
            data_type=data_type,
            table_col_count=num_cols
        )
        
        return Chunk(
            id=f"{table_id}_row_{row_idx}",
            content=row_text,
            chunk_type="table_row",
            metadata=metadata
        )
    
    def _create_table_column_chunk_pdf(self, table_data: List[List[str]], col_idx: int,
                                      header_row: List[str], document_id: str,
                                      page_num: int, parent_id: Optional[str],
                                      section_title: str, table_id: str,
                                      table_title: Optional[str], num_rows: int,
                                      data_type: Optional[str]) -> Optional[Chunk]:
        """열 단위 청크 생성 (열별 집계 검색용)"""
        if col_idx >= len(header_row):
            return None
        
        col_header = header_row[col_idx]
        col_values = []
        
        # 해당 열의 모든 값 추출
        for row_idx, row in enumerate(table_data[1:], start=1):  # 헤더 제외
            if col_idx < len(row):
                cell_text = str(row[col_idx]).strip() if row[col_idx] else ""
                col_values.append(cell_text)
        
        # 열 데이터를 텍스트로 변환
        col_text = f"{col_header} 열: {', '.join(col_values)}"
        
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=1.1,  # 열 단위는 중간 가중치
            has_table=True,
            table_id=table_id,
            table_title=table_title,
            col_index=col_idx,
            header_row=header_row,
            data_type=data_type,
            table_row_count=num_rows
        )
        
        return Chunk(
            id=f"{table_id}_col_{col_idx}",
            content=col_text,
            chunk_type="table_column",
            metadata=metadata
        )
    
    def _create_table_key_value_chunks_pdf(self, table_data: List[List[str]],
                                          header_row: List[str], document_id: str,
                                          page_num: int, parent_id: Optional[str],
                                          section_title: str, table_id: str,
                                          table_title: Optional[str],
                                          item_map: Dict[str, Dict],
                                          data_type: Optional[str]) -> List[Chunk]:
        """키-값 쌍 청크 생성 (항목 번호 검색용, Phase 2)"""
        chunks = []
        
        for item_number, item_info in item_map.items():
            row_idx = item_info["row_index"]
            row_data = item_info["full_row_data"]
            
            # 키-값 쌍 형식으로 변환
            kv_pairs = []
            for col_idx, value in enumerate(row_data):
                if col_idx < len(header_row):
                    kv_pairs.append(f"{header_row[col_idx]}: {value}")
            
            kv_text = f"{item_number} - {' | '.join(kv_pairs)}"
            
            metadata = ChunkMetadata(
                document_id=document_id,
                page_number=page_num,
                parent_chunk_id=parent_id,
                section_title=section_title,
                chunk_type_weight=1.5,  # 항목 번호는 높은 가중치
                has_table=True,
                table_id=table_id,
                table_title=table_title,
                row_index=row_idx,
                cell_reference=f"R{row_idx + 1}C1",
                header_row=header_row,
                item_number=item_number,
                data_type=data_type
            )
            
            chunk = Chunk(
                id=f"{table_id}_item_{item_number}",
                content=kv_text,
                chunk_type="table_key_value",
                metadata=metadata
            )
            chunks.append(chunk)
        
        return chunks
    
    def _extract_item_numbers_from_table_data(self, table_data: List[List[str]],
                                              header_row: List[str]) -> Dict[str, Dict]:
        """표에서 항목 번호 추출 (Phase 2)"""
        item_map = {}
        
        if len(table_data) <= 1:
            return item_map
        
        import re
        
        # 첫 번째 열에서 항목 번호 추출
        for row_idx, row in enumerate(table_data[1:], start=1):  # 헤더 제외
            if len(row) > 0:
                first_cell = str(row[0]).strip() if row[0] else ""
                
                # "항목 1", "항목 2" 패턴 추출
                if match := re.search(r'항목\s*(\d+)', first_cell):
                    item_num = match.group(1)
                    item_number = f"항목 {item_num}"
                    
                    # 전체 행 데이터 추출
                    full_row_data = [str(cell).strip() if cell else "" for cell in row]
                    
                    item_map[item_number] = {
                        "row_index": row_idx,
                        "full_row_data": full_row_data
                    }
        
        return item_map
    
    def _detect_table_data_type(self, header_row: List[str],
                                table_data: List[List[str]]) -> Optional[str]:
        """표 데이터 타입 자동 감지 (Phase 3)"""
        if not header_row:
            return None
        
        header_text = " ".join([str(h).lower() for h in header_row])
        
        # 예산 관련 키워드
        if any(keyword in header_text for keyword in ["예산", "budget", "지출", "비용"]):
            return "budget"
        
        # 매출 관련 키워드
        if any(keyword in header_text for keyword in ["매출", "sales", "수익", "revenue"]):
            return "sales"
        
        # 성과 관련 키워드
        if any(keyword in header_text for keyword in ["성과", "performance", "점수", "score"]):
            return "performance"
        
        # 일정 관련 키워드
        if any(keyword in header_text for keyword in ["일정", "schedule", "기간", "period"]):
            return "schedule"
        
        return None
    
    def _convert_table_data_to_markdown(self, table_data: List[List[str]]) -> str:
        """테이블 데이터를 Markdown 형식으로 변환"""
        markdown_lines = []
        
        try:
            if len(table_data) == 0:
                return ""
            
            # 헤더 (첫 번째 행)
            header_cells = [str(cell).strip() if cell else "" for cell in table_data[0]]
            markdown_lines.append(f"| {' | '.join(header_cells)} |")
            markdown_lines.append(f"| {' | '.join(['---'] * len(header_cells))} |")
            
            # 본문 (나머지 행)
            for row in table_data[1:]:
                body_cells = [str(cell).strip() if cell else "" for cell in row]
                markdown_lines.append(f"| {' | '.join(body_cells)} |")
            
            return "\n".join(markdown_lines)
        
        except Exception as e:
            print(f"테이블 변환 중 오류: {e}")
            return ""
    
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
    
    def _filter_invalid_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """유효하지 않은 청크 필터링 (상용 서비스 수준)"""
        valid_chunks = []
        min_chunk_size = self.config.get("min_chunk_size", 50)
        min_word_count = self.config.get("min_word_count", 5)
        
        for chunk in chunks:
            content = chunk.content
            
            # 1. 빈 내용 필터링
            if not content or not content.strip():
                continue
            
            # 2. 최소 길이 필터링
            if len(content.strip()) < min_chunk_size:
                continue
            
            # 3. 최소 단어 수 필터링
            word_count = len(content.strip().split())
            if word_count < min_word_count:
                continue
            
            # 4. 의미 없는 단일 문자/구두점 필터링
            cleaned = content.strip()
            if len(cleaned) == 1:
                # 단일 문자가 알파벳/숫자가 아니면 제외
                if not cleaned.isalnum():
                    continue
            
            # 5. 구두점/공백만 있는 경우 제외
            if not any(c.isalnum() for c in cleaned):
                continue

            valid_chunks.append(chunk)

        return valid_chunks

    # ========================================
    # Phase 2: Vision 관련 메서드
    # ========================================

    def _process_pdf_with_vision(self,
                                 pdf_path: str,
                                 llm_api_type: str,
                                 llm_base_url: str,
                                 llm_model: str,
                                 llm_api_key: str,
                                 cancel_callback=None,
                                 progress_callback=None) -> List[Chunk]:
        """
        PDF를 Vision API로 처리 (Phase 2)

        Args:
            pdf_path: PDF 파일 경로
            llm_api_type: LLM API 타입
            llm_base_url: LLM Base URL
            llm_model: LLM 모델명
            llm_api_key: LLM API 키

        Returns:
            Chunk 리스트
        """
        print(f"[PDFChunkingEngine] Vision 모드로 PDF 처리: {pdf_path}")

        # 필수 라이브러리 확인
        if convert_from_path is None:
            raise ImportError(
                "pdf2image 라이브러리가 설치되지 않았습니다. "
                "'pip install pdf2image' 실행 후 다시 시도하세요."
            )

        if PdfReader is None:
            raise ImportError(
                "PyPDF2/pypdf 라이브러리가 설치되지 않았습니다. "
                "'pip install pypdf' 실행 후 다시 시도하세요."
            )

        # PDF 파일 존재 확인
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 파일 없음: {pdf_path}")

        # PDF 페이지 수 확인
        try:
            reader = PdfReader(pdf_path)
            page_count = len(reader.pages)
            print(f"[PDFChunkingEngine] 총 {page_count}페이지")
        except Exception as e:
            raise RuntimeError(f"PDF 파일 읽기 실패: {e}")

        # PDF → 이미지 변환
        print("[PDFChunkingEngine] PDF → 이미지 변환 중...")
        try:
            kwargs = {"dpi": self.pdf_dpi}
            if self.poppler_path:
                kwargs["poppler_path"] = self.poppler_path

            images = convert_from_path(pdf_path, **kwargs)
            print(f"[PDFChunkingEngine] {len(images)}개 페이지 이미지 변환 완료")
        except Exception as e:
            error_msg = str(e)
            if "poppler" in error_msg.lower():
                raise RuntimeError(
                    f"PDF 이미지 변환 실패 (Poppler 문제): {e}\n\n"
                    "Poppler를 설치하세요. 설치 가이드: POPPLER_INSTALL_GUIDE.md"
                )
            else:
                raise RuntimeError(f"PDF 이미지 변환 실패: {e}")

        if len(images) != page_count:
            print(f"[WARNING] 페이지 수 불일치: {page_count} vs {len(images)}")

        # 각 페이지 분석
        chunks = []
        document_id = str(uuid.uuid4())

        # 재시도 설정
        MAX_RETRIES = 3
        RETRYABLE_EXCEPTIONS = (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
        RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]

        for page_num, image in enumerate(images, 1):
            # 취소 체크
            if cancel_callback and cancel_callback():
                raise CancelledException(f"업로드가 사용자에 의해 취소되었습니다 (페이지 {page_num}/{page_count})")

            # 진행 상황 업데이트
            progress_pct = (page_num / page_count) * 100
            if progress_callback:
                progress_callback(f"페이지 {page_num}/{page_count} 처리 중...", progress_pct)
            print(f"[PDFChunkingEngine] 페이지 {page_num}/{page_count} Vision 분석 중... ({progress_pct:.1f}%)")

            # 이미지 → Base64 (재시도 불가 - 인코딩 실패는 시스템 오류)
            try:
                print(f"  → 이미지 인코딩 중...")
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                print(f"  → 이미지 인코딩 완료 ({len(image_base64)} bytes)")
            except Exception as e:
                print(f"[ERROR] 페이지 {page_num} 이미지 인코딩 실패: {e}")
                raise PartialUploadException(f"페이지 {page_num} 이미지 인코딩 실패: {e}", page_num)

            # Vision 분석 (재시도 로직 포함)
            retry_count = 0
            last_exception = None
            while retry_count < MAX_RETRIES:
                try:
                    print(f"  → Vision API 호출 중... (모델: {self.vision_model})")
                    description = self._analyze_page_with_vision(
                        image_base64=image_base64,
                        page_num=page_num,
                        total_pages=page_count,
                        llm_api_type=self.vision_api_type,
                        llm_base_url=self.vision_base_url,
                        llm_api_key=self.vision_api_key,
                        llm_model=self.vision_model
                    )

                    # Chunk 생성
                    chunk = Chunk(
                        id=f"{document_id}_pdf_page_{page_num}",
                        content=description,
                        chunk_type="pdf_page_vision",
                        metadata=ChunkMetadata(
                            document_id=document_id,
                            page_number=page_num,
                            section_title=f"Page {page_num}",
                            chunk_type_weight=1.5  # Vision 페이지는 높은 가중치
                        )
                    )
                    chunks.append(chunk)
                    print(f"[PDFChunkingEngine] ✓ 페이지 {page_num}/{page_count} Vision 분석 완료 ({len(description)} chars)")
                    break  # 성공 → 재시도 루프 탈출

                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        print(f"[ERROR] 페이지 {page_num} Vision 분석 실패 (재시도 {MAX_RETRIES}회 초과): {e}")
                        raise PartialUploadException(
                            f"페이지 {page_num} Vision 분석 실패 (재시도 {MAX_RETRIES}회 초과): {e}",
                            page_num
                        )
                    else:
                        wait_time = 2 ** retry_count  # 2초, 4초, 8초
                        print(f"  [재시도 {retry_count}/{MAX_RETRIES}] {wait_time}초 후 재시도... (오류: {e})")
                        time.sleep(wait_time)
                        # 대기 중 취소 체크
                        if cancel_callback and cancel_callback():
                            raise CancelledException(f"업로드가 사용자에 의해 취소되었습니다 (페이지 {page_num} 재시도 중)")

                except requests.exceptions.HTTPError as e:
                    # HTTP 상태 코드 확인
                    if hasattr(e, 'response') and e.response is not None:
                        status_code = e.response.status_code
                        if status_code in RETRYABLE_STATUS_CODES:
                            # 재시도 가능한 HTTP 에러
                            last_exception = e
                            retry_count += 1
                            if retry_count >= MAX_RETRIES:
                                print(f"[ERROR] 페이지 {page_num} Vision 분석 실패 (HTTP {status_code}, 재시도 {MAX_RETRIES}회 초과): {e}")
                                raise PartialUploadException(
                                    f"페이지 {page_num} Vision 분석 실패 (HTTP {status_code}, 재시도 {MAX_RETRIES}회 초과): {e}",
                                    page_num
                                )
                            else:
                                wait_time = 2 ** retry_count
                                print(f"  [재시도 {retry_count}/{MAX_RETRIES}] HTTP {status_code} 에러, {wait_time}초 후 재시도...")
                                time.sleep(wait_time)
                                if cancel_callback and cancel_callback():
                                    raise CancelledException(f"업로드가 사용자에 의해 취소되었습니다 (페이지 {page_num} 재시도 중)")
                        else:
                            # 재시도 불가능한 HTTP 에러 (예: 401, 400)
                            print(f"[ERROR] 페이지 {page_num} Vision 분석 실패 (HTTP {status_code}): {e}")
                            raise PartialUploadException(
                                f"페이지 {page_num} Vision 분석 실패 (HTTP {status_code}): {e}",
                                page_num
                            )
                    else:
                        # 상태 코드 없는 HTTP 에러
                        print(f"[ERROR] 페이지 {page_num} Vision 분석 실패: {e}")
                        raise PartialUploadException(f"페이지 {page_num} Vision 분석 실패: {e}", page_num)

                except Exception as e:
                    # 기타 모든 예외는 재시도 불가
                    print(f"[ERROR] 페이지 {page_num} Vision 분석 실패: {e}")
                    raise PartialUploadException(f"페이지 {page_num} Vision 분석 실패: {e}", page_num)

        print(f"[PDFChunkingEngine] Vision 처리 완료: {len(chunks)}개 청크 생성")
        return chunks

    def _analyze_page_with_vision(self, image_base64: str, page_num: int,
                                  total_pages: int, llm_api_type: str,
                                  llm_base_url: str, llm_api_key: str,
                                  llm_model: str) -> str:
        """
        Vision API로 PDF 페이지 분석

        Args:
            image_base64: Base64 인코딩된 페이지 이미지
            page_num: 페이지 번호
            total_pages: 총 페이지 수
            llm_api_type: LLM API 타입
            llm_base_url: LLM Base URL
            llm_api_key: LLM API 키
            llm_model: LLM 모델명

        Returns:
            페이지 분석 결과 텍스트
        """
        # 프롬프트
        prompt = f"""이 PDF 페이지(Page {page_num}/{total_pages})의 내용을 자세히 분석하세요.

다음 정보를 추출하세요:

1. **주제**: 이 페이지의 주요 주제
2. **텍스트 내용**: 중요한 텍스트 (제목, 본문, 키워드)
3. **표**: 표가 있다면 제목, 행/열 구조, 주요 데이터
4. **차트/그래프**: 있다면 유형, 트렌드, 핵심 인사이트
5. **이미지**: 있다면 설명
6. **기타**: 주석, 강조 표시 등

추가 지시사항:
- 이미지에서 보이지 않거나 문서에서 확인할 수 없는 정보는 절대로 만들어내지 말고, "문서에서 확인 불가"라고 명시하세요.
- 숫자나 수식이 불명확한 경우에는 [약]/[추정] 또는 "확인 불가"라고 표시하세요.

구조화된 형식으로 답변하세요:
---
주제: ...
텍스트 내용: ...
표: ...
차트: ...
이미지: ...
"""

        # Vision API 호출
        try:
            if llm_api_type == "openai":
                # OpenAI 공식 Vision API
                api_url = "https://api.openai.com/v1/chat/completions"

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {llm_api_key}"
                }

                payload = {
                    "model": llm_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}",
                                        "detail": self.pdf_vision_detail
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 8000,
                    "temperature": 0
                }

            elif llm_api_type in ["request", "ollama", "openai-compatible"]:
                # 비전 설정 로드
                from config import ConfigManager
                cfg = ConfigManager().get_all()
                vision_enabled = cfg.get("vision_enabled", True)
                vision_mode = cfg.get("vision_mode", "auto")

                # 비전 모드 결정 함수
                def use_openai_style():
                    if vision_mode == "openai-compatible":
                        return True
                    if vision_mode == "ollama":
                        return False
                    # auto: URL 패턴으로 판단
                    return "/v1" in llm_base_url or llm_api_type in ["request", "openai-compatible"]

                if vision_enabled:
                    if use_openai_style():
                        # OpenAI 호환 멀티모달 API
                        api_url = f"{llm_base_url.rstrip('/')}/v1/chat/completions" if llm_base_url else "https://api.openai.com/v1/chat/completions"
                        payload = {
                            "model": llm_model,
                            "stream": False,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": prompt},
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/png;base64,{image_base64}",
                                                "detail": self.pdf_vision_detail
                                            }
                                        }
                                    ]
                                }
                            ],
                            "max_tokens": 8000,
                            "temperature": 0
                        }
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {llm_api_key}" if llm_api_key else ""
                        }
                    else:
                        # Ollama 네이티브 멀티모달 API
                        api_url = f"{llm_base_url.rstrip('/')}/api/chat"
                        payload = {
                            "model": llm_model,
                            "stream": False,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": prompt,
                                    "images": [image_base64]  # 순수 base64 (data: 접두 없음)
                                }
                            ],
                            "options": {
                                "temperature": 0,
                                "num_predict": 8000
                            }
                        }
                        headers = {"Content-Type": "application/json"}
                else:
                    raise RuntimeError("Vision이 비활성화되어 있습니다. config.json에서 vision_enabled를 true로 설정하세요.")

            else:
                raise ValueError(f"지원하지 않는 Vision API 타입: {llm_api_type}")

            print(f"  → API 요청 전송 중... (타임아웃: 연결 10초, 읽기 60초)")
            response = requests.post(api_url, headers=headers, json=payload, timeout=(10, 60))
            response.raise_for_status()

            print(f"  → API 응답 수신 완료 (상태: {response.status_code})")
            result = response.json()

            # 응답 파싱 (API 타입에 따라 다름)
            if llm_api_type == "openai":
                description = result["choices"][0]["message"]["content"]
            elif llm_api_type in ["request", "ollama", "openai-compatible"]:
                from config import ConfigManager
                cfg = ConfigManager().get_all()
                vision_mode = cfg.get("vision_mode", "auto")

                def use_openai_style():
                    if vision_mode == "openai-compatible":
                        return True
                    if vision_mode == "ollama":
                        return False
                    return "/v1/chat/completions" in api_url

                if use_openai_style() and "/v1/chat/completions" in api_url:
                    # OpenAI 호환 응답 처리
                    description = result["choices"][0]["message"]["content"]
                else:
                    # Ollama 응답 처리
                    description = result.get("message", {}).get("content", "")
            else:
                description = result["choices"][0]["message"]["content"]

            return description

        except requests.exceptions.Timeout:
            raise RuntimeError(f"Vision API 타임아웃 (페이지 {page_num})")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Vision API HTTP 오류 (페이지 {page_num}): {e}")
        except Exception as e:
            raise RuntimeError(f"Vision API 호출 실패 (페이지 {page_num}): {e}")

    # ========================================
    # Phase 3: Hybrid 모드 관련 메서드
    # ========================================

    def _should_use_vision(self, pdf_path: str, page_num: int) -> dict:
        """
        Smart Vision Decision: 이 페이지에 Vision이 필요한가?

        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (1-indexed)

        Returns:
            {
                "use_vision": bool,
                "reason": str,
                "has_table": bool,
                "has_image": bool,
                "text_only": bool
            }
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[page_num - 1]  # 0-indexed

                # 1. 이미지 확인
                images = page.images
                has_image = len(images) > 0

                # 2. 테이블 확인
                tables = page.extract_tables()
                has_table = len(tables) > 0

                # 3. 텍스트 확인
                text = page.extract_text()
                has_text = bool(text and text.strip())

                # 4. Decision Logic
                if has_image:
                    # 이미지 있음 → 차트/다이어그램 가능성 → Vision 필요
                    return {
                        "use_vision": True,
                        "reason": "이미지 포함 (차트/다이어그램 가능성)",
                        "has_table": has_table,
                        "has_image": has_image,
                        "text_only": False
                    }
                elif has_table:
                    # 테이블 있음 → Vision으로 구조 파악
                    return {
                        "use_vision": True,
                        "reason": "테이블 포함",
                        "has_table": has_table,
                        "has_image": has_image,
                        "text_only": False
                    }
                elif has_text:
                    # 텍스트만 → Vision 불필요
                    return {
                        "use_vision": False,
                        "reason": "텍스트 전용 페이지",
                        "has_table": has_table,
                        "has_image": has_image,
                        "text_only": True
                    }
                else:
                    # 빈 페이지
                    return {
                        "use_vision": False,
                        "reason": "빈 페이지",
                        "has_table": False,
                        "has_image": False,
                        "text_only": False
                    }

        except Exception as e:
            print(f"[WARNING] 페이지 {page_num} 분석 실패: {e}")
            # 실패 시 안전하게 Vision 사용
            return {
                "use_vision": True,
                "reason": f"분석 실패 (안전 모드): {e}",
                "has_table": False,
                "has_image": False,
                "text_only": False
            }

    def _is_pptx_converted_pdf(self, pdf_path: str) -> bool:
        """
        PDF가 PPTX에서 변환된 문서인지 감지

        PPTX 변환 PDF는 슬라이드 기반 레이아웃을 가지므로
        Hybrid 모드 대신 Full Vision 모드를 사용해야 함

        감지 기준:
        1. 메타데이터: /Producer, /Creator에 PowerPoint/Impress/Keynote 포함
        2. 화면 비율: 16:9 (1.78) 또는 4:3 (1.33) - 슬라이드 비율

        Args:
            pdf_path: PDF 파일 경로

        Returns:
            True if PPTX 변환 PDF, False otherwise
        """
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            try:
                from pypdf import PdfReader
            except ImportError:
                print(f"[WARNING] PyPDF2/pypdf 없음 - PPTX 변환 PDF 감지 불가")
                return False

        try:
            reader = PdfReader(pdf_path)

            # 1. 메타데이터 확인
            metadata = reader.metadata
            pptx_indicators = [
                "PowerPoint",
                "Microsoft Office PowerPoint",
                "Impress",  # LibreOffice
                "Keynote",  # Apple
                "Presentation",
                "pptx",
                "ppt"
            ]

            metadata_match = False
            if metadata:
                # Producer, Creator, Title, Subject 확인
                # PyPDF2는 '/Producer', pypdf는 'producer' 또는 '/Producer' 모두 지원
                for key in ['/Producer', '/Creator', '/Title', '/Subject']:
                    # 슬래시 있는 버전과 없는 버전 모두 체크 (pypdf 호환성)
                    value = metadata.get(key) or metadata.get(key.lstrip('/'), "")
                    if value:
                        for indicator in pptx_indicators:
                            if indicator.lower() in str(value).lower():
                                metadata_match = True
                                print(f"[PPTX Detection] 메타데이터 매칭: {key}='{value}'")
                                break
                    if metadata_match:
                        break

            # 2. 페이지 크기 분석 (슬라이드 비율 확인)
            if len(reader.pages) > 0:
                page = reader.pages[0]
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)
                aspect_ratio = width / height if height > 0 else 0

                # A4 크기 정확히 확인 (595x842 pt, 오차범위 ±5)
                # A4 가로: 842x595, A4 세로: 595x842
                is_a4_size = (
                    (abs(width - 842) < 5 and abs(height - 595) < 5) or
                    (abs(width - 595) < 5 and abs(height - 842) < 5)
                )

                # 슬라이드 비율 범위
                # 16:9 = 1.78, 4:3 = 1.33, A4 세로 = 0.71, A4 가로 = 1.41
                is_landscape = aspect_ratio > 1.2
                is_slide_ratio = 1.3 <= aspect_ratio <= 1.8

                if is_landscape and is_slide_ratio:
                    print(f"[PPTX Detection] 슬라이드 비율 감지: {aspect_ratio:.2f} ({width:.0f}x{height:.0f})")

                    # A4 가로 문서는 별도 처리 (False Positive 방지)
                    if is_a4_size:
                        print(f"[PPTX Detection] A4 크기 감지 → 메타데이터 필수")
                        # A4는 메타데이터 매칭이 있어야만 PPTX로 판정
                        if metadata_match:
                            print(f"[PPTX Detection] ✓ PPTX 변환 PDF 확정 (A4 + 메타데이터)")
                            return True
                        else:
                            print(f"[PPTX Detection] ✗ 일반 A4 문서 (메타데이터 없음)")
                            return False

                    # 슬라이드 비율 (A4 아님)
                    if metadata_match:
                        print(f"[PPTX Detection] ✓ PPTX 변환 PDF 확정 (메타데이터 + 비율)")
                        return True

                    # 비율만 맞는 경우 (메타데이터 없음, A4 아님)
                    print(f"[PPTX Detection] ✓ PPTX 변환 PDF 추정 (슬라이드 비율)")
                    return True

            # 메타데이터만 매칭되는 경우 (비율은 예외적인 경우 있을 수 있음)
            if metadata_match:
                print(f"[PPTX Detection] ✓ PPTX 변환 PDF 추정 (메타데이터만)")
                return True

            # 둘 다 해당 없음 - 일반 문서
            return False

        except Exception as e:
            print(f"[WARNING] PPTX 변환 PDF 감지 실패: {e}")
            # 오류 시 안전하게 일반 문서로 처리
            return False

    def _extract_text_from_page(self, pdf_path: str, page_num: int) -> str:
        """
        pdfplumber로 텍스트 추출 (Phase 3: 텍스트 전용 페이지)

        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (1-indexed)

        Returns:
            추출된 텍스트
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[page_num - 1]
                text = page.extract_text()

                # 테이블 텍스트도 추가
                tables = page.extract_tables()
                if tables:
                    text += "\n\n[표]\n"
                    for table in tables:
                        for row in table:
                            if row:
                                text += " | ".join([str(cell) if cell else "" for cell in row])
                                text += "\n"

                return text if text else ""

        except Exception as e:
            print(f"[ERROR] 페이지 {page_num} 텍스트 추출 실패: {e}")
            return f"[텍스트 추출 실패: {e}]"

    def _process_pdf_with_hybrid(self,
                                 pdf_path: str,
                                 llm_api_type: str,
                                 llm_base_url: str,
                                 llm_model: str,
                                 llm_api_key: str,
                                 cancel_callback=None,
                                 progress_callback=None) -> List[Chunk]:
        """
        PDF를 Hybrid 모드로 처리 (Phase 3)

        Smart Decision:
        - 표/차트/이미지 페이지 → Vision API
        - 텍스트 전용 페이지 → pdfplumber

        Args:
            pdf_path: PDF 파일 경로
            llm_api_type: LLM API 타입
            llm_base_url: LLM Base URL
            llm_model: LLM 모델명
            llm_api_key: LLM API 키

        Returns:
            Chunk 리스트
        """
        print(f"[PDFChunkingEngine] Hybrid 모드로 PDF 처리: {pdf_path}")

        # 필수 라이브러리 확인
        if convert_from_path is None:
            raise ImportError(
                "pdf2image 라이브러리가 설치되지 않았습니다. "
                "'pip install pdf2image' 실행 후 다시 시도하세요."
            )

        if PdfReader is None:
            raise ImportError(
                "PyPDF2/pypdf 라이브러리가 설치되지 않았습니다. "
                "'pip install pypdf' 실행 후 다시 시도하세요."
            )

        # PDF 파일 존재 확인
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 파일 없음: {pdf_path}")

        # PDF 페이지 수 확인
        try:
            reader = PdfReader(pdf_path)
            page_count = len(reader.pages)
            print(f"[PDFChunkingEngine] 총 {page_count}페이지")
        except Exception as e:
            raise RuntimeError(f"PDF 파일 읽기 실패: {e}")

        # Vision 사용 통계
        vision_used_count = 0
        text_only_count = 0
        chunks = []
        document_id = str(uuid.uuid4())

        # 재시도 설정
        MAX_RETRIES = 3
        RETRYABLE_EXCEPTIONS = (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
        RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]

        for page_num in range(1, page_count + 1):
            # 취소 체크
            if cancel_callback and cancel_callback():
                raise CancelledException(f"업로드가 사용자에 의해 취소되었습니다 (페이지 {page_num}/{page_count})")

            # 진행 상황 업데이트
            progress_pct = (page_num / page_count) * 100
            if progress_callback:
                progress_callback(f"페이지 {page_num}/{page_count} 처리 중...", progress_pct)
            print(f"[PDFChunkingEngine] 페이지 {page_num}/{page_count} 처리 중...")

            # Smart Decision
            decision = self._should_use_vision(pdf_path, page_num)
            use_vision_for_page = decision["use_vision"]
            print(f"  → Vision 사용: {use_vision_for_page} (이유: {decision['reason']})")

            # 페이지 처리
            try:
                if use_vision_for_page:
                    # Hybrid 경로: 텍스트 + Vision 모두 생성
                    vision_used_count += 1

                    # 1. 원본 텍스트 청크 생성
                    text_content = self._extract_text_from_page(pdf_path, page_num)
                    if text_content and text_content.strip():
                        text_chunk = Chunk(
                            id=f"{document_id}_pdf_page_{page_num}_text",
                            content=text_content,
                            chunk_type="pdf_page_text",
                            metadata=ChunkMetadata(
                                document_id=document_id,
                                page_number=page_num,
                                section_title=f"Page {page_num}",
                                chunk_type_weight=1.0
                            )
                        )
                        chunks.append(text_chunk)

                    # 2. Vision 분석 청크 생성
                    # PDF → 이미지 (해당 페이지만)
                    try:
                        kwargs = {
                            "dpi": self.pdf_dpi,
                            "first_page": page_num,
                            "last_page": page_num
                        }
                        if self.poppler_path:
                            kwargs["poppler_path"] = self.poppler_path
                            print(f"[DEBUG] Poppler 경로 전달: {self.poppler_path}")
                        else:
                            print(f"[WARN] Poppler 경로가 None입니다!")

                        print(f"[DEBUG] convert_from_path 호출: pdf_path={pdf_path}, kwargs={kwargs}")
                        images = convert_from_path(pdf_path, **kwargs)
                        print(f"[DEBUG] 이미지 변환 성공: {len(images)}개")
                        image = images[0]
                    except Exception as e:
                        error_msg = str(e)
                        if "poppler" in error_msg.lower():
                            raise RuntimeError(
                                f"PDF 이미지 변환 실패 (Poppler 문제): {e}\n\n"
                                "Poppler를 설치하세요. 설치 가이드: POPPLER_INSTALL_GUIDE.md"
                            )
                        else:
                            raise RuntimeError(f"PDF 이미지 변환 실패: {e}")

                    # 이미지 → Base64
                    buffered = BytesIO()
                    image.save(buffered, format="PNG")
                    image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

                    # Vision 분석 (재시도 로직 포함)
                    retry_count = 0
                    vision_success = False
                    vision_description = None
                    last_vision_exception = None

                    while retry_count < MAX_RETRIES and not vision_success:
                        try:
                            vision_description = self._analyze_page_with_vision(
                                image_base64=image_base64,
                                page_num=page_num,
                                total_pages=page_count,
                                llm_api_type=self.vision_api_type,
                                llm_base_url=self.vision_base_url,
                                llm_api_key=self.vision_api_key,
                                llm_model=self.vision_model
                            )
                            vision_success = True  # 성공

                        except RETRYABLE_EXCEPTIONS as e:
                            last_vision_exception = e
                            retry_count += 1
                            if retry_count < MAX_RETRIES:
                                wait_time = 2 ** retry_count
                                print(f"  [Vision 재시도 {retry_count}/{MAX_RETRIES}] {wait_time}초 후 재시도... (오류: {e})")
                                time.sleep(wait_time)
                                if cancel_callback and cancel_callback():
                                    raise CancelledException(f"업로드가 사용자에 의해 취소되었습니다 (페이지 {page_num} Vision 재시도 중)")

                        except requests.exceptions.HTTPError as e:
                            last_vision_exception = e
                            if hasattr(e, 'response') and e.response is not None:
                                status_code = e.response.status_code
                                if status_code in RETRYABLE_STATUS_CODES:
                                    retry_count += 1
                                    if retry_count < MAX_RETRIES:
                                        wait_time = 2 ** retry_count
                                        print(f"  [Vision 재시도 {retry_count}/{MAX_RETRIES}] HTTP {status_code}, {wait_time}초 후 재시도...")
                                        time.sleep(wait_time)
                                        if cancel_callback and cancel_callback():
                                            raise CancelledException(f"업로드가 사용자에 의해 취소되었습니다 (페이지 {page_num} Vision 재시도 중)")
                                else:
                                    # Non-retryable HTTP error
                                    break
                            else:
                                break

                        except Exception as e:
                            # Non-retryable exception
                            last_vision_exception = e
                            break

                    # Vision 성공 시 Vision 청크 추가
                    if vision_success and vision_description:
                        vision_chunk = Chunk(
                            id=f"{document_id}_pdf_page_{page_num}_vision",
                            content=vision_description,
                            chunk_type="pdf_page_vision",
                            metadata=ChunkMetadata(
                                document_id=document_id,
                                page_number=page_num,
                                section_title=f"Page {page_num} (Vision)",
                                chunk_type_weight=1.5  # Vision 청크는 가중치 높음
                            )
                        )
                        chunks.append(vision_chunk)
                    else:
                        # Vision 실패 → 예외를 발생시켜 fallback으로 이동
                        if last_vision_exception:
                            raise last_vision_exception
                        else:
                            raise RuntimeError("Vision 분석 실패 (알 수 없는 오류)")

                    print(f"[PDFChunkingEngine] 페이지 {page_num} 처리 완료 (Hybrid: text + vision)")
                else:
                    # 텍스트 전용 경로
                    text_only_count += 1
                    text_content = self._extract_text_from_page(pdf_path, page_num)

                    text_chunk = Chunk(
                        id=f"{document_id}_pdf_page_{page_num}_text",
                        content=text_content,
                        chunk_type="pdf_page_text",
                        metadata=ChunkMetadata(
                            document_id=document_id,
                            page_number=page_num,
                            section_title=f"Page {page_num}",
                            chunk_type_weight=1.0
                        )
                    )
                    chunks.append(text_chunk)

                    print(f"[PDFChunkingEngine] 페이지 {page_num} 처리 완료 (text only)")

            except Exception as e:
                print(f"[ERROR] 페이지 {page_num} 처리 실패: {e}")
                print(f"[FALLBACK] 텍스트 추출로 폴백 시도 중...")
                try:
                    # Vision 실패 시 텍스트 추출로 폴백
                    description = self._extract_text_from_page(pdf_path, page_num)
                    chunk_type = "pdf_page_text"
                    text_only_count += 1

                    chunk = Chunk(
                        id=f"{document_id}_pdf_page_{page_num}",
                        content=description,
                        chunk_type=chunk_type,
                        metadata=ChunkMetadata(
                            document_id=document_id,
                            page_number=page_num,
                            section_title=f"Page {page_num}",
                            chunk_type_weight=1.0
                        )
                    )
                    chunks.append(chunk)
                    print(f"[FALLBACK] 페이지 {page_num} 텍스트 추출 완료")
                except Exception as fallback_error:
                    print(f"[ERROR] 페이지 {page_num} 텍스트 폴백도 실패: {fallback_error}")
                    # 완전 실패 → PartialUploadException 발생 (전체 롤백)
                    raise PartialUploadException(
                        f"페이지 {page_num} 처리 완전 실패 (Vision 및 텍스트 추출 모두 실패): 원본 오류={e}, 폴백 오류={fallback_error}",
                        page_num
                    )

        # 통계 출력
        print(f"[PDFChunkingEngine] Hybrid 처리 완료:")
        print(f"  - 총 청크: {len(chunks)}개")
        print(f"  - Vision 사용: {vision_used_count}개 ({vision_used_count/page_count*100:.1f}%)")
        print(f"  - 텍스트 추출: {text_only_count}개 ({text_only_count/page_count*100:.1f}%)")
        if vision_used_count > 0:
            cost_reduction = (text_only_count / page_count) * 100
            print(f"  - 비용 절감: ~{cost_reduction:.1f}%")

        return chunks
