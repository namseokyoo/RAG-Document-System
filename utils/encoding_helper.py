#!/usr/bin/env python3
"""
Windows 터미널 UTF-8 인코딩 설정
모든 스크립트에서 import하여 사용
"""

import sys
import io
import locale
import os


def setup_utf8_encoding():
    """
    Windows 터미널에서 UTF-8 출력을 강제 설정

    문제: Windows CMD는 기본적으로 CP949 (한국어 코드 페이지) 사용
    해결: stdout/stderr를 UTF-8로 래핑

    사용법:
        from utils.encoding_helper import setup_utf8_encoding
        setup_utf8_encoding()
    """
    if sys.platform == 'win32':
        # stdout, stderr를 UTF-8로 강제 설정
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )

        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )

        # 환경 변수 설정
        os.environ['PYTHONIOENCODING'] = 'utf-8'

        # 콘솔 코드 페이지를 UTF-8로 변경 시도 (선택적)
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except:
            pass  # 실패해도 stdout/stderr 래핑으로 충분

        # locale 설정 (선택적)
        try:
            locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_ALL, 'Korean_Korea.65001')
            except:
                pass  # 실패해도 괜찮음


def get_encoding_info():
    """현재 인코딩 설정 정보 반환"""
    return {
        'stdout_encoding': sys.stdout.encoding if hasattr(sys.stdout, 'encoding') else 'unknown',
        'stderr_encoding': sys.stderr.encoding if hasattr(sys.stderr, 'encoding') else 'unknown',
        'default_encoding': sys.getdefaultencoding(),
        'filesystem_encoding': sys.getfilesystemencoding(),
        'locale': locale.getpreferredencoding(),
        'platform': sys.platform
    }


def print_encoding_info():
    """인코딩 설정 정보 출력 (디버깅용)"""
    info = get_encoding_info()
    print("="*60)
    print("인코딩 설정 정보")
    print("="*60)
    for key, value in info.items():
        print(f"  {key:25s}: {value}")
    print("="*60)


# 모듈 import 시 자동 설정 (선택적)
# 주석 해제하면 import만으로 자동 적용됨
# setup_utf8_encoding()
