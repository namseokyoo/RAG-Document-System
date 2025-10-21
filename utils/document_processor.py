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
                "enable_small_to_large": True,
                "enable_layout_analysis": True
            }
            self.pdf_engine = PDFChunkingEngine(pdf_config)
        else:
            self.pdf_engine = None
        
        # PPTX 고급 청킹 엔진 (활성화 시)
        if self.enable_advanced_pptx_chunking:
            pptx_config = {
                "max_size": 300,  # PPTX는 300자 최적
                "overlap_size": 50,
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
                # 메타데이터 변환
                metadata = {
                    "source": file_path,
                    "file_name": os.path.basename(file_path),
                    "page_number": chunk.metadata.page_number,
                    "chunk_type": chunk.chunk_type,
                    "chunk_type_weight": chunk.metadata.chunk_type_weight,
                    "parent_chunk_id": chunk.metadata.parent_chunk_id,
                    "section_title": chunk.metadata.section_title,
                    "font_size": chunk.metadata.font_size,
                    "is_bold": chunk.metadata.is_bold,
                    "word_count": chunk.metadata.word_count,
                    "char_count": chunk.metadata.char_count,
                    "has_code": chunk.metadata.has_code,
                    "has_table": chunk.metadata.has_table,
                    "has_list": chunk.metadata.has_list,
                    "has_formula": chunk.metadata.has_formula,
                    "language": chunk.metadata.language,
                    "created_at": chunk.metadata.created_at
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
            
            # PPTX 고급 청킹 엔진으로 청크 생성
            chunks = self.pptx_engine.process_pptx_document(file_path)
            
            # PPTXChunk 객체를 LangChain Document로 변환
            documents = []
            for chunk in chunks:
                # 메타데이터 변환
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
                    "created_at": chunk.metadata.created_at
                }
                
                document = Document(
                    page_content=chunk.content,
                    metadata=metadata
                )
                documents.append(document)
            
            print(f"고급 PPTX 청킹 완료: {len(documents)}개 청크 생성")
            return documents
            
        except Exception as e:
            print(f"고급 PPTX 청킹 실패, 기본 방식으로 폴백: {e}")
            import traceback
            traceback.print_exc()
            # 폴백: 기존 방식 사용
            try:
                loader = UnstructuredPowerPointLoader(file_path)
                return loader.load()
            except Exception as fallback_error:
                print(f"기본 PPTX 로드도 실패: {fallback_error}")
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

