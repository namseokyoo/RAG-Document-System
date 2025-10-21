from typing import List, Dict, Optional
from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QTextEdit, QLabel
from PySide6.QtGui import QKeySequence, QKeyEvent
from PySide6.QtWidgets import QApplication
import re


class StreamWorker(QObject):
    chunk = Signal(str)
    finished = Signal()

    def __init__(self, rag_chain, question: str, chat_history: List[Dict[str, str]]):
        super().__init__()
        self.rag_chain = rag_chain
        self.question = question
        self.chat_history = chat_history

    def run(self) -> None:
        try:
            for part in self.rag_chain.query_stream(self.question, chat_history=self.chat_history):
                self.chunk.emit(part)
        finally:
            self.finished.emit()


class ChatBubble(QWidget):
    def __init__(self, text: str, is_user: bool, max_width: Optional[int] = None) -> None:
        super().__init__()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        label = QLabel(self._to_html(text))
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        
        # label에 최대 너비 설정 (사용자 버블만 더 크게)
        if max_width:
            if is_user:
                # 사용자 버블은 더 크게 (1.5배)
                label.setMaximumWidth(int(max_width * 1.5))
            else:
                label.setMaximumWidth(max_width)
        
        label.setStyleSheet(
            """
            QLabel { padding: 8px 10px; border-radius: 8px; }
            """
            + (
                "QLabel { background: #1769aa; color: white; }"
                if is_user
                else "QLabel { background: #2b2b2b; color: #f0f0f0; }"
            )
        )
        
        # 레이아웃 설정
        if is_user:
            layout.addStretch(1)  # 왼쪽 여백
            layout.addWidget(label, 1)  # 오른쪽에 버블 (크게!)
        else:
            layout.addWidget(label, 1)  # 왼쪽에 버블
            layout.addStretch(0)  # 오른쪽 여백

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
        self._stream_thread: Optional[QThread] = None
        self._stream_worker: Optional[StreamWorker] = None
        self._assistant_buffer: str = ""
        self._last_question: str = ""

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

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
        item.setSizeHint(widget.sizeHint())
        self.list_view.addItem(item)
        self.list_view.setItemWidget(item, widget)
        self.list_view.scrollToBottom()

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
        self._stream_thread = QThread(self)
        self._stream_worker = StreamWorker(self.rag_chain, question, self.messages)
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
            user_w, ai_w = self._bubble_widths()
            max_w = ai_w
            new_widget = ChatBubble(text, is_user=False, max_width=max_w)
            item.setSizeHint(new_widget.sizeHint())
            self.list_view.setItemWidget(item, new_widget)
            self.list_view.scrollToBottom()

    def _format_sources(self, sources: List[Dict]) -> str:
        lines = []
        for s in sources:
            score = float(s.get("similarity_score", 0))
            # 정규화된 점수는 항상 0-100% 범위이므로 그대로 사용
            score_txt = f"{score:.1f}%"
            lines.append(f"- {s.get('file_name','?')} (p.{s.get('page_number','?')}) [{score_txt}]")
        return "\n".join(lines)

    def _on_stream_chunk(self, part: str) -> None:
        self._assistant_buffer += part
        self._update_last_assistant_bubble(self._assistant_buffer)

    def _on_stream_finished(self) -> None:
        self.messages.append({"role": "assistant", "content": self._assistant_buffer})
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
