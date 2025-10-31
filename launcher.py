#!/usr/bin/env python3
"""
OC_RAG 실행 런처
Streamlit 앱을 자동으로 실행하고 브라우저를 엽니다.
"""

import os
import sys
import webbrowser
import time
from pathlib import Path

def main():
    """메인 실행 함수"""
    
    # 실행 파일의 디렉토리 경로
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 경우
        app_dir = Path(sys._MEIPASS)
        base_dir = Path(sys.executable).parent
    else:
        # 일반 Python 실행
        app_dir = Path(__file__).parent
        base_dir = app_dir
    
    # 작업 디렉토리를 실행 파일 위치로 변경
    try:
        os.chdir(base_dir)
    except Exception as e:
        print(f"⚠️ 작업 디렉토리 변경 실패: {e}")
        # 현재 디렉토리 사용
        base_dir = Path.cwd()
    
    # 필요한 디렉토리 생성 (안전한 방식)
    try:
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "uploaded_files").mkdir(parents=True, exist_ok=True)
        (data_dir / "chroma_db").mkdir(parents=True, exist_ok=True)
        (base_dir / "chat_history").mkdir(parents=True, exist_ok=True)
        print(f"✅ 필요한 디렉토리 생성 완료")
    except Exception as e:
        print(f"❌ 디렉토리 생성 실패: {e}")
        print("🔄 기본 디렉토리로 계속 진행합니다...")
    
    # config.py 경로를 sys.path에 추가
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    
    # Streamlit 설정
    port = 3001
    
    print(f"🚀 OC_RAG를 시작합니다...")
    print(f"📂 작업 디렉토리: {base_dir}")
    print(f"📂 앱 디렉토리: {app_dir}")
    print(f"🌐 브라우저가 자동으로 열립니다: http://localhost:{port}")
    print(f"⏹️  종료하려면 Ctrl+C를 누르세요.\n")
    
    # 3초 후 브라우저 자동 오픈
    def open_browser():
        time.sleep(3)
        webbrowser.open(f"http://localhost:{port}")
    
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Streamlit 앱 직접 import 및 실행
    try:
        print(f"📦 Streamlit 모듈 로딩 중...")
        import streamlit as st
        import streamlit.web.cli as stcli
        
        # Streamlit 앱 경로 확인
        app_path = str(app_dir / "app.py")
        if not os.path.exists(app_path):
            raise FileNotFoundError(f"app.py를 찾을 수 없습니다: {app_path}")
        
        print(f"📄 앱 파일 경로: {app_path}")
        
        # Streamlit CLI 인자 설정
        sys.argv = [
            "streamlit",
            "run",
            app_path,
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--global.developmentMode", "false"
        ]
        
        print(f"🚀 Streamlit 서버 시작 중... (포트: {port})")
        # Streamlit 실행
        stcli.main()
        
    except Exception as e:
        print(f"❌ Streamlit 실행 실패: {e}")
        print(f"📋 상세 오류: {type(e).__name__}: {str(e)}")
        print("🔄 대안 방법으로 실행합니다...")
        
        # 대안: subprocess 사용
        import subprocess
        import threading
        
        def run_streamlit():
            try:
                subprocess.run([
                    sys.executable, "-m", "streamlit", "run",
                    str(app_dir / "app.py"),
                    "--server.port", str(port),
                    "--server.headless", "true",
                    "--browser.gatherUsageStats", "false"
                ], cwd=str(app_dir))
            except Exception as e2:
                print(f"❌ 대안 실행도 실패: {e2}")
        
        # 백그라운드에서 Streamlit 실행
        streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
        streamlit_thread.start()
        
        # 메인 스레드에서 대기
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 OC_RAG를 종료합니다.")
            sys.exit(0)

if __name__ == "__main__":
    main()

