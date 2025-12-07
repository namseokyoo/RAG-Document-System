"""
ChromaDB 손상 문제 해결 스크립트
"""

import os
import shutil
from datetime import datetime

def backup_and_recreate_db():
    """ChromaDB 백업 후 재생성"""

    db_path = "data/chroma_db"

    if not os.path.exists(db_path):
        print(f"[ERROR] DB 경로를 찾을 수 없습니다: {db_path}")
        return

    # 1. 백업 디렉토리 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"data/chroma_db_backup_{timestamp}"

    print(f"[1단계] DB 백업 중...")
    print(f"  원본: {db_path}")
    print(f"  백업: {backup_path}")

    try:
        shutil.copytree(db_path, backup_path)
        print(f"  [OK] 백업 완료")
    except Exception as e:
        print(f"  [ERROR] 백업 실패: {e}")
        return

    # 2. 기존 DB 삭제
    print(f"\n[2단계] 기존 DB 삭제 중...")
    try:
        shutil.rmtree(db_path)
        print(f"  [OK] 삭제 완료")
    except Exception as e:
        print(f"  [ERROR] 삭제 실패: {e}")
        return

    # 3. 새 디렉토리 생성
    print(f"\n[3단계] 새 DB 디렉토리 생성 중...")
    try:
        os.makedirs(db_path, exist_ok=True)
        print(f"  [OK] 생성 완료")
    except Exception as e:
        print(f"  [ERROR] 생성 실패: {e}")
        return

    print(f"\n{'='*60}")
    print(f"[SUCCESS] ChromaDB 재설정 완료!")
    print(f"{'='*60}")
    print(f"\n다음 단계:")
    print(f"1. 데스크탑 앱을 다시 실행하세요")
    print(f"2. 앱이 정상 실행되면 문서를 다시 임베딩하세요")
    print(f"3. 문제가 계속되면 백업 폴더를 확인하세요: {backup_path}")
    print(f"\n백업 삭제 명령 (성공 후 실행):")
    print(f"  rmdir /s /q {backup_path}")


if __name__ == "__main__":
    import chromadb
    print(f"ChromaDB 버전: {chromadb.__version__}")
    print(f"{'='*60}\n")

    backup_and_recreate_db()
