#!/usr/bin/env python
"""임베딩된 문서 상세 목록 확인"""
import sys
import os

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

from config import ConfigManager
from utils.vector_store import VectorStoreManager

def list_documents():
    print("=" * 80)
    print("임베딩된 문서 상세 목록")
    print("=" * 80)
    
    # 설정 로드
    config = ConfigManager().get_all()
    
    # Vector Store 초기화
    print(f"\n[Vector Store 초기화 중...]")
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url"),
        embedding_model=config.get("embedding_model"),
    )
    
    # 문서 목록 조회
    docs = vector_manager.get_documents_list()
    
    if not docs:
        print("\n⚠️  임베딩된 문서가 없습니다.")
        return
    
    print(f"\n총 {len(docs)}개 문서 임베딩됨\n")
    
    # 상세 정보 조회
    collection = vector_manager.vectorstore._collection
    
    for i, doc_summary in enumerate(docs, 1):
        print("-" * 80)
        print(f"문서 {i}: {doc_summary['file_name']}")
        print("-" * 80)
        print(f"  타입: {doc_summary['file_type']}")
        print(f"  업로드 시간: {doc_summary['upload_time']}")
        print(f"  청크 수: {doc_summary['chunk_count']}개")
        
        # 원본 파일 경로 확인
        try:
            data = collection.get(
                where={"file_name": doc_summary['file_name']}, 
                include=["metadatas"],
                limit=1
            )
            metas = data.get("metadatas") or []
            if metas:
                file_path = metas[0].get("file_path", "Unknown")
                print(f"  원본 경로: {file_path}")
                
                # 파일 존재 여부 확인
                if os.path.exists(file_path):
                    print(f"  상태: ✓ 파일 존재")
                    file_size = os.path.getsize(file_path)
                    print(f"  크기: {file_size:,} bytes ({file_size/1024:.2f} KB)")
                else:
                    print(f"  상태: ⚠️  파일 없음 (삭제됨 또는 이동됨)")
        except Exception as e:
            print(f"  원본 경로: 확인 불가 ({e})")
        
        print()
    
    print("=" * 80)

if __name__ == "__main__":
    list_documents()

