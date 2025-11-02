#!/usr/bin/env python
"""
앱 실행 테스트 스크립트
"""
import sys
import os

print("[INFO] 테스트 시작")
print(f"[INFO] Python 버전: {sys.version}")
print(f"[INFO] 현재 디렉토리: {os.getcwd()}")

# 모듈 확인
modules_to_check = [
    'streamlit',
    'PySide6',
    'langchain',
    'chromadb',
    'transformers',
    'torch',
    'openai'
]

print("\n[INFO] 모듈 확인:")
for module in modules_to_check:
    try:
        __import__(module)
        print(f"  ✓ {module} - 설치됨")
    except ImportError:
        print(f"  ✗ {module} - 설치 안됨")

# 설정 파일 확인
print("\n[INFO] 설정 파일 확인:")
files_to_check = [
    '.env',
    'config.json',
    'app.py',
    'desktop_app.py',
    'utils/rag_chain.py',
    'utils/vector_store.py'
]

for file in files_to_check:
    if os.path.exists(file):
        print(f"  ✓ {file} - 존재함")
    else:
        print(f"  ✗ {file} - 없음")

# 데이터베이스 확인
print("\n[INFO] 데이터베이스 확인:")
if os.path.exists('data/chroma_db'):
    print("  ✓ ChromaDB 디렉토리 존재")
    # 파일 개수 확인
    import glob
    db_files = glob.glob('data/chroma_db/**/*', recursive=True)
    print(f"  - 파일 개수: {len(db_files)}")
else:
    print("  ✗ ChromaDB 디렉토리 없음")

print("\n[INFO] 테스트 완료")