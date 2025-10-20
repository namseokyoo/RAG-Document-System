from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout, QToolBar, QMenuBar,
    QSystemTrayIcon, QMenu, QApplication
)

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

        self._is_dark = True  # 기본 다크

        self._init_ui()
        self._init_menu_toolbar()
        self._init_tray()
        self._init_statusbar()

    def _init_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget(self)

        self.doc_tab = DocumentWidget(self, document_processor=self.document_processor, vector_manager=self.vector_manager)
        self.chat_tab = ChatWidget(self, rag_chain=self.rag_chain)
        self.settings_tab = SettingsWidget(self, vector_manager=self.vector_manager, rag_chain=self.rag_chain)

        self.doc_tab.documents_changed.connect(self._on_documents_changed)

        self.tabs.addTab(self.doc_tab, "문서")
        self.tabs.addTab(self.chat_tab, "채팅")
        self.tabs.addTab(self.settings_tab, "설정")

        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

    def _init_menu_toolbar(self) -> None:
        # 메뉴
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        file_menu = menubar.addMenu("파일")
        view_menu = menubar.addMenu("보기")
        help_menu = menubar.addMenu("도움말")

        self.act_add = QAction("열기...", self)
        self.act_add.setShortcut(QKeySequence.Open)
        self.act_delete = QAction("삭제", self)
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_quit = QAction("종료", self)
        self.act_quit.setShortcut(QKeySequence.Quit)

        self.act_toggle_theme = QAction("테마 토글 (다크/라이트)", self)
        self.act_toggle_theme.setShortcut(QKeySequence("Ctrl+T"))

        file_menu.addAction(self.act_add)
        file_menu.addAction(self.act_delete)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        view_menu.addAction(self.act_toggle_theme)

        # 툴바
        toolbar = QToolBar("메인", self)
        toolbar.setMovable(False)
        toolbar.addAction(self.act_add)
        toolbar.addAction(self.act_delete)
        toolbar.addSeparator()
        toolbar.addAction(self.act_toggle_theme)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        # 연결
        self.act_add.triggered.connect(self.doc_tab.on_add)
        self.act_delete.triggered.connect(self.doc_tab.on_remove)
        self.act_quit.triggered.connect(QApplication.instance().quit)
        self.act_toggle_theme.triggered.connect(self._toggle_theme)

    def _init_tray(self) -> None:
        # 시스템 트레이
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.windowIcon())
        tray_menu = QMenu(self)
        act_show = QAction("열기", self)
        act_hide = QAction("숨기기", self)
        act_exit = QAction("종료", self)
        tray_menu.addAction(act_show)
        tray_menu.addAction(act_hide)
        tray_menu.addSeparator()
        tray_menu.addAction(act_exit)
        self.tray.setContextMenu(tray_menu)
        self.tray.show()

        act_show.triggered.connect(self.showNormal)
        act_hide.triggered.connect(self.hide)
        act_exit.triggered.connect(QApplication.instance().quit)
        self.tray.activated.connect(self._on_tray_activated)

    def _init_statusbar(self) -> None:
        self.statusBar().showMessage("준비됨")

    def _toggle_theme(self) -> None:
        # QDarkStyle 적용/해제
        app = QApplication.instance()
        if self._is_dark:
            app.setStyleSheet("")
            self._is_dark = False
            self.statusBar().showMessage("라이트 테마 적용", 2000)
        else:
            try:
                import qdarkstyle
                app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyside6"))
            except Exception:
                app.setStyleSheet("")
            self._is_dark = True
            self.statusBar().showMessage("다크 테마 적용", 2000)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            if self.isHidden() or self.isMinimized():
                self.showNormal()
            else:
                self.hide()

    def _on_documents_changed(self) -> None:
        self.statusBar().showMessage("문서 목록 갱신", 1500)
