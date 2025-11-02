import os
import fitz  # PyMuPDF
from datetime import datetime
from typing import List, Dict, Any
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, UnstructuredPowerPointLoader, UnstructuredExcelLoader

# PDF 고급 청킹 모듈들
from .pdf_chunking_engine import PDFChunkingEngine
from .pdf_chunking import Chunk, ChunkFactory

# PPTX 고급 청킹 모듈들
from .pptx_chunking_engine import PPTXChunkingEngine
from .pptx_chunking import PPTXChunk, PPTXChunkFactory

# PDF 로딩 안정화를 위한 선택적 설정 (지원되지 않으면 조용히 건너뜀)
try:
    if hasattr(fitz, "TOOLS") and hasattr(fitz.TOOLS, "mupdf_set_subset_fonts"):
        fitz.TOOLS.mupdf_set_subset_fonts(0)
        if hasattr(fitz.TOOLS, "mupdf_set_icc_profile"):
            fitz.TOOLS.mupdf_set_icc_profile(0)
        if hasattr(fitz.TOOLS, "mupdf_set_save_compression"):
            fitz.TOOLS.mupdf_set_save_compression(0)
except Exception:
    pass  # 지원되지 않는 환경은 조용히 통과


class DocumentProcessor:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, 
                 enable_advanced_pdf_chunking: bool = True,
                 enable_advanced_pptx_chunking: bool = True):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.enable_advanced_pdf_chunking = enable_advanced_pdf_chunking
        self.enable_advanced_pptx_chunking = enable_advanced_pptx_chunking
        
        # 기본 텍스트 분할기
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        
        # PDF 고급 청킹 엔진 (활성화 시)
        if self.enable_advanced_pdf_chunking:
            pdf_config = {
                "max_size": chunk_size,
                "overlap_size": chunk_overlap,
                "min_chunk_size": 50,  # 상용 서비스 수준: 최소 50자
                "min_word_count": 5,   # 상용 서비스 수준: 최소 5단어
                "enable_small_to_large": True,
                "enable_layout_analysis": True
            }
            self.pdf_engine = PDFChunkingEngine(pdf_config)
        else:
            self.pdf_engine = None
        
        # PPTX 고급 청킹 엔진 (활성화 시)
        if self.enable_advanced_pptx_chunking:
            # PPTX는 일반적으로 PDF보다 작은 청크가 적합하므로 비율 적용
            # 하지만 사용자 설정값도 고려하여 유연하게 설정
            pptx_max_size = min(chunk_size, int(chunk_size * 0.3)) if chunk_size > 500 else 300
            pptx_overlap = min(chunk_overlap, int(chunk_overlap * 0.25)) if chunk_overlap > 50 else 50
            
            pptx_config = {
                "max_size": max(200, pptx_max_size),  # 최소 200자 보장
                "overlap_size": max(30, pptx_overlap),  # 최소 30자 오버랩 보장
                "enable_small_to_large": True
            }
            self.pptx_engine = PPTXChunkingEngine(pptx_config)
        else:
            self.pptx_engine = None
    
    def load_document(self, file_path: str, file_type: str) -> List[Document]:
        """파일 타입에 따라 문서 로드"""
        try:
            if file_type == "pdf":
                if self.enable_advanced_pdf_chunking and self.pdf_engine:
                    # 고급 PDF 청킹 사용
                    documents = self._load_pdf_with_advanced_chunking(file_path)
                else:
                    # 기존 방식 사용
                    documents = self._load_pdf_with_fitz(file_path)
            elif file_type == "pptx":
                if self.enable_advanced_pptx_chunking and self.pptx_engine:
                    # 고급 PPTX 청킹 사용
                    documents = self._load_pptx_with_advanced_chunking(file_path)
                else:
                    # 기존 방식 사용
                    loader = UnstructuredPowerPointLoader(file_path)
                    documents = loader.load()
            elif file_type in ["xlsx", "xls"]:
                loader = UnstructuredExcelLoader(file_path)
                documents = loader.load()
            elif file_type == "txt":
                # 텍스트 파일 직접 로드
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                documents = [Document(page_content=content, metadata={"source": file_path})]
            else:
                raise ValueError(f"지원하지 않는 파일 형식: {file_type}")
            
            return documents
        except Exception as e:
            raise Exception(f"문서 로드 실패 ({file_path}): {str(e)}")
    
    def _load_pdf_with_advanced_chunking(self, file_path: str) -> List[Document]:
        """고급 PDF 청킹을 사용하여 PDF 로드"""
        try:
            print(f"고급 PDF 청킹으로 처리 중: {file_path}")
            
            # PDF 고급 청킹 엔진으로 청크 생성
            chunks = self.pdf_engine.process_pdf_document(file_path)
            
            # Chunk 객체를 LangChain Document로 변환
            documents = []
            for chunk in chunks:
                # 빈 텍스트 청크 필터링
                if not chunk.content or not chunk.content.strip():
                    continue
                
                # 메타데이터 변환
                metadata = {
                    "source": file_path,
                    "file_name": os.path.basename(file_path),
                    "page_number": chunk.metadata.page_number,
                    "chunk_id": chunk.id,
                    "chunk_type": chunk.chunk_type,
                    "chunk_type_weight": chunk.metadata.chunk_type_weight,
                    "parent_chunk_id": chunk.metadata.parent_chunk_id,
                    "section_title": chunk.metadata.section_title,
                    # Phase 3 구조 메타데이터
                    "heading_level": getattr(chunk.metadata, "heading_level", None),
                    "caption_type": getattr(chunk.metadata, "caption_type", None),
                    "section_number": getattr(chunk.metadata, "section_number", None),
                    "font_size": chunk.metadata.font_size,
                    "is_bold": chunk.metadata.is_bold,
                    "word_count": chunk.metadata.word_count,
                    "char_count": chunk.metadata.char_count,
                    "has_code": chunk.metadata.has_code,
                    "has_table": chunk.metadata.has_table,
                    "has_list": chunk.metadata.has_list,
                    "has_formula": chunk.metadata.has_formula,
                    "language": chunk.metadata.language,
                    "created_at": chunk.metadata.created_at,
                    # Phase 1-3: 표 구조화 메타데이터 (None 값은 저장하지 않음)
                    "table_id": getattr(chunk.metadata, "table_id", None) or None,
                    "table_title": getattr(chunk.metadata, "table_title", None) or None,
                    "row_index": getattr(chunk.metadata, "row_index", None),
                    "col_index": getattr(chunk.metadata, "col_index", None),
                    "cell_reference": getattr(chunk.metadata, "cell_reference", None) or None,
                    "header_row": (",".join(getattr(chunk.metadata, "header_row", [])) if getattr(chunk.metadata, "header_row", []) and len(getattr(chunk.metadata, "header_row", [])) > 0 else None),  # ChromaDB는 리스트 미지원
                    "is_header_row": getattr(chunk.metadata, "is_header_row", False),
                    "item_number": getattr(chunk.metadata, "item_number", None) or None,
                    "data_type": getattr(chunk.metadata, "data_type", None) or None,
                    "table_row_count": getattr(chunk.metadata, "table_row_count", None),
                    "table_col_count": getattr(chunk.metadata, "table_col_count", None)
                }
                
                # 좌표 정보가 있으면 추가
                if chunk.metadata.coordinates:
                    metadata["coordinates"] = chunk.metadata.coordinates
                
                document = Document(
                    page_content=chunk.content,
                    metadata=metadata
                )
                documents.append(document)
            
            print(f"고급 청킹 완료: {len(documents)}개 청크 생성")
            return documents
            
        except Exception as e:
            print(f"고급 PDF 청킹 실패, 기본 방식으로 폴백: {e}")
            # 폴백: 기존 방식 사용
            return self._load_pdf_with_fitz(file_path)
    
    def _load_pptx_with_advanced_chunking(self, file_path: str) -> List[Document]:
        """고급 PPTX 청킹을 사용하여 PPTX 로드"""
        try:
            print(f"고급 PPTX 청킹으로 처리 중: {file_path}")
            
            # Vision 설정을 runtime에 로드 (최신 설정 반영)
            from config import ConfigManager
            config = ConfigManager().get_all()
            enable_vision = config.get("enable_vision_chunking", False)
            llm_api_type = config.get("llm_api_type", "request")
            llm_base_url = config.get("llm_base_url", "http://localhost:11434")
            llm_model = config.get("llm_model", "gpt-4o")
            llm_api_key = config.get("llm_api_key", "")
            
            if enable_vision:
                print(f"  ✓ Vision 청킹 활성화: {llm_model}")
            
            # PPTX 고급 청킹 엔진으로 청크 생성 (Vision 설정 전달)
            chunks = self.pptx_engine.process_pptx_document(
                file_path,
                enable_vision=enable_vision,
                llm_api_type=llm_api_type,
                llm_base_url=llm_base_url,
                llm_model=llm_model,
                llm_api_key=llm_api_key
            )
            
            # PPTXChunk 객체를 LangChain Document로 변환
            documents = []
            for chunk in chunks:
                # 빈 텍스트 청크 필터링
                if not chunk.content or not chunk.content.strip():
                    continue
                
                # 메타데이터 변환 (Phase 1-3: 표 구조화 메타데이터 포함)
                metadata = {
                    "source": file_path,
                    "file_name": os.path.basename(file_path),
                    "slide_number": chunk.metadata.slide_number,
                    "chunk_type": chunk.chunk_type,
                    "chunk_type_weight": chunk.metadata.chunk_type_weight,
                    "parent_chunk_id": chunk.metadata.parent_chunk_id,
                    "slide_title": chunk.metadata.slide_title,
                    "word_count": chunk.metadata.word_count,
                    "char_count": chunk.metadata.char_count,
                    "bullet_level": chunk.metadata.bullet_level,
                    "has_notes": chunk.metadata.has_notes,
                    "has_table": chunk.metadata.has_table,
                    "shape_type": chunk.metadata.shape_type,
                    "language": chunk.metadata.language,
                    "created_at": chunk.metadata.created_at,
                    # Vision 청킹 사용 여부
                    "enable_vision_chunking": enable_vision if enable_vision else False,
                    # Phase 1-3: 표 구조화 메타데이터 (None 값은 저장하지 않음)
                    "table_id": chunk.metadata.table_id if chunk.metadata.table_id else None,
                    "table_title": chunk.metadata.table_title if chunk.metadata.table_title else None,
                    "row_index": chunk.metadata.row_index if chunk.metadata.row_index is not None else None,
                    "col_index": chunk.metadata.col_index if chunk.metadata.col_index is not None else None,
                    "cell_reference": chunk.metadata.cell_reference if chunk.metadata.cell_reference else None,
                    "header_row": ",".join(chunk.metadata.header_row) if chunk.metadata.header_row and len(chunk.metadata.header_row) > 0 else None,  # ChromaDB는 리스트 미지원
                    "is_header_row": chunk.metadata.is_header_row if chunk.metadata.is_header_row else False,
                    "item_number": chunk.metadata.item_number if chunk.metadata.item_number else None,
                    "data_type": chunk.metadata.data_type if chunk.metadata.data_type else None,
                    "table_row_count": chunk.metadata.table_row_count if chunk.metadata.table_row_count is not None else None,
                    "table_col_count": chunk.metadata.table_col_count if chunk.metadata.table_col_count is not None else None
                }
                
                document = Document(
                    page_content=chunk.content,
                    metadata=metadata
                )
                documents.append(document)
            
            print(f"고급 PPTX 청킹 완료: {len(documents)}개 청크 생성")
            
            # 빈 결과인 경우 폴백 (에러 발생했을 수 있음)
            if not documents:
                print("청크가 생성되지 않았습니다. 기본 방식으로 폴백합니다.")
                loader = UnstructuredPowerPointLoader(file_path)
                documents = loader.load()
                print(f"기본 PPTX 로드 완료: {len(documents)}개 문서")
            
            return documents
            
        except Exception as e:
            print(f"고급 PPTX 청킹 실패, 기본 방식으로 폴백: {e}")
            import traceback
            traceback.print_exc()
            # 폴백: 기본 UnstructuredPowerPointLoader 사용
            try:
                print(f"기본 PPTX 로더로 재시도 중...")
                loader = UnstructuredPowerPointLoader(file_path)
                documents = loader.load()
                print(f"기본 PPTX 로드 완료: {len(documents)}개 문서")
                return documents
            except Exception as fallback_error:
                print(f"기본 PPTX 로드도 실패: {fallback_error}")
                import traceback
                traceback.print_exc()
                return []
    
    def _load_pdf_with_fitz(self, file_path: str) -> List[Document]:
        """PyMuPDF를 사용하여 PDF 로드 (압축 해제 한계 문제 해결)"""
        try:
            doc = fitz.open(file_path)
            documents = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                
                if text.strip():  # 빈 페이지 제외
                    metadata = {
                        "source": file_path,
                        "page": page_num + 1,
                        "total_pages": doc.page_count
                    }
                    documents.append(Document(page_content=text, metadata=metadata))
            
            doc.close()
            return documents
        except Exception as e:
            raise Exception(f"PyMuPDF PDF 로드 실패: {str(e)}")
    
    def process_document(self, file_path: str, file_name: str, file_type: str) -> List[Document]:
        """문서를 로드하고 청크로 분할하며 메타데이터 추가"""
        # 문서 로드
        documents = self.load_document(file_path, file_type)
        
        # 업로드 시간
        upload_time = datetime.now().isoformat()
        
        # 각 문서에 메타데이터 추가
        for i, doc in enumerate(documents):
            if doc.metadata is None:
                doc.metadata = {}
            
            doc.metadata.update({
                "file_name": file_name,
                "file_type": file_type,
                "file_path": file_path,
                "upload_time": upload_time,
                "page_number": doc.metadata.get("page", i + 1),
            })
        
        # 청크로 분할
        chunks = self.text_splitter.split_documents(documents)
        
        # 청크 인덱스 추가
        for idx, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = idx
            chunk.metadata["total_chunks"] = len(chunks)
        
        return chunks
    
    def get_file_type(self, file_name: str) -> str:
        """파일 확장자에서 타입 추출"""
        ext = os.path.splitext(file_name)[1].lower()
        if ext == ".pdf":
            return "pdf"
        elif ext == ".pptx":
            return "pptx"
        elif ext in [".xlsx", ".xls"]:
            return "xlsx"
        else:
            return ext[1:] if ext else "unknown"

