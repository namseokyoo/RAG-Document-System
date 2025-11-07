"""
최적화된 설정으로 문서 재임베딩
- chunk_size: 800
- chunk_overlap: 150
- reranker_initial_k: 30
"""
import sys
import os

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager

def re_embed_all_documents():
    """모든 문서 재임베딩"""
    print("=" * 80)
    print("문서 재임베딩 (최적화된 설정)")
    print("=" * 80)

    # 1. 설정 로드
    print("\n[1단계] 설정 로드...")
    config = ConfigManager().get_all()

    print(f"  - chunk_size: {config.get('chunk_size')}")
    print(f"  - chunk_overlap: {config.get('chunk_overlap')}")
    print(f"  - reranker_initial_k: {config.get('reranker_initial_k')}")
    print(f"  - enable_hybrid_search: {config.get('enable_hybrid_search')}")

    # 2. DocumentProcessor 초기화
    print("\n[2단계] DocumentProcessor 초기화...")
    doc_processor = DocumentProcessor(
        chunk_size=config.get("chunk_size", 800),
        chunk_overlap=config.get("chunk_overlap", 150),
    )

    # 3. VectorStoreManager 초기화
    print("\n[3단계] VectorStoreManager 초기화...")
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    # 4. 임베딩할 파일 목록
    embedded_docs_dir = "data/embedded_documents"
    if not os.path.exists(embedded_docs_dir):
        print(f"[ERROR] 문서 디렉토리가 없습니다: {embedded_docs_dir}")
        return False

    files = os.listdir(embedded_docs_dir)
    if not files:
        print(f"[ERROR] 임베딩할 파일이 없습니다: {embedded_docs_dir}")
        return False

    print(f"\n[4단계] 파일 임베딩 시작 ({len(files)}개 파일)")
    print("-" * 80)

    # 5. 각 파일 임베딩
    total_chunks = 0
    for i, file_name in enumerate(files, 1):
        file_path = os.path.join(embedded_docs_dir, file_name)

        # 파일 타입 결정
        if file_name.endswith('.pptx'):
            file_type = 'pptx'
        elif file_name.endswith('.pdf'):
            file_type = 'pdf'
        elif file_name.endswith(('.xlsx', '.xls')):
            file_type = 'xlsx'
        elif file_name.endswith('.txt'):
            file_type = 'txt'
        else:
            print(f"\n[{i}/{len(files)}] [SKIP] 지원하지 않는 파일 형식: {file_name}")
            continue

        print(f"\n[{i}/{len(files)}] {file_name} ({file_type})")
        print("-" * 60)

        try:
            # 문서 처리
            chunks = doc_processor.process_document(
                file_path=file_path,
                file_name=file_name,
                file_type=file_type
            )

            if not chunks:
                print(f"  [WARN] 청크 생성 실패")
                continue

            print(f"  [OK] {len(chunks)}개 청크 생성")

            # 청크 타입 통계 (Phase 3 검증)
            chunk_types = {}
            slide_types = {}
            for chunk in chunks:
                ct = chunk.metadata.chunk_type if hasattr(chunk.metadata, 'chunk_type') else 'unknown'
                chunk_types[ct] = chunk_types.get(ct, 0) + 1

                if hasattr(chunk.metadata, 'slide_type') and chunk.metadata.slide_type:
                    st = chunk.metadata.slide_type
                    slide_types[st] = slide_types.get(st, 0) + 1

            print(f"  [청크 타입]")
            for ct, count in sorted(chunk_types.items(), key=lambda x: x[1], reverse=True):
                print(f"    - {ct}: {count}개")

            if slide_types and file_type == 'pptx':
                print(f"  [슬라이드 타입] (Phase 3)")
                for st, count in sorted(slide_types.items(), key=lambda x: x[1], reverse=True):
                    print(f"    - {st}: {count}개")

            # 임베딩
            success = vector_manager.add_documents(chunks)
            if success:
                print(f"  [OK] 임베딩 완료")
                total_chunks += len(chunks)
            else:
                print(f"  [ERROR] 임베딩 실패")

        except Exception as e:
            print(f"  [ERROR] 처리 실패: {e}")
            import traceback
            traceback.print_exc()

    # 6. 완료
    print("\n" + "=" * 80)
    print("재임베딩 완료")
    print("=" * 80)
    print(f"\n[통계]")
    print(f"  - 총 파일: {len(files)}개")
    print(f"  - 총 청크: {total_chunks}개")

    return True


if __name__ == "__main__":
    try:
        success = re_embed_all_documents()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARN] 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 재임베딩 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
