"""
청킹 Fallback 메커니즘
의미론적 청킹 실패 시 강제 분할을 수행하는 시스템
"""
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
import uuid
from .pdf_chunking import Chunk, ChunkMetadata, ChunkFactory


class ChunkingFallback:
    """의미론적 청킹 실패 시 Fallback 처리"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_size = config.get("max_size", 500)
        self.overlap_size = config.get("overlap_size", 100)
        
        # 상용 서비스 수준의 최소 청크 길이 설정
        self.min_chunk_size = config.get("min_chunk_size", 50)  # 최소 50자
        self.min_word_count = config.get("min_word_count", 5)    # 최소 5단어
        
        # RecursiveCharacterTextSplitter 초기화
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.max_size,
            chunk_overlap=self.overlap_size,
            separators=["\n\n", "\n", ". ", " ", ""]  # 문단 → 문장 → 단어 순으로 분할
        )
    
    def chunk_element_with_fallback(self, content: str, element_type: str, 
                                  base_metadata: ChunkMetadata) -> List[Chunk]:
        """요소가 max_size를 초과할 경우 Fallback 적용 (상용 서비스 수준 개선)"""
        chunks = []
        
        # 1. 내용 검증: 빈 내용 또는 의미 없는 내용 필터링
        if not self._is_valid_content(content):
            return chunks  # 빈 리스트 반환
        
        if len(content) <= self.max_size:
            # 단일 청크로 충분하지만 최소 길이 검증
            if self._meets_minimum_requirements(content):
                chunk = ChunkFactory.create_chunk(
                    content=content,
                    chunk_type=element_type,
                    metadata=base_metadata
                )
                chunks.append(chunk)
        else:
            # Fallback: 강제 분할 (문장 단위 우선)
            # 먼저 문장 단위로 시도
            if self._should_use_sentence_chunking(content):
                sub_contents = self._split_by_sentences_smart(content)
            else:
                # 일반 텍스트 분할
                sub_contents = self.text_splitter.split_text(content)
            
            # 분할된 청크들을 병합하여 최소 길이 확보
            merged_contents = self._merge_short_chunks(sub_contents)
            
            for i, sub_content in enumerate(merged_contents):
                # 최소 길이 요구사항 검증
                if not self._meets_minimum_requirements(sub_content):
                    continue  # 짧은 청크는 스킵
                
                # 원본 타입을 유지하되, 분할되었음을 명시
                chunk_type = f"{element_type}_segment"
                
                # 메타데이터 복사 및 수정
                segment_metadata = ChunkMetadata(
                    document_id=base_metadata.document_id,
                    page_number=base_metadata.page_number,
                    parent_chunk_id=base_metadata.parent_chunk_id,
                    section_title=base_metadata.section_title,
                    chunk_type_weight=base_metadata.chunk_type_weight * 0.9,  # 분할된 청크는 약간 낮은 가중치
                    font_size=base_metadata.font_size,
                    is_bold=base_metadata.is_bold,
                    coordinates=base_metadata.coordinates,
                    word_count=len(sub_content.split()),
                    char_count=len(sub_content),
                    has_code=base_metadata.has_code,
                    has_table=base_metadata.has_table,
                    has_list=base_metadata.has_list,
                    has_formula=base_metadata.has_formula,
                    language=base_metadata.language
                )
                
                chunk = Chunk(
                    id=str(uuid.uuid4()),
                    content=sub_content,
                    chunk_type=chunk_type,
                    metadata=segment_metadata
                )
                chunks.append(chunk)
        
        return chunks
    
    def chunk_table_with_fallback(self, table_data: List[List[str]], 
                                base_metadata: ChunkMetadata) -> List[Chunk]:
        """테이블 데이터를 Fallback으로 청킹"""
        chunks = []
        
        # 테이블을 텍스트로 변환
        table_text = self._convert_table_to_text(table_data)
        
        # Fallback 적용
        table_chunks = self.chunk_element_with_fallback(
            content=table_text,
            element_type="table",
            base_metadata=base_metadata
        )
        
        chunks.extend(table_chunks)
        return chunks
    
    def chunk_list_with_fallback(self, list_items: List[str], 
                               base_metadata: ChunkMetadata) -> List[Chunk]:
        """리스트 항목들을 Fallback으로 청킹"""
        chunks = []
        
        # 리스트를 텍스트로 결합
        list_text = "\n".join(list_items)
        
        # Fallback 적용
        list_chunks = self.chunk_element_with_fallback(
            content=list_text,
            element_type="list",
            base_metadata=base_metadata
        )
        
        chunks.extend(list_chunks)
        return chunks
    
    def _convert_table_to_text(self, table_data: List[List[str]]) -> str:
        """테이블 데이터를 읽기 쉬운 텍스트로 변환"""
        if not table_data:
            return ""
        
        text_lines = []
        
        for i, row in enumerate(table_data):
            # None 값을 빈 문자열로 변환
            clean_row = [str(cell) if cell is not None else "" for cell in row]
            
            if i == 0:
                # 헤더 행
                text_lines.append("표 헤더: " + " | ".join(clean_row))
            else:
                # 데이터 행
                text_lines.append("행 " + str(i) + ": " + " | ".join(clean_row))
        
        return "\n".join(text_lines)
    
    def smart_chunk_by_sentences(self, content: str, element_type: str,
                               base_metadata: ChunkMetadata) -> List[Chunk]:
        """문장 단위로 스마트 청킹"""
        chunks = []
        
        # 문장으로 분할
        sentences = self._split_into_sentences(content)
        
        current_chunk = ""
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            if current_size + sentence_size <= self.max_size:
                # 현재 청크에 문장 추가
                current_chunk += sentence + " "
                current_size += sentence_size + 1
            else:
                # 현재 청크 완성
                if current_chunk.strip():
                    chunk = ChunkFactory.create_chunk(
                        content=current_chunk.strip(),
                        chunk_type=element_type,
                        metadata=base_metadata
                    )
                    chunks.append(chunk)
                
                # 새 청크 시작
                current_chunk = sentence + " "
                current_size = sentence_size + 1
        
        # 마지막 청크 처리
        if current_chunk.strip():
            chunk = ChunkFactory.create_chunk(
                content=current_chunk.strip(),
                chunk_type=element_type,
                metadata=base_metadata
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """텍스트를 문장으로 분할"""
        import re
        
        # 문장 끝 패턴
        sentence_endings = r'[.!?]\s+'
        sentences = re.split(sentence_endings, text)
        
        # 빈 문장 제거 및 정리
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def _is_valid_content(self, content: str) -> bool:
        """내용이 유효한지 검증 (상용 서비스 수준 필터링)"""
        if not content or not content.strip():
            return False
        
        # 의미 없는 단일 문자/구두점만 있는 경우 제외
        cleaned = content.strip()
        if len(cleaned) == 1:
            # 단일 문자가 알파벳/숫자가 아니면 제외 (구두점, 괄호 등)
            if not cleaned.isalnum():
                return False
        
        # 구두점/공백만 있는 경우 제외
        if not any(c.isalnum() for c in cleaned):
            return False
        
        return True
    
    def _meets_minimum_requirements(self, content: str) -> bool:
        """최소 길이 및 단어 수 요구사항 충족 여부"""
        if not content or not content.strip():
            return False
        
        # 최소 문자 수 검증
        if len(content.strip()) < self.min_chunk_size:
            return False
        
        # 최소 단어 수 검증
        word_count = len(content.strip().split())
        if word_count < self.min_word_count:
            return False
        
        return True
    
    def _should_use_sentence_chunking(self, content: str) -> bool:
        """문장 단위 청킹을 사용해야 하는지 판단"""
        # 문장 끝 패턴이 충분히 있는 경우 문장 단위 청킹 사용
        import re
        sentence_endings = re.findall(r'[.!?]\s+', content)
        return len(sentence_endings) >= 2  # 최소 2개 문장 이상
    
    def _split_by_sentences_smart(self, content: str) -> List[str]:
        """문장 단위로 스마트 분할 (상용 서비스 수준)"""
        sentences = self._split_into_sentences(content)
        
        chunks = []
        current_chunk = ""
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # 현재 청크에 문장 추가 가능한지 확인
            if current_size + sentence_size <= self.max_size:
                current_chunk += sentence + ". "
                current_size += sentence_size + 2
            else:
                # 현재 청크 완성
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                
                # 새 청크 시작
                current_chunk = sentence + ". "
                current_size = sentence_size + 2
        
        # 마지막 청크 처리
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _merge_short_chunks(self, chunks: List[str]) -> List[str]:
        """짧은 청크들을 병합하여 최소 길이 확보 (상용 서비스 수준)"""
        if not chunks:
            return []
        
        merged = []
        current_chunk = ""
        
        for chunk in chunks:
            chunk_stripped = chunk.strip()
            
            # 현재 청크가 최소 길이 미만이면 병합 시도
            if len(current_chunk) < self.min_chunk_size:
                if current_chunk:
                    current_chunk += " " + chunk_stripped
                else:
                    current_chunk = chunk_stripped
            else:
                # 현재 청크가 충분히 길면 완성
                merged.append(current_chunk)
                current_chunk = chunk_stripped
        
        # 마지막 청크 처리
        if current_chunk:
            # 최소 길이를 충족하지 못하면 이전 청크에 병합
            if len(current_chunk) < self.min_chunk_size and merged:
                merged[-1] += " " + current_chunk
            else:
                merged.append(current_chunk)
        
        return merged
