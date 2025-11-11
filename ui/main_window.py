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

        # 공용 DB 재접속 메뉴
        settings_menu.addSeparator()
        act_reconnect_shared_db = QAction("공용DB 재접속", self)
        settings_menu.addAction(act_reconnect_shared_db)
        act_reconnect_shared_db.triggered.connect(self._reconnect_shared_db)

        # 메뉴: 도움말
        help_menu = menubar.addMenu("도움말")
        act_usage = QAction("사용방법", self)
        help_menu.addAction(act_usage)
        act_usage.triggered.connect(self._show_usage_guide)

        # 메뉴: 기타
        etc_menu = menubar.addMenu("기타")
        act_about = QAction("제작자", self)
        etc_menu.addAction(act_about)
        act_about.triggered.connect(self._show_about)

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

    def _show_usage_guide(self) -> None:
        """사용방법 도움말 표시"""
        from PySide6.QtWidgets import QMessageBox

        usage_text = """
<h3>OC RAG 시스템 사용방법</h3>

<p><b>1. 문서 업로드</b></p>
<ul>
  <li>좌측 '업로드' 탭에서 PDF, PPTX, Excel 파일 선택</li>
  <li>여러 파일 동시 업로드 가능</li>
  <li>업로드된 문서는 자동으로 임베딩되어 검색 가능</li>
</ul>

<p><b>2. 질문하기</b></p>
<ul>
  <li>하단 입력창에 질문 작성</li>
  <li>Enter 또는 '전송' 버튼으로 전송</li>
  <li>AI가 문서 기반으로 답변 생성</li>
  <li>답변에는 출처(파일명, 페이지 번호) 표시</li>
</ul>

<p><b>3. 대화 관리</b></p>
<ul>
  <li>'대화' 탭에서 이전 대화 내역 확인</li>
  <li>'새로운 대화'로 새 세션 시작</li>
  <li>더블클릭으로 대화 불러오기</li>
  <li>'내보내기'로 대화 저장</li>
</ul>

<p><b>4. 설정</b></p>
<ul>
  <li>'설정' 탭에서 LLM 모델 및 임베딩 설정</li>
  <li>API 타입, 모델명, Base URL 설정 가능</li>
  <li>설정 변경 후 '설정 저장' 클릭</li>
</ul>

<p><b>5. 팁</b></p>
<ul>
  <li>구체적인 질문일수록 정확한 답변</li>
  <li>페이지 번호로 원본 문서 참조 가능</li>
  <li>대화 이력은 자동 저장됨</li>
</ul>
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("사용방법")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(usage_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec()

    def _show_about(self) -> None:
        """제작자 정보 표시"""
        from PySide6.QtWidgets import QMessageBox

        about_text = """
<h3>OC RAG 문서 시스템 v3.4.1</h3>

<p><b>제작자</b></p>
<p>OC연구/개발5팀 유남석</p>

<p><b>주요 기능</b></p>
<ul>
  <li>NotebookLM 스타일 인라인 인용</li>
  <li>고급 PDF/PPTX 청킹</li>
  <li>하이브리드 검색 (벡터 + BM25)</li>
  <li>Re-ranker 기반 정확도 향상</li>
  <li>다중 쿼리 확장</li>
</ul>

<p><b>개발 기간</b></p>
<p>2024.10.14 - 2025.01.XX</p>
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("제작자 정보")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec()

    def _reconnect_shared_db(self) -> None:
        """공용 DB 재접속 시도"""
        from PySide6.QtWidgets import QMessageBox

        try:
            # Vector Manager를 통해 재접속 시도
            success = self.vector_manager.reconnect_shared_db()

            if success:
                # 성공 메시지
                QMessageBox.information(
                    self,
                    "공용 DB 재접속 성공",
                    f"공용 DB에 성공적으로 재접속했습니다.\n\n"
                    f"경로: {self.vector_manager.shared_db_path}"
                )

                # UI 상태 업데이트
                self.doc_tab._update_shared_db_status()
                self.chat_tab._update_search_mode_status()

                self.statusBar().showMessage("공용 DB 재접속 성공", 3000)
            else:
                # 실패 메시지
                QMessageBox.warning(
                    self,
                    "공용 DB 재접속 실패",
                    "공용 DB를 찾을 수 없거나 접근할 수 없습니다.\n\n"
                    "다음 사항을 확인해주세요:\n"
                    "1. 설정 탭에서 공유 DB 사용이 활성화되어 있는지 확인\n"
                    "2. 설정 탭에서 공유 DB 경로가 올바르게 설정되어 있는지 확인\n"
                    "3. 네트워크 드라이브가 연결되어 있는지 확인\n"
                    "4. 설정된 경로에 chroma.sqlite3 파일이 있는지 확인"
                )
                self.statusBar().showMessage("공용 DB 재접속 실패", 3000)

        except Exception as e:
            QMessageBox.critical(
                self,
                "오류",
                f"공용 DB 재접속 중 오류가 발생했습니다:\n\n{str(e)}"
            )
            self.statusBar().showMessage(f"공용 DB 재접속 오류: {str(e)}", 5000)
