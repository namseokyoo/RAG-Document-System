from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import QSplashScreen, QLabel, QProgressBar, QVBoxLayout, QWidget, QHBoxLayout
from utils.resource_path import resource_path


class SplashScreen(QSplashScreen):
    def __init__(self, version: str = "0.4.1"):
        super().__init__()

        self.version = version
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        # 메인 위젯 생성
        self.main_widget = QWidget()
        self.main_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-radius: 10px;
            }
        """)

        # 레이아웃 구성
        main_layout = QHBoxLayout(self.main_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # 왼쪽: 아이콘
        icon_label = QLabel()
        try:
            icon_path = resource_path("oc.ico")
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                # 아이콘 크기 조정 (128x128)
                scaled_pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_label.setPixmap(scaled_pixmap)
            else:
                # 아이콘 로드 실패 시 텍스트 표시
                icon_label.setText("📄")
                icon_label.setStyleSheet("font-size: 96px;")
                print(f"[SplashScreen] ⚠ 아이콘 로드 실패: {icon_path}")
        except Exception as e:
            # 아이콘 로드 실패 시 이모지 표시
            icon_label.setText("📄")
            icon_label.setStyleSheet("font-size: 96px;")
            print(f"[SplashScreen] ⚠ 아이콘 로드 오류: {e}")

        icon_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(icon_label)

        # 오른쪽: 정보 및 진행률
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)

        # 프로그램 이름
        title_label = QLabel("RAG Document System")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #3daee9; margin-bottom: 5px;")
        right_layout.addWidget(title_label)

        # 버전 정보
        version_label = QLabel(f"Version {self.version}")
        version_font = QFont()
        version_font.setPointSize(10)
        version_label.setFont(version_font)
        version_label.setStyleSheet("color: #a0a0a0; margin-bottom: 10px;")
        right_layout.addWidget(version_label)

        # 진행 상태 메시지
        self.status_label = QLabel("초기화 중...")
        status_font = QFont()
        status_font.setPointSize(11)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet("color: #ffffff; margin-top: 10px;")
        right_layout.addWidget(self.status_label)

        # 프로그레스 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
                background-color: #2b2b2b;
                color: #ffffff;
                min-height: 25px;
            }
            QProgressBar::chunk {
                background-color: #3daee9;
                border-radius: 3px;
            }
        """)
        right_layout.addWidget(self.progress_bar)

        # 상세 메시지 (작은 글씨)
        self.detail_label = QLabel("")
        detail_font = QFont()
        detail_font.setPointSize(9)
        self.detail_label.setFont(detail_font)
        self.detail_label.setStyleSheet("color: #a0a0a0; margin-top: 5px;")
        self.detail_label.setWordWrap(True)
        right_layout.addWidget(self.detail_label)

        right_layout.addStretch()
        main_layout.addLayout(right_layout, 1)

        # 크기 설정
        self.main_widget.setFixedSize(700, 300)
        self.setPixmap(self.main_widget.grab())

    def update_progress(self, progress: int, message: str, detail: str = ""):
        """
        진행률 업데이트

        Args:
            progress: 진행률 (0-100)
            message: 주 메시지
            detail: 상세 메시지 (선택사항)
        """
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
        if detail:
            self.detail_label.setText(detail)

        # 위젯을 다시 그려서 pixmap 업데이트
        self.setPixmap(self.main_widget.grab())

        # UI 업데이트 강제 실행
        QTimer.singleShot(0, lambda: None)
