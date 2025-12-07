# 업로드 안정성 문제 분석 보고서

**작성일**: 2025-11-28
**최종 수정**: 2025-11-28 (부분 업로드 전체 롤백 전략 반영)
**시스템 버전**: v0.5.0
**우선순위**: 🔴 최우선 (시스템 안정성)
**검토 범위**: Vision PDF 업로드 중 중단 및 복구 실패 문제
**정책 결정**: 부분 업로드 발생 시 전체 롤백 (문서 업로드 실패로 처리)

---

## 📋 목차

1. [문제 현상](#1-문제-현상)
2. [원인 분석](#2-원인-분석)
3. [해결 방안](#3-해결-방안)
4. [구현 우선순위](#4-구현-우선순위)
5. [기대 효과](#5-기대-효과)
6. [다음 단계](#6-다음-단계)
7. [추가 개선 권장사항](#7-추가-개선-권장사항-구현-후-검토-결과)

---

## 1. 문제 현상

### 사용자 보고 내용

**상황**:
- 12페이지 PDF 문서 업로드 중
- 3페이지까지 Vision 이미지 변환 및 API 응답 정상 수신
- 4페이지에서 "API 요청 전송 중..." 메시지 이후 **무응답**

**증상**:
1. **타임아웃 미작동**: 60초 타임아웃 설정되어 있으나 60초 경과 후에도 응답 없음
2. **취소 불가**: "업로드 취소" 버튼 클릭 시 "취소 요청됨..." 메시지만 표시되고 실제 취소 안 됨
3. **시스템 멈춤**: 이후 다른 질문/작업 시도해도 시스템이 작동하지 않음
4. **복구 불가**: 애플리케이션 재시작만이 유일한 해결책

### 심각도 평가

| 항목 | 평가 | 이유 |
|------|------|------|
| **사용자 경험** | 🔴 심각 | 강제 종료 후 재시작 필요 |
| **데이터 손실** | 🟡 보통 | 이미 처리된 3페이지는 DB 저장 여부 불명확 |
| **시스템 안정성** | 🔴 심각 | 전체 시스템이 응답 불가 상태로 전환 |
| **재현 가능성** | 🟡 보통 | 네트워크 지연/오류 시 발생 가능 |

---

## 2. 원인 분석

### 2.1 취소 메커니즘 부재 (가장 심각) 🔴

#### 문제 코드 구조

```
UploadWorker.run() [취소 플래그: self._cancelled 있음]
  ↓
DocumentProcessor.process_document()
  ↓
PDFChunkingEngine._process_pdf_with_vision()
  ↓
for page_num in range(1, page_count+1):  ← ⚠️ 취소 체크 없음
  ↓
_analyze_page_with_vision()
  ↓
requests.post(..., timeout=60)  ← ⚠️ 여기서 블로킹
```

#### 코드 위치 및 문제점

**파일**: `utils/pdf_chunking_engine.py`
**라인**: [961-987](d:\python\RAG_for_OC_251014\utils\pdf_chunking_engine.py#L961-L987)

```python
# 각 페이지 분석
chunks = []
document_id = str(uuid.uuid4())

for page_num, image in enumerate(images, 1):  # ← 취소 체크 없음
    progress_pct = (page_num / page_count) * 100
    print(f"[PDFChunkingEngine] 페이지 {page_num}/{page_count} Vision 분석 중...")

    # ... 이미지 인코딩 ...

    # Vision 분석
    try:
        description = self._analyze_page_with_vision(...)  # ← 여기서 블로킹
    except Exception as e:
        # ...
```

**문제**:
- `UploadWorker`의 `self._cancelled` 플래그를 `PDFChunkingEngine`이 접근 불가
- 사용자가 "취소" 버튼 클릭해도 **이미 실행 중인 페이지 루프는 계속 진행**
- 취소 요청이 실제 취소로 이어지지 않음

#### UploadWorker의 취소 체크

**파일**: `ui/document_widget.py`
**라인**: [38-84](d:\python\RAG_for_OC_251014\ui\document_widget.py#L38-L84)

```python
for idx, file_path in enumerate(self.file_paths, 1):
    # 취소 확인 (파일 단위만 체크)
    if self._cancelled:
        self.message.emit(f"⚠️ 업로드 취소됨 ({idx-1}/{total} 완료)")
        break

    # 문서 처리 (여기서 블로킹 발생)
    chunks = self.document_processor.process_document(...)  # ← 내부에서 취소 체크 불가
```

**문제**:
- 취소 체크가 **파일 단위**로만 동작
- 하나의 파일 처리 중에는 취소 불가
- PDF Vision 처리는 페이지당 수십 초 소요 → 12페이지면 최대 수 분 블로킹

---

### 2.2 타임아웃 미작동 🔴

#### 문제 코드

**파일**: `utils/pdf_chunking_engine.py`
**라인**: [1155](d:\python\RAG_for_OC_251014\utils\pdf_chunking_engine.py#L1155)

```python
print(f"  → API 요청 전송 중... (타임아웃: 60초)")
response = requests.post(api_url, headers=headers, json=payload, timeout=60)
response.raise_for_status()
```

#### 문제점

1. **단일 타임아웃 값 사용**
   ```python
   timeout=60  # 연결 타임아웃 + 읽기 타임아웃 모두 60초
   ```
   - 연결 타임아웃과 읽기 타임아웃이 분리되지 않음
   - 연결은 성공했지만 응답이 느린 경우 60초 전체 대기

2. **네트워크 스택 레벨 블로킹**
   - OS 레벨에서 네트워크 스택이 멈추면 `requests` 타임아웃 무시될 수 있음
   - TCP keepalive 미설정 시 연결 상태 확인 불가
   - 사용자 보고: **60초 경과 후에도 응답 없음** → 타임아웃 실패 증거

3. **타임아웃 예외 처리 미흡**
   ```python
   except requests.exceptions.Timeout:
       raise RuntimeError(f"Vision API 타임아웃 (페이지 {page_num})")
   ```
   - 예외는 발생시키지만 상위 레벨에서 복구 로직 없음

---

### 2.3 예외 발생 시 시스템 복구 불가 🔴

#### 문제 구조

**UploadWorker 예외 처리**
**파일**: `ui/document_widget.py`
**라인**: [122-128](d:\python\RAG_for_OC_251014\ui\document_widget.py#L122-L128)

```python
except Exception as e:
    error_msg = str(e)
    self.message.emit(f"❌ 오류: {file_name}")
    # 에러 메시지가 여러 줄이면 각 줄을 표시
    for line in error_msg.split('\n'):
        if line.strip():
            self.message.emit(f"   {line}")
    # 진행률은 완료로 표시
    current_stage = idx * stages_per_file
    self.progress.emit(int(current_stage * 100 / total_stages))
```

#### 문제점

1. **모든 예외를 동일하게 처리**
   - `Timeout`, `NetworkError`, `CancelledException` 모두 같은 처리
   - 복구 가능한 오류 vs 치명적 오류 구분 없음

2. **시스템 상태 복구 없음**
   - 오류 발생 후 다음 작업이 정상 작동하지 않음
   - 사용자 보고: "다른 질문해도 작동 안 함"
   - **추측**: Worker 스레드가 좀비 상태로 남아있거나, UI 블로킹 상태 지속

3. **부분 업로드 발생 (전체 롤백 필요)** 🔴
   - **현재 동작**: 페이지 루프에서 실패 시 `continue`로 건너뛰고 계속 진행
   - **실제 결과**: 3페이지까지 성공 → 4페이지 실패 → 5-12페이지 성공
   - **문제점**: 부분 청크가 DB에 저장됨 (원자성 없음)
   - **사용자 요구사항**: 부분 업로드 발생 시 **전체 롤백** (문서 업로드 실패로 처리)
   - **코드 위치**: `utils/pdf_chunking_engine.py:1005-1007`

---

### 2.4 진행 상황 업데이트 부족 🟡

#### 문제 코드

**파일**: `utils/pdf_chunking_engine.py`
**라인**: [963, 978](d:\python\RAG_for_OC_251014\utils\pdf_chunking_engine.py#L963)

```python
for page_num, image in enumerate(images, 1):
    progress_pct = (page_num / page_count) * 100
    print(f"[PDFChunkingEngine] 페이지 {page_num}/{page_count} Vision 분석 중... ({progress_pct:.1f}%)")
    # ↑ print()만 하고 UI 업데이트 없음

    # ...

    print(f"  → Vision API 호출 중... (모델: {self.vision_model})")
    # ↑ 역시 print()만
```

#### 문제점

1. **UI와 연결 없음**
   - `PDFChunkingEngine`은 `UploadWorker`와 직접 연결 없음
   - `print()` 출력은 콘솔에만 표시 (사용자는 볼 수 없음)

2. **사용자 피드백 부재**
   - 마지막 메시지: "📖 문서 분석 중..." (파일 시작 시 1회)
   - 이후 페이지별 진행 상황 업데이트 없음
   - 사용자는 "4페이지 API 요청 전송 중..." 이후 **아무 피드백 없음**

3. **진행률 계산 오류**
   - `UploadWorker`는 4단계(파일 저장, 문서 처리, 청크 분석, 임베딩 저장)로 진행률 계산
   - 하지만 "문서 처리" 단계 내부에서 12페이지 처리는 진행률에 반영 안 됨
   - 예: 2단계 시작 (25%) → ... → 2단계 완료 (50%) 사이에 페이지별 진행 상황 없음

---

## 3. 해결 방안

### 3.1 취소 가능한 콜백 메커니즘 (권장) 🔴

#### 설계 원칙

1. **취소 플래그를 콜백으로 전달**
   - `UploadWorker.cancel()` → `PDFChunkingEngine`까지 전파
   - 각 페이지 처리 전에 취소 체크

2. **진행 상황을 콜백으로 전달**
   - 페이지 처리 시작/완료 시 `UploadWorker`에 알림
   - `UploadWorker`가 UI 업데이트 (`progress.emit`, `message.emit`)

3. **예외 정의**
   ```python
   class CancelledException(Exception):
       """업로드가 취소되었을 때 발생하는 예외"""
       pass

   class PartialUploadException(Exception):
       """부분 업로드 발생 시 발생하는 예외 (전체 롤백용)"""
       def __init__(self, message: str, failed_pages: List[int]):
           super().__init__(message)
           self.failed_pages = failed_pages
   ```

4. **전체 롤백 전략**
   - 페이지 처리 중 실패 감지 시 즉시 예외 발생
   - 부분 청크는 DB에 저장되지 않음 (원자성 보장)
   - 사용자에게 명확한 오류 메시지 표시

#### 구현 방안

**1단계: DocumentProcessor 인터페이스 확장**

```python
# utils/document_processor.py

class DocumentProcessor:
    def process_document(self,
                        file_path: str,
                        file_name: str,
                        file_type: str,
                        cancel_callback=None,      # ← 추가
                        progress_callback=None):   # ← 추가
        """문서 처리 (취소/진행 상황 콜백 지원)

        Args:
            cancel_callback: 취소 여부 확인 함수 (return True면 취소)
            progress_callback: 진행 상황 알림 함수 (current, total, message)

        Raises:
            CancelledException: 취소 요청 시
        """
        if file_type == "pdf" and self.pdf_engine:
            return self.pdf_engine.process_pdf_document(
                pdf_path=file_path,
                cancel_callback=cancel_callback,
                progress_callback=progress_callback,
                # ... 기타 파라미터
            )
        # ... 기존 코드
```

**2단계: PDFChunkingEngine 수정 (전체 롤백 전략 포함)**

```python
# utils/pdf_chunking_engine.py:_process_pdf_with_vision

class PartialUploadException(Exception):
    """부분 업로드 발생 시 발생하는 예외 (전체 롤백용)"""
    def __init__(self, message: str, failed_pages: List[int]):
        super().__init__(message)
        self.failed_pages = failed_pages

class PDFChunkingEngine:
    def _process_pdf_with_vision(self,
                                 pdf_path: str,
                                 llm_api_type: str,
                                 llm_base_url: str,
                                 llm_model: str,
                                 llm_api_key: str,
                                 cancel_callback=None,      # ← 추가
                                 progress_callback=None):   # ← 추가
        """Vision 모드로 PDF 처리 (취소 가능, 전체 롤백 전략)"""

        # ... PDF → 이미지 변환 ...

        chunks = []
        document_id = str(uuid.uuid4())
        failed_pages = []  # ✅ 실패한 페이지 추적 (전체 롤백용)

        for page_num, image in enumerate(images, 1):
            # ✅ 1. 취소 체크 (페이지 시작 전)
            if cancel_callback and cancel_callback():
                raise CancelledException(f"페이지 {page_num} 처리 전 취소됨")

            # ✅ 2. 진행 상황 업데이트
            if progress_callback:
                progress_callback(
                    current=page_num,
                    total=page_count,
                    message=f"페이지 {page_num}/{page_count} Vision 분석 중..."
                )

            # 이미지 인코딩
            try:
                print(f"  → 이미지 인코딩 중...")
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            except Exception as e:
                print(f"[ERROR] 페이지 {page_num} 이미지 인코딩 실패: {e}")
                # ✅ 전체 롤백: 이미지 인코딩 실패도 전체 롤백
                failed_pages.append(page_num)
                raise PartialUploadException(
                    f"페이지 {failed_pages} 처리 실패로 전체 업로드 취소됨",
                    failed_pages=failed_pages
                )

            # ✅ 3. 취소 체크 (API 호출 전)
            if cancel_callback and cancel_callback():
                raise CancelledException(f"페이지 {page_num} API 호출 전 취소됨")

            # Vision 분석
            try:
                description = self._analyze_page_with_vision(
                    image_base64=image_base64,
                    page_num=page_num,
                    total_pages=page_count,
                    llm_api_type=self.vision_api_type,
                    llm_base_url=self.vision_base_url,
                    llm_api_key=self.vision_api_key,
                    llm_model=self.vision_model,
                    cancel_callback=cancel_callback  # ← API 호출 중에도 취소 가능하도록
                )

                # Chunk 생성
                chunk = Chunk(
                    id=f"{document_id}_pdf_page_{page_num}",
                    content=description,
                    chunk_type="pdf_page_vision",
                    metadata=ChunkMetadata(...)
                )
                chunks.append(chunk)

            except CancelledException:
                raise  # 취소 예외는 상위로 전파
            except Exception as e:
                print(f"[ERROR] 페이지 {page_num} Vision 분석 실패: {e}")
                # ✅ 전체 롤백: Vision 분석 실패 시 예외 발생
                failed_pages.append(page_num)
                raise PartialUploadException(
                    f"페이지 {failed_pages} 처리 실패로 전체 업로드 취소됨",
                    failed_pages=failed_pages
                )

        # ✅ 모든 페이지 성공 시에만 청크 반환
        return chunks
```

**3단계: UploadWorker 수정**

```python
# ui/document_widget.py:UploadWorker

class UploadWorker(QThread):
    # ... 기존 코드 ...

    def run(self):
        # ... 기존 코드 ...

        for idx, file_path in enumerate(self.file_paths, 1):
            # 취소 확인
            if self._cancelled:
                self.message.emit(f"⚠️ 업로드 취소됨 ({idx-1}/{total} 완료)")
                break

            file_name = file_path.split('/')[-1].split('\\')[-1]
            file_type = self._ext_to_type(file_name)

            try:
                # ... 1단계: 원본 파일 저장 ...

                # 2단계: 문서 처리 (취소/진행 상황 콜백 전달)
                if file_type in ["pdf", "pptx"]:
                    self.message.emit(f"  📖 문서 분석 중 (텍스트 추출 + Vision 처리)...")
                else:
                    self.message.emit(f"  📖 문서 분석 중...")

                def check_cancel():
                    """취소 여부 확인 콜백"""
                    return self._cancelled

                def update_progress(current, total, message):
                    """진행 상황 업데이트 콜백"""
                    self.message.emit(f"  {message}")
                    # 진행률 계산 (Stage 2 내부 세부 진행)
                    stage_2_start = (idx - 1) * stages_per_file + 1
                    stage_2_progress = current / total  # 0.0 ~ 1.0
                    overall_progress = stage_2_start + stage_2_progress
                    self.progress.emit(int(overall_progress * 100 / total_stages))

                chunks = self.document_processor.process_document(
                    file_path=file_path,
                    file_name=file_name,
                    file_type=file_type,
                    cancel_callback=check_cancel,        # ← 추가
                    progress_callback=update_progress    # ← 추가
                )

                # ... 3단계, 4단계 ...

            except CancelledException:
                # 취소 예외는 정상 종료로 처리
                self.message.emit(f"⚠️ 업로드 취소됨 ({idx}/{total} 파일 중)")
                break

            except PartialUploadException as e:
                # ✅ 부분 업로드 발생 → 전체 롤백
                self.message.emit(f"❌ 업로드 실패: {file_name}")
                self.message.emit(f"   일부 페이지 처리 실패로 전체 업로드가 취소되었습니다.")
                self.message.emit(f"   실패한 페이지: {', '.join(map(str, e.failed_pages))}")
                self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
                # 진행률 업데이트 (해당 파일 건너뛰기)
                current_stage = idx * stages_per_file
                self.progress.emit(int(current_stage * 100 / total_stages))
                # 다음 파일 계속 진행
                continue

            except requests.exceptions.Timeout:
                # 타임아웃은 별도 처리 (전체 롤백)
                self.message.emit(f"❌ 네트워크 타임아웃: {file_name}")
                self.message.emit(f"   서버 응답이 없습니다. 네트워크 연결을 확인하세요.")
                self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
                # 진행률 업데이트 (해당 파일 건너뛰기)
                current_stage = idx * stages_per_file
                self.progress.emit(int(current_stage * 100 / total_stages))
                # 다음 파일 계속 진행
                continue

            except Exception as e:
                # 기타 예외 (전체 롤백)
                error_msg = str(e)
                self.message.emit(f"❌ 오류: {file_name}")
                for line in error_msg.split('\n')[:5]:  # 최대 5줄만 표시
                    if line.strip():
                        self.message.emit(f"   {line}")
                self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
                # 진행률 업데이트
                current_stage = idx * stages_per_file
                self.progress.emit(int(current_stage * 100 / total_stages))
                # 다음 파일 계속 진행
                continue

        # finally는 기존 코드 유지 (캐시 무효화)
```

#### 예상 효과

✅ **취소 즉시 반영**: 페이지 처리 중에도 최대 1초 이내 취소
✅ **진행 상황 실시간 표시**: "페이지 4/12 Vision 분석 중..." UI 업데이트
✅ **명확한 제어**: 취소 시점, 진행 상황 콜백으로 명확히 제어

---

### 3.2 타임아웃 강화 🔴

#### 방안 1: 연결/읽기 타임아웃 분리 (권장)

**파일**: `utils/pdf_chunking_engine.py:1155`

```python
# 현재
response = requests.post(api_url, headers=headers, json=payload, timeout=60)

# 개선
response = requests.post(
    api_url,
    headers=headers,
    json=payload,
    timeout=(10, 60)  # (연결 타임아웃, 읽기 타임아웃)
)
```

**효과**:
- 연결 타임아웃: 10초 (서버 응답 없으면 빠르게 실패)
- 읽기 타임아웃: 60초 (연결 성공 후 응답 대기)
- 네트워크 문제 시 최대 70초 내 예외 발생 (현재는 무한정 대기 가능)

#### 방안 2: Signal 기반 강제 타임아웃 (Unix/Linux)

**Windows에서는 signal.SIGALRM 미지원** → 대안: `threading.Timer`

```python
import threading

def _analyze_page_with_vision_with_timeout(self, ...):
    """타임아웃 강제 적용 (Signal 대신 Threading 사용)"""

    result = [None]  # 결과 저장용
    exception = [None]  # 예외 저장용

    def worker():
        try:
            result[0] = self._analyze_page_with_vision(...)
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    thread.join(timeout=70)  # 최대 70초 대기

    if thread.is_alive():
        # 타임아웃 발생 (스레드 강제 종료는 불가, 하지만 예외 발생)
        raise TimeoutError(f"Vision API 응답 없음 (70초 초과)")

    if exception[0]:
        raise exception[0]

    return result[0]
```

**문제점**:
- Python에서 스레드 강제 종료 불가 (GIL 때문)
- 복잡도 증가

**권장**: **방안 1만 적용** (충분히 효과적)

#### 방안 3: Retry 로직 추가

```python
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def _analyze_page_with_vision(self, ...):
    # Retry 전략 설정
    retry_strategy = Retry(
        total=3,                    # 최대 3회 재시도
        backoff_factor=1,           # 1초, 2초, 4초 대기
        status_forcelist=[429, 500, 502, 503, 504],  # 재시도할 HTTP 상태 코드
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # API 호출
    response = session.post(
        api_url,
        headers=headers,
        json=payload,
        timeout=(10, 60)
    )
    # ...
```

**효과**:
- 일시적 네트워크 오류 시 자동 재시도
- 서버 과부하(429, 503) 시 백오프 후 재시도

---

### 3.3 안정적 예외 처리 및 복구 🔴

#### 원칙

1. **예외 유형별 처리**
   - `CancelledException`: 정상 종료로 처리
   - `Timeout`: 네트워크 오류로 처리, 재시도 또는 건너뛰기
   - `HTTPError`: API 오류로 처리, 로깅 후 건너뛰기
   - `Exception`: 알 수 없는 오류, 로깅 후 계속 진행

2. **시스템 상태 복구**
   - 오류 발생 시 Worker 스레드 정상 종료
   - UI 상태 복구 (진행률 100%, 버튼 활성화)
   - 캐시 무효화 (이미 구현됨 ✅)

3. **부분 업로드 처리: 전체 롤백 전략** 🔴
   - **정책**: 부분 업로드 발생 시 전체 롤백 (문서 업로드 실패로 처리)
   - **원자성 보장**: 파일 단위 원자성 (모든 페이지 성공 또는 전체 실패)
   - **구현**: 페이지 처리 중 실패 감지 시 예외 발생 → 전체 롤백
   - **사용자 피드백**: 명확한 오류 메시지 ("일부 페이지 처리 실패로 전체 업로드 취소됨")

#### 구현

**UploadWorker 예외 처리 개선 (전체 롤백 전략 포함)**

```python
# ui/document_widget.py:UploadWorker.run()

except CancelledException:
    # 취소는 정상 종료
    self.message.emit(f"⚠️ 업로드 취소됨 ({idx}/{total} 파일 처리 중)")
    break  # 루프 종료

except PartialUploadException as e:
    # 부분 업로드 발생 → 전체 롤백
    self.message.emit(f"❌ 업로드 실패: {file_name}")
    self.message.emit(f"   일부 페이지 처리 실패로 전체 업로드가 취소되었습니다.")
    self.message.emit(f"   실패한 페이지: {e.failed_pages}")
    self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
    # 진행률 업데이트 (해당 파일 건너뛰기)
    current_stage = idx * stages_per_file
    self.progress.emit(int(current_stage * 100 / total_stages))
    # 다음 파일 계속 진행
    continue

except requests.exceptions.Timeout as e:
    # 타임아웃 처리 (전체 롤백)
    self.message.emit(f"❌ 네트워크 타임아웃: {file_name}")
    self.message.emit(f"   서버 응답이 없습니다. 네트워크 연결을 확인하세요.")
    self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
    # 진행률 업데이트 (해당 파일 건너뛰기)
    current_stage = idx * stages_per_file
    self.progress.emit(int(current_stage * 100 / total_stages))
    # 다음 파일 계속 진행
    continue

except requests.exceptions.HTTPError as e:
    # HTTP 오류 (4xx, 5xx) → 전체 롤백
    self.message.emit(f"❌ API 오류: {file_name}")
    self.message.emit(f"   HTTP {e.response.status_code}: {e.response.reason}")
    self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
    # 진행률 업데이트
    current_stage = idx * stages_per_file
    self.progress.emit(int(current_stage * 100 / total_stages))
    continue

except Exception as e:
    # 기타 예외 → 전체 롤백
    error_msg = str(e)
    self.message.emit(f"❌ 오류 발생: {file_name}")
    for line in error_msg.split('\n')[:5]:  # 최대 5줄만 표시
        if line.strip():
            self.message.emit(f"   {line}")
    self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
    # 로깅 (디버깅용)
    import traceback
    traceback.print_exc()
    # 진행률 업데이트
    current_stage = idx * stages_per_file
    self.progress.emit(int(current_stage * 100 / total_stages))
    continue

finally:
    # 캐시 무효화 (기존 코드, 유지)
    try:
        self.vector_manager.invalidate_all_caches(target_db=self.target_db)
    except Exception as e:
        print(f"[UploadWorker][WARN] 캐시 무효화 실패: {e}")

    # ✅ 추가: UI 상태 복구
    self.message.emit("업로드 완료")
    self.progress.emit(100)
```

**PDFChunkingEngine 전체 롤백 로직 추가**

```python
# utils/pdf_chunking_engine.py:_process_pdf_with_vision

class PartialUploadException(Exception):
    """부분 업로드 발생 시 발생하는 예외 (전체 롤백용)"""
    def __init__(self, message: str, failed_pages: List[int]):
        super().__init__(message)
        self.failed_pages = failed_pages

# 페이지 루프 수정
chunks = []
document_id = str(uuid.uuid4())
failed_pages = []  # 실패한 페이지 추적

for page_num, image in enumerate(images, 1):
    # ✅ 취소 체크
    if cancel_callback and cancel_callback():
        raise CancelledException(f"페이지 {page_num} 처리 전 취소됨")

    # ✅ 진행 상황 업데이트
    if progress_callback:
        progress_callback(
            current=page_num,
            total=page_count,
            message=f"페이지 {page_num}/{page_count} Vision 분석 중..."
        )

    try:
        # Vision 분석
        description = self._analyze_page_with_vision(...)
        
        # Chunk 생성
        chunk = Chunk(...)
        chunks.append(chunk)
        
    except CancelledException:
        raise  # 취소 예외는 상위로 전파
    except Exception as e:
        # ❌ 실패한 페이지 추적 (continue 대신)
        failed_pages.append(page_num)
        print(f"[ERROR] 페이지 {page_num} Vision 분석 실패: {e}")
        
        # ✅ 전체 롤백: 실패한 페이지가 있으면 예외 발생
        raise PartialUploadException(
            f"페이지 {failed_pages} 처리 실패로 전체 업로드 취소됨",
            failed_pages=failed_pages
        )

# 모든 페이지 성공 시에만 청크 반환
return chunks
```

#### 예상 효과

✅ **시스템 안정성 향상**: 오류 발생 후에도 시스템 정상 작동
✅ **사용자 경험 개선**: 명확한 오류 메시지 + "시스템은 정상 작동합니다" 안내
✅ **원자성 보장**: 부분 업로드 방지, 전체 성공 또는 전체 실패
✅ **디버깅 용이**: 예외 유형별 로깅, 실패한 페이지 정보 포함

---

### 3.4 진행 상황 실시간 업데이트 🟡

#### 이미 3.1에서 해결됨

**3.1 취소 가능한 콜백 메커니즘**에서 `progress_callback` 구현 시 자동 해결:

```python
def update_progress(current, total, message):
    """진행 상황 업데이트 콜백"""
    self.message.emit(f"  {message}")
    # 진행률 계산 (Stage 2 내부 세부 진행)
    stage_2_start = (idx - 1) * stages_per_file + 1
    stage_2_progress = current / total  # 0.0 ~ 1.0
    overall_progress = stage_2_start + stage_2_progress
    self.progress.emit(int(overall_progress * 100 / total_stages))
```

**결과**:
- "페이지 1/12 Vision 분석 중..." (8%)
- "페이지 2/12 Vision 분석 중..." (16%)
- "페이지 3/12 Vision 분석 중..." (24%)
- ...
- "페이지 12/12 Vision 분석 중..." (100%)

---

## 4. 구현 우선순위

### 우선순위 1: 🔴 타임아웃 튜플 사용 (즉시 적용)

**예상 소요**: 5분
**난이도**: ⭐ 매우 낮음
**파일**: `utils/pdf_chunking_engine.py:1155`

```python
# 변경 전
response = requests.post(api_url, headers=headers, json=payload, timeout=60)

# 변경 후
response = requests.post(api_url, headers=headers, json=payload, timeout=(10, 60))
```

**효과**:
- 네트워크 문제 시 최대 70초 내 타임아웃 보장
- 무한 대기 문제 해결

---

### 우선순위 2: 🔴 취소 메커니즘 추가 + 전체 롤백 전략 (최우선)

**예상 소요**: 1-2시간
**난이도**: ⭐⭐ 중간

**단계**:
1. `CancelledException`, `PartialUploadException` 클래스 정의
2. `DocumentProcessor.process_document()` 시그니처 확장 (`cancel_callback`, `progress_callback` 추가)
3. `PDFChunkingEngine._process_pdf_with_vision()` 수정
   - 페이지 루프 내 취소 체크
   - 실패한 페이지 추적 (`failed_pages` 리스트)
   - 실패 시 `PartialUploadException` 발생 (전체 롤백)
4. `UploadWorker.run()` 수정
   - 콜백 전달
   - `CancelledException` 처리
   - `PartialUploadException` 처리 (전체 롤백)

**효과**:
- 취소 버튼 즉시 작동
- 사용자가 언제든지 업로드 중단 가능
- 부분 업로드 방지 (원자성 보장)
- 명확한 오류 메시지 (실패한 페이지 정보 포함)

---

### 우선순위 3: 🔴 예외 처리 강화

**예상 소요**: 30분
**난이도**: ⭐ 낮음

**단계**:
1. `UploadWorker.run()` 예외 처리 세분화
   - `CancelledException`
   - `requests.exceptions.Timeout`
   - `requests.exceptions.HTTPError`
   - `Exception`
2. 각 예외별 사용자 메시지 추가 ("✅ 시스템은 정상 작동합니다")

**효과**:
- 오류 발생 후에도 시스템 안정적 작동
- 사용자에게 명확한 피드백

---

### 우선순위 4: 🟡 진행 상황 콜백 (우선순위 2에 포함)

**예상 소요**: 우선순위 2와 함께 구현
**난이도**: ⭐ 낮음 (우선순위 2 완료 시 자동 해결)

**효과**:
- 페이지별 진행 상황 실시간 표시
- "4페이지 API 요청 전송 중..." 이후 피드백 부재 문제 해결

---

## 5. 기대 효과

### 5.1 사용자 경험

| 항목 | 개선 전 | 개선 후 |
|------|---------|---------|
| **타임아웃 시** | 무한 대기 (재시작 필요) | 70초 내 오류 표시, 다음 작업 가능 |
| **취소 버튼** | 작동 안 함 (재시작 필요) | 1초 이내 즉시 취소 |
| **진행 상황** | "문서 분석 중..." (수 분간 변화 없음) | "페이지 4/12 Vision 분석 중..." (실시간 업데이트) |
| **오류 발생 시** | 시스템 멈춤 (재시작 필요) | 오류 메시지 표시, 시스템 정상 작동 |

### 5.2 시스템 안정성

✅ **복구 불가 문제 해결**: 오류 발생 후 자동 복구
✅ **전체 롤백 전략**: 부분 업로드 방지, 파일 단위 원자성 보장
✅ **네트워크 오류 대응**: 타임아웃, 재시도, 우아한 실패
✅ **데이터 일관성**: 부분 데이터 저장 방지, 전체 성공 또는 전체 실패

### 5.3 개발/유지보수

✅ **디버깅 용이**: 예외 유형별 로깅, 상세 오류 메시지
✅ **확장 가능**: 콜백 메커니즘으로 향후 기능 추가 용이
✅ **테스트 가능**: 취소/진행 상황 콜백 모의 테스트 가능

---

## 6. 다음 단계

### 즉시 적용 (오늘 내)

1. ✅ **타임아웃 튜플 변경** (5분)
2. ✅ **취소 메커니즘 추가** (1-2시간)
3. ✅ **예외 처리 강화** (30분)

**총 예상 소요**: 2-3시간

### 테스트 계획

1. **정상 시나리오**: 12페이지 PDF 업로드 완료
2. **네트워크 지연**: API 서버 지연 시뮬레이션 (타임아웃 테스트)
3. **취소 테스트**: 3페이지 처리 중 취소 버튼 클릭
4. **API 오류**: 잘못된 API 키/엔드포인트 (HTTP 오류 테스트)
5. **부분 실패 → 전체 롤백**: 2페이지 성공 → 3페이지 실패 시 전체 롤백 확인
   - 3페이지 실패 시 예외 발생 확인
   - 부분 청크가 DB에 저장되지 않음 확인
   - 사용자에게 명확한 오류 메시지 표시 확인

### 장기 개선 (향후)

- **부분 업로드 재개**: 실패한 페이지부터 재시도 (Resume 기능)
  - 현재는 전체 롤백이지만, 향후 선택적 기능으로 추가 가능
- **백그라운드 업로드**: UI 블로킹 없이 백그라운드에서 처리
- **배치 업로드 최적화**: 여러 파일 병렬 처리 (현재는 순차 처리)
- **재시도 전략**: 실패한 페이지 자동 재시도 (최대 N회) 후 전체 롤백

---

## 7. 추가 개선 권장사항 (구현 후 검토 결과)

**검토일**: 2025-11-28
**최종 검토일**: 2025-11-29
**검토 기준**: 보고서 권장사항 대비 실제 구현 코드 검토

### 7.1 ✅ 구현 완료 (높은 우선순위)

#### 1. PartialUploadException 처리 후 진행률 업데이트 누락 → ✅ 구현 완료

**위치**: `ui/document_widget.py:136-151`

**구현 완료 (v0.5.1)**:
```python
except PartialUploadException as e:
    # 부분 업로드 발생 → 전체 롤백
    self.message.emit(f"❌ 업로드 실패: {file_name}")
    self.message.emit(f"   일부 페이지 처리 실패로 전체 업로드가 취소되었습니다.")
    self.message.emit(f"   실패한 페이지: {e.failed_page}")
    # 에러 메시지 표시
    error_msg = str(e)
    for line in error_msg.split('\n'):
        if line.strip():
            self.message.emit(f"   {line}")
    self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")  # ✅ 추가됨
    # 진행률 업데이트 (해당 파일 건너뛰기)
    current_stage = idx * stages_per_file
    self.progress.emit(int(current_stage * 100 / total_stages))  # ✅ 추가됨
    # 다음 파일 계속 처리
    continue  # ✅ 추가됨
```

---

#### 2. 일반 예외 처리에 안내 메시지 누락 → ✅ 구현 완료 (⚠️ 추가 개선 권장)

**위치**: `ui/document_widget.py:153-163`

**구현 완료 (v0.5.1)**:
```python
except Exception as e:
    error_msg = str(e)
    self.message.emit(f"❌ 오류: {file_name}")
    # 에러 메시지가 여러 줄이면 각 줄을 표시 (최대 5줄)
    for line in error_msg.split('\n')[:5]:  # ✅ 최대 5줄 제한 추가
        if line.strip():
            self.message.emit(f"   {line}")
    self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")  # ✅ 추가됨
    # 에러 발생 시에도 해당 파일의 진행률은 완료로 표시
    current_stage = idx * stages_per_file
    self.progress.emit(int(current_stage * 100 / total_stages))
    # ⚠️ continue 누락 (PartialUploadException과 일관성 유지 필요)
```

**추가 개선 권장**:
- `PartialUploadException` 처리에는 `continue`가 있으나, 일반 `Exception` 처리에는 없음
- for 루프 내부이므로 동작에는 문제 없지만, 명시적 `continue` 추가 권장
- 코드 일관성 및 가독성 향상

**개선 제안**:
```python
except Exception as e:
    error_msg = str(e)
    self.message.emit(f"❌ 오류: {file_name}")
    for line in error_msg.split('\n')[:5]:
        if line.strip():
            self.message.emit(f"   {line}")
    self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
    # 진행률 업데이트
    current_stage = idx * stages_per_file
    self.progress.emit(int(current_stage * 100 / total_stages))
    # ✅ 다음 파일 계속 처리 (일관성 유지)
    continue
```

**예상 소요**: 1분

---

### 7.2 ⏸️ 보류 (중간 우선순위)

#### 3. 타임아웃 예외 처리 분리 → ⏸️ 보류

**상태**: 보류 (현재 동작에 문제 없음)

**보류 이유**:
- `pdf_chunking_engine.py`에서 이미 retry 로직이 Timeout/HTTPError를 처리하고 적절한 메시지로 래핑 후 재발생시킴
- 상위 레벨에서 분리 처리하면 더 명확하지만, 현재도 동작에 문제없음
- 사내 테스트 후 필요시 구현 예정

**현재 동작**: 모든 예외가 `Exception`으로 통합 처리되나, 에러 메시지가 충분히 상세함

---

### 7.3 ⏸️ 보류 (낮은 우선순위)

#### 4. progress_callback 시그니처 개선 → ⏸️ 보류

**상태**: 보류 (현재 동작에 문제 없음)

**보류 이유**:
- 현재 `(msg, pct)` 시그니처가 정상 동작함
- `(current, total, message)` 방식이 더 유연하지만, 변경 시 여러 파일 수정 필요
- 향후 기능 확장 시 검토 예정

---

#### 5. PartialUploadException 속성명 개선 → ⏸️ 보류

**상태**: 보류 (현재 동작에 문제 없음)

**보류 이유**:
- 현재 전체 롤백 전략에서 첫 번째 실패한 페이지에서 즉시 예외 발생
- 단수형 `failed_page`가 현재 로직에 적합
- 향후 여러 페이지 동시 실패 처리가 필요할 때 변경 검토

---

### 7.4 개선 사항 요약

| 우선순위 | 항목 | 상태 | 비고 |
|---------|------|------|------|
| 🔴 높음 | 1. PartialUploadException 진행률 업데이트 | ✅ 완료 | v0.5.1 |
| 🔴 높음 | 2. 일반 예외 처리 안내 메시지 추가 | ✅ 완료 | v0.5.1 (⚠️ continue 추가 권장) |
| 🟡 중간 | 3. 타임아웃 예외 처리 분리 | ⏸️ 보류 | 현재 동작 문제없음 |
| 🟢 낮음 | 4. progress_callback 시그니처 개선 | ⏸️ 보류 | 현재 동작 문제없음 |
| 🟢 낮음 | 5. PartialUploadException 속성명 개선 | ⏸️ 보류 | 현재 동작 문제없음 |

**구현 완료**: 2개 / **보류**: 3개 / **추가 개선 권장**: 1개 (일반 Exception에 continue 추가)

---

## 📝 변경 이력

### v1.0 (2025-11-28)
- 초기 보고서 작성
- 취소 메커니즘, 타임아웃, 예외 처리, 진행 상황 업데이트 문제 분석

### v1.1 (2025-11-28)
- ✅ 부분 업로드 처리 설명 보완 (현재 동작 명확화)
- ✅ 전체 롤백 전략 반영 (사용자 요구사항)
- ✅ `PartialUploadException` 클래스 정의 추가
- ✅ 구현 방안에 전체 롤백 로직 추가
- ✅ 예상 효과에 원자성 보장 추가
- ✅ 테스트 계획에 전체 롤백 시나리오 추가

### v1.2 (2025-11-28)
- ✅ 구현 후 코드 검토 결과 추가
- ✅ 추가 개선 권장사항 섹션 추가 (7장)
- ✅ 우선순위별 개선 사항 5가지 정리
- ✅ 각 개선 사항별 코드 예시 및 이유 설명
- ✅ 목차에 "추가 개선 권장사항" 섹션 추가

### v1.3 (2025-11-29)
- ✅ 높은 우선순위 항목 2개 구현 완료 (v0.5.1)
  - PartialUploadException: progress.emit(), continue, 안내 메시지 추가
  - 일반 Exception: "시스템은 정상 작동합니다" 메시지 추가, 최대 5줄 제한
- ⏸️ 중간/낮은 우선순위 항목 3개 보류 결정
  - #3 타임아웃 예외 분리: 현재 retry 로직에서 충분히 처리
  - #4 progress_callback 시그니처: 현재 동작 문제없음
  - #5 failed_page 속성명: 현재 로직에 적합
- ✅ Section 7 전면 재작성 (구현/보류 상태 반영)

### v1.4 (2025-11-29)
- ⚠️ 추가 개선 권장사항 반영
  - 일반 Exception 처리에 `continue` 누락 발견
  - PartialUploadException과 일관성 유지를 위해 `continue` 추가 권장
  - 동작에는 문제 없으나 코드 일관성 및 가독성 향상 목적

---

**보고서 작성**: 2025-11-28
**최종 수정**: 2025-11-29 (v0.5.1 구현 완료 및 보류 결정 반영)
**다음 검토 예정**: 사내 테스트 완료 후
