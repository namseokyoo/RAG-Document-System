import os
from datetime import datetime
from typing import List, Dict, Any
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, UnstructuredPowerPointLoader, UnstructuredExcelLoader


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
                loader = PyPDFLoader(file_path)
            elif file_type == "pptx":
                loader = UnstructuredPowerPointLoader(file_path)
            elif file_type in ["xlsx", "xls"]:
                loader = UnstructuredExcelLoader(file_path)
            else:
                raise ValueError(f"지원하지 않는 파일 형식: {file_type}")
            
            documents = loader.load()
            return documents
        except Exception as e:
            raise Exception(f"문서 로드 실패 ({file_path}): {str(e)}")
    
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

