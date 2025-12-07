"""
DB 재구축 스크립트 (chunk_size=1500)
기존 embedded_documents 폴더의 모든 문서를 재인제스트
"""

import os
import sys
from pathlib import Path

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 환경 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.document_processor import DocumentProcessor

print("=" * 80)
print("DB 재구축 (chunk_size=1500)")
print("=" * 80)

# Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

# 설정 확인
print(f"\n[설정 확인]")
print(f"  - chunk_size: {config.get('chunk_size', 'N/A')}")
print(f"  - chunk_overlap: {config.get('chunk_overlap', 'N/A')}")
print(f"  - small_to_large_context_size: {config.get('small_to_large_context_size', 'N/A')}")

if config.get('chunk_size') != 1500:
    print(f"\n[경고] chunk_size가 1500이 아닙니다: {config.get('chunk_size')}")
    print(f"[자동 진행] config.json을 먼저 수정하세요.")
    sys.exit(1)

# 기존 DB 삭제
db_path = Path("data/chroma_db")
if db_path.exists():
    print(f"\n[준비] 기존 DB 삭제 중...")
    import shutil
    shutil.rmtree(db_path)
    print(f"  - 기존 DB 삭제 완료")

# VectorStore 초기화
print(f"\n[1단계] VectorStore 초기화")
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    embedding_api_key=config.get("embedding_api_key", ""),
)
print(f"  - VectorStore 초기화 완료")

# DocumentProcessor 초기화
print(f"\n[2단계] DocumentProcessor 초기화")
doc_processor = DocumentProcessor(
    chunk_size=config.get("chunk_size", 1500),
    chunk_overlap=config.get("chunk_overlap", 200)
)
print(f"  - chunk_size: {doc_processor.chunk_size}")
print(f"  - chunk_overlap: {doc_processor.chunk_overlap}")

# 문서 목록 수집
docs_dir = Path("data/embedded_documents")
if not docs_dir.exists():
    print(f"\n[오류] 문서 폴더가 없습니다: {docs_dir}")
    sys.exit(1)

# PDF와 PPTX 파일만
doc_files = []
for ext in ['*.pdf', '*.pptx']:
    doc_files.extend(list(docs_dir.glob(ext)))

if not doc_files:
    print(f"\n[오류] 문서가 없습니다: {docs_dir}")
    sys.exit(1)

print(f"\n[3단계] 문서 목록 ({len(doc_files)}개)")
for i, doc_file in enumerate(doc_files, 1):
    file_size_mb = doc_file.stat().st_size / 1024 / 1024
    print(f"  {i}. {doc_file.name} ({file_size_mb:.1f} MB)")

# 자동 진행
print(f"\n[주의] 기존 DB는 백업되었습니다.")
print(f"  백업 위치: data/chroma_db_backup_800_20251108_113220")
print(f"\n총 {len(doc_files)}개 문서를 chunk_size=1500으로 재인제스트합니다.")
print(f"[자동 진행 모드]")

# 재인제스트
print(f"\n{'=' * 80}")
print(f"재인제스트 시작")
print(f"{'=' * 80}")

success_count = 0
fail_count = 0

for i, doc_file in enumerate(doc_files, 1):
    print(f"\n[{i}/{len(doc_files)}] {doc_file.name}")
    print(f"-" * 80)

    try:
        # 문서 처리 (청크 생성)
        file_ext = doc_file.suffix[1:].lower()  # .pdf -> pdf
        chunks = doc_processor.process_document(
            file_path=str(doc_file),
            file_name=doc_file.name,
            file_type=file_ext
        )

        if not chunks:
            print(f"  ✗ 청크 생성 실패")
            fail_count += 1
            continue

        print(f"  - {len(chunks)}개 청크 생성")

        # 임베딩 추가
        result = vector_manager.add_documents(chunks)
        if result:
            print(f"  ✓ 임베딩 완료!")
            success_count += 1
        else:
            print(f"  ✗ 임베딩 실패")
            fail_count += 1

    except Exception as e:
        print(f"  ✗ 오류: {e}")
        import traceback
        traceback.print_exc()
        fail_count += 1

# 결과 요약
print(f"\n{'=' * 80}")
print(f"재구축 완료")
print(f"{'=' * 80}")

print(f"\n[결과]")
print(f"  - 성공: {success_count}/{len(doc_files)}")
print(f"  - 실패: {fail_count}/{len(doc_files)}")

# DB 통계
print(f"\n[DB 통계]")
try:
    collection = vector_manager.vectorstore._collection
    total_chunks = collection.count()
    print(f"  - 총 청크 수: {total_chunks:,}개")
except Exception as e:
    print(f"  - 통계 조회 실패: {e}")

print(f"\n{'=' * 80}")
print(f"완료!")
print(f"{'=' * 80}")
