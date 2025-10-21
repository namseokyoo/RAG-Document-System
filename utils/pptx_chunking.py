"""
PPTX 슬라이드 중심 청킹을 위한 핵심 데이터 구조
Small-to-Large 아키텍처와 불릿 레벨 기반 그룹핑 지원
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import uuid
import re


@dataclass
class PPTXChunkMetadata:
    """PPTX 청크의 풍부한 메타데이터"""
    document_id: str
    slide_number: int
    parent_chunk_id: Optional[str] = None  # Small-to-Large용 부모 청크 ID
    slide_title: str = ""  # 슬라이드 제목 (검색 필터용)
    chunk_type_weight: float = 1.0  # 청크 타입별 가중치
    word_count: int = 0
    char_count: int = 0
    bullet_level: Optional[int] = None  # 불릿 레벨 (0, 1, 2...)
    has_notes: bool = False  # 노트 포함 여부
    has_table: bool = False  # 표 포함 여부
    shape_type: str = "text"  # text, table, chart
    language: str = "ko"
    created_at: str = field(default_factory=lambda: "")


@dataclass
class PPTXChunk:
    """PPTX 청크의 최종 형태"""
    id: str
    content: str
    chunk_type: str  # slide_title, bullet_group, slide_notes, table, slide_summary
    metadata: PPTXChunkMetadata
    
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
        
        # 표 감지
        if re.search(r'\|.*\|', content):
            self.metadata.has_table = True


class PPTXChunkFactory:
    """PPTX 청크 생성을 위한 팩토리 클래스"""
    
    @staticmethod
    def create_chunk(content: str, chunk_type: str, metadata: PPTXChunkMetadata) -> PPTXChunk:
        """새로운 청크 생성"""
        return PPTXChunk(
            id=str(uuid.uuid4()),
            content=content,
            chunk_type=chunk_type,
            metadata=metadata
        )
    
    @staticmethod
    def create_slide_summary_chunk(slide_text: str, document_id: str, slide_num: int,
                                  slide_title: str = "") -> PPTXChunk:
        """슬라이드 전체 텍스트를 부모 청크로 생성"""
        slide_id = f"{document_id}_slide_{slide_num}"
        
        metadata = PPTXChunkMetadata(
            document_id=document_id,
            slide_number=slide_num,
            parent_chunk_id=None,  # 최상위 부모
            slide_title=slide_title,
            chunk_type_weight=0.5  # 직접 검색 확률 낮춤
        )
        
        return PPTXChunk(
            id=slide_id,
            content=slide_text,
            chunk_type="slide_summary",
            metadata=metadata
        )
    
    @staticmethod
    def create_slide_title_chunk(title_text: str, document_id: str, slide_num: int,
                                parent_id: str, slide_title: str = "") -> PPTXChunk:
        """슬라이드 제목 청크 생성"""
        metadata = PPTXChunkMetadata(
            document_id=document_id,
            slide_number=slide_num,
            parent_chunk_id=parent_id,
            slide_title=slide_title or title_text,
            chunk_type_weight=2.0  # 제목은 높은 가중치
        )
        
        return PPTXChunk(
            id=str(uuid.uuid4()),
            content=title_text,
            chunk_type="slide_title",
            metadata=metadata
        )
    
    @staticmethod
    def create_slide_notes_chunk(notes_text: str, document_id: str, slide_num: int,
                                parent_id: str, slide_title: str = "") -> PPTXChunk:
        """슬라이드 노트 청크 생성"""
        metadata = PPTXChunkMetadata(
            document_id=document_id,
            slide_number=slide_num,
            parent_chunk_id=parent_id,
            slide_title=slide_title,
            chunk_type_weight=1.7,  # 노트는 높은 가중치
            has_notes=True
        )
        
        return PPTXChunk(
            id=str(uuid.uuid4()),
            content=notes_text,
            chunk_type="slide_notes",
            metadata=metadata
        )
    
    @staticmethod
    def create_bullet_group_chunk(bullet_text: str, document_id: str, slide_num: int,
                                 parent_id: str, slide_title: str = "",
                                 bullet_level: int = 0) -> PPTXChunk:
        """불릿 그룹 청크 생성"""
        metadata = PPTXChunkMetadata(
            document_id=document_id,
            slide_number=slide_num,
            parent_chunk_id=parent_id,
            slide_title=slide_title,
            chunk_type_weight=1.0,  # 기본 가중치
            bullet_level=bullet_level
        )
        
        return PPTXChunk(
            id=str(uuid.uuid4()),
            content=bullet_text,
            chunk_type="bullet_group",
            metadata=metadata
        )
    
    @staticmethod
    def create_table_chunk(table_text: str, document_id: str, slide_num: int,
                         parent_id: str, slide_title: str = "") -> PPTXChunk:
        """테이블 청크 생성"""
        metadata = PPTXChunkMetadata(
            document_id=document_id,
            slide_number=slide_num,
            parent_chunk_id=parent_id,
            slide_title=slide_title,
            chunk_type_weight=1.2,  # 테이블은 약간 높은 가중치
            has_table=True,
            shape_type="table"
        )
        
        return PPTXChunk(
            id=str(uuid.uuid4()),
            content=table_text,
            chunk_type="table",
            metadata=metadata
        )


# 청크 타입별 가중치 상수
PPTX_CHUNK_TYPE_WEIGHTS = {
    "slide_title": 2.0,        # 제목
    "slide_notes": 1.7,        # 발표자 노트
    "table": 1.2,              # 표
    "bullet_group": 1.0,       # 불릿 그룹
    "slide_summary": 0.5,      # 슬라이드 요약 (컨텍스트용)
    "bullet_group_segment": 0.9  # 분할된 불릿 그룹
}
