"""
ChromaDB 완전 초기화 및 재구축 스크립트
"""

import os
import shutil
import glob

def clean_all_chromadb():
    """모든 ChromaDB 관련 폴더 삭제"""

    print("=" * 60)
    print("ChromaDB 완전 초기화")
    print("=" * 60)

    # 1. 모든 chroma_db 관련 폴더 찾기
    chroma_folders = glob.glob("data/chroma_db*")

    print(f"\n[1단계] 삭제 대상 폴더 확인")
    print(f"  발견된 폴더: {len(chroma_folders)}개")
    for folder in chroma_folders:
        print(f"    - {folder}")

    if not chroma_folders:
        print("  삭제할 폴더가 없습니다.")
        return

    # 2. 모두 삭제
    print(f"\n[2단계] 폴더 삭제 중...")
    for folder in chroma_folders:
        try:
            shutil.rmtree(folder)
            print(f"  [OK] 삭제: {folder}")
        except Exception as e:
            print(f"  [ERROR] 삭제 실패 ({folder}): {e}")

    # 3. 새 ChromaDB 디렉토리 생성
    print(f"\n[3단계] 새 ChromaDB 디렉토리 생성")
    new_db_path = "data/chroma_db"
    try:
        os.makedirs(new_db_path, exist_ok=True)
        print(f"  [OK] 생성: {new_db_path}")
    except Exception as e:
        print(f"  [ERROR] 생성 실패: {e}")
        return

    print(f"\n{'='*60}")
    print(f"[SUCCESS] ChromaDB 초기화 완료!")
    print(f"{'='*60}")
    print(f"\n다음 단계: 문서 재임베딩")
    print(f"  python re_embed_documents.py")


if __name__ == "__main__":
    clean_all_chromadb()
