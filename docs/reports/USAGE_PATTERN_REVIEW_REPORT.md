# 사용 패턴 기반 시스템 검토 보고서

**작성일**: 2025-11-29
**검토 범위**: 사용자 사용 패턴 관점에서의 시스템 안정성 및 불합리한 점
**검토 기준**: 실제 사용 시나리오별 잠재적 문제점 분석
**코드 검토일**: 2025-11-29 (실제 코드 기반 검증 완료)

---

## 📋 목차

1. [검토 개요](#1-검토-개요)
2. [동시 작업 처리 문제](#2-동시-작업-처리-문제)
3. [설정 변경 시 기존 작업 영향](#3-설정-변경-시-기존-작업-영향)
4. [리소스 정리 및 메모리 관리](#4-리소스-정리-및-메모리-관리)
5. [스레드 안전성 및 동시성](#5-스레드-안전성-및-동시성)
6. [데이터베이스 동시 접근](#6-데이터베이스-동시-접근)
7. [종합 평가 및 권장사항](#7-종합-평가-및-권장사항)
8. [검토 후 개선 사항](#8-검토-후-개선-사항)
9. [변경 이력](#9-변경-이력)

---

## 1. 검토 개요

### 1.1 검토 목적

실제 사용자가 시스템을 사용할 때 발생할 수 있는 문제점을 사전에 발견하고 개선하기 위함.

### 1.2 주요 검토 시나리오

1. **동시 작업**: 업로드 중 질문, 질문 중 업로드
2. **설정 변경**: 업로드/질문 진행 중 설정 변경
3. **앱 종료**: 진행 중인 작업이 있을 때 앱 종료
4. **연속 작업**: 빠르게 연속으로 질문/업로드
5. **대용량 처리**: 큰 파일 업로드, 긴 질문 처리
6. **네트워크 오류**: 네트워크 문제 발생 시 복구

### 1.3 검토 방법

- 코드 분석: 실제 구현 코드 검토
- 시나리오 분석: 사용 패턴별 잠재적 문제점 도출
- 리소스 관리: 메모리, 스레드, 파일 핸들링 검토

---

## 2. 동시 작업 처리 문제

### 2.1 🔴 스레드 중복 실행 방지 부재 (심각)

#### 문제 현상

**시나리오 1: 질문 중복 실행**
- 사용자가 질문을 보냄 → 응답 생성 중
- 사용자가 또 다른 질문을 보냄 → **이전 질문이 완료되지 않았는데 새 스레드 시작**

**시나리오 2: 업로드 중복 실행**
- 파일 업로드 중
- 사용자가 또 다른 파일 업로드 → **이전 업로드가 완료되지 않았는데 새 스레드 시작**

#### 코드 위치

**ChatWidget** (`ui/chat_widget.py:605-614`):
```python
def on_send(self) -> None:
    # ... 질문 처리 ...
    
    # ❌ 이전 스레드 실행 중인지 확인 없음
    self._stream_thread = QThread(self)
    self._stream_worker = StreamWorker(self.rag_chain, question, self.messages, search_mode)
    self._stream_worker.moveToThread(self._stream_thread)
    # ... 스레드 시작 ...
    self._stream_thread.start()
```

**DocumentWidget** (`ui/document_widget.py:425-459`):
```python
def _start_upload(self, file_paths):
    # ... 업로드 준비 ...

    # ❌ 이전 스레드 실행 중인지 확인 없음
    self._thread = QThread(self)
    self._worker = UploadWorker(...)
    # ... 스레드 시작 ...
    self._thread.start()
```

#### 문제점

1. **메모리 누수 가능성**
   - 이전 스레드가 완료되지 않았는데 새 스레드 생성
   - 이전 스레드의 Worker 객체가 메모리에 남을 수 있음
   - `deleteLater()`는 스레드가 완료된 후에만 호출됨

2. **리소스 경합**
   - 동시에 여러 질문이 RAGChain을 사용
   - 동시에 여러 업로드가 VectorStore를 사용
   - ChromaDB 동시 접근 시 파일 잠금 오류 가능

3. **사용자 혼란**
   - 여러 응답이 동시에 생성되어 UI가 혼란스러울 수 있음
   - 진행률 표시가 겹칠 수 있음

#### 해결 방안

**ChatWidget 개선**:
```python
def on_send(self) -> None:
    question = self.input_edit.toPlainText().strip()
    if not question:
        return
    
    # ✅ 이전 스레드 실행 중인지 확인
    if self._stream_thread and self._stream_thread.isRunning():
        QMessageBox.warning(
            self,
            "질문 진행 중",
            "이전 질문이 아직 처리 중입니다. 완료 후 다시 시도해주세요."
        )
        return
    
    # ... 기존 코드 ...
```

**DocumentWidget 개선**:
```python
def _start_upload(self, file_paths):
    if not file_paths:
        return
    
    # ✅ 이전 업로드 진행 중인지 확인
    if self._thread and self._thread.isRunning():
        QMessageBox.warning(
            self,
            "업로드 진행 중",
            "이전 업로드가 아직 진행 중입니다. 완료 후 다시 시도해주세요."
        )
        return
    
    # ... 기존 코드 ...
```

**우선순위**: 🔴 높음  
**예상 소요**: 30분

---

### 2.2 🟡 업로드 중 질문 가능 (의도된 동작)

#### 현재 동작

- 업로드와 질문은 별도 스레드에서 실행되므로 동시에 가능
- 이는 **의도된 동작**으로 보임 (사용자가 업로드 중에도 질문 가능)

#### 잠재적 문제

1. **리소스 경합**
   - 업로드 중 VectorStore에 쓰기 작업
   - 질문 중 VectorStore에서 읽기 작업
   - ChromaDB는 읽기/쓰기 동시 접근을 지원하지만, 성능 저하 가능

2. **데이터 일관성**
   - 업로드 중인 문서가 질문 결과에 포함되지 않을 수 있음
   - 이는 정상 동작이지만 사용자가 혼란스러울 수 있음

#### 권장사항

- 현재 동작 유지 (사용자 편의성)
- 필요 시 사용자에게 알림: "업로드 중인 문서는 아직 검색되지 않습니다"

**우선순위**: 🟢 낮음 (현재 동작 문제 없음)

---

## 3. 설정 변경 시 기존 작업 영향

### 3.1 🔴 설정 변경 시 진행 중 작업 취소 없음 (중간)

#### 문제 현상

**시나리오**:
1. 사용자가 질문을 보냄 → 응답 생성 중 (이전 LLM 설정 사용)
2. 사용자가 설정 탭에서 LLM 모델 변경 → `rag_chain.update_llm()` 호출
3. 진행 중인 질문은 **이전 설정으로 계속 진행**
4. 새 질문은 **새 설정으로 진행**

#### 코드 위치

**SettingsWidget** (`ui/settings_widget.py:289-303`):
```python
# LLM 설정이 변경된 경우에만 업데이트
if llm_changed and self.rag_chain:
    progress.setLabelText("LLM 설정 적용 중...")
    QApplication.processEvents()
    
    # ❌ 진행 중인 질문/업로드 취소 없음
    self.rag_chain.update_llm(
        llm_api_type=new_llm_api_type,
        llm_base_url=new_llm_base_url,
        llm_model=new_llm_model,
        llm_api_key=new_llm_api_key,
        temperature=new_temperature,
    )
```

#### 문제점

1. **설정 불일치**
   - 진행 중인 질문: 이전 LLM 사용
   - 새 질문: 새 LLM 사용
   - 사용자가 혼란스러울 수 있음

2. **임베딩 설정 변경 시**
   - 진행 중인 업로드: 이전 임베딩 모델 사용
   - 새 업로드: 새 임베딩 모델 사용
   - **차원 불일치 가능성** (심각)

#### 해결 방안

**옵션 1: 진행 중 작업 취소 (권장)**
```python
def _save(self) -> None:
    # ... 설정 변경 감지 ...
    
    # ✅ 진행 중인 작업 확인 및 취소
    if llm_changed or embedding_changed:
        # ChatWidget에서 진행 중인 질문 취소
        if hasattr(self.parent(), 'chat_tab'):
            chat_widget = self.parent().chat_tab
            if chat_widget._stream_thread and chat_widget._stream_thread.isRunning():
                reply = QMessageBox.question(
                    self,
                    "설정 변경",
                    "진행 중인 질문이 있습니다. 취소하고 설정을 변경하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    # 스레드 종료 (안전하게)
                    chat_widget._stream_thread.quit()
                    chat_widget._stream_thread.wait(3000)  # 최대 3초 대기
                else:
                    return  # 설정 변경 취소
        
        # DocumentWidget에서 진행 중인 업로드 취소
        if hasattr(self.parent(), 'doc_tab'):
            doc_widget = self.parent().doc_tab
            if doc_widget._thread and doc_widget._thread.isRunning():
                reply = QMessageBox.question(
                    self,
                    "설정 변경",
                    "진행 중인 업로드가 있습니다. 취소하고 설정을 변경하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    if doc_widget._worker:
                        doc_widget._worker.cancel()
                    doc_widget._thread.quit()
                    doc_widget._thread.wait(3000)
                else:
                    return
    
    # ... 설정 업데이트 ...
```

**옵션 2: 설정 변경 대기 (간단)**
```python
def _save(self) -> None:
    # 진행 중인 작업 확인
    if self._has_running_operations():
        QMessageBox.warning(
            self,
            "설정 변경 불가",
            "진행 중인 작업이 있습니다. 완료 후 설정을 변경해주세요."
        )
        return
    
    # ... 설정 업데이트 ...
```

**우선순위**: 🔴 중간 (임베딩 차원 불일치 방지 중요)  
**예상 소요**: 1시간

---

### 3.2 🟡 설정 변경 후 즉시 새 작업 시작 시 일관성 문제

#### 문제 현상

- 설정 변경 후 즉시 새 질문/업로드 시작
- 설정 변경이 완료되기 전에 새 작업이 시작될 수 있음

#### 현재 동작

- `update_llm()`, `update_embeddings()`는 동기적으로 실행
- 설정 변경이 완료된 후에만 `_save()` 메서드가 반환
- 따라서 즉시 새 작업을 시작해도 새 설정 사용 (문제 없음)

#### 권장사항

- 현재 동작 유지
- 필요 시 설정 변경 완료 메시지 추가

**우선순위**: 🟢 낮음 (현재 동작 문제 없음)

---

## 4. 리소스 정리 및 메모리 관리

### 4.1 🔴 앱 종료 시 리소스 정리 없음 (중간)

#### 문제 현상

**시나리오**:
1. 사용자가 질문을 보냄 → 응답 생성 중
2. 사용자가 앱 종료 (X 버튼 클릭)
3. **진행 중인 스레드가 정리되지 않음**
4. ChromaDB 연결이 정리되지 않음

#### 코드 위치

**MainWindow** (`ui/main_window.py`):
- `closeEvent()` 메서드 없음 ❌
- 스레드 정리 로직 없음 ❌

#### 문제점

1. **스레드 좀비 상태**
   - 진행 중인 QThread가 정리되지 않음
   - 메모리 누수 가능성

2. **파일 잠금**
   - ChromaDB 연결이 정리되지 않아 파일 잠금 가능
   - 다음 실행 시 "database is locked" 오류 가능

3. **불완전한 작업**
   - 진행 중인 업로드가 중단되어 부분 데이터 저장 가능

#### 해결 방안

**MainWindow에 closeEvent 추가**:
```python
def closeEvent(self, event) -> None:
    """앱 종료 시 리소스 정리"""
    
    # 진행 중인 작업 확인
    has_running_ops = False
    
    # ChatWidget 스레드 확인
    if hasattr(self, 'chat_tab') and self.chat_tab._stream_thread:
        if self.chat_tab._stream_thread.isRunning():
            has_running_ops = True
    
    # DocumentWidget 스레드 확인
    if hasattr(self, 'doc_tab') and self.doc_tab._thread:
        if self.doc_tab._thread.isRunning():
            has_running_ops = True
    
    if has_running_ops:
        reply = QMessageBox.question(
            self,
            "작업 진행 중",
            "진행 중인 작업이 있습니다. 종료하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            event.ignore()
            return
        
        # 진행 중인 작업 취소
        if hasattr(self, 'chat_tab') and self.chat_tab._stream_thread:
            if self.chat_tab._stream_thread.isRunning():
                self.chat_tab._stream_thread.quit()
                self.chat_tab._stream_thread.wait(2000)  # 최대 2초 대기
        
        if hasattr(self, 'doc_tab') and self.doc_tab._thread:
            if self.doc_tab._thread.isRunning():
                if self.doc_tab._worker:
                    self.doc_tab._worker.cancel()
                self.doc_tab._thread.quit()
                self.doc_tab._thread.wait(2000)
    
    # ChromaDB 연결 정리 (필요 시)
    # VectorStoreManager에 cleanup 메서드 추가 필요
    
    # 자동 저장 (대화 이력)
    try:
        if hasattr(self, 'chat_tab') and self.chat_tab.messages:
            self._autosave()
    except Exception:
        pass
    
    event.accept()
```

**우선순위**: 🔴 중간  
**예상 소요**: 1시간

---

### 4.2 🟢 SessionContext 메모리 누수 가능성 - 수정 보류

#### 문제 현상

**위치**: `utils/session_context.py:159-174`

**현재 동작**:
```python
def _cleanup_old_uploads(self):
    """타임아웃 경과 문서 제거"""
    now = datetime.now()

    # 타임아웃의 2배 이상 경과한 문서만 제거
    self.recent_uploads = [
        doc for doc in self.recent_uploads
        if (now - doc.upload_timestamp) < self.timeout * 2
    ]
```

#### 분석 결과

1. **최대 개수 제한 없음**
   - 타임아웃이 5분이면 최대 10분간 유지
   - 업로드가 매우 많으면 (예: 1분에 10개) 리스트가 증가할 수 있음

2. **정리 빈도**
   - `_cleanup_old_uploads()`는 `get_active_documents()`에서 호출됨
   - 질문 시마다 호출되어 주기적으로 정리됨

#### 코드 검토 결과

**실제 발생 가능성 낮음**:
- 실제 사용 패턴에서 1분에 10개 이상 업로드는 현실적이지 않음
- 타임아웃(5분)의 2배인 10분 후에는 자동 정리됨
- 질문할 때마다 정리 로직이 실행됨
- 각 업로드 기록은 메타데이터만 저장하여 메모리 사용량 미미함

**우선순위**: 🟢 낮음 (실제 발생 가능성 낮음)
**수정 결정**: ⏸️ **보류** - 현재 동작에 실질적 문제 없음

---

## 5. 스레드 안전성 및 동시성

### 5.1 🟡 RAGChain 동시 접근 안전성

#### 현재 동작

- `ChatWidget`에서 `rag_chain.query_stream()` 호출
- 여러 질문이 동시에 실행되면 동일한 `rag_chain` 객체 공유

#### 잠재적 문제

1. **내부 상태 공유**
   - `rag_chain._last_retrieved_docs`는 매번 덮어쓰기 (문제 없음 ✅)
   - 하지만 내부적으로 상태를 변경하는 메서드가 있다면 문제 가능

2. **VectorStore 동시 접근**
   - 여러 질문이 동시에 `vectorstore.as_retriever()` 호출
   - ChromaDB는 읽기 동시 접근 지원 (문제 없음 ✅)

#### 검토 결과

- 현재 구현은 **스레드 안전** (상태 변경 없음)
- `_last_retrieved_docs`는 매번 새로 할당되어 이전 데이터 자동 해제

**우선순위**: 🟢 낮음 (현재 동작 문제 없음)

---

### 5.2 🟡 VectorStore 동시 접근

#### 현재 동작

- 업로드: `vectorstore.add_documents()` (쓰기)
- 질문: `vectorstore.as_retriever()` (읽기)

#### 잠재적 문제

1. **ChromaDB 파일 잠금**
   - SQLite 기반이므로 동시 쓰기 시 잠금 오류 가능
   - 하지만 읽기/쓰기 동시 접근은 지원

2. **BM25 인덱스 업데이트**
   - 업로드 시 BM25 인덱스 백그라운드 재로딩
   - 재로딩 중 질문 시 이전 인덱스 사용 (문제 없음 ✅)

#### 검토 결과

- 현재 구현은 **안전** (읽기/쓰기 동시 접근 지원)
- 공유 DB 환경에서만 주의 필요 (6장 참조)

**우선순위**: 🟢 낮음 (현재 동작 문제 없음)

---

## 6. 데이터베이스 동시 접근

### 6.1 🔴 공유 DB 동시 접근 시 파일 잠금 문제 (중간)

#### 문제 현상

**시나리오**:
- 사용자 A: 공유 DB에 문서 업로드 중
- 사용자 B: 동시에 공유 DB에 문서 업로드 시도
- **ChromaDB 파일 잠금 오류 발생 가능**

#### 코드 위치

**VectorStore** (`utils/vector_store.py:742-751`):
```python
if target_db == "shared":
    print(f"[VectorStore] 문서 임베딩 생성 중... ({len(documents)}개 청크 → 공유 DB)")
    self.shared_vectorstore.add_documents(documents)  # ← 파일 잠금 가능
    db_name = "공유 DB"
```

#### 문제점

1. **SQLite 동시 쓰기 제한**
   - ChromaDB는 SQLite 기반
   - 동시 쓰기 시 `database is locked` 오류 발생
   - 읽기/쓰기 동시 접근은 지원하지만, 쓰기/쓰기는 제한

2. **재시도 로직 없음**
   - 파일 잠금 오류 발생 시 즉시 실패
   - 재시도 로직 없음

#### 해결 방안

**옵션 1: 재시도 로직 추가 (권장)**
```python
def add_documents(self, documents: List[Document], ..., target_db: str = "personal", ...):
    # ... 기존 코드 ...
    
    if target_db == "shared":
        # ✅ 재시도 로직 추가
        MAX_RETRIES = 3
        RETRY_DELAY = 1.0  # 1초
        
        for attempt in range(MAX_RETRIES):
            try:
                self.shared_vectorstore.add_documents(documents)
                break
            except Exception as e:
                error_msg = str(e).lower()
                if "locked" in error_msg or "database is locked" in error_msg:
                    if attempt < MAX_RETRIES - 1:
                        print(f"[VectorStore][WARN] DB 잠금 오류 (시도 {attempt + 1}/{MAX_RETRIES}), {RETRY_DELAY}초 후 재시도...")
                        time.sleep(RETRY_DELAY)
                        RETRY_DELAY *= 2  # 지수 백오프
                    else:
                        raise RuntimeError(
                            f"공유 DB에 문서 추가 실패 (재시도 {MAX_RETRIES}회 초과): "
                            f"다른 사용자가 DB를 사용 중입니다. 잠시 후 다시 시도해주세요."
                        )
                else:
                    raise  # 다른 오류는 즉시 전파
```

**옵션 2: 파일 잠금 감지 및 사용자 안내**
```python
except Exception as e:
    if "locked" in str(e).lower():
        raise RuntimeError(
            "공유 DB가 다른 사용자에 의해 사용 중입니다.\n"
            "잠시 후 다시 시도해주세요."
        )
    raise
```

**우선순위**: 🔴 중간 (공유 DB 사용 시 중요)  
**예상 소요**: 30분

---

### 6.2 🟡 공유 DB 경로 검증 부족

#### 문제 현상

**위치**: `desktop_app.py:111-123`, `utils/vector_store.py:reconnect_shared_db()`

**현재 검증**:
- `chroma.sqlite3` 파일 존재만 확인
- 실제 읽기/쓰기 권한 확인 없음

#### 문제점

1. **권한 문제 미감지**
   - 파일은 존재하지만 쓰기 권한 없을 수 있음
   - 네트워크 드라이브 접근 불가능할 수 있음

2. **초기화 시에만 검증**
   - 설정 변경 시 재검증 없음

#### 해결 방안

```python
def reconnect_shared_db(self) -> bool:
    # ... 기존 경로 확인 ...
    
    # ✅ 실제 읽기/쓰기 권한 테스트
    try:
        # 테스트 파일 생성/삭제
        test_file = os.path.join(shared_db_path, ".write_test")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            raise RuntimeError(f"공유 DB 경로에 쓰기 권한이 없습니다: {e}")
        
        # ChromaDB 연결 테스트
        test_client = chromadb.PersistentClient(path=shared_db_path)
        # 간단한 조회 테스트
        test_client.get_or_create_collection("_test")
        test_client.delete_collection("_test")
        
    except Exception as e:
        print(f"[VectorStore] 공유 DB 접근 테스트 실패: {e}")
        return False
    
    # ... 기존 초기화 로직 ...
```

**우선순위**: 🟡 낮음 (현재 동작 문제 없음)  
**예상 소요**: 20분

---

## 7. 종합 평가 및 권장사항

### 7.1 발견된 문제 요약

| 우선순위 | 문제 | 위치 | 심각도 | 예상 소요 | 수정 여부 |
|---------|------|------|--------|----------|----------|
| 🔴 높음 | 스레드 중복 실행 방지 부재 | `ui/chat_widget.py`, `ui/document_widget.py` | 심각 | 30분 | ✅ **완료** |
| 🔴 중간 | 설정 변경 시 진행 중 작업 취소 없음 | `ui/settings_widget.py` | 중간 | 1시간 | ✅ **완료** |
| 🔴 중간 | 앱 종료 시 리소스 정리 없음 | `ui/main_window.py` | 중간 | 1시간 | ✅ **완료** |
| 🔴 중간 | 공유 DB 동시 접근 시 파일 잠금 | `utils/vector_store.py` | 중간 | 30분 | ✅ **완료** |
| 🟢 낮음 | SessionContext 메모리 제한 없음 | `utils/session_context.py` | 낮음 | - | ⏸️ 보류 |
| 🟡 낮음 | 공유 DB 경로 검증 부족 | `utils/vector_store.py` | 낮음 | 20분 | ⏸️ 보류 |

**수정 예정 총 소요**: 약 3시간

**참고**: 아래 수정 계획에는 검토 후 개선 사항이 반영되어 있습니다.

---

### 7.2 수정 계획

#### Phase 1: 즉시 적용 (30분)

**1. 스레드 중복 실행 방지**

| 파일 | 수정 내용 |
|-----|---------|
| `ui/chat_widget.py` | `on_send()` 시작 부분에 `isRunning()` 체크 추가 |
| `ui/document_widget.py` | `_start_upload()` 시작 부분에 `isRunning()` 체크 추가 |

**ChatWidget 수정안**:
```python
def on_send(self) -> None:
    question = self.input_edit.toPlainText().strip()
    if not question:
        return

    # ✅ 이전 스레드 실행 중인지 확인
    if self._stream_thread and self._stream_thread.isRunning():
        QMessageBox.warning(
            self,
            "질문 진행 중",
            "이전 질문이 아직 처리 중입니다. 완료 후 다시 시도해주세요."
        )
        return

    # ... 기존 코드 ...
```

**DocumentWidget 수정안**:
```python
def _start_upload(self, file_paths):
    if not file_paths:
        return

    # ✅ 이전 업로드 진행 중인지 확인
    if self._thread and self._thread.isRunning():
        QMessageBox.warning(
            self,
            "업로드 진행 중",
            "이전 업로드가 아직 진행 중입니다. 완료 후 다시 시도해주세요."
        )
        return

    # ... 기존 코드 ...
```

---

#### Phase 2: 단기 개선 (2시간 30분)

**2. 앱 종료 시 리소스 정리** (1시간)

| 파일 | 수정 내용 |
|-----|---------|
| `ui/main_window.py` | `closeEvent()` 메서드 추가 |

**MainWindow 수정안** (개선된 버전):
```python
def closeEvent(self, event) -> None:
    """앱 종료 시 리소스 정리"""
    from PySide6.QtWidgets import QMessageBox

    # ✅ 진행 중인 작업 확인 및 수집 (중복 제거)
    running_threads = []

    if hasattr(self, 'chat_tab') and hasattr(self.chat_tab, '_stream_thread'):
        if self.chat_tab._stream_thread and self.chat_tab._stream_thread.isRunning():
            running_threads.append(('chat', self.chat_tab._stream_thread, None))

    if hasattr(self, 'doc_tab') and hasattr(self.doc_tab, '_thread'):
        if self.doc_tab._thread and self.doc_tab._thread.isRunning():
            worker = getattr(self.doc_tab, '_worker', None)
            running_threads.append(('doc', self.doc_tab._thread, worker))

    if running_threads:
        reply = QMessageBox.question(
            self,
            "작업 진행 중",
            "진행 중인 작업이 있습니다. 종료하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            event.ignore()
            return

        # ✅ 스레드 정리 (중복 제거, 강제 종료 처리)
        for thread_type, thread, worker in running_threads:
            if thread_type == 'doc' and worker:
                worker.cancel()
            thread.quit()
            if not thread.wait(2000):  # 2초 내 종료 안 되면
                print(f"[MainWindow][WARN] {thread_type} 스레드가 2초 내 종료되지 않음")
                # QThread는 앱 종료 시 자동으로 정리되므로 강제 종료 불필요

    # 자동 저장
    try:
        if hasattr(self, 'chat_tab') and self.chat_tab.messages:
            self._autosave()
    except Exception:
        pass

    event.accept()
```

**개선 사항**:
- ✅ 중복 체크 제거: 스레드를 리스트로 수집하여 한 번만 처리
- ✅ 강제 종료 처리: `wait()` 결과 확인 및 경고 로그
- ✅ 코드 간결성: 반복 코드 제거

---

**3. 설정 변경 시 진행 중 작업 대기** (1시간)

| 파일 | 수정 내용 |
|-----|---------|
| `ui/settings_widget.py` | `_save()` 시작 부분에 진행 중 작업 체크 추가 |

**SettingsWidget 수정안** (옵션 2: 간단한 대기 방식, 개선된 버전):
```python
def _save(self) -> None:
    # ✅ 진행 중인 작업 확인
    if self._has_running_operations():
        QMessageBox.warning(
            self,
            "설정 변경 불가",
            "진행 중인 작업이 있습니다. 완료 후 설정을 변경해주세요."
        )
        return

    # ... 기존 설정 저장 코드 ...

def _has_running_operations(self) -> bool:
    """진행 중인 작업이 있는지 확인"""
    # ✅ MainWindow 참조 안전하게 가져오기
    # addTab으로 reparent될 수 있으므로 self.main_window 또는 self.parent() 사용
    main_window = self.main_window
    if not main_window:
        # reparent된 경우 parent() 사용
        parent = self.parent()
        # MainWindow 타입 찾기 (간단한 방법)
        while parent and not hasattr(parent, 'chat_tab'):
            parent = parent.parent()
        if parent:
            main_window = parent
        else:
            return False  # MainWindow를 찾을 수 없으면 False 반환
    
    if not main_window:
        return False
    
    # ChatWidget 확인
    if hasattr(main_window, 'chat_tab'):
        chat = main_window.chat_tab
        if hasattr(chat, '_stream_thread') and chat._stream_thread:
            if chat._stream_thread.isRunning():
                return True

    # DocumentWidget 확인
    if hasattr(main_window, 'doc_tab'):
        doc = main_window.doc_tab
        if hasattr(doc, '_thread') and doc._thread:
            if doc._thread.isRunning():
                return True
    
    return False
```

**개선 사항**:
- ✅ MainWindow 접근 안전성: `self.main_window`가 None일 경우 `self.parent()` 사용
- ✅ reparent 대응: `addTab`으로 reparent된 경우에도 동작
- ✅ 예외 처리: MainWindow를 찾을 수 없으면 안전하게 False 반환

---

**4. 공유 DB 동시 접근 재시도** (30분)

| 파일 | 수정 내용 |
|-----|---------|
| `utils/vector_store.py` | `add_documents()` 내 공유 DB 쓰기 시 재시도 로직 추가 |

**VectorStore 수정안** (개선된 버전):
```python
# add_documents 메서드 내 공유 DB 처리 부분
# ✅ time 모듈은 파일 상단에서 import (utils/vector_store.py 상단에 추가 필요)
# import time  # 파일 상단에 추가

if target_db == "shared":
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    for attempt in range(MAX_RETRIES):
        try:
            print(f"[VectorStore] 문서 임베딩 생성 중... ({len(documents)}개 청크 → 공유 DB)")
            self.shared_vectorstore.add_documents(documents)
            print(f"[VectorStore] ✓ 임베딩 생성 완료 (공유 DB)")
            break
        except Exception as e:
            error_msg = str(e).lower()
            if "locked" in error_msg or "database is locked" in error_msg:
                if attempt < MAX_RETRIES - 1:
                    print(f"[VectorStore][WARN] DB 잠금 (시도 {attempt + 1}/{MAX_RETRIES}), {RETRY_DELAY}초 후 재시도...")
                    time.sleep(RETRY_DELAY)  # ✅ 파일 상단에서 import한 time 사용
                    RETRY_DELAY *= 2  # 지수 백오프
                else:
                    raise RuntimeError(
                        f"공유 DB 문서 추가 실패: 다른 사용자가 사용 중입니다. 잠시 후 다시 시도해주세요."
                    )
            else:
                raise  # 다른 오류는 즉시 전파
    db_name = "공유 DB"
```

**개선 사항**:
- ✅ time 모듈 import 위치: 루프 내부가 아닌 파일 상단에서 import
- ✅ 주석 추가: import 위치 명시
- ✅ 코드 가독성: 주석으로 개선 사항 설명

---

### 7.3 보류 항목

#### SessionContext 메모리 제한 (보류)

**보류 사유**:
- 실제 사용 패턴에서 문제 발생 가능성 매우 낮음
- 타임아웃 기반 자동 정리 로직이 이미 존재함
- 메타데이터만 저장하여 메모리 영향 미미함

#### 공유 DB 경로 검증 강화 (보류)

**보류 사유**:
- 현재 파일 존재 여부 검증으로 기본적인 검증은 수행됨
- 실제 사용 시 연결 실패 메시지가 명확하게 표시됨
- 추가 검증 로직이 오히려 초기 로딩 시간을 증가시킬 수 있음

---

### 7.4 기대 효과

#### 사용자 경험

✅ **작업 중복 방지**: 사용자가 실수로 중복 작업을 시작하는 것 방지  
✅ **명확한 피드백**: 진행 중인 작업이 있을 때 명확한 안내  
✅ **안전한 종료**: 앱 종료 시 진행 중인 작업 정리

#### 시스템 안정성

✅ **메모리 누수 방지**: 스레드 정리로 메모리 누수 방지  
✅ **파일 잠금 방지**: 공유 DB 동시 접근 시 재시도로 안정성 향상  
✅ **설정 일관성**: 설정 변경 시 진행 중 작업 취소로 일관성 보장

#### 개발/유지보수

✅ **디버깅 용이**: 명확한 오류 메시지 및 로깅  
✅ **코드 품질**: 리소스 정리 패턴 도입  
✅ **확장성**: 향후 기능 추가 시 안정적 기반

---

### 7.5 테스트 계획

#### 시나리오 1: 스레드 중복 실행 방지
1. 질문을 보냄
2. 응답 생성 중에 또 다른 질문 보내기 시도
3. 경고 메시지 표시 확인
4. 이전 질문 완료 후 새 질문 가능 확인

#### 시나리오 2: 설정 변경 중 작업
1. 질문을 보냄 (응답 생성 중)
2. 설정 탭에서 LLM 모델 변경
3. 진행 중인 작업 취소 확인 또는 대기 확인

#### 시나리오 3: 앱 종료 시 정리
1. 업로드 진행 중
2. 앱 종료 (X 버튼)
3. 확인 다이얼로그 표시
4. 종료 선택 시 스레드 정리 확인

#### 시나리오 4: 공유 DB 동시 접근
1. 사용자 A: 공유 DB에 문서 업로드
2. 사용자 B: 동시에 공유 DB에 문서 업로드
3. 재시도 로직 작동 확인 또는 명확한 오류 메시지 확인

---

## 8. 검토 후 개선 사항

### 8.1 수정 계획 검토 결과

**검토일**: 2025-11-29  
**검토 기준**: 구현 가능성, 코드 품질, 안전성

#### ✅ 적절한 부분

1. **스레드 중복 실행 방지**: `isRunning()` 체크 방식 적절
2. **공유 DB 재시도 로직**: 지수 백오프 및 사용자 친화적 메시지 적절
3. **보류 결정**: SessionContext, 공유 DB 경로 검증 보류 타당

#### ⚠️ 개선 필요 부분

1. **closeEvent 스레드 정리 로직 중복**
   - 문제: `has_running_ops` 확인 후 다시 `hasattr` 체크 중복
   - 개선: 스레드를 리스트로 수집하여 한 번만 처리
   - 개선: `wait()` 결과 확인 및 경고 로그 추가

2. **SettingsWidget MainWindow 접근 안전성**
   - 문제: `self.main_window`가 None일 수 있음, reparent 대응 부족
   - 개선: `self.parent()` fallback 추가
   - 개선: MainWindow 찾기 실패 시 안전하게 False 반환

3. **공유 DB 재시도 로직의 time import**
   - 문제: 루프 내부에서 import (비효율)
   - 개선: 파일 상단에서 import

4. **closeEvent 스레드 강제 종료 처리**
   - 문제: `wait()` 후 결과 확인 없음
   - 개선: `wait()` 결과 확인 및 경고 로그 추가

### 8.2 개선 사항 반영

위 개선 사항들이 **7.2 수정 계획** 섹션에 반영되었습니다:
- ✅ MainWindow closeEvent: 중복 제거 및 강제 종료 처리 추가
- ✅ SettingsWidget: MainWindow 접근 안전성 강화
- ✅ VectorStore: time import 위치 개선

---

## 9. 변경 이력

| 날짜 | 내용 |
|-----|------|
| 2025-11-29 | 초안 작성 |
| 2025-11-29 | 코드 기반 검증 완료, 수정 계획 수립 |
| 2025-11-29 | 수정 계획 검토 및 개선 사항 반영 |
| 2025-11-29 | **코드 수정 완료** (Phase 1 + Phase 2 전체) |

**보고서 작성**: 2025-11-29
**코드 검증 완료**: 2025-11-29
**수정 계획 검토 완료**: 2025-11-29
**코드 수정 완료**: 2025-11-29
**상태**: ✅ 완료

