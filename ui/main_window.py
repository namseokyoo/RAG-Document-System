from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QWidget, QTabWidget, QVBoxLayout

from .chat_widget import ChatWidget
from .document_widget import DocumentWidget
from .settings_widget import SettingsWidget


class MainWindow(QMainWindow):
    def __init__(self, document_processor=None, vector_manager=None, rag_chain=None) -> None:
        super().__init__()
        self.setWindowTitle("OC_RAG (Desktop)")
        self.resize(1200, 800)

        self.document_processor = document_processor
        self.vector_manager = vector_manager
        self.rag_chain = rag_chain

        self._init_ui()

    def _init_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget(self)

        self.doc_tab = DocumentWidget(self, document_processor=self.document_processor, vector_manager=self.vector_manager)
        self.chat_tab = ChatWidget(self, rag_chain=self.rag_chain)
        self.settings_tab = SettingsWidget(self, vector_manager=self.vector_manager, rag_chain=self.rag_chain)

        # 문서 탭에서 목록 변경 시 채팅 탭에 반영(필요 시)
        self.doc_tab.documents_changed.connect(self._on_documents_changed)

        self.tabs.addTab(self.doc_tab, "문서")
        self.tabs.addTab(self.chat_tab, "채팅")
        self.tabs.addTab(self.settings_tab, "설정")

        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

    def _on_documents_changed(self) -> None:
        # 훗날 문서 통계/상태 갱신 등에 활용 가능
        pass
