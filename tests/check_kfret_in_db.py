"""ChromaDB에서 kFRET 관련 청크 검색"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.vector_store import VectorStoreManager

def check_kfret():
    """kFRET 관련 청크 확인"""
    print("=" * 80)
    print("ChromaDB에서 'kFRET' 또는 'FRET' 검색")
    print("=" * 80)

    config = ConfigManager().get_all()

    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    collection = vector_manager.vectorstore._collection
    all_docs = collection.get()

    print(f"\n[INFO] 전체 청크 개수: {len(all_docs['ids'])}")

    # kFRET 검색
    kfret_chunks = []
    fret_chunks = []

    for i, (doc_id, document, metadata) in enumerate(zip(all_docs['ids'], all_docs['documents'], all_docs['metadatas'])):
        doc_upper = document.upper()

        if 'KFRET' in doc_upper:
            kfret_chunks.append({
                'id': doc_id,
                'file': metadata.get('file_name', 'unknown'),
                'page': metadata.get('page_number', 'unknown'),
                'content': document[:200]
            })

        if 'FRET' in doc_upper and 'KFRET' not in doc_upper:
            fret_chunks.append({
                'id': doc_id,
                'file': metadata.get('file_name', 'unknown'),
                'page': metadata.get('page_number', 'unknown'),
                'content': document[:200]
            })

    print(f"\n[결과] 'kFRET' 포함 청크: {len(kfret_chunks)}개")
    if kfret_chunks:
        for chunk in kfret_chunks[:5]:
            print(f"\n  - 파일: {chunk['file']}")
            print(f"    페이지: {chunk['page']}")
            print(f"    내용: {chunk['content']}...")

    print(f"\n[결과] 'FRET' 포함 청크 (kFRET 제외): {len(fret_chunks)}개")
    if fret_chunks:
        for chunk in fret_chunks[:5]:
            print(f"\n  - 파일: {chunk['file']}")
            print(f"    페이지: {chunk['page']}")
            print(f"    내용: {chunk['content']}...")

    # 도메인별 통계
    print(f"\n" + "=" * 80)
    print("파일별 청크 분포")
    print("=" * 80)

    file_stats = {}
    for metadata in all_docs['metadatas']:
        file_name = metadata.get('file_name', 'unknown')
        file_stats[file_name] = file_stats.get(file_name, 0) + 1

    for file_name, count in sorted(file_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {file_name}: {count}개 청크")

if __name__ == "__main__":
    check_kfret()
