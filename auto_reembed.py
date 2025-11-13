#!/usr/bin/env python3
"""
자동 재임베딩 스크립트
"""

import sys
import os
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 오프라인 모드 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json
from pathlib import Path
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.document_processor import DocumentProcessor

print("="*80)
print("자동 재임베딩")
print("="*80)

# Config 로드
print(f"\n[1/5] Config 로드")
with open('config_test.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

print(f"  Embedding API: {config.get('embedding_api_type')}")
print(f"  Embedding Model: {config.get('embedding_model')}")
print(f"  Diversity Penalty: {config.get('diversity_penalty')}")
print(f"  File Aggregation: {config.get('enable_file_aggregation')}")

# 문서 확인
print(f"\n[2/5] 문서 확인")
doc_dir = "data/embedded_documents"
files = list(Path(doc_dir).rglob("*.*"))
pdfs = [str(f) for f in files if f.suffix.lower() == '.pdf']
pptxs = [str(f) for f in files if f.suffix.lower() == '.pptx']

print(f"  PDF: {len(pdfs)}개")
print(f"  PPTX: {len(pptxs)}개")
print(f"  총: {len(pdfs) + len(pptxs)}개")

# VectorStore 초기화 (새 DB 생성)
print(f"\n[3/5] VectorStore 초기화 (새 DB 생성)")
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    distance_function=config.get("chroma_distance_function", "cosine")
)
print(f"  ✅ 초기화 완료")

# DocumentProcessor 초기화
print(f"\n[4/5] DocumentProcessor 초기화")
doc_processor = DocumentProcessor(
    chunk_size=config.get("chunk_size", 1500),
    chunk_overlap=config.get("chunk_overlap", 200)
)
print(f"  ✅ 초기화 완료")

# 임베딩 시작
print(f"\n[5/5] 문서 임베딩 시작")
print(f"  예상 소요 시간: 약 30-40분")
print(f"")

total_docs = len(pdfs) + len(pptxs)
all_files = pdfs + pptxs

for i, file_path in enumerate(all_files, 1):
    file_path_obj = Path(file_path)
    filename = file_path_obj.name
    file_type = file_path_obj.suffix.lower()[1:]  # .pdf -> pdf, .pptx -> pptx

    print(f"  [{i}/{total_docs}] {filename[:50]}")

    try:
        # 문서 처리 (file_path, file_name, file_type 전달)
        chunks = doc_processor.process_document(file_path, filename, file_type)

        if not chunks:
            print(f"       ⚠️  청크 생성 실패")
            continue

        # VectorStore에 추가
        vector_manager.add_documents(chunks)
        print(f"       ✅ {len(chunks)} 청크 임베딩 완료")

    except Exception as e:
        print(f"       ❌ 오류: {str(e)[:100]}")

print(f"\n" + "="*80)
print("임베딩 완료!")
print("="*80)

# 통계
print(f"\n[통계]")
vectorstore = vector_manager.get_vectorstore()
collection = vectorstore._collection
count = collection.count()
print(f"  총 임베딩 수: {count:,}개")

print(f"\n다음 단계: 빠른 검증 테스트 실행 가능")
print(f"  python quick_exhaustive_test.py")
