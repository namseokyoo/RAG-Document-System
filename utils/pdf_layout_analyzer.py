"""
PDF Layout-Aware 분석기
PDF의 시각적 레이아웃을 분석하여 구조화된 요소들을 추출
"""
import pdfplumber
import fitz  # PyMuPDF
import re
from typing import List, Dict, Any, Tuple, Optional
import statistics
from dataclasses import dataclass


@dataclass
class FontInfo:
    """폰트 정보를 담는 데이터 클래스"""
    size: float
    is_bold: bool
    family: str = ""


@dataclass
class TextBlock:
    """텍스트 블록 정보"""
    text: str
    font_size: float
    is_bold: bool
    coordinates: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    font_family: str = ""


class PDFLayoutAnalyzer:
    """PDF의 시각적 레이아웃을 분석하는 클래스"""
    
    def __init__(self):
        self.title_font_threshold = 18.0  # 제목으로 간주할 최소 폰트 크기
        self.bold_threshold = 0.7  # 굵기 판별 임계값
        self.min_title_length = 3  # 최소 제목 길이
        self.max_title_length = 50  # 최대 제목 길이
    
    def analyze_page_elements(self, page) -> List[Dict[str, Any]]:
        """페이지의 시각적 요소를 분석하여 구조화된 리스트 반환"""
        elements = []
        
        try:
            # 1. 텍스트 블록과 폰트 정보 추출
            text_blocks = self._extract_text_blocks_with_font(page)
            
            if not text_blocks:
                return elements
            
            # 2. 폰트 크기 통계 계산
            font_stats = self._calculate_font_statistics(text_blocks)
            
            # 3. 요소 유형 분류 및 메타데이터 추출
            for block in text_blocks:
                element_type = self._classify_element_type(block, font_stats)
                text = block.text.strip()
                
                # 기본 요소 정보
                element = {
                    "type": element_type,
                    "content": text,
                    "properties": {
                        "font_size": block.font_size,
                        "is_bold": block.is_bold,
                        "coordinates": block.coordinates,
                        "font_family": block.font_family
                    }
                }
                
                # 추가 메타데이터 추출
                if element_type == "heading":
                    heading_level = self._detect_heading(block, font_stats)
                    if heading_level:
                        element["heading_level"] = heading_level
                
                elif element_type == "caption":
                    caption_info = self._detect_caption(block)
                    if caption_info:
                        element["caption_type"] = caption_info["caption_type"]
                
                elif element_type == "section":
                    section_number = self._detect_section_number(text)
                    if section_number:
                        element["section_number"] = section_number
                
                elements.append(element)
            
            # 4. 테이블 추출
            tables = self._extract_tables(page)
            for table in tables:
                elements.append({
                    "type": "table",
                    "data": table["data"],
                    "properties": {"coordinates": table["coordinates"]}
                })
            
            # 5. 시각적 순서로 정렬
            elements = self._sort_elements_by_position(elements)
            
        except Exception as e:
            print(f"페이지 분석 중 오류 발생: {e}")
            # 폴백: 기본 텍스트 추출
            try:
                basic_text = page.extract_text()
                if basic_text:
                    elements.append({
                        "type": "paragraph",
                        "content": basic_text,
                        "properties": {"font_size": 12.0, "is_bold": False}
                    })
            except:
                pass
        
        return elements
    
    def _extract_text_blocks_with_font(self, page) -> List[TextBlock]:
        """텍스트 블록과 폰트 정보 추출"""
        text_blocks = []
        
        try:
            # pdfplumber 사용 (더 정확한 폰트 정보)
            if hasattr(page, 'chars'):
                # 문자 단위로 폰트 정보 추출
                chars = page.chars
                if chars:
                    # 문자들을 블록으로 그룹화
                    blocks = self._group_chars_into_blocks(chars)
                    for block_chars in blocks:
                        if block_chars:
                            text = ''.join([char['text'] for char in block_chars])
                            if text.strip():
                                font_info = self._extract_font_from_chars(block_chars)
                                coords = self._calculate_block_coordinates(block_chars)
                                
                                text_blocks.append(TextBlock(
                                    text=text,
                                    font_size=font_info.size,
                                    is_bold=font_info.is_bold,
                                    coordinates=coords,
                                    font_family=font_info.family
                                ))
            
            # 폴백: 기본 텍스트 추출
            if not text_blocks:
                basic_text = page.extract_text()
                if basic_text:
                    text_blocks.append(TextBlock(
                        text=basic_text,
                        font_size=12.0,
                        is_bold=False,
                        coordinates=(0, 0, 100, 100)
                    ))
                    
        except Exception as e:
            print(f"텍스트 블록 추출 중 오류: {e}")
            # 최종 폴백
            try:
                basic_text = page.extract_text()
                if basic_text:
                    text_blocks.append(TextBlock(
                        text=basic_text,
                        font_size=12.0,
                        is_bold=False,
                        coordinates=(0, 0, 100, 100)
                    ))
            except:
                pass
        
        return text_blocks
    
    def _group_chars_into_blocks(self, chars) -> List[List[Dict]]:
        """문자들을 블록으로 그룹화"""
        if not chars:
            return []
        
        blocks = []
        current_block = []
        
        for char in chars:
            if not current_block:
                current_block.append(char)
            else:
                # 같은 줄에 있고 폰트가 비슷하면 같은 블록
                last_char = current_block[-1]
                # 폰트 크기 키 확인 (size 또는 fontsize)
                char_size = char.get('size', char.get('fontsize', 12.0))
                last_size = last_char.get('size', last_char.get('fontsize', 12.0))
                
                if (abs(char.get('top', 0) - last_char.get('top', 0)) < 5 and  # 같은 줄
                    abs(char_size - last_size) < 2):  # 비슷한 폰트 크기
                    current_block.append(char)
                else:
                    if current_block:
                        blocks.append(current_block)
                    current_block = [char]
        
        if current_block:
            blocks.append(current_block)
        
        return blocks
    
    def _extract_font_from_chars(self, chars) -> FontInfo:
        """문자들로부터 폰트 정보 추출"""
        if not chars:
            return FontInfo(size=12.0, is_bold=False)
        
        # 가장 빈번한 폰트 크기 사용 (size 또는 fontsize 키 확인)
        font_sizes = [char.get('size', char.get('fontsize', 12.0)) for char in chars]
        most_common_size = max(set(font_sizes), key=font_sizes.count) if font_sizes else 12.0
        
        # 굵기 판별 (문자 속성 기반)
        is_bold = any(char.get('fontname', '').lower().find('bold') != -1 for char in chars)
        
        # 폰트 패밀리
        font_family = chars[0].get('fontname', 'Arial') if chars else 'Arial'
        
        return FontInfo(
            size=most_common_size,
            is_bold=is_bold,
            family=font_family
        )
    
    def _calculate_block_coordinates(self, chars) -> Tuple[float, float, float, float]:
        """블록의 좌표 계산"""
        if not chars:
            return (0, 0, 0, 0)
        
        x1 = min(char['x0'] for char in chars)
        y1 = min(char['top'] for char in chars)
        x2 = max(char['x1'] for char in chars)
        y2 = max(char['bottom'] for char in chars)
        
        return (x1, y1, x2, y2)
    
    def _calculate_font_statistics(self, text_blocks: List[TextBlock]) -> Dict[str, float]:
        """폰트 크기 통계 계산"""
        if not text_blocks:
            return {"mean": 12.0, "std": 0.0, "threshold": 18.0}
        
        font_sizes = [block.font_size for block in text_blocks]
        
        mean_size = statistics.mean(font_sizes)
        std_size = statistics.stdev(font_sizes) if len(font_sizes) > 1 else 0.0
        
        # 제목 임계값: 평균 + 표준편차
        threshold = mean_size + std_size
        
        return {
            "mean": mean_size,
            "std": std_size,
            "threshold": max(threshold, self.title_font_threshold)
        }
    
    def _detect_heading(self, block: TextBlock, font_stats: Dict[str, float]) -> Optional[str]:
        """제목 레벨 감지 (H1, H2, H3)"""
        text = block.text.strip()
        
        if not text or len(text) > 100:  # 너무 긴 텍스트는 제목이 아님
            return None
        
        # 제목 판별 조건
        is_large_font = block.font_size >= self.title_font_threshold
        is_bold = block.is_bold
        is_uppercase = text.isupper() and len(text) > 3
        is_short = len(text) < self.max_title_length
        
        if not (is_large_font or (is_bold and is_short)):
            return None
        
        # 레벨 판별 (폰트 크기 기반)
        avg_font = font_stats.get("median_font_size", 12.0)
        font_ratio = block.font_size / avg_font
        
        if font_ratio >= 2.0 or (font_ratio >= 1.8 and is_uppercase):
            return "H1"
        elif font_ratio >= 1.5 or (font_ratio >= 1.3 and is_bold):
            return "H2"
        elif font_ratio >= 1.2 or (is_bold and is_short):
            return "H3"
        
        return None
    
    def _detect_caption(self, block: TextBlock) -> Optional[Dict[str, str]]:
        """캡션 감지 및 타입 판별 (figure/table)"""
        text = block.text.strip()
        
        if not text or len(text) > 150:  # 캡션은 보통 짧음
            return None
        
        text_lower = text.lower()
        
        # Figure 캡션 패턴
        figure_patterns = [
            r'^fig\.?\s*\d+',
            r'^figure\s+\d+',
            r'^그림\s+\d+',
            r'^그림\s*\.',
        ]
        
        for pattern in figure_patterns:
            if re.search(pattern, text_lower):
                return {"caption_type": "figure", "text": text}
        
        # Table 캡션 패턴
        table_patterns = [
            r'^table\s+\d+',
            r'^tab\.?\s*\d+',
            r'^표\s+\d+',
            r'^표\s*\.',
        ]
        
        for pattern in table_patterns:
            if re.search(pattern, text_lower):
                return {"caption_type": "table", "text": text}
        
        return None
    
    def _detect_section_number(self, text: str) -> Optional[str]:
        """섹션 번호 추출 (1., 1.1, Chapter 1 등)"""
        if not text or len(text) > 100:
            return None
        
        text_stripped = text.strip()
        
        # 패턴 1: 숫자 계층 구조 (1., 1.1, 1.1.1)
        section_patterns = [
            r'^(\d+(?:\.\d+)*)\.',  # 1., 1.1., 2.3.4.
            r'^(\d+(?:\.\d+)+)',     # 1.1, 2.3.4 (마침표 없이)
        ]
        
        for pattern in section_patterns:
            match = re.search(pattern, text_stripped)
            if match:
                return match.group(1)
        
        # 패턴 2: Chapter, Section 등의 키워드
        keyword_patterns = [
            r'^chapter\s+(\d+)',
            r'^section\s+(\d+(?:\.\d+)*)',
            r'^제\s*(\d+)\s*장',
            r'^(\d+)장',
        ]
        
        for pattern in keyword_patterns:
            match = re.search(pattern, text_stripped, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _classify_element_type(self, block: TextBlock, font_stats: Dict[str, float]) -> str:
        """요소 유형 분류 (개선 버전)"""
        text = block.text.strip()
        
        # 빈 텍스트 처리
        if not text:
            return "paragraph"
        
        # 1. 캡션 판별 (우선순위 높음)
        caption_info = self._detect_caption(block)
        if caption_info:
            return "caption"
        
        # 2. 제목 판별
        heading_level = self._detect_heading(block, font_stats)
        if heading_level:
            return "heading"
        
        # 3. 섹션 번호 판별
        section_number = self._detect_section_number(text)
        if section_number:
            return "section"
        
        # 4. 리스트 항목 판별
        if self._is_list_item(text):
            return "list_item"
        
        # 5. 기본은 문단
        return "paragraph"
    
    def _is_title(self, block: TextBlock, font_stats: Dict[str, float], text: str) -> bool:
        """제목 여부 판별"""
        # 길이 체크
        if len(text) < self.min_title_length or len(text) > self.max_title_length:
            return False
        
        # 폰트 크기 체크
        if block.font_size < font_stats["threshold"]:
            return False
        
        # 굵기 체크
        if not block.is_bold:
            return False
        
        # 단어 수 체크 (제목은 보통 짧음)
        word_count = len(text.split())
        if word_count > 10:
            return False
        
        # 제목 패턴 체크
        title_patterns = [
            r'^제?\d+[장절]',  # 제1장, 1절 등
            r'^\d+\.\d*',      # 1.1, 1.2 등
            r'^[A-Z][A-Z\s]+$',  # 대문자 제목
            r'^#{1,6}\s',      # Markdown 헤더
        ]
        
        for pattern in title_patterns:
            if re.match(pattern, text):
                return True
        
        return True
    
    def _is_list_item(self, text: str) -> bool:
        """리스트 항목 여부 판별"""
        list_patterns = [
            r'^[-*•]\s',       # 불릿 포인트
            r'^\d+\.\s',       # 번호 리스트
            r'^[a-z]\.\s',     # 소문자 리스트
            r'^[A-Z]\.\s',     # 대문자 리스트
        ]
        
        for pattern in list_patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _extract_tables(self, page) -> List[Dict[str, Any]]:
        """테이블 추출"""
        tables = []
        
        try:
            # pdfplumber의 테이블 추출 기능 사용
            page_tables = page.extract_tables()
            
            for table in page_tables:
                if table:
                    # 테이블을 Markdown 형식으로 변환
                    markdown_table = self._convert_table_to_markdown(table)
                    
                    tables.append({
                        "data": table,
                        "markdown": markdown_table,
                        "coordinates": (0, 0, 100, 100)  # 기본 좌표
                    })
                    
        except Exception as e:
            print(f"테이블 추출 중 오류: {e}")
        
        return tables
    
    def _convert_table_to_markdown(self, table_data) -> str:
        """테이블 데이터를 Markdown 형식으로 변환"""
        if not table_data:
            return ""
        
        markdown_lines = []
        
        for i, row in enumerate(table_data):
            # None 값을 빈 문자열로 변환
            clean_row = [str(cell) if cell is not None else "" for cell in row]
            
            # Markdown 테이블 행 생성
            markdown_line = "| " + " | ".join(clean_row) + " |"
            markdown_lines.append(markdown_line)
            
            # 첫 번째 행 다음에 구분선 추가
            if i == 0:
                separator = "| " + " | ".join(["---"] * len(clean_row)) + " |"
                markdown_lines.append(separator)
        
        return "\n".join(markdown_lines)
    
    def _sort_elements_by_position(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """요소들을 시각적 순서(y좌표, x좌표)로 정렬"""
        def get_position(element):
            coords = element.get("properties", {}).get("coordinates", (0, 0, 0, 0))
            return (coords[1], coords[0])  # (y, x) 순서로 정렬
        
        return sorted(elements, key=get_position)
