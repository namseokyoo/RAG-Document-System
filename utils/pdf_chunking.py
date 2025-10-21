"""
PDF 고급 청킹을 위한 핵심 데이터 구조
Small-to-Large 아키텍처와 Layout-Aware 분석을 지원
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import uuid
import re


@dataclass
class ChunkMetadata:
    """PDF 청크의 풍부한 메타데이터"""
    document_id: str
    page_number: int
    parent_chunk_id: Optional[str] = None  # Small-to-Large용 부모 청크 ID
    section_title: str = ""  # 이 청크가 속한 섹션 제목
    chunk_type_weight: float = 1.0  # 청크 타입별 가중치 (title=2.0, paragraph=1.0)
    font_size: float = 12.0  # 텍스트의 평균 폰트 크기
    is_bold: bool = False  # 텍스트의 굵기 여부
    coordinates: Optional[tuple] = None  # 페이지 내 (x1, y1, x2, y2) 좌표
    word_count: int = 0  # 단어 수
    char_count: int = 0  # 문자 수
    has_code: bool = False  # 코드 블록 포함 여부
    has_table: bool = False  # 표 포함 여부
    has_list: bool = False  # 리스트 포함 여부
    has_formula: bool = False  # 수식 포함 여부
    language: str = "ko"  # 언어 (ko, en 등)
    created_at: str = field(default_factory=lambda: "")


@dataclass
class Chunk:
    """PDF 청크의 최종 형태"""
    id: str
    content: str
    chunk_type: str  # title, paragraph, table, list, page_summary, list_segment 등
    metadata: ChunkMetadata
    
    def __post_init__(self):
        """초기화 후 메타데이터 자동 계산"""
        if not self.metadata.word_count:
            self.metadata.word_count = len(self.content.split())
        if not self.metadata.char_count:
            self.metadata.char_count = len(self.content)
        if not self.metadata.created_at:
            from datetime import datetime
            self.metadata.created_at = datetime.now().isoformat()
        
        # 내용 기반 특성 자동 감지
        self._detect_content_features()
    
    def _detect_content_features(self):
        """내용을 분석하여 특성 자동 감지"""
        content = self.content
        
        # 코드 블록 감지
        if re.search(r'```[\s\S]*?```|`[^`]+`', content):
            self.metadata.has_code = True
        
        # 표 감지
        if re.search(r'\|.*\|', content):
            self.metadata.has_table = True
        
        # 리스트 감지
        if re.search(r'^\d+\.|^[-*•]', content, re.MULTILINE):
            self.metadata.has_list = True
        
        # 수식 감지
        if re.search(r'[=+\-*/]', content):
            self.metadata.has_formula = True


@dataclass
class Element:
    """PDF 페이지의 구조화된 요소"""
    type: str  # title, paragraph, list_item, table
    content: str
    properties: Dict[str, Any] = field(default_factory=dict)


class ChunkFactory:
    """청크 생성을 위한 팩토리 클래스"""
    
    @staticmethod
    def create_chunk(content: str, chunk_type: str, metadata: ChunkMetadata) -> Chunk:
        """새로운 청크 생성"""
        return Chunk(
            id=str(uuid.uuid4()),
            content=content,
            chunk_type=chunk_type,
            metadata=metadata
        )
    
    @staticmethod
    def create_page_summary_chunk(page_text: str, document_id: str, page_num: int, 
                                 section_title: str = "") -> Chunk:
        """페이지 전체 텍스트를 부모 청크로 생성"""
        page_id = f"{document_id}_page_{page_num}"
        
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=None,  # 최상위 부모
            section_title=section_title,
            chunk_type_weight=1.0
        )
        
        return Chunk(
            id=page_id,
            content=page_text,
            chunk_type="page_summary",
            metadata=metadata
        )
    
    @staticmethod
    def create_title_chunk(title_text: str, document_id: str, page_num: int,
                          parent_id: str, section_title: str, font_size: float = 18.0,
                          is_bold: bool = True) -> Chunk:
        """제목 청크 생성"""
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=2.0,  # 제목은 높은 가중치
            font_size=font_size,
            is_bold=is_bold
        )
        
        return Chunk(
            id=str(uuid.uuid4()),
            content=title_text,
            chunk_type="title",
            metadata=metadata
        )
    
    @staticmethod
    def create_paragraph_chunk(para_text: str, document_id: str, page_num: int,
                             parent_id: str, section_title: str, font_size: float = 12.0) -> Chunk:
        """문단 청크 생성"""
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=1.0,
            font_size=font_size
        )
        
        return Chunk(
            id=str(uuid.uuid4()),
            content=para_text,
            chunk_type="paragraph",
            metadata=metadata
        )
    
    @staticmethod
    def create_list_chunk(list_text: str, document_id: str, page_num: int,
                         parent_id: str, section_title: str, font_size: float = 12.0) -> Chunk:
        """리스트 청크 생성"""
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=1.2,  # 리스트는 약간 높은 가중치
            font_size=font_size
        )
        
        return Chunk(
            id=str(uuid.uuid4()),
            content=list_text,
            chunk_type="list",
            metadata=metadata
        )
    
    @staticmethod
    def create_table_chunk(table_text: str, document_id: str, page_num: int,
                          parent_id: str, section_title: str) -> Chunk:
        """테이블 청크 생성"""
        metadata = ChunkMetadata(
            document_id=document_id,
            page_number=page_num,
            parent_chunk_id=parent_id,
            section_title=section_title,
            chunk_type_weight=1.3,  # 테이블은 약간 높은 가중치
            has_table=True
        )
        
        return Chunk(
            id=str(uuid.uuid4()),
            content=table_text,
            chunk_type="table",
            metadata=metadata
        )


# 청크 타입별 가중치 상수
CHUNK_TYPE_WEIGHTS = {
    "title": 2.0,           # 제목
    "page_summary": 1.0,   # 페이지 요약
    "table": 1.3,          # 표
    "list": 1.2,           # 리스트
    "paragraph": 1.0,      # 일반 문단
    "paragraph_segment": 0.9,  # 분할된 문단
    "list_segment": 1.1,   # 분할된 리스트
    "table_segment": 1.2   # 분할된 표
}
