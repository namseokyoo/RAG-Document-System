"""ChromaDB에서 현진건 소설 청크 삭제"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.vector_store import VectorStoreManager

def delete_literature_chunks():
    print("=" * 80)
    print("ChromaDB에서 현진건-운수좋은날 청크 삭제")
    print("=" * 80)

    config = ConfigManager().get_all()

    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    # 삭제 전 통계
    collection = vector_manager.vectorstore._collection
    all_docs_before = collection.get()
    print(f"\n[삭제 전] 총 청크 개수: {len(all_docs_before['ids'])}")

    # 파일명으로 삭제
    file_name = "현진건-운수좋은날+B3356-개벽.pdf"
    success = vector_manager.delete_documents_by_file_name(file_name)

    # 삭제 후 통계
    all_docs_after = collection.get()
    print(f"[삭제 후] 총 청크 개수: {len(all_docs_after['ids'])}")
    print(f"[삭제됨] {len(all_docs_before['ids']) - len(all_docs_after['ids'])}개 청크")

    # 남은 파일 목록
    print(f"\n[남은 파일 목록]")
    file_stats = {}
    for metadata in all_docs_after['metadatas']:
        file_name = metadata.get('file_name', 'unknown')
        file_stats[file_name] = file_stats.get(file_name, 0) + 1

    for file_name, count in sorted(file_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {file_name}: {count}개 청크")

    print("\n" + "=" * 80)
    print("삭제 완료")
    print("=" * 80)

    return success

if __name__ == "__main__":
    delete_literature_chunks()
