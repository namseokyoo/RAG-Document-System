from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QComboBox, QSpinBox


class SettingsWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        form = QFormLayout(self)

        self.api_type = QComboBox(self)
        self.api_type.addItems(["request", "ollama", "openai", "openai-compatible"])

        self.model_name = QLineEdit(self)
        self.base_url = QLineEdit(self)
        self.api_key = QLineEdit(self)
        self.api_key.setEchoMode(QLineEdit.Password)

        self.chunk_size = QSpinBox(self)
        self.chunk_size.setRange(100, 4000)
        self.chunk_size.setValue(500)

        self.chunk_overlap = QSpinBox(self)
        self.chunk_overlap.setRange(0, 1000)
        self.chunk_overlap.setValue(100)

        form.addRow("LLM API 타입", self.api_type)
        form.addRow("모델명", self.model_name)
        form.addRow("Base URL", self.base_url)
        form.addRow("API Key", self.api_key)
        form.addRow("Chunk Size", self.chunk_size)
        form.addRow("Chunk Overlap", self.chunk_overlap)
