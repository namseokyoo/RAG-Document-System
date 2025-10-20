from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QWidget, QTabWidget, QVBoxLayout

from .chat_widget import ChatWidget
from .document_widget import DocumentWidget
from .settings_widget import SettingsWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OC_RAG (Desktop)")
        self.resize(1200, 800)
        self._init_ui()

    def _init_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        tabs = QTabWidget(self)
        tabs.addTab(DocumentWidget(self), "문서")
        tabs.addTab(ChatWidget(self), "채팅")
        tabs.addTab(SettingsWidget(self), "설정")

        layout.addWidget(tabs)
        self.setCentralWidget(central)
