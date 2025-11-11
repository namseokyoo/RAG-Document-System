from typing import List, Dict, Optional
from PySide6.QtCore import Qt, Signal, QObject, QThread, QUrl
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
                               QListWidgetItem, QTextEdit, QLabel, QRadioButton, QButtonGroup)
from PySide6.QtGui import QKeySequence, QKeyEvent, QTextCursor, QDesktopServices
from PySide6.QtWidgets import QApplication
import re


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
    def __init__(self, text: str, is_user: bool, max_width: Optional[int] = None) -> None:
        super().__init__()
        
        self.text = text
        self.is_user = is_user
        self.max_width = max_width
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        
        # QTextEdit을 사용하여 텍스트 선택 가능하게 함
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)  # 읽기 전용
        self.text_edit.setHtml(self._to_html(text))
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 스크롤바 숨김
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
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
        
        # 스타일 설정
        background_color = "#1769aa" if is_user else "#2b2b2b"
        text_color = "white" if is_user else "#f0f0f0"
        
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                padding: 8px 10px;
                border-radius: 8px;
                background: {background_color};
                color: {text_color};
                border: none;
            }}
            QTextEdit::selected {{
                background: rgba(255, 255, 255, 0.3);
                color: {text_color};
            }}
        """)
        
        # 레이아웃 설정
        if is_user:
            layout.addStretch(1)  # 왼쪽 여백
            layout.addWidget(self.text_edit, 1)  # 오른쪽에 버블 (크게!)
        else:
            layout.addWidget(self.text_edit, 1)  # 왼쪽에 버블
            layout.addStretch(0)  # 오른쪽 여백
    
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
        # links
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"<a href='\2'>\1</a>", t)
        return t.replace("\n", "<br>")

    def _to_html(self, text: str) -> str:
        return self._md(text)


class ChatInput(QTextEdit):
    sendRequested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
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
        search_mode_label.setStyleSheet("QLabel { font-weight: bold; }")

        self.search_mode_group = QButtonGroup(self)
        self.search_integrated_radio = QRadioButton("통합 검색", self)
        self.search_personal_radio = QRadioButton("개인 DB", self)
        self.search_shared_radio = QRadioButton("공유 DB", self)

        self.search_integrated_radio.setChecked(True)  # 기본값: 통합 검색

        self.search_mode_group.addButton(self.search_integrated_radio, 0)
        self.search_mode_group.addButton(self.search_personal_radio, 1)
        self.search_mode_group.addButton(self.search_shared_radio, 2)

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
        widget = ChatBubble(text, is_user, max_width=max_w)
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

        # 어시스턴트 스트리밍 시작
        self._assistant_buffer = ""
        self._append_bubble("", is_user=False)  # placeholder

        if not self.rag_chain:
            self._append_bubble("RAGChain 미초기화", is_user=False)
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
            new_widget = ChatBubble(text, is_user=False, max_width=max_w)
            
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
        # 파일명별로 그룹화하고, 같은 페이지는 최고 점수만 유지
        file_dict = {}
        for s in sources:
            file_name = s.get('file_name', '?')
            page_number = s.get('page_number', '?')
            score = float(s.get("similarity_score", 0))

            if file_name not in file_dict:
                file_dict[file_name] = {}  # 딕셔너리로 변경 (페이지 → 점수)

            # 같은 페이지 번호는 최고 점수만 유지 (한 페이지에 여러 청크가 있을 수 있음)
            if page_number not in file_dict[file_name] or score > file_dict[file_name][page_number]:
                file_dict[file_name][page_number] = score

        # 파일명별로 정렬하여 표시 (페이지 개수에 따라 정렬)
        lines = []
        for file_name, page_scores in sorted(file_dict.items(), key=lambda x: len(x[1]), reverse=True):
            # 페이지 번호 순서대로 정렬
            pages = sorted(page_scores.items(), key=lambda x: (isinstance(x[0], str), x[0]))

            if len(pages) == 1:
                # 페이지가 하나면 기존 형식
                page_num, score = pages[0]
                lines.append(f"- {file_name} (p.{page_num}) [{score:.1f}%]")
            else:
                # 여러 페이지면 파일명 한 번만 + 페이지 나열
                page_list = ", ".join([f"p.{page_num} ({score:.1f}%)" for page_num, score in pages])
                lines.append(f"- {file_name}\n  {page_list}")

        return "\n".join(lines)

    def _on_stream_chunk(self, part: str) -> None:
        self._assistant_buffer += part
        self._update_last_assistant_bubble(self._assistant_buffer)
    
    def _on_stream_error(self, error_msg: str) -> None:
        """스트리밍 중 에러 발생 시 처리"""
        print(f"스트리밍 에러 수신: {error_msg}")

    def _on_stream_finished(self) -> None:
        self.messages.append({"role": "assistant", "content": self._assistant_buffer})

        # 질문 분류 결과 표시 (Classification Info)
        try:
            if self.rag_chain and hasattr(self.rag_chain, 'get_last_classification'):
                classification = self.rag_chain.get_last_classification()
                if classification:
                    classification_text = self._format_classification(classification)
                    self._append_bubble(classification_text, is_user=False)
        except Exception:
            pass

        # 출처 표시 (Sources)
        sources: List[Dict] = []
        try:
            sources = self.rag_chain.get_source_documents(self._last_question) if self.rag_chain else []
            if sources:
                self._append_bubble("[출처]\n" + self._format_sources(sources), is_user=False)
        except Exception:
            pass

        self.answer_committed.emit(self._last_question, self._assistant_buffer, sources)

    def copy_last_answer(self) -> None:
        for i in range(self.list_view.count() - 1, -1, -1):
            if i < len(self.messages) and self.messages[i].get("role") == "assistant":
                QApplication.clipboard().setText(self.messages[i].get("content", ""))
                break
