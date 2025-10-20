from typing import List, Dict
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton


class ChatWidget(QWidget):
    def __init__(self, parent=None, rag_chain=None) -> None:
        super().__init__(parent)
        self.rag_chain = rag_chain
        self.messages: List[Dict[str, str]] = []
        self._init_ui()
        self._connect()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.chat_view = QTextEdit(self)
        self.chat_view.setReadOnly(True)

        input_row = QHBoxLayout()
        self.input_edit = QTextEdit(self)
        self.input_edit.setFixedHeight(80)
        self.send_btn = QPushButton("전송", self)

        input_row.addWidget(self.input_edit)
        input_row.addWidget(self.send_btn)

        layout.addWidget(self.chat_view)
        layout.addLayout(input_row)

    def _connect(self) -> None:
        self.send_btn.clicked.connect(self.on_send)

    def on_send(self) -> None:
        question = self.input_edit.toPlainText().strip()
        if not question:
            return
        self.input_edit.clear()

        self._append_message("user", question)

        try:
            result = self.rag_chain.query(question, chat_history=self.messages) if self.rag_chain else {"answer": "RAGChain 미초기화", "sources": []}
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            self._append_message("assistant", answer)

            if sources:
                preview = "\n".join([f"- {s['file_name']} (p.{s['page_number']}) score={s['similarity_score']:.4f}" for s in sources])
                self._append_message("assistant", f"[출처]\n{preview}")
        except Exception as e:
            self._append_message("assistant", f"오류: {e}")

    def _append_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        role_name = "사용자" if role == "user" else "AI"
        self.chat_view.append(f"{role_name}: {content}")
