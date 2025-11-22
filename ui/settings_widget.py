from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QComboBox, QSpinBox, QPushButton, QVBoxLayout, QMessageBox, QCheckBox, QGroupBox, QHBoxLayout, QFileDialog, QProgressDialog, QApplication
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
import os


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

        # LLM 설정 그룹
        llm_group = QGroupBox("LLM 설정 (답변 생성)")
        llm_form = QFormLayout(llm_group)

        self.api_type = QComboBox(self)
        self.api_type.addItems(["request", "ollama", "openai", "openai-compatible"])
        llm_form.addRow("API 타입", self.api_type)

        self.model_name = QLineEdit(self)
        self.model_name.setPlaceholderText("gpt-4o-mini, llama3.2:3b 등")
        llm_form.addRow("모델명", self.model_name)

        self.base_url = QLineEdit(self)
        self.base_url.setPlaceholderText("https://api.openai.com/v1 또는 http://localhost:11434")
        llm_form.addRow("Base URL", self.base_url)

        self.api_key = QLineEdit(self)
        self.api_key.setEchoMode(QLineEdit.Password)
        llm_form.addRow("API Key", self.api_key)

        # 임베딩 설정 그룹
        embed_group = QGroupBox("임베딩 설정 (문서 검색)")
        embed_form = QFormLayout(embed_group)

        self.embed_api_type = QComboBox(self)
        self.embed_api_type.addItems(["request", "ollama", "openai", "openai-compatible"])
        embed_form.addRow("API 타입", self.embed_api_type)

        self.embed_model = QLineEdit(self)
        self.embed_model.setPlaceholderText("nomic-embed-text, text-embedding-3-small 등")
        embed_form.addRow("모델명", self.embed_model)

        self.embed_base_url = QLineEdit(self)
        self.embed_base_url.setPlaceholderText("http://localhost:11434 또는 https://api.openai.com/v1")
        embed_form.addRow("Base URL", self.embed_base_url)

        self.embed_api_key = QLineEdit(self)
        self.embed_api_key.setEchoMode(QLineEdit.Password)
        embed_form.addRow("API Key", self.embed_api_key)

        # 다중 쿼리 설정
        self.multi_query_num = QSpinBox(self)
        self.multi_query_num.setRange(0, 5)
        self.multi_query_num.setValue(3)
        self.multi_query_num.setToolTip("0을 선택하면 다중 쿼리 생성을 비활성화합니다.")
        embed_form.addRow("다중 쿼리 갯수", self.multi_query_num)

        # 비전 API 설정 그룹
        vision_group = QGroupBox("비전 API 설정 (PDF/PPTX Vision 분석)")
        vision_form = QFormLayout(vision_group)

        self.vision_api_type = QComboBox(self)
        self.vision_api_type.addItems(["openai", "ollama", "openai-compatible"])
        self.vision_api_type.setToolTip("Vision API 타입 (LLM과 별개 설정 가능)")
        vision_form.addRow("Vision API 타입", self.vision_api_type)

        self.vision_model = QLineEdit(self)
        self.vision_model.setPlaceholderText("gpt-4o-mini, gpt-4o, llama3.2-vision:11b 등")
        self.vision_model.setToolTip("Vision을 지원하는 모델명")
        vision_form.addRow("Vision 모델", self.vision_model)

        self.vision_base_url = QLineEdit(self)
        self.vision_base_url.setPlaceholderText("https://api.openai.com/v1 또는 http://localhost:11434")
        self.vision_base_url.setToolTip("Vision API Base URL")
        vision_form.addRow("Vision Base URL", self.vision_base_url)

        self.vision_api_key = QLineEdit(self)
        self.vision_api_key.setEchoMode(QLineEdit.Password)
        self.vision_api_key.setPlaceholderText("비어있으면 LLM API 키 사용")
        self.vision_api_key.setToolTip("Vision API 키 (선택사항, 없으면 LLM API 키 사용)")
        vision_form.addRow("Vision API Key", self.vision_api_key)

        # 공유 DB 설정
        shared_db_group = QGroupBox("공유 DB 설정")
        shared_db_form = QFormLayout(shared_db_group)

        # 공유 DB 경로 입력 필드 (경로가 있으면 자동 활성화)
        shared_db_path_layout = QHBoxLayout()
        self.shared_db_path = QLineEdit(self)
        self.shared_db_path.setPlaceholderText("예: U:\\OC_RAG_system_DB\\data\\chroma_db (비워두면 공유 DB 비활성화)")
        self.shared_db_path.setToolTip("공유 DB의 절대 경로를 입력하세요. 경로가 설정되면 자동으로 공유 DB가 활성화됩니다.")
        self.shared_db_browse_btn = QPushButton("찾아보기", self)
        self.shared_db_browse_btn.clicked.connect(self._browse_shared_db_path)
        shared_db_path_layout.addWidget(self.shared_db_path)
        shared_db_path_layout.addWidget(self.shared_db_browse_btn)

        shared_db_form.addRow("공유 DB 경로", shared_db_path_layout)

        self.save_btn = QPushButton("설정 저장", self)

        # 그룹 배치
        root.addWidget(llm_group)
        root.addWidget(embed_group)
        root.addWidget(vision_group)
        root.addWidget(shared_db_group)
        root.addWidget(self.save_btn)

        self.save_btn.clicked.connect(self._save)
        
        # API 타입 변경 시 Base URL 필드 활성/비활성 처리
        self.api_type.currentTextChanged.connect(self._on_llm_api_type_changed)
        self.embed_api_type.currentTextChanged.connect(self._on_embed_api_type_changed)
        
        # 초기 상태 설정
        self._on_llm_api_type_changed(self.api_type.currentText())
        self._on_embed_api_type_changed(self.embed_api_type.currentText())

    def _on_llm_api_type_changed(self, api_type: str):
        """LLM API 타입 변경 시 Base URL 필드 활성/비활성 처리"""
        if api_type == "openai":
            # OpenAI 공식 API는 고정된 URL 사용
            self.base_url.setEnabled(False)
            self.base_url.setPlaceholderText("자동 (https://api.openai.com/v1)")
            self.base_url.setToolTip("OpenAI 공식 API는 자동으로 https://api.openai.com/v1를 사용합니다.")
        else:
            self.base_url.setEnabled(True)
            self.base_url.setPlaceholderText("예: http://localhost:11434")
            self.base_url.setToolTip("")

    def _on_embed_api_type_changed(self, api_type: str):
        """임베딩 API 타입 변경 시 Base URL 필드 활성/비활성 처리"""
        if api_type == "openai":
            # OpenAI 공식 API는 고정된 URL 사용
            self.embed_base_url.setEnabled(False)
            self.embed_base_url.setPlaceholderText("자동 (https://api.openai.com/v1)")
            self.embed_base_url.setToolTip("OpenAI 공식 API는 자동으로 https://api.openai.com/v1를 사용합니다.")
        else:
            self.embed_base_url.setEnabled(True)
            self.embed_base_url.setPlaceholderText("예: http://localhost:11434")
            self.embed_base_url.setToolTip("")

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
        self.multi_query_num.setValue(int(cfg.get("multi_query_num", 3)))
        # 비전 API 설정
        self.vision_api_type.setCurrentText(cfg.get("vision_api_type", "openai"))
        self.vision_model.setText(cfg.get("vision_model", "gpt-4o-mini"))
        self.vision_base_url.setText(cfg.get("vision_base_url", "https://api.openai.com/v1"))
        self.vision_api_key.setText(cfg.get("vision_api_key", ""))
        # 공유 DB 설정
        self.shared_db_path.setText(cfg.get("shared_db_path", ""))

    def _save(self) -> None:
        # 로딩 다이얼로그 표시
        progress = QProgressDialog("설정 적용 중...", None, 0, 0, self)
        progress.setWindowTitle("설정 저장")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)  # 취소 버튼 없음
        progress.setMinimumDuration(0)  # 즉시 표시
        progress.show()

        try:
            cfg = self.config_mgr.get_all()

            # 기존 설정 저장 (변경 감지용)
            old_embedding_api_type = cfg.get("embedding_api_type", "ollama")
            old_embedding_model = cfg.get("embedding_model", "nomic-embed-text")
            old_embedding_base_url = cfg.get("embedding_base_url", "http://localhost:11434")
            old_embedding_api_key = cfg.get("embedding_api_key", "")

            old_llm_api_type = cfg.get("llm_api_type", "request")
            old_llm_model = cfg.get("llm_model", "gemma3:4b")
            old_llm_base_url = cfg.get("llm_base_url", "http://localhost:11434")
            old_llm_api_key = cfg.get("llm_api_key", "")
            old_temperature = cfg.get("temperature", 0.7)

            old_multi_query_num = cfg.get("multi_query_num", 3)
            old_top_k = cfg.get("top_k", 3)

            old_shared_db_enabled = cfg.get("shared_db_enabled", False)
            old_shared_db_path = cfg.get("shared_db_path", "")

            # 새로운 설정 값
            new_embedding_api_type = self.embed_api_type.currentText()
            new_embedding_model = self.embed_model.text().strip()
            new_embedding_base_url = self.embed_base_url.text().strip()
            new_embedding_api_key = self.embed_api_key.text().strip()

            new_llm_api_type = self.api_type.currentText()
            new_llm_model = self.model_name.text().strip()
            new_llm_base_url = self.base_url.text().strip()
            new_llm_api_key = self.api_key.text().strip()
            new_temperature = cfg.get("temperature", 0.7)  # 현재는 UI에서 변경 불가

            new_multi_query_num = int(self.multi_query_num.value())
            new_top_k = cfg.get("top_k", 3)  # 현재는 UI에서 변경 불가

            new_shared_db_path = self.shared_db_path.text().strip()
            new_shared_db_enabled = bool(new_shared_db_path)

            # 설정 업데이트
            cfg.update({
                # LLM
                "llm_api_type": new_llm_api_type,
                "llm_model": new_llm_model,
                "llm_base_url": new_llm_base_url,
                "llm_api_key": new_llm_api_key,
                # Embedding
                "embedding_api_type": new_embedding_api_type,
                "embedding_model": new_embedding_model,
                "embedding_base_url": new_embedding_base_url,
                "embedding_api_key": new_embedding_api_key,
            })
            cfg["multi_query_num"] = new_multi_query_num
            cfg["enable_multi_query"] = new_multi_query_num > 0
            # 비전 API 설정
            cfg["vision_api_type"] = self.vision_api_type.currentText()
            cfg["vision_model"] = self.vision_model.text().strip()
            cfg["vision_base_url"] = self.vision_base_url.text().strip()
            cfg["vision_api_key"] = self.vision_api_key.text().strip()
            # 공유 DB 설정
            cfg["shared_db_enabled"] = new_shared_db_enabled
            cfg["shared_db_path"] = new_shared_db_path

            # config.json 저장
            self.config_mgr.save_config(cfg)

            # 변경 감지 및 스마트 업데이트
            embedding_changed = (
                old_embedding_api_type != new_embedding_api_type or
                old_embedding_model != new_embedding_model or
                old_embedding_base_url != new_embedding_base_url or
                old_embedding_api_key != new_embedding_api_key
            )

            llm_changed = (
                old_llm_api_type != new_llm_api_type or
                old_llm_model != new_llm_model or
                old_llm_base_url != new_llm_base_url or
                old_llm_api_key != new_llm_api_key or
                old_temperature != new_temperature
            )

            multi_query_changed = old_multi_query_num != new_multi_query_num
            retriever_changed = old_top_k != new_top_k or embedding_changed

            shared_db_changed = (
                old_shared_db_enabled != new_shared_db_enabled or
                old_shared_db_path != new_shared_db_path
            )

            # 임베딩 설정이 변경된 경우에만 업데이트
            if embedding_changed and self.vector_manager:
                progress.setLabelText("임베딩 설정 적용 중...")
                self.vector_manager.update_embeddings(
                    embedding_api_type=new_embedding_api_type,
                    embedding_base_url=new_embedding_base_url,
                    embedding_model=new_embedding_model,
                    embedding_api_key=new_embedding_api_key,
                )

            # LLM 설정이 변경된 경우에만 업데이트
            if llm_changed and self.rag_chain:
                progress.setLabelText("LLM 설정 적용 중...")
                llm_base_url = new_llm_base_url
                if new_llm_api_type == "openai":
                    pass  # OpenAI는 base_url 무시

                self.rag_chain.update_llm(
                    llm_api_type=new_llm_api_type,
                    llm_base_url=llm_base_url,
                    llm_model=new_llm_model,
                    llm_api_key=new_llm_api_key,
                    temperature=new_temperature,
                )

            # Retriever 설정이 변경된 경우에만 업데이트
            if retriever_changed and self.rag_chain and self.vector_manager:
                progress.setLabelText("검색 설정 적용 중...")
                self.rag_chain.update_retriever(
                    vectorstore=self.vector_manager.get_vectorstore(),
                    top_k=new_top_k,
                )

            # 다중 쿼리 설정이 변경된 경우에만 업데이트
            if multi_query_changed and self.rag_chain:
                self.rag_chain.multi_query_num = max(0, new_multi_query_num)
                self.rag_chain.enable_multi_query = (new_multi_query_num > 0)

            # 일반 완료 메시지
            progress.close()

            # 공유 DB 경로가 변경된 경우 안내 메시지
            if shared_db_changed:
                QMessageBox.information(
                    self,
                    "설정 저장 완료",
                    "설정이 저장되었습니다.\n\n"
                    "공유 DB 설정이 변경되었습니다.\n"
                    "메뉴에서 '설정 → 공용DB 재접속'을 실행하여\n"
                    "공유 DB를 활성화하세요."
                )
            else:
                QMessageBox.information(self, "설정 저장", "설정이 저장되었습니다.")

        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self,
                "설정 저장 오류",
                f"설정 저장 중 오류가 발생했습니다:\n\n{str(e)}"
            )

    def _browse_shared_db_path(self) -> None:
        """공유 DB 경로 찾아보기 다이얼로그"""
        current_path = self.shared_db_path.text().strip()
        start_dir = current_path if current_path and os.path.exists(current_path) else ""

        # 폴더 선택 다이얼로그
        selected_path = QFileDialog.getExistingDirectory(
            self,
            "공유 DB 경로 선택",
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if selected_path:
            # 경로 유효성 검증 (chroma.sqlite3 파일 존재 여부)
            chroma_db_file = os.path.join(selected_path, "chroma.sqlite3")
            if os.path.exists(chroma_db_file):
                self.shared_db_path.setText(selected_path)
                QMessageBox.information(
                    self,
                    "경로 확인",
                    f"유효한 공유 DB 경로입니다.\n\n경로: {selected_path}"
                )
            else:
                # 경고만 표시하고 경로는 설정 (사용자가 미리 경로 지정 가능하도록)
                reply = QMessageBox.question(
                    self,
                    "경로 확인",
                    f"선택한 경로에 ChromaDB 파일(chroma.sqlite3)이 없습니다.\n\n"
                    f"그래도 이 경로를 사용하시겠습니까?\n\n"
                    f"경로: {selected_path}",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.shared_db_path.setText(selected_path)
