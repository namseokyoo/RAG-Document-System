"""
ChromaDB 재초기화 및 test_documents 임베딩
"""

import os
import shutil
import sys
from pathlib import Path

# 환경 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from config import ConfigManager
from utils.document_processor import DocumentProcessor

print("=" * 80)
print("ChromaDB 재초기화 및 test_documents 임베딩")
print("=" * 80)

# Step 1: 기존 ChromaDB 삭제
chroma_db_path = Path("data/chroma_db")
if chroma_db_path.exists():
    print(f"\n[1단계] 기존 ChromaDB 삭제 중...")
    try:
        shutil.rmtree(chroma_db_path)
        print(f"  - 삭제 완료: {chroma_db_path}")
    except Exception as e:
        print(f"  - 삭제 실패: {e}")
        print(f"  수동으로 폴더를 삭제해주세요: {chroma_db_path}")
        sys.exit(1)
else:
    print(f"\n[1단계] ChromaDB 폴더 없음 (새로 생성)")

# Step 2: Config 로드
print(f"\n[2단계] Config 로드")
config_manager = ConfigManager()
config = config_manager.get_all()
print(f"  - Embedding Model: {config.get('embedding_model')}")
print(f"  - Chunk Size: {config.get('chunk_size')}")
print(f"  - Chunk Overlap: {config.get('chunk_overlap')}")

# Step 3: test_documents 확인
test_docs_path = Path("data/test_documents")
if not test_docs_path.exists():
    print(f"\n[오류] test_documents 폴더가 없습니다: {test_docs_path}")
    sys.exit(1)

pdf_files = list(test_docs_path.glob("*.pdf"))
print(f"\n[3단계] test_documents 확인")
print(f"  - 폴더: {test_docs_path}")
print(f"  - PDF 파일 수: {len(pdf_files)}")
for pdf in pdf_files:
    print(f"    - {pdf.name}")

# Step 4: DocumentProcessor 및 VectorStore 초기화
print(f"\n[4단계] DocumentProcessor 초기화")
try:
    processor = DocumentProcessor(
        chunk_size=config.get("chunk_size", 1500),
        chunk_overlap=config.get("chunk_overlap", 200),
    )
    print(f"  - DocumentProcessor 초기화 완료")
except Exception as e:
    print(f"  [오류] DocumentProcessor 초기화 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: VectorStore 초기화
print(f"\n[5단계] VectorStore 초기화")
try:
    from utils.vector_store import VectorStoreManager

    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "request"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )
    print(f"  - VectorStore 초기화 완료")
except Exception as e:
    print(f"  [오류] VectorStore 초기화 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 6: 문서 임베딩
print(f"\n[6단계] 문서 임베딩 시작")
success_count = 0
fail_count = 0
total_chunks = 0

for i, pdf_file in enumerate(pdf_files, 1):
    print(f"\n  [{i}/{len(pdf_files)}] 처리 중: {pdf_file.name}")
    try:
        # 문서 처리
        chunks = processor.process_document(
            file_path=str(pdf_file),
            file_name=pdf_file.name,
            file_type='pdf'
        )

        if not chunks:
            print(f"    - 청크 생성 실패")
            fail_count += 1
            continue

        print(f"    - {len(chunks)}개 청크 생성")

        # 임베딩
        result = vector_manager.add_documents(chunks)
        if result:
            print(f"    - 임베딩 완료!")
            success_count += 1
            total_chunks += len(chunks)
        else:
            print(f"    - 임베딩 실패")
            fail_count += 1

    except Exception as e:
        fail_count += 1
        print(f"    - 실패: {e}")
        import traceback
        traceback.print_exc()

print(f"\n[완료] 임베딩 결과")
print(f"  - 성공: {success_count}개")
print(f"  - 실패: {fail_count}개")
print(f"  - 총 청크: {total_chunks}개")
print(f"  - ChromaDB 위치: {chroma_db_path}")

print(f"\n" + "=" * 80)
print(f"ChromaDB 재구축 완료!")
print(f"=" * 80)
