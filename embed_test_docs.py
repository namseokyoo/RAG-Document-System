#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""테스트 문서 임베딩"""
import sys
import os
from pathlib import Path

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ensure project root on sys.path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from datetime import datetime

def embed_test_documents():
    """테스트 문서 임베딩"""
    print("=" * 80)
    print("테스트 문서 임베딩")
    print("=" * 80)
    
    # 설정 로드
    config = ConfigManager().get_all()
    
    # DocumentProcessor 초기화
    doc_processor = DocumentProcessor(
        chunk_size=config.get("chunk_size", 1500),
        chunk_overlap=config.get("chunk_overlap", 400),
    )
    
    # VectorStoreManager 초기화
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "request"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
        embedding_api_key=config.get("embedding_api_key", "")
    )
    
    # 테스트 문서 목록
    test_docs_dir = Path("data/test_documents")
    pdf_files = list(test_docs_dir.glob("*.pdf"))
    
    print(f"\n임베딩할 문서: {len(pdf_files)}개\n")
    
    total_chunks = 0
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] {pdf_file.name}")
        print("-" * 80)
        
        try:
            # 문서 처리
            chunks = doc_processor.process_document(
                file_path=str(pdf_file),
                file_name=pdf_file.name,
                file_type="pdf"
            )
            
            print(f"  청크 생성: {len(chunks)}개")
            
            # 벡터 스토어에 추가
            vector_manager.add_documents(chunks)
            print(f"  ✓ 임베딩 완료")
            
            total_chunks += len(chunks)
            
        except Exception as e:
            print(f"  ✗ 오류: {e}")
        
        print()
    
    print("=" * 80)
    print(f"총 {total_chunks}개 청크 임베딩 완료")
    print("=" * 80)

if __name__ == "__main__":
    embed_test_documents()

