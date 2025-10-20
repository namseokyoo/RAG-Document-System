from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QListWidget, QHBoxLayout, QMessageBox, QProgressBar, QApplication, QTextEdit


class UploadWorker(QObject):
    progress = Signal(int)
    message = Signal(str)
    finished = Signal()

    def __init__(self, file_paths, document_processor, vector_manager):
        super().__init__()
        self.file_paths = file_paths
        self.document_processor = document_processor
        self.vector_manager = vector_manager

    def run(self):
        total = len(self.file_paths) or 1
        try:
            self.message.emit("업로드 시작")
            for idx, file_path in enumerate(self.file_paths, 1):
                file_name = file_path.split('/')[-1].split('\\')[-1]
                self.message.emit(f"업로드 중: {file_name} ({idx}/{total})")
                try:
                    file_type = self._ext_to_type(file_name)
                    self.message.emit(f"문서 처리: {file_name} ...")
                    chunks = self.document_processor.process_document(
                        file_path=file_path, file_name=file_name, file_type=file_type
                    )
                    self.message.emit(f"임베딩 추가: {file_name} (청크 {len(chunks)}개)")
                    self.vector_manager.add_documents(chunks)
                except Exception as e:
                    self.message.emit(f"오류: {file_name} - {e}")
                self.progress.emit(int(idx * 100 / total))
        finally:
            self.message.emit("업로드 완료")
            self.finished.emit()

    def _ext_to_type(self, file_name: str) -> str:
        ext = file_name.lower().split('.')[-1]
        if ext == 'pdf':
            return 'pdf'
        if ext == 'pptx':
            return 'pptx'
        if ext in ('xlsx', 'xls'):
            return 'xlsx'
        if ext == 'txt':
            return 'txt'
        return 'unknown'


class DocumentWidget(QWidget):
    documents_changed = Signal()
    progress_message = Signal(str)

    def __init__(self, parent=None, document_processor=None, vector_manager=None) -> None:
        super().__init__(parent)
        self.document_processor = document_processor
        self.vector_manager = vector_manager
        self.setAcceptDrops(True)
        self._init_ui()
        self._connect()
        self.refresh_list()
        self._thread: QThread | None = None
        self._worker: UploadWorker | None = None

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.drop_label = QLabel("여기에 파일을 드롭하거나, '파일 추가'를 클릭하세요", self)
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setStyleSheet("QLabel { border: 1px dashed #555; padding: 10px; }")

        self.list_widget = QListWidget(self)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("파일 추가", self)
        self.remove_btn = QPushButton("선택 삭제", self)
        self.preview_btn = QPushButton("미리보기", self)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.hide()

        self.log_view = QTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("업로드 안내 메시지가 여기에 표시됩니다.")
        self.log_view.setFixedHeight(90)

        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addWidget(self.preview_btn)

        layout.addWidget(self.drop_label)
        layout.addWidget(self.list_widget)
        layout.addLayout(btn_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_view)

    def _connect(self) -> None:
        self.add_btn.clicked.connect(self.on_add)
        self.remove_btn.clicked.connect(self.on_remove)
        self.preview_btn.clicked.connect(self.on_preview)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = []
        for url in e.mimeData().urls():
            paths.append(url.toLocalFile())
        if paths:
            self._start_upload(paths)

    def refresh_list(self) -> None:
        self.list_widget.clear()
        if not self.vector_manager:
            return
        items = self.vector_manager.get_documents_list()
        for item in items:
            self.list_widget.addItem(f"{item['file_name']}  (chunks: {item['chunk_count']})")

    def _start_upload(self, file_paths):
        if not file_paths:
            return
        self.progress.setValue(0)
        self.progress.show()
        self.add_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)

        # QThread 시작
        self._thread = QThread(self)
        self._worker = UploadWorker(file_paths, self.document_processor, self.vector_manager)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.message.connect(self._on_worker_message)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_worker_message(self, text: str):
        self.progress_message.emit(text)
        self.log_view.append(text)

    def _on_worker_finished(self):
        self.progress.hide()
        self.add_btn.setEnabled(True)
        self.remove_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        self.refresh_list()
        self.documents_changed.emit()

    def on_add(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(self, "파일 선택", "", "Documents (*.pdf *.pptx *.xlsx *.xls *.txt)")
        if not file_paths:
            return
        self._start_upload(file_paths)

    def on_remove(self) -> None:
        current = self.list_widget.currentItem()
        if not current:
            return
        file_name = current.text().split('  (chunks:')[0]
        try:
            self.vector_manager.delete_document(file_name)
        except Exception:
            pass
        self.refresh_list()
        self.documents_changed.emit()

    def on_preview(self) -> None:
        current = self.list_widget.currentItem()
        if not current:
            return
        file_name = current.text().split('  (chunks:')[0]
        try:
            collection = self.vector_manager.get_vectorstore()._collection
            data = collection.get(where={"file_name": file_name}, include=["documents", "metadatas"])
            docs = data.get("documents") or []
            metas = data.get("metadatas") or []
            if not docs:
                QMessageBox.information(self, "미리보기", "미리볼 내용이 없습니다.")
                return
            preview_text = str(docs[0])
            if len(preview_text) > 500:
                preview_text = preview_text[:500] + "..."
            meta = metas[0] if metas else {}
            QMessageBox.information(self, "미리보기", f"{file_name}\npage: {meta.get('page_number','?')}\n\n{preview_text}")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"미리보기 실패: {e}")

    def _ext_to_type(self, file_name: str) -> str:
        ext = file_name.lower().split('.')[-1]
        if ext == 'pdf':
            return 'pdf'
        if ext == 'pptx':
            return 'pptx'
        if ext in ('xlsx', 'xls'):
            return 'xlsx'
        if ext == 'txt':
            return 'txt'
        return 'unknown'
