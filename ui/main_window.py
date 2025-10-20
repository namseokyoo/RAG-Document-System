from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout, QToolBar, QMenuBar,
    QSystemTrayIcon, QMenu, QApplication, QSplitter, QListWidget, QLabel, QStackedWidget, QPushButton, QFileDialog
)

from .chat_widget import ChatWidget
from .document_widget import DocumentWidget
from .settings_widget import SettingsWidget
from utils.chat_history import ChatHistoryManager


class MainWindow(QMainWindow):
    def __init__(self, document_processor=None, vector_manager=None, rag_chain=None) -> None:
        super().__init__()
        self.setWindowTitle("OC_RAG (Desktop)")
        self.resize(1200, 800)

        self.document_processor = document_processor
        self.vector_manager = vector_manager
        self.rag_chain = rag_chain
        self.history_mgr = ChatHistoryManager()
        self.session_id = "current_session"

        self._is_dark = True  # 기본 다크

        self._init_ui()
        self._init_menu_toolbar()
        self._init_tray()
        self._init_statusbar()
        self._init_autosave()

    def _init_ui(self) -> None:
        # 좌우 분할: 왼쪽 사이드바, 오른쪽 메인(채팅)
        splitter = QSplitter(Qt.Horizontal, self)

        # 사이드바(이력/업로드/설정 탭)
        self.sidebar_tabs = QTabWidget(self)
        self.history_list = QListWidget(self)
        self.history_reload_btn = QPushButton("새로고침", self)
        self.history_export_btn = QPushButton("내보내기", self)
        self.history_import_btn = QPushButton("불러오기", self)
        self.history_clear_btn = QPushButton("전체삭제", self)

        hist_wrap = QWidget(self)
        hist_layout = QVBoxLayout(hist_wrap)
        hist_layout.setContentsMargins(6, 6, 6, 6)
        hist_layout.addWidget(QLabel("채팅 이력"))
        hist_layout.addWidget(self.history_list)
        btn_row = QVBoxLayout()
        btn_row.addWidget(self.history_reload_btn)
        btn_row.addWidget(self.history_export_btn)
        btn_row.addWidget(self.history_import_btn)
        btn_row.addWidget(self.history_clear_btn)
        hist_layout.addLayout(btn_row)

        self.doc_tab = DocumentWidget(self, document_processor=self.document_processor, vector_manager=self.vector_manager)
        self.settings_tab = SettingsWidget(self, vector_manager=self.vector_manager, rag_chain=self.rag_chain)

        self.sidebar_tabs.addTab(hist_wrap, "이력")
        self.sidebar_tabs.addTab(self.doc_tab, "업로드")
        self.sidebar_tabs.addTab(self.settings_tab, "설정")

        # 메인 채팅 영역
        self.chat_tab = ChatWidget(self, rag_chain=self.rag_chain)
        self.chat_tab.answer_committed.connect(self._on_answer_committed)

        splitter.addWidget(self.sidebar_tabs)
        splitter.addWidget(self.chat_tab)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        self.setCentralWidget(splitter)

        # 문서 변경 이벤트 연결
        self.doc_tab.documents_changed.connect(self._on_documents_changed)
        # (상태바 연결은 기존 progress_message.connect 로 반영됨)

        # 이력 로딩
        self._reload_history_sidebar()

        # 사이드 이벤트 연결
        self.history_reload_btn.clicked.connect(self._reload_history_sidebar)
        self.history_export_btn.clicked.connect(self._export_history)
        self.history_import_btn.clicked.connect(self._import_history)
        self.history_clear_btn.clicked.connect(self._clear_current_history)

    def _init_menu_toolbar(self) -> None:
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        # 메뉴: 파일(종료만 유지), 보기 메뉴 제거
        file_menu = menubar.addMenu("파일")
        act_quit = QAction("종료", self)
        act_quit.setShortcut(QKeySequence.Quit)
        file_menu.addAction(act_quit)
        act_quit.triggered.connect(QApplication.instance().quit)

        # 툴바 제거: 상단에 아무 액션도 표시하지 않음
        # (열기/삭제/테마 토글은 각 탭/설정에서 사용)

    def _init_tray(self) -> None:
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

    def _init_autosave(self) -> None:
        # 60초 간격 자동 저장(마지막 메시지를 기준으로 현재 세션 저장)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start(60000)

    def _autosave(self) -> None:
        # ChatWidget 메시지 히스토리를 파일로 저장
        if not self.chat_tab.messages:
            return
        try:
            # 간단 저장: 마지막 Q/A만 저장 (확장 여지)
            q = ""
            a = ""
            for m in reversed(self.chat_tab.messages):
                if not a and m.get("role") == "assistant":
                    a = m.get("content", "")
                if not q and m.get("role") == "user":
                    q = m.get("content", "")
                if q and a:
                    break
            if q or a:
                self.history_mgr.save_message(self.session_id, q, a, [])
        except Exception:
            pass

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            if self.isHidden() or self.isMinimized():
                self.showNormal()
            else:
                self.hide()

    def _on_documents_changed(self) -> None:
        self.statusBar().showMessage("문서 목록 갱신", 1500)

    def _on_answer_committed(self, question: str, answer: str, sources: list) -> None:
        self.history_mgr.save_message(self.session_id, question, answer, sources)
        self._reload_history_sidebar()

    def _reload_history_sidebar(self) -> None:
        self.history_list.clear()
        sessions = self.history_mgr.get_all_sessions_with_info()
        for s in sessions:
            self.history_list.addItem(f"{s['title']}  ({s['message_count']})")

    def _export_history(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "내보내기", "history.json", "JSON (*.json)")
        if not path:
            return
        self.history_mgr.export_history(self.session_id, path)

    def _import_history(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "불러오기", "", "JSON (*.json)")
        if not path:
            return
        # 현재 세션에 덮어쓰기
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 간단히 첫 레코드만 저장해 세션 생성 효과
            for rec in data:
                self.history_mgr.save_message(self.session_id, rec.get('question',''), rec.get('answer',''), rec.get('sources',[]))
            self._reload_history_sidebar()
        except Exception:
            pass

    def _clear_current_history(self) -> None:
        self.history_mgr.clear_history(self.session_id)
        self._reload_history_sidebar()

    def _toggle_theme(self) -> None:
        app = QApplication.instance()
        if getattr(self, "_is_dark", True):
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
