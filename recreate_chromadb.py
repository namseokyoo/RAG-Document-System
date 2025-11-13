#!/usr/bin/env python3
"""
ChromaDB 재생성 및 문서 재임베딩
"""

import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import shutil
import json
from pathlib import Path

print("="*80)
print("ChromaDB 재생성 및 문서 재임베딩")
print("="*80)

# 1. 기존 DB 삭제
print(f"\n[1/4] 기존 ChromaDB 삭제")
chroma_path = "data/chroma_db"
if os.path.exists(chroma_path):
    print(f"  삭제 중: {chroma_path}")
    shutil.rmtree(chroma_path)
    print(f"  ✅ 삭제 완료")
else:
    print(f"  (이미 없음)")

# 2. 문서 확인
print(f"\n[2/4] 임베딩할 문서 확인")
doc_dir = "data/documents"
if os.path.exists(doc_dir):
    files = list(Path(doc_dir).rglob("*.*"))
    pdfs = [f for f in files if f.suffix.lower() == '.pdf']
    pptxs = [f for f in files if f.suffix.lower() == '.pptx']

    print(f"  PDF: {len(pdfs)}개")
    print(f"  PPTX: {len(pptxs)}개")
    print(f"  총: {len(files)}개 파일")
else:
    print(f"  ❌ 문서 디렉토리 없음: {doc_dir}")
    sys.exit(1)

# 3. Config 확인
print(f"\n[3/4] Config 확인")
with open('config_test.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

print(f"  Embedding API: {config.get('embedding_api_type')}")
print(f"  Embedding Model: {config.get('embedding_model')}")
print(f"  Diversity Penalty: {config.get('diversity_penalty')}")
print(f"  File Aggregation: {config.get('enable_file_aggregation')}")

# 4. 재임베딩 시작
print(f"\n[4/4] 문서 재임베딩 시작")
print(f"")
print(f"다음 명령어로 재임베딩을 실행하세요:")
print(f"")
print(f"  방법 1 (Desktop App - 권장):")
print(f"    venv/Scripts/python.exe desktop_app.py")
print(f"    → GUI에서 '문서 임베딩' 버튼 클릭")
print(f"")
print(f"  방법 2 (Streamlit App):")
print(f"    venv/Scripts/streamlit.exe run app.py")
print(f"    → 사이드바에서 '문서 임베딩' 버튼 클릭")
print(f"")
print(f"예상 소요 시간: 30분~1시간")
print(f"임베딩 완료 후 자동으로 테스트 가능합니다.")

print(f"\n" + "="*80)
print("준비 완료!")
print("="*80)
