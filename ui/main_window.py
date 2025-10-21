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

        # 사이드바(대화/업로드/설정 탭)
        self.sidebar_tabs = QTabWidget(self)
        self.history_list = QListWidget(self)
        self.history_list.setSelectionMode(QListWidget.ExtendedSelection)  # Ctrl+클릭으로 다중 선택
        self.new_chat_btn = QPushButton("새로운 대화", self)
        self.history_load_btn = QPushButton("대화 불러오기", self)
        self.history_export_btn = QPushButton("내보내기", self)
        self.history_delete_btn = QPushButton("선택삭제", self)  # 이름 변경

        hist_wrap = QWidget(self)
        hist_layout = QVBoxLayout(hist_wrap)
        hist_layout.setContentsMargins(6, 6, 6, 6)
        hist_layout.addWidget(QLabel("대화 목록"))
        hist_layout.addWidget(self.history_list)
        btn_row = QVBoxLayout()
        btn_row.addWidget(self.new_chat_btn)
        btn_row.addWidget(self.history_load_btn)
        btn_row.addWidget(self.history_export_btn)
        btn_row.addWidget(self.history_delete_btn)  # 버튼명 변경
        hist_layout.addLayout(btn_row)

        self.doc_tab = DocumentWidget(self, document_processor=self.document_processor, vector_manager=self.vector_manager)
        self.settings_tab = SettingsWidget(self, vector_manager=self.vector_manager, rag_chain=self.rag_chain)

        self.sidebar_tabs.addTab(hist_wrap, "대화")
        self.sidebar_tabs.addTab(self.doc_tab, "업로드")
        self.sidebar_tabs.addTab(self.settings_tab, "설정")
        
        # 기본 탭을 이력으로 설정
        self.sidebar_tabs.setCurrentIndex(0)

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
        self.new_chat_btn.clicked.connect(self._start_new_chat)
        self.history_load_btn.clicked.connect(self._load_history_to_chat)
        self.history_export_btn.clicked.connect(self._export_history)
        self.history_delete_btn.clicked.connect(self._delete_selected_histories)  # 버튼명 변경
        
        # 이력 목록 더블클릭 시 대화 불러오기
        self.history_list.itemDoubleClicked.connect(lambda: self._load_history_to_chat())

    def _init_menu_toolbar(self) -> None:
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        # 메뉴: 파일(종료만 유지)
        file_menu = menubar.addMenu("파일")
        act_quit = QAction("종료", self)
        act_quit.setShortcut(QKeySequence.Quit)
        file_menu.addAction(act_quit)
        act_quit.triggered.connect(QApplication.instance().quit)

        # 메뉴: 설정
        settings_menu = menubar.addMenu("설정")
        act_theme = QAction("테마 변경", self)
        settings_menu.addAction(act_theme)
        act_theme.triggered.connect(self._toggle_theme)

        # 툴바 제거: 상단에 아무 액션도 표시하지 않음
        # (열기/삭제는 각 탭에서 사용)

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

    def _start_new_chat(self) -> None:
        """새로운 대화 세션 시작"""
        # 채팅창 초기화
        self.chat_tab.messages.clear()
        self.chat_tab.list_view.clear()
        
        # 새로운 세션 ID 생성
        import time
        self.session_id = f"session_{int(time.time() * 1000)}"
        
        # 이력 목록 새로고침
        self._reload_history_sidebar()
        
        self.statusBar().showMessage("새로운 대화를 시작했습니다", 2000)
    
    def _reload_history_sidebar(self) -> None:
        self.history_list.clear()
        self._session_map = {}  # 인덱스 -> 세션 ID 매핑
        sessions = self.history_mgr.get_all_sessions_with_info()
        for idx, s in enumerate(sessions):
            self.history_list.addItem(f"{s['title']}  ({s['message_count']})")
            self._session_map[idx] = s['session_id']

    def _export_history(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "내보내기", "history.json", "JSON (*.json)")
        if not path:
            return
        self.history_mgr.export_history(self.session_id, path)

    def _load_history_to_chat(self) -> None:
        """선택한 세션의 대화 내용을 채팅창에 불러오기"""
        current_row = self.history_list.currentRow()
        if current_row < 0:
            self.statusBar().showMessage("불러올 이력을 선택해주세요", 2000)
            return
        
        session_id = self._session_map.get(current_row)
        if not session_id:
            return
        
        # 세션 데이터 로드
        history = self.history_mgr.load_history(session_id)
        if not history:
            self.statusBar().showMessage("이력을 불러올 수 없습니다", 2000)
            return
        
        # 채팅창 초기화 및 메시지 추가
        self.chat_tab.messages.clear()
        self.chat_tab.list_view.clear()
        
        for record in history:
            question = record.get('question', '')
            answer = record.get('answer', '')
            sources = record.get('sources', [])
            
            if question:
                self.chat_tab.messages.append({"role": "user", "content": question})
                self.chat_tab._append_bubble(question, is_user=True)
            
            if answer:
                self.chat_tab.messages.append({"role": "assistant", "content": answer})
                self.chat_tab._append_bubble(answer, is_user=False)
                
                # 출처 표시
                if sources:
                    source_text = self.chat_tab._format_sources(sources)
                    self.chat_tab._append_bubble(f"[출처]\n{source_text}", is_user=False)
        
        # 현재 세션 ID 업데이트
        self.session_id = session_id
        self.statusBar().showMessage(f"대화 내용을 불러왔습니다 ({len(history)}개 메시지)", 3000)

    def _delete_selected_histories(self) -> None:
        """선택된 대화 이력들 삭제"""
        from PySide6.QtWidgets import QMessageBox
        
        selected_items = self.history_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "선택 없음", "삭제할 대화를 선택해주세요.")
            return
        
        # 확인 메시지
        count = len(selected_items)
        reply = QMessageBox.question(
            self, 
            "삭제 확인", 
            f"{count}개의 대화를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            # 선택된 항목들의 인덱스로 세션 ID 찾기
            for item in selected_items:
                row = self.history_list.row(item)
                if row in self._session_map:
                    session_id = self._session_map[row]
                    self.history_mgr.clear_history(session_id)
                    print(f"삭제된 세션: {session_id}")  # 디버그용
            
            # 목록 새로고침
            self._reload_history_sidebar()
            QMessageBox.information(self, "완료", f"{count}개의 대화가 삭제되었습니다.")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"대화 삭제 실패:\n{e}")
            print(f"삭제 오류: {e}")  # 디버그용

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
