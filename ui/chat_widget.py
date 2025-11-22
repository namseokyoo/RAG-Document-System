from typing import List, Dict, Optional
from PySide6.QtCore import Qt, Signal, QObject, QThread, QUrl
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
                               QListWidgetItem, QTextEdit, QTextBrowser, QLabel, QRadioButton, QButtonGroup, QCompleter, QMessageBox)
from PySide6.QtCore import QStringListModel
from PySide6.QtGui import QKeySequence, QKeyEvent, QTextCursor, QDesktopServices
from PySide6.QtWidgets import QApplication
import re
import os
import sys
import subprocess


class StreamWorker(QObject):
    chunk = Signal(str)
    finished = Signal()
    error = Signal(str)  # 에러 메시지 전달용

    def __init__(self, rag_chain, question: str, chat_history: List[Dict[str, str]], search_mode: str = "integrated"):
        super().__init__()
        self.rag_chain = rag_chain
        self.question = question
        self.chat_history = chat_history
        self.search_mode = search_mode

    def run(self) -> None:
        try:
            for part in self.rag_chain.query_stream(self.question, chat_history=self.chat_history, search_mode=self.search_mode):
                self.chunk.emit(part)
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 스트리밍 오류: {error_msg}")
            # 사용자 친화적 에러 메시지 생성
            if "404" in error_msg or "page not found" in error_msg.lower():
                friendly_msg = (
                    "OpenAI API 연결 오류가 발생했습니다.\n\n"
                    "가능한 원인:\n"
                    "1. 인터넷 연결 확인\n"
                    "2. API 키가 올바른지 확인 (설정 탭에서 확인)\n"
                    "3. 모델명이 올바른지 확인 (gpt-4o-mini 등)\n\n"
                    f"상세 오류: {error_msg[:200]}"
                )
            elif "401" in error_msg or "authentication" in error_msg.lower():
                friendly_msg = (
                    "OpenAI API 인증 오류가 발생했습니다.\n\n"
                    "API 키가 올바르지 않거나 만료되었습니다.\n"
                    "설정 탭에서 API 키를 다시 확인해주세요."
                )
            else:
                friendly_msg = f"오류가 발생했습니다: {error_msg[:300]}"
            
            self.chunk.emit(f"❌ {friendly_msg}")
            self.error.emit(error_msg)
        finally:
            self.finished.emit()


class ChatBubble(QWidget):
    linkClicked = Signal(str)  # 링크 클릭 시 파일명 전달

    def __init__(self, text: str, is_user: bool, max_width: Optional[int] = None, is_dark: bool = True) -> None:
        super().__init__()

        self.text = text
        self.is_user = is_user
        self.max_width = max_width
        self.is_dark = is_dark

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)

        # QTextBrowser를 사용하여 텍스트 선택 및 링크 클릭 가능하게 함
        self.text_edit = QTextBrowser()
        self.text_edit.setReadOnly(True)  # 읽기 전용
        self.text_edit.setHtml(self._to_html(text))
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 스크롤바 숨김
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 링크 클릭 활성화 (외부 링크 자동 열기 비활성화)
        self.text_edit.setOpenLinks(False)  # 링크를 직접 처리
        self.text_edit.anchorClicked.connect(self._on_link_clicked)

        # 텍스트 선택 활성화
        textCursor = self.text_edit.textCursor()
        textCursor.clearSelection()
        self.text_edit.setTextCursor(textCursor)

        # 리치 텍스트 허용 (HTML 렌더링)
        self.text_edit.setAcceptRichText(True)

        # 최대 너비 설정 (사용자 버블만 더 크게)
        if max_width:
            if is_user:
                # 사용자 버블은 더 크게 (1.5배)
                self.text_edit.setMaximumWidth(int(max_width * 1.5))
            else:
                self.text_edit.setMaximumWidth(max_width)

        # 테마 적용
        self._apply_theme()

        # 레이아웃 설정
        if is_user:
            layout.addStretch(1)  # 왼쪽 여백
            layout.addWidget(self.text_edit, 1)  # 오른쪽에 버블 (크게!)
        else:
            layout.addWidget(self.text_edit, 1)  # 왼쪽에 버블
            layout.addStretch(0)  # 오른쪽 여백

    def _apply_theme(self):
        """현재 테마에 맞게 스타일 적용"""
        if self.is_dark:
            # 다크 테마
            background_color = "#1769aa" if self.is_user else "#2b2b2b"
            text_color = "white" if self.is_user else "#f0f0f0"
        else:
            # 라이트 테마
            background_color = "#0078d4" if self.is_user else "#e8e8e8"
            text_color = "white" if self.is_user else "#000000"

        # 폰트 크기: 사용자 메시지 12pt, AI 응답 11pt
        font_size = "12pt" if self.is_user else "11pt"
        code_font_size = "11pt" if self.is_user else "10pt"

        self.text_edit.setStyleSheet(f"""
            QTextBrowser {{
                padding: 8px 10px;
                border-radius: 8px;
                background: {background_color};
                color: {text_color};
                border: none;
                font-size: {font_size};
            }}
            QTextBrowser::selected {{
                background: rgba(255, 255, 255, 0.3);
                color: {text_color};
            }}
        """)

        # HTML 내 코드 블록 스타일 설정
        self.text_edit.document().setDefaultStyleSheet(f"""
            code {{
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: {code_font_size};
                background-color: rgba(255, 255, 255, 0.1);
                padding: 2px 4px;
                border-radius: 3px;
            }}
            pre {{
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: {code_font_size};
                background-color: rgba(255, 255, 255, 0.1);
                padding: 8px;
                border-radius: 4px;
                white-space: pre-wrap;
            }}
        """)

    def set_theme(self, is_dark: bool):
        """테마 변경"""
        self.is_dark = is_dark
        self._apply_theme()
    
    def _update_height(self):
        """텍스트 내용에 맞게 높이 조정"""
        # 문서 너비 설정 (최대 너비 기준)
        doc = self.text_edit.document()
        if self.max_width:
            doc.setTextWidth(self.text_edit.viewport().width())
        else:
            doc.setTextWidth(self.text_edit.viewport().width())
        
        # 문서 높이 계산
        doc_height = doc.size().height()
        # 여백 추가 (padding + 약간의 여유)
        height = int(doc_height) + 25
        
        # 최소 높이 설정
        min_height = 40
        # 최대 높이 제한 (너무 긴 경우 스크롤 추가 가능하도록)
        max_height = 800
        
        final_height = max(min_height, min(height, max_height))
        self.text_edit.setFixedHeight(final_height)
        
        return final_height
    
    def sizeHint(self):
        """컨텐츠에 맞게 크기 조정"""
        from PySide6.QtCore import QSize
        
        # 높이 업데이트
        height = self._update_height()
        
        # 레이아웃의 sizeHint를 가져오되, 높이는 계산된 값 사용
        layout_hint = self.layout().sizeHint()
        width = layout_hint.width() if layout_hint.width() > 0 else 500
        
        return QSize(width, height)

    def _md(self, text: str) -> str:
        # 매우 경량 마크다운: **bold**, `code`, ```block```, [text](url)
        def esc(t: str) -> str:
            return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        t = esc(text)
        # code block
        t = re.sub(r"```([\s\S]*?)```", r"<pre><code>\1</code></pre>", t)
        # inline code
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        # bold
        t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
        # links (supports http://, https://, and openfile:///)
        t = re.sub(r"\[([^\]]+)\]\(((?:https?://|openfile:///)[^)]+)\)", r"<a href='\2'>\1</a>", t)
        return t.replace("\n", "<br>")

    def _to_html(self, text: str) -> str:
        return self._md(text)

    def _on_link_clicked(self, url: QUrl) -> None:
        """링크 클릭 시 처리 - openfile:/// 스킴 처리"""
        url_str = url.toString()
        if url_str.startswith("openfile:///"):
            # 파일명 추출 (openfile:/// 이후 부분)
            file_name = url_str[len("openfile:///"):]
            self.linkClicked.emit(file_name)
        else:
            # 일반 URL은 기본 브라우저로 열기
            QDesktopServices.openUrl(url)


class ChatInput(QTextEdit):
    sendRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent

        # Placeholder 힌트 추가
        self.setPlaceholderText("메시지 입력 (Shift+Enter: 줄바꿈, @: 파일 언급)")

        # 파일명 자동완성 설정
        self.file_completer = QCompleter(self)
        self.file_completer.setWidget(self)
        self.file_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.file_completer.setCompletionMode(QCompleter.PopupCompletion)

        # QStringListModel로 파일 목록 관리
        self.file_list_model = QStringListModel(self)
        self.file_completer.setModel(self.file_list_model)

        # 자동완성 선택 시 삽입
        self.file_completer.activated.connect(self._insert_completion)

        # 텍스트 변경 감지
        self.textChanged.connect(self._check_file_mention)

        # 멘션 시작 위치 저장
        self._mention_start_pos = -1

    def _check_file_mention(self):
        """@기호 감지 및 자동완성 트리거"""
        cursor = self.textCursor()
        text = self.toPlainText()
        pos = cursor.position()

        # 현재 위치 기준으로 "@" 찾기
        if pos > 0 and text[pos-1:pos] == '@':
            # 멘션 시작
            self._mention_start_pos = pos - 1
            self._update_file_list()
            self.file_completer.complete()
        elif self._mention_start_pos >= 0:
            # 멘션 진행 중: "@" 이후 텍스트 가져오기
            mention_text = text[self._mention_start_pos+1:pos]

            # 공백이나 줄바꿈이 나오면 멘션 종료
            if ' ' in mention_text or '\n' in mention_text:
                self._mention_start_pos = -1
                self.file_completer.popup().hide()
            else:
                # 입력에 따라 필터링
                self.file_completer.setCompletionPrefix(mention_text)
                if mention_text:  # 텍스트가 있을 때만 팝업 표시
                    self.file_completer.complete()

    def _update_file_list(self):
        """VectorStore에서 파일 목록 가져오기"""
        if self.parent_widget and hasattr(self.parent_widget, 'rag_chain'):
            rag_chain = self.parent_widget.rag_chain
            if rag_chain and hasattr(rag_chain, 'vectorstore_manager'):
                try:
                    # 문서 목록 가져오기
                    docs_list = rag_chain.vectorstore_manager.get_documents_list()
                    # 파일명만 추출 (중복 제거)
                    filenames = list(set([doc['file_name'] for doc in docs_list if 'file_name' in doc]))
                    self.file_list_model.setStringList(filenames)
                except Exception as e:
                    print(f"파일 목록 가져오기 실패: {e}")
                    self.file_list_model.setStringList([])

    def _insert_completion(self, completion):
        """자동완성 선택 시 텍스트 삽입"""
        if self._mention_start_pos < 0:
            return

        cursor = self.textCursor()
        # "@" 부터 현재 위치까지 선택
        cursor.setPosition(self._mention_start_pos)
        cursor.setPosition(self.textCursor().position(), QTextCursor.KeepAnchor)
        # 선택 영역을 "@파일명"으로 대체
        cursor.insertText(f"@{completion}")
        self.setTextCursor(cursor)

        self._mention_start_pos = -1

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # 파일 자동완성 팝업이 보이는 경우 Tab/Enter로 선택 가능하게
        popup = self.file_completer.popup()
        if popup.isVisible():
            if event.key() in (Qt.Key_Tab, Qt.Key_Return, Qt.Key_Enter):
                # 팝업에서 현재 선택된 항목 가져오기
                index = popup.currentIndex()
                if index.isValid():
                    completion = popup.model().data(index)
                    self.file_completer.activated.emit(completion)
                    event.accept()
                    return

        # 자동완성이 아닌 경우의 Enter/Tab 처리
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                # 줄바꿈
                return super().keyPressEvent(event)
            # 전송
            self.sendRequested.emit()
            return

        return super().keyPressEvent(event)


class ChatWidget(QWidget):
    answer_committed = Signal(str, str, list)  # question, answer, sources

    def __init__(self, parent=None, rag_chain=None) -> None:
        super().__init__(parent)
        self.rag_chain = rag_chain
        self.messages: List[Dict[str, str]] = []
        self._is_dark = True  # 기본 다크 테마
        self._init_ui()
        self._connect()
        self._update_search_mode_status()  # 공유 DB 상태에 따라 검색 모드 활성화/비활성화
        self._stream_thread: Optional[QThread] = None
        self._stream_worker: Optional[StreamWorker] = None
        self._assistant_buffer: str = ""
        self._last_question: str = ""

    def _update_search_mode_status(self) -> None:
        """공유 DB 상태에 따라 검색 모드 라디오 버튼 활성화/비활성화"""
        if self.rag_chain and hasattr(self.rag_chain, 'vectorstore_manager'):
            vector_manager = self.rag_chain.vectorstore_manager
            if hasattr(vector_manager, 'shared_db_enabled'):
                if not vector_manager.shared_db_enabled:
                    # 공유 DB 비활성화 시 공유 DB 검색 옵션만 비활성화
                    self.search_shared_radio.setEnabled(False)
                    self.search_shared_radio.setToolTip("공유 DB가 연결되지 않았습니다")

                    # 통합 검색은 활성화 유지 (개인 DB만 검색하도록 자동 폴백됨)
                    self.search_integrated_radio.setEnabled(True)
                    self.search_integrated_radio.setToolTip("공유 DB가 없어 개인 DB만 검색됩니다")

                    # 통합 검색이 선택되어 있으면 유지, 공유 DB가 선택되어 있으면 통합으로 변경
                    if self.search_shared_radio.isChecked():
                        self.search_integrated_radio.setChecked(True)
                else:
                    # 공유 DB 활성화 시 모든 옵션 활성화
                    self.search_shared_radio.setEnabled(True)
                    self.search_shared_radio.setToolTip("")
                    self.search_integrated_radio.setEnabled(True)
                    self.search_integrated_radio.setToolTip("")

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 검색 범위 선택 (상단 오른쪽)
        search_mode_layout = QHBoxLayout()
        search_mode_label = QLabel("🔍 검색 범위:", self)
        search_mode_label.setStyleSheet("QLabel { font-weight: bold; background-color: transparent; }")

        self.search_mode_group = QButtonGroup(self)
        self.search_integrated_radio = QRadioButton("통합 검색", self)
        self.search_personal_radio = QRadioButton("개인 DB", self)
        self.search_shared_radio = QRadioButton("공유 DB", self)

        self.search_integrated_radio.setChecked(True)  # 기본값: 통합 검색

        # 라디오 버튼 스타일 적용 (테마 자동 적용)
        # qdarkstyle이 있으면 다크 테마, 없으면 라이트 테마 자동 적용
        radio_style = """
            QRadioButton {
                background-color: transparent;
                spacing: 5px;
            }
        """
        self.search_integrated_radio.setStyleSheet(radio_style)
        self.search_personal_radio.setStyleSheet(radio_style)
        self.search_shared_radio.setStyleSheet(radio_style)

        self.search_mode_group.addButton(self.search_integrated_radio, 0)
        self.search_mode_group.addButton(self.search_personal_radio, 1)
        self.search_mode_group.addButton(self.search_shared_radio, 2)

        # 사이드바 토글 버튼
        self.toggle_sidebar_btn = QPushButton("◀ 접기", self)
        self.toggle_sidebar_btn.setFixedSize(70, 28)
        self.toggle_sidebar_btn.setToolTip("사이드바 접기/펼치기")
        search_mode_layout.addWidget(self.toggle_sidebar_btn)

        # 새 대화 버튼
        self.new_chat_btn = QPushButton("➕ 새 대화", self)
        self.new_chat_btn.setFixedSize(90, 28)
        self.new_chat_btn.setToolTip("새로운 대화 시작")
        search_mode_layout.addWidget(self.new_chat_btn)

        search_mode_layout.addStretch()
        search_mode_layout.addWidget(search_mode_label)
        search_mode_layout.addWidget(self.search_integrated_radio)
        search_mode_layout.addWidget(self.search_personal_radio)
        search_mode_layout.addWidget(self.search_shared_radio)

        layout.addLayout(search_mode_layout)

        self.list_view = QListWidget(self)
        self.list_view.setUniformItemSizes(False)
        self.list_view.setWordWrap(True)
        self.list_view.setAlternatingRowColors(False)

        input_row = QHBoxLayout()
        self.input_edit = ChatInput(self)
        self.input_edit.setFixedHeight(80)
        self.send_btn = QPushButton("전송", self)
        self.copy_btn = QPushButton("복사", self)

        input_row.addWidget(self.input_edit)
        input_row.addWidget(self.send_btn)
        input_row.addWidget(self.copy_btn)

        layout.addWidget(self.list_view)
        layout.addLayout(input_row)

        self.send_btn.setShortcut(QKeySequence("Ctrl+Return"))
        self.copy_btn.setShortcut(QKeySequence("Ctrl+Shift+C"))

    def _connect(self) -> None:
        self.send_btn.clicked.connect(self.on_send)
        self.copy_btn.clicked.connect(self.copy_last_answer)
        self.input_edit.sendRequested.connect(self.on_send)

    def _bubble_widths(self) -> (int, int):
        vw = max(500, self.list_view.viewport().width())  # 최소 크기 더 증가
        user_w = int(vw * 0.8)  # 사용자 80% (화면의 대부분)
        ai_w = int(vw * 0.95)  # AI 95% (여백 고려)
        return user_w, ai_w

    def _append_bubble(self, text: str, is_user: bool) -> None:
        user_w, ai_w = self._bubble_widths()
        max_w = user_w if is_user else ai_w
        widget = ChatBubble(text, is_user, max_width=max_w, is_dark=self._is_dark)

        # 링크 클릭 시그널 연결
        widget.linkClicked.connect(self._on_file_link_clicked)

        item = QListWidgetItem(self.list_view)

        # 높이를 정확하게 계산하여 설정
        size_hint = widget.sizeHint()
        item.setSizeHint(size_hint)

        self.list_view.addItem(item)
        self.list_view.setItemWidget(item, widget)

        # 위젯이 화면에 표시된 후 높이 재조정
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._adjust_bubble_height(item, widget))

        self.list_view.scrollToBottom()
    
    def _adjust_bubble_height(self, item, widget):
        """버블 높이를 실제 렌더링 후 재조정"""
        size_hint = widget.sizeHint()
        if item.sizeHint().height() != size_hint.height():
            item.setSizeHint(size_hint)

    def on_send(self) -> None:
        question = self.input_edit.toPlainText().strip()
        if not question:
            return
        self.input_edit.clear()

        self._last_question = question

        # 사용자 메시지
        self.messages.append({"role": "user", "content": question})
        self._append_bubble(question, is_user=True)

        # 어시스턴트 스트리밍 시작 - 초기 상태 표시
        self._assistant_buffer = ""
        self._append_bubble("🔍 문서 검색 중...", is_user=False)  # 상태 메시지

        if not self.rag_chain:
            self._update_last_assistant_bubble("❌ RAGChain이 초기화되지 않았습니다")
            return

        # 선택된 검색 모드 결정
        if self.search_integrated_radio.isChecked():
            search_mode = "integrated"
        elif self.search_shared_radio.isChecked():
            search_mode = "shared"
        else:
            search_mode = "personal"

        self._stream_thread = QThread(self)
        self._stream_worker = StreamWorker(self.rag_chain, question, self.messages, search_mode)
        self._stream_worker.moveToThread(self._stream_thread)
        self._stream_thread.started.connect(self._stream_worker.run)
        self._stream_worker.chunk.connect(self._on_stream_chunk)
        self._stream_worker.finished.connect(self._on_stream_finished)
        self._stream_worker.finished.connect(self._stream_thread.quit)
        self._stream_worker.finished.connect(self._stream_worker.deleteLater)
        self._stream_thread.finished.connect(self._stream_thread.deleteLater)
        self._stream_thread.start()

    def _update_last_assistant_bubble(self, text: str) -> None:
        row = self.list_view.count() - 1
        if row < 0:
            return
        item = self.list_view.item(row)
        widget = self.list_view.itemWidget(item)
        if isinstance(widget, ChatBubble):
            # 기존 위젯의 텍스트만 업데이트 (성능 향상)
            user_w, ai_w = self._bubble_widths()
            max_w = ai_w
            new_widget = ChatBubble(text, is_user=False, max_width=max_w, is_dark=self._is_dark)

            # 링크 클릭 시그널 연결
            new_widget.linkClicked.connect(self._on_file_link_clicked)

            # 높이 재계산
            size_hint = new_widget.sizeHint()
            item.setSizeHint(size_hint)

            self.list_view.setItemWidget(item, new_widget)

            # 위젯이 화면에 표시된 후 높이 재조정
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._adjust_bubble_height(item, new_widget))

            self.list_view.scrollToBottom()

    def _format_classification(self, classification: Dict) -> str:
        """질문 분류 정보 포맷팅"""
        q_type = classification.get('type', 'unknown')
        confidence = classification.get('confidence', 0.0)
        method = classification.get('method', 'unknown')
        multi_query = classification.get('multi_query', False)
        max_results = classification.get('max_results', 0)
        reranker_k = classification.get('reranker_k', 0)
        max_tokens = classification.get('max_tokens', 0)

        # 질문 유형 라벨
        type_labels = {
            'simple': '단순 질문',
            'normal': '일반 질문',
            'complex': '복잡한 질문',
            'exhaustive': '전체 조회'
        }
        type_label = type_labels.get(q_type, q_type)

        # 분류 방법 라벨
        method_labels = {
            'rule-based': '규칙 기반',
            'llm': 'LLM 판단',
            'hybrid': '하이브리드'
        }
        method_label = method_labels.get(method, method)

        lines = [
            "[질문 분류]",
            f"유형: **{type_label}** (신뢰도: {confidence:.0%})",
            f"분류 방법: {method_label}",
            f"최적화: Multi-Query={'ON' if multi_query else 'OFF'}, Max Results={max_results}, Rerank K={reranker_k}, Max Tokens={max_tokens}"
        ]

        return "\n".join(lines)

    def _format_sources(self, sources: List[Dict]) -> str:
        """참고문서를 파일명만 표시 (중복 제거, 링크 포함)"""
        # 파일명만 수집 (중복 제거)
        filenames = list(set([s.get('file_name', '?') for s in sources]))

        # 파일명을 클릭 가능한 링크로 표시
        lines = []
        for file_name in sorted(filenames):
            clickable_file = f"[{file_name}](openfile:///{file_name})"
            lines.append(f"- {clickable_file}")

        return "\n".join(lines)

    def _on_file_link_clicked(self, file_name: str) -> None:
        """출처 파일명 클릭 시 파일 열기"""
        try:
            # VectorStore를 통해 DB 경로 확인
            vector_manager = None
            if self.rag_chain and hasattr(self.rag_chain, 'vectorstore_manager'):
                vector_manager = self.rag_chain.vectorstore_manager

            # 파일 경로 결정 - 개인 DB 우선 검색, 없으면 공유 DB 검색
            file_path = None

            # 1. 개인 DB에서 파일 검색
            personal_path = os.path.join("data/embedded_documents", file_name)
            if os.path.exists(personal_path):
                file_path = personal_path
            # 2. 공유 DB에서 파일 검색
            elif vector_manager and vector_manager.shared_db_enabled:
                shared_base = os.path.dirname(vector_manager.shared_db_path)
                shared_path = os.path.join(shared_base, "embedded_documents", file_name)
                if os.path.exists(shared_path):
                    file_path = shared_path

            if not file_path:
                QMessageBox.warning(
                    self,
                    "파일 열기 실패",
                    f"파일을 찾을 수 없습니다:\n{file_name}\n\n"
                    "파일이 삭제되었거나 임베딩 시 저장되지 않았을 수 있습니다."
                )
                return

            # 절대 경로로 변환
            abs_path = os.path.abspath(file_path)

            # OS별 파일 열기
            if sys.platform == "win32":
                os.startfile(abs_path)
            elif sys.platform == "darwin":
                subprocess.call(['open', abs_path])
            else:
                subprocess.call(['xdg-open', abs_path])

        except Exception as e:
            QMessageBox.warning(
                self,
                "파일 열기 실패",
                f"파일을 여는 중 오류가 발생했습니다:\n{file_name}\n\n오류: {e}"
            )

    def _on_stream_chunk(self, part: str) -> None:
        # 첫 청크가 도착하면 상태 메시지 제거
        if not self._assistant_buffer:
            self._assistant_buffer = "💬 응답 생성중...\n\n"

        self._assistant_buffer += part
        self._update_last_assistant_bubble(self._assistant_buffer)
    
    def _on_stream_error(self, error_msg: str) -> None:
        """스트리밍 중 에러 발생 시 처리"""
        print(f"스트리밍 에러 수신: {error_msg}")

    def _on_stream_finished(self) -> None:
        # 출처 표시 (Sources) - 응답과 같은 버블에 통합
        sources: List[Dict] = []
        try:
            sources = self.rag_chain.get_source_documents(self._last_question) if self.rag_chain else []
            if sources:
                # 상태 메시지 제거 후 응답에 출처 추가
                clean_response = self._assistant_buffer.replace("💬 응답 생성중...\n\n", "")
                combined_content = clean_response + "\n\n---\n\n**[참고문서]**\n" + self._format_sources(sources)
                self._assistant_buffer = combined_content
                self._update_last_assistant_bubble(self._assistant_buffer)
            else:
                # 출처가 없으면 상태 메시지만 제거
                clean_response = self._assistant_buffer.replace("💬 응답 생성중...\n\n", "")
                self._assistant_buffer = clean_response
                self._update_last_assistant_bubble(self._assistant_buffer)
                print(f"[DEBUG] 출처 없음: sources={sources}")
        except Exception as e:
            print(f"[ERROR] 출처 표시 실패: {e}")
            import traceback
            traceback.print_exc()
            # 오류 발생 시에도 상태 메시지 제거
            clean_response = self._assistant_buffer.replace("💬 응답 생성중...\n\n", "")
            self._assistant_buffer = clean_response
            self._update_last_assistant_bubble(self._assistant_buffer)

        self.messages.append({"role": "assistant", "content": self._assistant_buffer})
        self.answer_committed.emit(self._last_question, self._assistant_buffer, sources)

    def set_theme(self, is_dark: bool):
        """테마 변경 - 모든 버블 업데이트"""
        self._is_dark = is_dark
        # 모든 기존 버블의 테마 업데이트
        for i in range(self.list_view.count()):
            item = self.list_view.item(i)
            widget = self.list_view.itemWidget(item)
            if isinstance(widget, ChatBubble):
                widget.set_theme(is_dark)

    def copy_last_answer(self) -> None:
        for i in range(self.list_view.count() - 1, -1, -1):
            if i < len(self.messages) and self.messages[i].get("role") == "assistant":
                QApplication.clipboard().setText(self.messages[i].get("content", ""))
                break
