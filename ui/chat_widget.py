from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton


class ChatWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._init_ui()

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
