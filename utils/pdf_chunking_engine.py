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
