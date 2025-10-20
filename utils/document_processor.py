import os
import fitz  # PyMuPDF
from datetime import datetime
from typing import List, Dict, Any
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, UnstructuredPowerPointLoader, UnstructuredExcelLoader

# PDF 압축 해제 한계 증가 설정
try:
    # PyMuPDF 버전에 따라 다른 API 사용
    if hasattr(fitz.TOOLS, 'mupdf_set_subset_fonts'):
        fitz.TOOLS.mupdf_set_subset_fonts(0)  # 폰트 서브셋 비활성화
        fitz.TOOLS.mupdf_set_icc_profile(0)   # ICC 프로필 비활성화
        fitz.TOOLS.mupdf_set_save_compression(0)  # 압축 저장 비활성화
    else:
        # 최신 버전에서는 다른 방식 사용
        fitz.set_option("subset_fonts", 0)
        fitz.set_option("icc_profile", 0)
        fitz.set_option("save_compression", 0)
except Exception as e:
    print(f"PyMuPDF 설정 경고: {e}")
    pass  # 설정 실패해도 계속 진행


class DocumentProcessor:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
    
    def load_document(self, file_path: str, file_type: str) -> List[Document]:
        """파일 타입에 따라 문서 로드"""
        try:
            if file_type == "pdf":
                # PyMuPDF를 사용하여 직접 PDF 로드 (압축 해제 한계 문제 해결)
                documents = self._load_pdf_with_fitz(file_path)
            elif file_type == "pptx":
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

