"""ChromaDB 초기화 후 카테고리 메타데이터와 함께 샘플 문서 재임베딩"""
import sys
import os
import shutil

# UTF-8 출력 설정 (Windows 콘솔 호환)
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.document_processor import DocumentProcessor
from utils.request_llm import RequestLLM

def main():
    print("=" * 80)
    print("ChromaDB 초기화 및 카테고리 메타데이터 적용 재임베딩")
    print("=" * 80)

    # 설정 로드
    config = ConfigManager().get_all()

    # 1. 기존 ChromaDB 백업
    chroma_db_path = "data/chroma_db"
    backup_path = "data/chroma_db_backup"

    if os.path.exists(chroma_db_path):
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
        shutil.copytree(chroma_db_path, backup_path)
        print(f"✓ 기존 DB 백업 완료: {backup_path}")

    # 2. ChromaDB 초기화
    if os.path.exists(chroma_db_path):
        shutil.rmtree(chroma_db_path)
        print(f"✓ 기존 DB 삭제 완료")

    # 3. VectorStore 초기화
    vector_manager = VectorStoreManager(
        persist_directory=chroma_db_path,
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )
    print(f"✓ VectorStore 초기화 완료")

    # 4. LLM 클라이언트 생성 (카테고리 분류용)
    llm_client = RequestLLM(
        api_type=config.get("llm_api_type", "ollama"),
        base_url=config.get("llm_base_url", "http://localhost:11434"),
        model=config.get("llm_model", "llama3"),
        api_key=config.get("llm_api_key", ""),
        temperature=0.0  # 카테고리 분류는 temperature 0으로 일관성 유지
    )
    print(f"✓ LLM 클라이언트 초기화 완료: {config.get('llm_model', 'llama3')}")

    # 5. DocumentProcessor 생성 (LLM 클라이언트 포함)
    doc_processor = DocumentProcessor(
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"],
        llm_client=llm_client
    )
    print(f"✓ DocumentProcessor 초기화 완료 (LLM 기반 카테고리 분류 활성화)")

    # 6. 샘플 문서 재임베딩
    embedded_docs_dir = "data/embedded_documents"

    if not os.path.exists(embedded_docs_dir):
        print(f"⚠ 샘플 문서 폴더가 없습니다: {embedded_docs_dir}")
        return

    files = [f for f in os.listdir(embedded_docs_dir) if not f.startswith('.')]

    if not files:
        print(f"⚠ 임베딩할 문서가 없습니다")
        return

    print(f"\n[임베딩할 문서 목록] ({len(files)}개)")
    for i, file_name in enumerate(files, 1):
        print(f"  {i}. {file_name}")

    print("\n" + "=" * 80)
    print("임베딩 시작")
    print("=" * 80)

    for i, file_name in enumerate(files, 1):
        file_path = os.path.join(embedded_docs_dir, file_name)
        print(f"\n[{i}/{len(files)}] {file_name}")

        try:
            # 문서 처리 (카테고리 자동 분류 포함)
            file_type = doc_processor.get_file_type(file_name)
            chunks = doc_processor.process_document(file_path, file_name, file_type)

            # 첫 번째 청크의 카테고리 확인
            if chunks:
                category = chunks[0].metadata.get("category", "unknown")
                print(f"  → 분류된 카테고리: {category}")
                print(f"  → 생성된 청크 개수: {len(chunks)}개")

            # VectorStore에 추가
            vector_manager.add_documents(chunks)
            print(f"  ✓ 임베딩 완료")

        except Exception as e:
            print(f"  ✗ 임베딩 실패: {e}")
            import traceback
            traceback.print_exc()

    # 7. 최종 통계
    print("\n" + "=" * 80)
    print("임베딩 통계")
    print("=" * 80)

    collection = vector_manager.vectorstore._collection
    all_docs = collection.get()
    total_chunks = len(all_docs['ids'])

    print(f"\n총 청크 개수: {total_chunks}개")

    # 파일별 통계
    print(f"\n[파일별 청크 수]")
    file_stats = {}
    for metadata in all_docs['metadatas']:
        file_name = metadata.get('file_name', 'unknown')
        file_stats[file_name] = file_stats.get(file_name, 0) + 1

    for file_name, count in sorted(file_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {file_name}: {count}개")

    # 카테고리별 통계
    print(f"\n[카테고리별 청크 수]")
    category_stats = {}
    for metadata in all_docs['metadatas']:
        category = metadata.get('category', 'unknown')
        category_stats[category] = category_stats.get(category, 0) + 1

    for category, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {category}: {count}개")

    # 파일별 카테고리
    print(f"\n[파일별 카테고리]")
    file_category = {}
    for metadata in all_docs['metadatas']:
        file_name = metadata.get('file_name', 'unknown')
        category = metadata.get('category', 'unknown')
        file_category[file_name] = category

    for file_name, category in sorted(file_category.items()):
        print(f"  - {file_name}: {category}")

    print("\n" + "=" * 80)
    print("재임베딩 완료!")
    print("=" * 80)
    print(f"\n[참고]")
    print(f"  - 백업 위치: {backup_path}")
    print(f"  - 새 DB 위치: {chroma_db_path}")

if __name__ == "__main__":
    main()
