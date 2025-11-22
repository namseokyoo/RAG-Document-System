"""
폰트 로더 유틸리티
나눔고딕 폰트를 애플리케이션에 로드하고 적용
"""
import os
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication


def load_nanumgothic_font() -> bool:
    """
    나눔고딕 폰트를 로드하고 애플리케이션에 적용

    Returns:
        bool: 폰트 로드 성공 여부
    """
    # 폰트 파일 경로 (우선순위 순)
    font_paths = [
        "resources/fonts/NanumGothic.ttf",
        "resources/fonts/NanumGothicBold.ttf",
        "resources/fonts/NanumGothicExtraBold.ttf",
    ]

    font_loaded = False
    font_family = "NanumGothic"

    # 폰트 파일 로드 시도
    for font_path in font_paths:
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    font_family = families[0]
                    print(f"[폰트] ✓ 나눔고딕 폰트 로드 성공: {font_path}")
                    print(f"[폰트] 폰트 패밀리: {font_family}")
                    font_loaded = True
                    break
            else:
                print(f"[폰트] ⚠ 폰트 로드 실패: {font_path}")

    if not font_loaded:
        print(f"[폰트] ℹ 나눔고딕 폰트 파일을 찾을 수 없습니다")
        print(f"[폰트] 시스템 기본 폰트를 사용합니다")
        return False

    # 애플리케이션 전체에 폰트 적용
    app = QApplication.instance()
    if app:
        default_font = QFont(font_family)
        default_font.setPointSize(10)  # 기본 크기 10pt
        app.setFont(default_font)
        print(f"[폰트] ✓ 전체 애플리케이션에 {font_family} 폰트 적용 완료")

    return True


def get_nanumgothic_font(point_size: int = 10, weight: int = QFont.Weight.Normal) -> QFont:
    """
    나눔고딕 폰트 객체를 생성

    Args:
        point_size: 폰트 크기 (pt)
        weight: 폰트 굵기 (QFont.Weight.Light, QFont.Weight.Normal, QFont.Weight.Bold 등)

    Returns:
        QFont: 폰트 객체
    """
    font = QFont("NanumGothic")
    font.setPointSize(point_size)
    font.setWeight(weight)
    return font
