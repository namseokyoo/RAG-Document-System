"""ChromaDB 디렉토리 이름 변경"""
import os
import shutil

if os.path.exists('data/chroma_db'):
    try:
        os.rename('data/chroma_db', 'data/chroma_db_old_backup')
        print("[OK] ChromaDB 백업 완료: data/chroma_db -> data/chroma_db_old_backup")
        print("[INFO] 새로운 ChromaDB가 자동 생성됩니다")
    except Exception as e:
        print(f"[ERROR] 이름 변경 실패: {e}")
        print("[INFO] 수동으로 data/chroma_db 폴더를 다른 이름으로 변경하세요")
else:
    print("[INFO] ChromaDB 디렉토리가 없습니다 (이미 초기화됨)")
