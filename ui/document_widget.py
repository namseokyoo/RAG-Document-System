from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog,
                               QListWidget, QHBoxLayout, QMessageBox, QProgressBar,
                               QApplication, QTextEdit, QCheckBox, QRadioButton, QButtonGroup, QComboBox)
import os
import shutil
import sys
import subprocess


class UploadWorker(QObject):
    progress = Signal(int)
    message = Signal(str)
    finished = Signal()

    def __init__(self, file_paths, document_processor, vector_manager, target_db="personal"):
        super().__init__()
        self.file_paths = file_paths
        self.document_processor = document_processor
        self.vector_manager = vector_manager
        self.target_db = target_db

    def run(self):
        total = len(self.file_paths) or 1
        try:
            db_name = "공유 DB" if self.target_db == "shared" else "개인 DB"
            self.message.emit(f"업로드 시작 ({db_name})")
            for idx, file_path in enumerate(self.file_paths, 1):
                file_name = file_path.split('/')[-1].split('\\')[-1]
                self.message.emit(f"업로드 중: {file_name} ({idx}/{total})")
                try:
                    # 원본 파일을 DB별 embedded_documents에 저장
                    self._save_embedded_file(file_path, file_name, self.target_db, self.vector_manager)

                    file_type = self._ext_to_type(file_name)
                    self.message.emit(f"문서 처리: {file_name} ...")
                    chunks = self.document_processor.process_document(
                        file_path=file_path, file_name=file_name, file_type=file_type
                    )
                    self.message.emit(f"임베딩 추가: {file_name} (청크 {len(chunks)}개) → {db_name}")
                    self.vector_manager.add_documents(chunks, target_db=self.target_db)
                    self.message.emit(f"✅ 완료: {file_name}")
                except Exception as e:
                    error_msg = str(e)
                    self.message.emit(f"❌ 오류: {file_name}")
                    # 에러 메시지가 여러 줄이면 각 줄을 표시
                    for line in error_msg.split('\n'):
                        if line.strip():
                            self.message.emit(f"   {line}")
                self.progress.emit(int(idx * 100 / total))
        finally:
            self.message.emit("업로드 완료")
            self.finished.emit()
    
    def _save_embedded_file(self, file_path: str, file_name: str, target_db: str, vector_manager) -> None:
        """임베딩된 파일을 DB별 embedded_documents 폴더에 저장"""
        try:
            # DB별 embedded_documents 경로 결정
            if target_db == "shared" and vector_manager.shared_db_enabled:
                # 공유 DB: [공유DB경로]/../embedded_documents
                shared_base = os.path.dirname(vector_manager.shared_db_path)  # .../data/chroma_db → .../data
                embedded_dir = os.path.join(shared_base, "embedded_documents")
            else:
                # 개인 DB: data/embedded_documents
                embedded_dir = "data/embedded_documents"

            os.makedirs(embedded_dir, exist_ok=True)

            dest_path = os.path.join(embedded_dir, file_name)
            shutil.copy2(file_path, dest_path)  # copy2: 메타데이터 보존
        except Exception as e:
            # 파일 복사 실패해도 계속 진행
            print(f"[DocumentWidget][WARN] 원본 파일 저장 실패 ({file_name}): {e}")
            pass

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
        self._update_shared_db_status()  # 공유 DB 상태 업데이트
        self.refresh_list()
        self._thread: QThread | None = None
        self._worker: UploadWorker | None = None

    def _update_shared_db_status(self) -> None:
        """공유 DB 상태 업데이트"""
        if self.vector_manager and hasattr(self.vector_manager, 'shared_db_enabled'):
            if self.vector_manager.shared_db_enabled:
                self.shared_db_radio.setEnabled(True)
                db_path = getattr(self.vector_manager, 'shared_db_path', '')
                self.shared_db_status_label.setText(f"✓ 공유 DB 연결됨: {db_path}")
                self.shared_db_status_label.setStyleSheet("QLabel { color: green; font-size: 11px; }")
            else:
                self.shared_db_radio.setEnabled(False)
                self.shared_db_status_label.setText("✗ 공유 DB 비활성화 (개인 DB만 사용 가능)")
                self.shared_db_status_label.setStyleSheet("QLabel { color: #888; font-size: 11px; }")
        else:
            self.shared_db_radio.setEnabled(False)
            self.shared_db_status_label.setText("✗ 공유 DB 비활성화 (개인 DB만 사용 가능)")
            self.shared_db_status_label.setStyleSheet("QLabel { color: #888; font-size: 11px; }")

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 텍스트 직접 입력 섹션 추가
        text_section = QLabel("📝 텍스트 직접 입력", self)
        text_section.setStyleSheet("QLabel { font-weight: bold; margin-top: 5px; }")
        layout.addWidget(text_section)
        
        # 제목 입력
        title_label = QLabel("제목:", self)
        layout.addWidget(title_label)
        self.title_input = QTextEdit(self)
        self.title_input.setMaximumHeight(30)
        self.title_input.setPlaceholderText("문서 제목을 입력하세요...")
        layout.addWidget(self.title_input)
        
        # 내용 입력
        content_label = QLabel("내용:", self)
        layout.addWidget(content_label)
        self.content_input = QTextEdit(self)
        self.content_input.setMaximumHeight(100)
        self.content_input.setPlaceholderText("문서 내용을 입력하세요...")
        layout.addWidget(self.content_input)
        
        # 텍스트 추가 버튼
        self.add_text_btn = QPushButton("📝 텍스트 문서 추가", self)
        layout.addWidget(self.add_text_btn)
        
        # 구분선
        separator = QLabel("─" * 30, self)
        separator.setAlignment(Qt.AlignCenter)
        layout.addWidget(separator)
        
        # Vision 청킹 체크박스 (PPTX 전용)
        self.vision_checkbox = QCheckBox("🎨 Vision 청킹 사용 (PPTX - 슬라이드 이미지 분석)", self)
        self.vision_checkbox.setToolTip("PPTX 파일 업로드 시 각 슬라이드를 이미지로 변환하여 Vision LLM으로 분석합니다.\n표, 그래프 등의 시각적 요소를 더 잘 인식할 수 있습니다.")
        layout.addWidget(self.vision_checkbox)

        # DB 선택 섹션
        db_section = QLabel("💾 저장 위치 선택", self)
        db_section.setStyleSheet("QLabel { font-weight: bold; margin-top: 10px; }")
        layout.addWidget(db_section)

        # 라디오 버튼으로 DB 선택
        db_layout = QHBoxLayout()
        self.db_button_group = QButtonGroup(self)
        self.personal_db_radio = QRadioButton("개인 DB", self)
        self.shared_db_radio = QRadioButton("공유 DB", self)
        self.personal_db_radio.setChecked(True)  # 기본값: 개인 DB

        self.db_button_group.addButton(self.personal_db_radio, 0)
        self.db_button_group.addButton(self.shared_db_radio, 1)

        db_layout.addWidget(self.personal_db_radio)
        db_layout.addWidget(self.shared_db_radio)
        db_layout.addStretch()
        layout.addLayout(db_layout)

        # 공유 DB 상태 표시
        self.shared_db_status_label = QLabel("", self)
        self.shared_db_status_label.setStyleSheet("QLabel { color: #888; font-size: 11px; }")
        layout.addWidget(self.shared_db_status_label)

        # 구분선
        separator2 = QLabel("─" * 30, self)
        separator2.setAlignment(Qt.AlignCenter)
        layout.addWidget(separator2)

        # 파일 목록 필터
        filter_layout = QHBoxLayout()
        filter_label = QLabel("📂 파일 목록 필터:", self)
        self.list_filter_combo = QComboBox(self)
        self.list_filter_combo.addItems(["모두 표시", "개인 DB만", "공유 DB만"])
        self.list_filter_combo.currentTextChanged.connect(self.refresh_list)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.list_filter_combo)
        filter_layout.addStretch()
        layout.addWidget(QWidget())  # 간격 조정
        layout.addLayout(filter_layout)

        self.drop_label = QLabel("여기에 파일을 드롭하거나, '파일 추가'를 클릭하세요", self)
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setStyleSheet("QLabel { border: 1px dashed #555; padding: 10px; }")

        self.list_widget = QListWidget(self)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("파일 추가", self)
        self.remove_btn = QPushButton("선택 삭제", self)
        self.preview_btn = QPushButton("파일 열기", self)

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
        self.add_text_btn.clicked.connect(self.on_add_text)
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

        # 필터 설정
        filter_mode = self.list_filter_combo.currentText()
        if filter_mode == "개인 DB만":
            db_filter = "personal"
        elif filter_mode == "공유 DB만":
            db_filter = "shared"
        else:
            db_filter = "both"

        items = self.vector_manager.get_documents_list(db_type=db_filter)
        for item in items:
            # Vision 청킹 사용 여부 표시
            vision_marker = "🎨 " if item.get("enable_vision_chunking", False) else ""
            db_type_marker = f"[{item.get('db_type', '개인 DB')}]"
            self.list_widget.addItem(
                f"{vision_marker}{db_type_marker} {item['file_name']}  (chunks: {item['chunk_count']})"
            )

    def _start_upload(self, file_paths):
        if not file_paths:
            return

        # 대상 DB 선택
        target_db = "shared" if self.shared_db_radio.isChecked() else "personal"

        # 공유 DB 선택 시 활성화 여부 확인
        if target_db == "shared" and not self.vector_manager.shared_db_enabled:
            QMessageBox.warning(
                self,
                "공유 DB 비활성화",
                "공유 DB가 비활성화되어 있습니다.\n개인 DB만 사용 가능합니다."
            )
            return

        self.progress.setValue(0)
        self.progress.show()
        self.add_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)

        # Vision 설정을 config에 저장 (임베딩 시 사용)
        enable_vision = self.vision_checkbox.isChecked()
        from config import ConfigManager
        config_manager = ConfigManager()
        config_manager.update("enable_vision_chunking", enable_vision)
        config_manager.save_config(config_manager.get_all())

        # QThread 시작
        self._thread = QThread(self)
        self._worker = UploadWorker(file_paths, self.document_processor, self.vector_manager, target_db=target_db)
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

    def on_add_text(self) -> None:
        """텍스트 직접 입력으로 문서 추가"""
        title = self.title_input.toPlainText().strip()
        content = self.content_input.toPlainText().strip()
        
        if not title or not content:
            QMessageBox.warning(self, "입력 오류", "제목과 내용을 모두 입력해주세요.")
            return
        
        try:
            # 임시 텍스트 파일 생성
            import tempfile
            import os
            
            # 텍스트 파일 생성
            temp_dir = "data/uploaded_files"
            os.makedirs(temp_dir, exist_ok=True)
            
            # 파일명 생성 (제목 기반)
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()
            safe_title = safe_title[:30]  # 길이 제한
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{safe_title}_{timestamp}.txt"
            file_path = os.path.join(temp_dir, file_name)
            
            # 파일 저장
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"제목: {title}\n\n")
                f.write(content)
            
            # 업로드 처리
            self.log_view.append(f"📝 텍스트 문서 생성: {file_name}")
            self._start_upload([file_path])
            
            # 입력 필드 초기화
            self.title_input.clear()
            self.content_input.clear()
            
            QMessageBox.information(self, "완료", f"텍스트 문서가 추가되었습니다:\n{file_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"텍스트 문서 추가 실패:\n{e}")
    
    def on_add(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(self, "파일 선택", "", "Documents (*.pdf *.pptx *.xlsx *.xls *.txt)")
        if not file_paths:
            return
        self._start_upload(file_paths)

    def on_remove(self) -> None:
        current = self.list_widget.currentItem()
        if not current:
            return

        # Vision 마커 및 DB 타입 마커 제거
        display_text = current.text()

        # DB 타입 파악
        target_db = "personal"  # 기본값
        if "[공유 DB]" in display_text:
            target_db = "shared"
        elif "[개인 DB]" in display_text:
            target_db = "personal"

        # 파일 이름 추출
        # 예: "🎨 [개인 DB] filename.pdf  (chunks: 10)"
        import re
        # 마커 제거 후 파일명 추출
        cleaned_text = re.sub(r'^🎨 ', '', display_text)  # Vision 마커 제거
        cleaned_text = re.sub(r'^\[.*?\] ', '', cleaned_text)  # DB 타입 마커 제거
        file_name = cleaned_text.split('  (chunks:')[0].strip()

        db_type_name = "공유 DB" if target_db == "shared" else "개인 DB"

        # 임베딩 삭제 여부 확인
        reply = QMessageBox.question(
            self,
            "문서 삭제",
            f"'{file_name}' 문서를 {db_type_name}에서 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # ChromaDB에서 청크 삭제
        try:
            success = self.vector_manager.delete_documents_by_file_name(file_name, target_db=target_db)
            if not success:
                QMessageBox.warning(
                    self,
                    "삭제 경고",
                    f"{db_type_name}에서 '{file_name}' 청크 삭제에 실패했습니다.\n파일만 삭제됩니다."
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                "삭제 오류",
                f"ChromaDB 삭제 중 오류:\n{e}\n\n파일만 삭제됩니다."
            )

        # 저장된 원본 파일도 삭제할지 물어보기
        # DB별 embedded_documents 경로 결정
        if target_db == "shared" and self.vector_manager.shared_db_enabled:
            # 공유 DB: [공유DB경로]/../embedded_documents
            shared_base = os.path.dirname(self.vector_manager.shared_db_path)
            embedded_path = os.path.join(shared_base, "embedded_documents", file_name)
        else:
            # 개인 DB: data/embedded_documents
            embedded_path = os.path.join("data/embedded_documents", file_name)

        if os.path.exists(embedded_path):
            reply = QMessageBox.question(
                self,
                "원본 파일 삭제",
                f"저장된 원본 파일도 함께 삭제하시겠습니까?\n\n{file_name}\n\n위치: {embedded_path}",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    os.remove(embedded_path)
                    self.log_view.append(f"✓ 원본 파일 삭제 완료: {file_name}")
                except Exception as e:
                    QMessageBox.warning(self, "삭제 실패", f"원본 파일 삭제 실패:\n{e}")
        
        self.refresh_list()
        self.documents_changed.emit()

    def on_preview(self) -> None:
        """선택된 파일을 OS 기본 프로그램으로 열기"""
        current = self.list_widget.currentItem()
        if not current:
            QMessageBox.information(self, "파일 열기", "파일을 먼저 선택해주세요.")
            return

        display_text = current.text()

        # DB 타입 파악
        target_db = "personal"  # 기본값
        if "[공유 DB]" in display_text:
            target_db = "shared"
        elif "[개인 DB]" in display_text:
            target_db = "personal"

        # 파일 이름 추출 (마커 제거)
        import re
        cleaned_text = re.sub(r'^🎨 ', '', display_text)  # Vision 마커 제거
        cleaned_text = re.sub(r'^\[.*?\] ', '', cleaned_text)  # DB 타입 마커 제거
        file_name = cleaned_text.split('  (chunks:')[0].strip()

        # DB별 embedded_documents 경로 결정
        if target_db == "shared" and self.vector_manager.shared_db_enabled:
            # 공유 DB: [공유DB경로]/../embedded_documents
            shared_base = os.path.dirname(self.vector_manager.shared_db_path)
            file_path = os.path.join(shared_base, "embedded_documents", file_name)
        else:
            # 개인 DB: data/embedded_documents
            file_path = os.path.join("data/embedded_documents", file_name)

        # 파일 존재 확인
        if not os.path.exists(file_path):
            QMessageBox.warning(
                self,
                "파일 열기 실패",
                f"파일을 찾을 수 없습니다:\n{file_name}\n\n"
                "파일이 삭제되었거나 임베딩 시 저장되지 않았을 수 있습니다."
            )
            return

        try:
            # 절대 경로로 변환
            abs_path = os.path.abspath(file_path)

            # OS별 파일 열기
            if sys.platform == "win32":
                # Windows: os.startfile 사용
                os.startfile(abs_path)
            elif sys.platform == "darwin":
                # macOS: open 명령어 사용
                subprocess.call(['open', abs_path])
            else:
                # Linux: xdg-open 사용
                subprocess.call(['xdg-open', abs_path])

            # 성공 메시지는 표시하지 않음 (파일이 바로 열리므로)

        except Exception as e:
            QMessageBox.warning(
                self,
                "파일 열기 실패",
                f"파일을 여는 중 오류가 발생했습니다:\n{file_name}\n\n오류: {e}"
            )

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
