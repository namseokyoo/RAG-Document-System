from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QComboBox, QSpinBox, QPushButton, QVBoxLayout
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


class SettingsWidget(QWidget):
    def __init__(self, parent=None, vector_manager: VectorStoreManager = None, rag_chain: RAGChain = None) -> None:
        super().__init__(parent)
        self.vector_manager = vector_manager
        self.rag_chain = rag_chain
        self.config_mgr = ConfigManager()
        self._init_ui()
        self._load()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        # LLM 설정
        self.api_type = QComboBox(self)
        self.api_type.addItems(["request", "ollama", "openai", "openai-compatible"])
        self.model_name = QLineEdit(self)
        self.base_url = QLineEdit(self)
        self.api_key = QLineEdit(self)
        self.api_key.setEchoMode(QLineEdit.Password)

        # 임베딩 설정
        self.embed_api_type = QComboBox(self)
        self.embed_api_type.addItems(["ollama", "openai", "openai-compatible"])
        self.embed_base_url = QLineEdit(self)
        self.embed_model = QLineEdit(self)
        self.embed_api_key = QLineEdit(self)
        self.embed_api_key.setEchoMode(QLineEdit.Password)

        # 문서 처리
        self.chunk_size = QSpinBox(self)
        self.chunk_size.setRange(100, 4000)
        self.chunk_size.setValue(500)

        self.chunk_overlap = QSpinBox(self)
        self.chunk_overlap.setRange(0, 1000)
        self.chunk_overlap.setValue(100)

        self.top_k = QSpinBox(self)
        self.top_k.setRange(1, 20)
        self.top_k.setValue(3)

        self.save_btn = QPushButton("설정 저장", self)

        # 폼 배치
        form.addRow("LLM API 타입", self.api_type)
        form.addRow("LLM 모델명", self.model_name)
        form.addRow("LLM Base URL", self.base_url)
        form.addRow("LLM API Key", self.api_key)

        form.addRow("임베딩 API 타입", self.embed_api_type)
        form.addRow("임베딩 모델명", self.embed_model)
        form.addRow("임베딩 Base URL", self.embed_base_url)
        form.addRow("임베딩 API Key", self.embed_api_key)

        form.addRow("Chunk Size", self.chunk_size)
        form.addRow("Chunk Overlap", self.chunk_overlap)
        form.addRow("Top K", self.top_k)

        root.addLayout(form)
        root.addWidget(self.save_btn)

        self.save_btn.clicked.connect(self._save)

    def _load(self) -> None:
        cfg = self.config_mgr.get_all()
        # LLM
        self.api_type.setCurrentText(cfg.get("llm_api_type", "request"))
        self.model_name.setText(cfg.get("llm_model", "gemma3:4b"))
        self.base_url.setText(cfg.get("llm_base_url", "http://localhost:11434"))
        self.api_key.setText(cfg.get("llm_api_key", ""))
        # Embedding
        self.embed_api_type.setCurrentText(cfg.get("embedding_api_type", "ollama"))
        self.embed_model.setText(cfg.get("embedding_model", "nomic-embed-text"))
        self.embed_base_url.setText(cfg.get("embedding_base_url", "http://localhost:11434"))
        self.embed_api_key.setText(cfg.get("embedding_api_key", ""))
        # Document
        self.chunk_size.setValue(int(cfg.get("chunk_size", 500)))
        self.chunk_overlap.setValue(int(cfg.get("chunk_overlap", 100)))
        self.top_k.setValue(int(cfg.get("top_k", 3)))

    def _save(self) -> None:
        cfg = self.config_mgr.get_all()
        cfg.update({
            # LLM
            "llm_api_type": self.api_type.currentText(),
            "llm_model": self.model_name.text().strip(),
            "llm_base_url": self.base_url.text().strip(),
            "llm_api_key": self.api_key.text().strip(),
            # Embedding
            "embedding_api_type": self.embed_api_type.currentText(),
            "embedding_model": self.embed_model.text().strip(),
            "embedding_base_url": self.embed_base_url.text().strip(),
            "embedding_api_key": self.embed_api_key.text().strip(),
            # Document
            "chunk_size": int(self.chunk_size.value()),
            "chunk_overlap": int(self.chunk_overlap.value()),
            "top_k": int(self.top_k.value()),
        })
        self.config_mgr.save_config(cfg)

        # 서비스 즉시 반영
        if self.vector_manager:
            self.vector_manager.update_embeddings(
                embedding_api_type=cfg.get("embedding_api_type", "ollama"),
                embedding_base_url=cfg.get("embedding_base_url", "http://localhost:11434"),
                embedding_model=cfg.get("embedding_model", "nomic-embed-text"),
                embedding_api_key=cfg.get("embedding_api_key", ""),
            )
        if self.rag_chain and self.vector_manager:
            self.rag_chain.update_llm(
                llm_api_type=cfg.get("llm_api_type", "request"),
                llm_base_url=cfg.get("llm_base_url", "http://localhost:11434"),
                llm_model=cfg.get("llm_model", "gemma3:4b"),
                llm_api_key=cfg.get("llm_api_key", ""),
                temperature=cfg.get("temperature", 0.7),
            )
            self.rag_chain.update_retriever(
                vectorstore=self.vector_manager.get_vectorstore(),
                top_k=cfg.get("top_k", 3),
            )
