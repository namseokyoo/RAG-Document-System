"""
PyInstaller 빌드 환경에서 리소스 파일 경로를 올바르게 찾기 위한 헬퍼 모듈
"""
import sys
import os


def resource_path(relative_path: str) -> str:
    """
    리소스 파일의 절대 경로를 반환

    PyInstaller로 빌드된 경우 sys._MEIPASS에서 리소스를 찾고,
    개발 환경에서는 현재 작업 디렉토리에서 찾습니다.

    Args:
        relative_path: 리소스 파일의 상대 경로 (예: "oc.ico", "resources/icon.png")

    Returns:
        리소스 파일의 절대 경로
    """
    try:
        # PyInstaller가 생성하는 임시 폴더 경로
        base_path = sys._MEIPASS
    except AttributeError:
        # 개발 환경: 현재 작업 디렉토리 사용
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
