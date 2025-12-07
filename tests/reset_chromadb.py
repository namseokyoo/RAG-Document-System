"""
ChromaDB 초기화 스크립트
오래된 데이터를 삭제하고 깨끗한 상태로 시작
"""
import os
import shutil
import time

def reset_chromadb():
    """ChromaDB 초기화"""
    chroma_dir = "data/chroma_db"

    if not os.path.exists(chroma_dir):
        print(f"[INFO] ChromaDB 디렉토리가 없습니다: {chroma_dir}")
        print("[OK] 이미 초기화된 상태입니다")
        return True

    print(f"[INFO] ChromaDB 초기화 시작: {chroma_dir}")

    try:
        # 여러 번 시도 (파일이 잠겨있을 수 있음)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                shutil.rmtree(chroma_dir)
                print(f"[OK] ChromaDB 삭제 완료 (시도 {attempt}회)")
                break
            except PermissionError as e:
                if attempt < max_attempts:
                    print(f"[WARN] 파일 사용 중, 2초 후 재시도... ({attempt}/{max_attempts})")
                    time.sleep(2)
                else:
                    print(f"[ERROR] ChromaDB 삭제 실패: {e}")
                    print(f"[INFO] 수동 삭제 필요: {chroma_dir} 폴더를 직접 삭제하세요")
                    return False
            except Exception as e:
                print(f"[ERROR] ChromaDB 삭제 실패: {e}")
                return False

        print("[OK] ChromaDB 초기화 완료")
        print("[INFO] 다음 단계: 데이터를 재임베딩하세요")
        return True

    except Exception as e:
        print(f"[ERROR] 초기화 실패: {e}")
        return False


if __name__ == "__main__":
    import sys
    success = reset_chromadb()
    sys.exit(0 if success else 1)
