"""
PPTX 슬라이드 중심 청킹 엔진
Small-to-Large 아키텍처와 paragraph.level 기반 불릿 그룹핑
"""
from typing import List, Dict, Any, Optional
from pptx import Presentation
import uuid
from .pptx_chunking import PPTXChunk, PPTXChunkMetadata, PPTXChunkFactory, PPTX_CHUNK_TYPE_WEIGHTS
from .chunking_fallback import ChunkingFallback


class PPTXChunkingEngine:
    """PPTX 슬라이드 중심 청킹 엔진"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.fallback = ChunkingFallback(config)
        
        # 설정값들
        self.max_size = config.get("max_size", 300)  # PPTX는 300자 최적
        self.overlap_size = config.get("overlap_size", 50)
        self.enable_small_to_large = config.get("enable_small_to_large", True)
    
    def process_pptx_document(self, pptx_path: str) -> List[PPTXChunk]:
        """PPTX 문서를 슬라이드 구조 인식 기반으로 청킹"""
        all_chunks = []
        document_id = str(uuid.uuid4())
        
        try:
            presentation = Presentation(pptx_path)
            
            for slide_index, slide in enumerate(presentation.slides):
                slide_number = slide_index + 1
                print(f"슬라이드 {slide_number} 처리 중...")
                
                # 슬라이드 제목 추출 (메타데이터용)
                slide_title = self._extract_slide_title(slide)
                
                # 1. Large 청크 생성 (슬라이드 전체) - Small-to-Large 아키텍처
                if self.enable_small_to_large:
                    slide_chunk = self._create_slide_summary_chunk(
                        slide, document_id, slide_number, slide_title
                    )
                    all_chunks.append(slide_chunk)
                    parent_id = slide_chunk.id
                else:
                    parent_id = None
                
                # 2. Small 청크 생성
                slide_chunks = self._process_slide_elements(
                    slide, document_id, slide_number, parent_id, slide_title
                )
                all_chunks.extend(slide_chunks)
        
        except Exception as e:
            print(f"PPTX 처리 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"총 {len(all_chunks)}개 청크 생성 완료")
        return all_chunks
    
    def _extract_slide_title(self, slide) -> str:
        """슬라이드 제목 추출"""
        try:
            if slide.shapes.title and hasattr(slide.shapes.title, 'text'):
                title_text = slide.shapes.title.text.strip()
                if title_text:
                    return title_text
        except:
            pass
        return ""
    
    def _create_slide_summary_chunk(self, slide, document_id: str, slide_num: int,
                                   slide_title: str) -> PPTXChunk:
        """슬라이드 전체 텍스트를 부모 청크로 생성"""
        slide_text = self._extract_full_text_from_slide(slide)
        
        return PPTXChunkFactory.create_slide_summary_chunk(
            slide_text=slide_text,
            document_id=document_id,
            slide_num=slide_num,
            slide_title=slide_title
        )
    
    def _extract_full_text_from_slide(self, slide) -> str:
        """슬라이드 내의 모든 보이는 텍스트 추출 (노트 제외)"""
        full_text = []
        
        try:
            # 1. 제목
            if slide.shapes.title and hasattr(slide.shapes.title, 'text'):
                title_text = slide.shapes.title.text.strip()
                if title_text:
                    full_text.append(f"[제목]:\n{title_text}")
            
            # 2. 본문 및 기타 텍스트
            for shape in slide.shapes:
                # 제목 중복 방지
                if shape == slide.shapes.title:
                    continue
                
                # 텍스트 프레임
                if hasattr(shape, 'text_frame') and shape.has_text_frame:
                    text = shape.text_frame.text.strip()
                    if text:
                        full_text.append(f"[본문]:\n{text}")
                
                # 테이블
                if hasattr(shape, 'table') and shape.has_table:
                    table_text = self._convert_table_to_simple_text(shape.table)
                    if table_text:
                        full_text.append(f"[표]:\n{table_text}")
        
        except Exception as e:
            print(f"슬라이드 텍스트 추출 중 오류: {e}")
        
        return "\n\n".join(full_text) if full_text else ""
    
    def _process_slide_elements(self, slide, document_id: str, slide_num: int,
                               parent_id: Optional[str], slide_title: str) -> List[PPTXChunk]:
        """슬라이드 요소들을 Small 청크로 처리"""
        chunks = []
        
        try:
            # 2a. 슬라이드 제목
            title_chunk = self._create_slide_title_chunk(
                slide, document_id, slide_num, parent_id, slide_title
            )
            if title_chunk:
                chunks.append(title_chunk)
            
            # 2b. 슬라이드 노트
            notes_chunks = self._create_slide_notes_chunks(
                slide, document_id, slide_num, parent_id, slide_title
            )
            chunks.extend(notes_chunks)
            
            # 2c. 슬라이드 본문 (도형 순회)
            for shape in slide.shapes:
                # 제목 중복 방지
                if shape == slide.shapes.title:
                    continue
                
                # 텍스트 프레임 (불릿 포인트)
                if hasattr(shape, 'text_frame') and shape.has_text_frame:
                    bullet_chunks = self._chunk_bullet_points_by_level(
                        shape.text_frame, document_id, slide_num, parent_id, slide_title
                    )
                    chunks.extend(bullet_chunks)
                
                # 테이블
                if hasattr(shape, 'table') and shape.has_table:
                    table_chunks = self._chunk_pptx_table(
                        shape.table, document_id, slide_num, parent_id, slide_title
                    )
                    chunks.extend(table_chunks)
        
        except Exception as e:
            print(f"슬라이드 요소 처리 중 오류: {e}")
        
        return chunks
    
    def _create_slide_title_chunk(self, slide, document_id: str, slide_num: int,
                                 parent_id: Optional[str], slide_title: str) -> Optional[PPTXChunk]:
        """슬라이드 제목 청크 생성"""
        try:
            if slide.shapes.title and hasattr(slide.shapes.title, 'text'):
                title_text = slide.shapes.title.text.strip()
                if title_text:
                    return PPTXChunkFactory.create_slide_title_chunk(
                        title_text=title_text,
                        document_id=document_id,
                        slide_num=slide_num,
                        parent_id=parent_id,
                        slide_title=slide_title
                    )
        except Exception as e:
            print(f"제목 청크 생성 중 오류: {e}")
        
        return None
    
    def _create_slide_notes_chunks(self, slide, document_id: str, slide_num: int,
                                  parent_id: Optional[str], slide_title: str) -> List[PPTXChunk]:
        """슬라이드 노트 청크 생성"""
        chunks = []
        
        try:
            if hasattr(slide, 'notes_slide') and slide.notes_slide:
                notes_slide = slide.notes_slide
                if hasattr(notes_slide, 'notes_text_frame'):
                    notes_text = notes_slide.notes_text_frame.text.strip()
                    if notes_text:
                        # 노트가 길 수 있으므로 Fallback 적용
                        from .pdf_chunking import ChunkMetadata
                        
                        base_metadata = ChunkMetadata(
                            document_id=document_id,
                            page_number=slide_num,
                            parent_chunk_id=parent_id,
                            section_title=slide_title,
                            chunk_type_weight=PPTX_CHUNK_TYPE_WEIGHTS.get("slide_notes", 1.7)
                        )
                        
                        fallback_chunks = self.fallback.chunk_element_with_fallback(
                            content=notes_text,
                            element_type="slide_notes",
                            base_metadata=base_metadata
                        )
                        
                        # PDF Chunk를 PPTX Chunk로 변환
                        for chunk in fallback_chunks:
                            pptx_metadata = PPTXChunkMetadata(
                                document_id=document_id,
                                slide_number=slide_num,
                                parent_chunk_id=parent_id,
                                slide_title=slide_title,
                                chunk_type_weight=1.7,
                                has_notes=True
                            )
                            
                            pptx_chunk = PPTXChunk(
                                id=chunk.id,
                                content=chunk.content,
                                chunk_type=chunk.chunk_type,
                                metadata=pptx_metadata
                            )
                            chunks.append(pptx_chunk)
        
        except Exception as e:
            print(f"노트 청크 생성 중 오류: {e}")
        
        return chunks
    
    def _chunk_bullet_points_by_level(self, text_frame, document_id: str, slide_num: int,
                                     parent_id: Optional[str], slide_title: str) -> List[PPTXChunk]:
        """paragraph.level을 사용하여 불릿을 의미론적 그룹으로 묶기"""
        chunks = []
        current_bullet_group_lines = []
        
        try:
            # TextFrame 내의 모든 문단(불릿) 순회
            for paragraph in text_frame.paragraphs:
                para_text = paragraph.text.strip()
                if not para_text:
                    continue
                
                # 들여쓰기 시각화
                indent_level = paragraph.level
                formatted_text = f"{'  ' * indent_level}{para_text}"
                
                # 새 최상위 불릿(level 0)이 시작되고, 버퍼에 내용이 있다면
                if indent_level == 0 and current_bullet_group_lines:
                    # 지금까지 모은 버퍼를 하나의 청크로
                    group_content = "\n".join(current_bullet_group_lines)
                    
                    # Fallback 적용 (너무 크면 분할)
                    from .pdf_chunking import ChunkMetadata
                    
                    base_metadata = ChunkMetadata(
                        document_id=document_id,
                        page_number=slide_num,
                        parent_chunk_id=parent_id,
                        section_title=slide_title,
                        chunk_type_weight=PPTX_CHUNK_TYPE_WEIGHTS.get("bullet_group", 1.0)
                    )
                    
                    fallback_chunks = self.fallback.chunk_element_with_fallback(
                        content=group_content,
                        element_type="bullet_group",
                        base_metadata=base_metadata
                    )
                    
                    # PDF Chunk를 PPTX Chunk로 변환
                    for chunk in fallback_chunks:
                        pptx_metadata = PPTXChunkMetadata(
                            document_id=document_id,
                            slide_number=slide_num,
                            parent_chunk_id=parent_id,
                            slide_title=slide_title,
                            chunk_type_weight=1.0,
                            bullet_level=0
                        )
                        
                        pptx_chunk = PPTXChunk(
                            id=chunk.id,
                            content=chunk.content,
                            chunk_type=chunk.chunk_type,
                            metadata=pptx_metadata
                        )
                        chunks.append(pptx_chunk)
                    
                    # 버퍼 비우고 새 최상위 불릿으로 시작
                    current_bullet_group_lines = [formatted_text]
                else:
                    # 하위 불릿이거나 첫 번째 상위 불릿이면 버퍼에 추가
                    current_bullet_group_lines.append(formatted_text)
            
            # 루프 종료 후, 마지막 불릿 그룹 처리
            if current_bullet_group_lines:
                group_content = "\n".join(current_bullet_group_lines)
                
                from .pdf_chunking import ChunkMetadata
                
                base_metadata = ChunkMetadata(
                    document_id=document_id,
                    page_number=slide_num,
                    parent_chunk_id=parent_id,
                    section_title=slide_title,
                    chunk_type_weight=PPTX_CHUNK_TYPE_WEIGHTS.get("bullet_group", 1.0)
                )
                
                fallback_chunks = self.fallback.chunk_element_with_fallback(
                    content=group_content,
                    element_type="bullet_group",
                    base_metadata=base_metadata
                )
                
                for chunk in fallback_chunks:
                    pptx_metadata = PPTXChunkMetadata(
                        document_id=document_id,
                        slide_number=slide_num,
                        parent_chunk_id=parent_id,
                        slide_title=slide_title,
                        chunk_type_weight=1.0,
                        bullet_level=0
                    )
                    
                    pptx_chunk = PPTXChunk(
                        id=chunk.id,
                        content=chunk.content,
                        chunk_type=chunk.chunk_type,
                        metadata=pptx_metadata
                    )
                    chunks.append(pptx_chunk)
        
        except Exception as e:
            print(f"불릿 포인트 청킹 중 오류: {e}")
        
        return chunks
    
    def _chunk_pptx_table(self, table, document_id: str, slide_num: int,
                         parent_id: Optional[str], slide_title: str) -> List[PPTXChunk]:
        """테이블 청킹"""
        chunks = []
        
        try:
            # 테이블을 Markdown 형식으로 변환
            markdown_table = self._convert_table_to_markdown(table)
            
            if markdown_table:
                from .pdf_chunking import ChunkMetadata
                
                base_metadata = ChunkMetadata(
                    document_id=document_id,
                    page_number=slide_num,
                    parent_chunk_id=parent_id,
                    section_title=slide_title,
                    chunk_type_weight=PPTX_CHUNK_TYPE_WEIGHTS.get("table", 1.2)
                )
                
                fallback_chunks = self.fallback.chunk_element_with_fallback(
                    content=markdown_table,
                    element_type="table",
                    base_metadata=base_metadata
                )
                
                for chunk in fallback_chunks:
                    pptx_metadata = PPTXChunkMetadata(
                        document_id=document_id,
                        slide_number=slide_num,
                        parent_chunk_id=parent_id,
                        slide_title=slide_title,
                        chunk_type_weight=1.2,
                        has_table=True,
                        shape_type="table"
                    )
                    
                    pptx_chunk = PPTXChunk(
                        id=chunk.id,
                        content=chunk.content,
                        chunk_type=chunk.chunk_type,
                        metadata=pptx_metadata
                    )
                    chunks.append(pptx_chunk)
        
        except Exception as e:
            print(f"테이블 청킹 중 오류: {e}")
        
        return chunks
    
    def _convert_table_to_markdown(self, table) -> str:
        """테이블을 Markdown 형식으로 변환"""
        markdown_lines = []
        
        try:
            if len(table.rows) == 0:
                return ""
            
            # 헤더 (첫 번째 행)
            header_cells = [cell.text.strip() for cell in table.rows[0].cells]
            markdown_lines.append(f"| {' | '.join(header_cells)} |")
            markdown_lines.append(f"| {' | '.join(['---'] * len(header_cells))} |")
            
            # 본문 (나머지 행)
            for row in table.rows[1:]:
                body_cells = [cell.text.strip() for cell in row.cells]
                markdown_lines.append(f"| {' | '.join(body_cells)} |")
            
            return "\n".join(markdown_lines)
        
        except Exception as e:
            print(f"테이블 변환 중 오류: {e}")
            return ""
    
    def _convert_table_to_simple_text(self, table) -> str:
        """테이블을 단순 텍스트로 변환"""
        text_lines = []
        
        try:
            for row in table.rows:
                row_text = " | ".join([cell.text.strip() for cell in row.cells])
                if row_text:
                    text_lines.append(row_text)
            
            return "\n".join(text_lines)
        
        except Exception as e:
            print(f"테이블 텍스트 변환 중 오류: {e}")
            return ""
    
    def get_chunk_statistics(self, chunks: List[PPTXChunk]) -> Dict[str, Any]:
        """청크 통계 정보 반환"""
        if not chunks:
            return {}
        
        stats = {
            "total_chunks": len(chunks),
            "chunk_types": {},
            "avg_word_count": 0,
            "avg_char_count": 0,
            "slides_covered": set(),
            "slides_with_notes": 0
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
            
            # 슬라이드 정보
            stats["slides_covered"].add(chunk.metadata.slide_number)
            if chunk.metadata.has_notes:
                stats["slides_with_notes"] += 1
        
        stats["avg_word_count"] = total_words / len(chunks)
        stats["avg_char_count"] = total_chars / len(chunks)
        stats["slides_covered"] = len(stats["slides_covered"])
        
        return stats
