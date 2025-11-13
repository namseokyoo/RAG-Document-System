#!/usr/bin/env python3
"""
ChromaDB 상태 체크 및 복구
"""

import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import os
from pathlib import Path

def check_chromadb(db_path="data/chroma_db/chroma.sqlite3"):
    """ChromaDB SQLite 파일 체크"""
    print("="*80)
    print("ChromaDB 상태 체크")
    print("="*80)

    if not os.path.exists(db_path):
        print(f"\n❌ DB 파일 없음: {db_path}")
        return False

    # 파일 크기
    size_mb = os.path.getsize(db_path) / (1024*1024)
    print(f"\n[파일 정보]")
    print(f"  경로: {db_path}")
    print(f"  크기: {size_mb:.1f} MB")

    # SQLite 무결성 체크
    print(f"\n[무결성 체크]")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # PRAGMA integrity_check
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()

        if result[0] == 'ok':
            print(f"  ✅ 무결성: OK")
        else:
            print(f"  ❌ 무결성 문제: {result[0]}")
            conn.close()
            return False

        # 테이블 목록
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\n[테이블 목록] ({len(tables)}개)")
        for table in tables:
            print(f"  - {table[0]}")

        # 각 테이블 row 수
        print(f"\n[테이블 통계]")
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]};")
                count = cursor.fetchone()[0]
                print(f"  - {table[0]}: {count:,} rows")
            except Exception as e:
                print(f"  - {table[0]}: ❌ {str(e)[:50]}")

        conn.close()
        return True

    except Exception as e:
        print(f"  ❌ 체크 실패: {e}")
        return False

def backup_chromadb(src="data/chroma_db", dst="data/chroma_db_backup"):
    """ChromaDB 백업"""
    print(f"\n{'='*80}")
    print("ChromaDB 백업")
    print("="*80)

    import shutil

    if os.path.exists(dst):
        print(f"  기존 백업 삭제: {dst}")
        shutil.rmtree(dst)

    print(f"  백업 생성 중...")
    shutil.copytree(src, dst)
    print(f"  ✅ 백업 완료: {dst}")

if __name__ == "__main__":
    # 체크
    is_ok = check_chromadb()

    print(f"\n{'='*80}")
    print("[최종 판정]")
    print("="*80)

    if is_ok:
        print(f"\n✅ ChromaDB 정상")
        print(f"")
        print(f"하지만 런타임 오류가 발생했다면:")
        print(f"  1. ChromaDB 버전 문제")
        print(f"  2. 인덱스 손상")
        print(f"  3. 메타데이터 불일치")
        print(f"")
        print(f"해결책: DB 재생성 권장")
    else:
        print(f"\n❌ ChromaDB 손상됨")
        print(f"")
        print(f"해결책: DB 백업 후 재생성 필요")

    # 자동 백업
    print(f"\n[자동 백업 시작]")
    backup_chromadb()

    print(f"\n[다음 단계]")
    print(f"  1. data/chroma_db 디렉토리 삭제")
    print(f"  2. 문서 재임베딩")
    print(f"")
    print(f"명령어:")
    print(f"  rmdir /s /q data\\chroma_db")
    print(f"  python desktop_app.py  # GUI에서 '문서 임베딩' 클릭")
