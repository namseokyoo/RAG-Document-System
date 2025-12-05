# 업로드 안정성 개선 보고서 검토 및 개선 계획

**검토일**: 2025-11-28
**검토 대상**: UPLOAD_STABILITY_ISSUE_REPORT.md (부분 업로드 전체 롤백 전략)
**검토자**: Claude Code
**결론**: ✅ **타당함** (일부 개선 사항 포함)

---

## 📋 목차

1. [주요 변경 사항 요약](#1-주요-변경-사항-요약)
2. [타당성 분석](#2-타당성-분석)
3. [잠재적 문제점 및 개선 방안](#3-잠재적-문제점-및-개선-방안)
4. [최종 구현 계획](#4-최종-구현-계획)
5. [테스트 시나리오](#5-테스트-시나리오)

---

## 1. 주요 변경 사항 요약

### 1.1 핵심 정책 변경

**기존 방안**:
- 부분 업로드 시 이미 처리된 청크만 DB 저장 (옵션)
- 또는 전체 롤백 (파일 단위 원자성)
- 정책이 명확하지 않음

**변경된 방안**:
- ✅ **전체 롤백 전략 명확화**
- ✅ 페이지 실패 시 즉시 예외 발생 (`PartialUploadException`)
- ✅ 부분 청크는 DB에 저장되지 않음 (원자성 보장)
- ✅ 사용자에게 명확한 오류 메시지 제공

### 1.2 코드 변경 사항

#### 새로운 예외 클래스 추가

```python
class PartialUploadException(Exception):
    """부분 업로드 발생 시 발생하는 예외 (전체 롤백용)"""
    def __init__(self, message: str, failed_pages: List[int]):
        super().__init__(message)
        self.failed_pages = failed_pages
```

#### PDFChunkingEngine 수정

**기존 코드** (라인 1005-1007):
```python
except Exception as e:
    print(f"[ERROR] 페이지 {page_num} Vision 분석 실패: {e}")
    continue  # ← 실패해도 계속 진행 (부분 업로드 발생)
```

**변경 코드**:
```python
failed_pages = []  # 실패한 페이지 추적

try:
    # Vision 분석
    description = self._analyze_page_with_vision(...)
    chunks.append(chunk)

except CancelledException:
    raise  # 취소 예외는 상위로 전파
except Exception as e:
    # ✅ 실패한 페이지 추적
    failed_pages.append(page_num)
    print(f"[ERROR] 페이지 {page_num} Vision 분석 실패: {e}")

    # ✅ 전체 롤백: 즉시 예외 발생
    raise PartialUploadException(
        f"페이지 {failed_pages} 처리 실패로 전체 업로드 취소됨",
        failed_pages=failed_pages
    )
```

#### UploadWorker 예외 처리 추가

```python
except PartialUploadException as e:
    # 부분 업로드 발생 → 전체 롤백
    self.message.emit(f"❌ 업로드 실패: {file_name}")
    self.message.emit(f"   일부 페이지 처리 실패로 전체 업로드가 취소되었습니다.")
    self.message.emit(f"   실패한 페이지: {', '.join(map(str, e.failed_pages))}")
    self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
    # 다음 파일 계속 진행
    continue
```

---

## 2. 타당성 분석

### 2.1 전체 롤백 전략 ✅ 타당함

#### 장점

1. **원자성(Atomicity) 보장** ✅
   - ACID 원칙의 핵심
   - 파일 단위 원자성: 전체 성공 또는 전체 실패
   - 중간 상태 없음 → 데이터 일관성 보장

2. **데이터 일관성** ✅
   - 부분 데이터가 DB에 남으면 혼란 발생
   - 예: 3페이지 성공 → 4페이지 실패 → 3페이지 청크만 검색됨 → 불완전한 정보
   - 사용자가 재시도 시 중복 데이터 문제 없음

3. **사용자 경험** ✅
   - 명확한 오류 메시지: "일부 페이지 처리 실패로 전체 업로드 취소됨"
   - 실패한 페이지 정보 제공: "실패한 페이지: 4"
   - 재시도 유도: "재시도하세요"

4. **디버깅 용이** ✅
   - `failed_pages` 정보로 어느 페이지에서 실패했는지 명확
   - 로그 분석 용이

#### 업계 표준과의 비교

| 시스템 | 전략 | 비고 |
|--------|------|------|
| **데이터베이스 트랜잭션** | 전체 롤백 (ROLLBACK) | ACID 원칙 |
| **Git** | 커밋 단위 원자성 | 부분 커밋 불가 |
| **파일 업로드 (AWS S3)** | 멀티파트 업로드 + 전체 롤백 | 실패 시 자동 정리 |
| **Docker 이미지 빌드** | 레이어 단위 캐싱 + 전체 실패 | 실패 시 이미지 미생성 |

✅ **결론**: 업계 표준과 일치 (원자성 보장)

---

### 2.2 PartialUploadException 설계 ✅ 타당함

#### 장점

1. **예외 유형별 처리** ✅
   - `CancelledException`: 사용자 취소 (정상 종료)
   - `Timeout`: 네트워크 오류 (재시도 권장)
   - `PartialUploadException`: 부분 업로드 (전체 롤백)
   - `Exception`: 알 수 없는 오류

2. **메타데이터 포함** ✅
   - `failed_pages`: 실패한 페이지 목록
   - 디버깅 및 사용자 피드백에 유용

#### 개선 제안

**현재 구현의 논리적 모순**:
```python
failed_pages = []

for page_num, image in enumerate(images, 1):
    try:
        # Vision 분석
        ...
    except Exception as e:
        failed_pages.append(page_num)  # ← 추가
        raise PartialUploadException(...)  # ← 즉시 예외 발생
        # ↑ 여기서 루프 종료되므로 failed_pages는 항상 단일 페이지
```

**문제점**: `failed_pages`는 항상 1개 페이지만 포함 (즉시 예외 발생하므로)

**개선 방안 1: 단일 페이지 저장** (권장)
```python
class PartialUploadException(Exception):
    def __init__(self, message: str, failed_page: int):  # ← List 대신 int
        super().__init__(message)
        self.failed_page = failed_page  # ← 단일 값
```

**개선 방안 2: 여러 페이지 실패 누적** (복잡함, 비권장)
```python
for page_num, image in enumerate(images, 1):
    try:
        # Vision 분석
        ...
    except Exception as e:
        failed_pages.append(page_num)
        # continue로 계속 진행 (누적)

# 루프 종료 후 실패 페이지 있으면 예외
if failed_pages:
    raise PartialUploadException(...)
```

**권장**: **방안 1 (단일 페이지)** → 즉시 실패 전략과 일치

---

### 2.3 페이지 실패 시 즉시 예외 ✅ 타당함

#### 장점

1. **빠른 실패(Fail-fast) 원칙** ✅
   - 문제 발생 즉시 중단
   - 불필요한 리소스 낭비 방지 (4페이지 실패 시 5-12페이지 처리 안 함)

2. **사용자 피드백 빠름** ✅
   - 12페이지 문서에서 4페이지 실패 → 4페이지까지만 처리 후 즉시 오류 표시
   - vs. 모든 페이지 처리 후 오류 표시 → 사용자 대기 시간 증가

3. **디버깅 용이** ✅
   - 첫 번째 실패 원인 파악 용이
   - vs. 여러 페이지 실패 → 어느 것이 근본 원인인지 불명확

#### 업계 표준과의 비교

| 시스템 | 전략 | 비고 |
|--------|------|------|
| **컴파일러** | 첫 오류 발견 시 중단 (또는 오류 수집 후 중단) | Fail-fast |
| **단위 테스트** | 첫 실패 시 중단 (옵션) 또는 모든 테스트 실행 | 설정 가능 |
| **데이터베이스 INSERT** | 첫 제약 조건 위반 시 즉시 롤백 | Fail-fast |
| **파일 복사** | 오류 발생 시 즉시 중단 | Fail-fast |

✅ **결론**: 업계 표준과 일치 (Fail-fast)

---

## 3. 잠재적 문제점 및 개선 방안

### 3.1 문제점 1: 일시적 네트워크 오류 시 재처리 부담 🟡

#### 시나리오

```
1페이지 ✅ 성공 (30초)
2페이지 ✅ 성공 (30초)
3페이지 ✅ 성공 (30초)
4페이지 ❌ 실패 (네트워크 일시 오류)
→ 전체 롤백
→ 재시도 시 1-3페이지 재처리 (90초 추가 소요)
```

#### 영향도

- **빈도**: 🟡 보통 (네트워크 불안정 환경에서 발생 가능)
- **심각도**: 🟡 보통 (사용자 대기 시간 증가, 하지만 데이터 손실 없음)
- **사용자 경험**: 🟡 나쁨 (재시도 부담)

#### 개선 방안

##### 방안 A: 페이지별 재시도 로직 (권장) ⭐

**구현**:
```python
MAX_RETRIES = 3  # 페이지당 최대 3회 재시도

for page_num, image in enumerate(images, 1):
    retry_count = 0

    while retry_count < MAX_RETRIES:
        try:
            description = self._analyze_page_with_vision(...)
            chunks.append(chunk)
            break  # 성공 시 루프 탈출

        except requests.exceptions.Timeout as e:
            retry_count += 1
            if retry_count >= MAX_RETRIES:
                # 최대 재시도 초과 → 전체 롤백
                raise PartialUploadException(
                    f"페이지 {page_num} 처리 실패 ({MAX_RETRIES}회 재시도)",
                    failed_page=page_num
                )
            else:
                # 재시도
                wait_time = 2 ** retry_count  # 지수 백오프: 2초, 4초, 8초
                print(f"  → 페이지 {page_num} 재시도 중... ({retry_count}/{MAX_RETRIES})")
                if progress_callback:
                    progress_callback(
                        current=page_num,
                        total=page_count,
                        message=f"페이지 {page_num} 재시도 중 ({retry_count}/{MAX_RETRIES})..."
                    )
                time.sleep(wait_time)

        except Exception as e:
            # 재시도 불가능한 오류 (이미지 인코딩 실패 등) → 즉시 전체 롤백
            raise PartialUploadException(...)
```

**효과**:
- ✅ 일시적 네트워크 오류 대응 (429, 503, Timeout 등)
- ✅ 재처리 부담 감소 (성공할 때까지 재시도)
- ✅ 지수 백오프로 서버 부담 완화

**우선순위**: 🔴 최우선 (일시적 오류 빈도 높음)

##### 방안 B: Resume 기능 (장기 개선)

**구현**:
```python
# 부분 처리 결과를 임시 저장
temp_chunks = []

for page_num, image in enumerate(images, 1):
    try:
        chunk = self._process_page(...)
        temp_chunks.append(chunk)
    except Exception as e:
        # 실패 지점 저장
        save_temp_state(temp_chunks, failed_page=page_num)
        raise PartialUploadException(...)

# 재시도 시 실패 지점부터 재개
if resume_from_page:
    temp_chunks = load_temp_state()
    start_page = resume_from_page
else:
    temp_chunks = []
    start_page = 1
```

**효과**:
- ✅ 재처리 부담 완전 제거
- ✅ 대용량 문서 (100+ 페이지) 처리 가능

**단점**:
- ⚠️ 복잡도 높음 (임시 상태 관리)
- ⚠️ 저장 공간 필요
- ⚠️ 동시성 문제 (같은 파일 여러 번 업로드)

**우선순위**: 🟢 낮음 (장기 개선, 현재는 불필요)

---

### 3.2 문제점 2: 재시도 불가능한 오류와 재시도 가능한 오류 구분 🟡

#### 시나리오

**재시도 가능한 오류**:
- `requests.exceptions.Timeout`: 네트워크 타임아웃
- `requests.exceptions.HTTPError` (429, 503): 서버 과부하
- `ConnectionError`: 네트워크 연결 오류

**재시도 불가능한 오류**:
- 이미지 인코딩 실패: `image.save()` 예외
- Vision API 인증 오류: 401 Unauthorized
- 잘못된 이미지 포맷: 400 Bad Request

#### 현재 구현 문제

```python
except Exception as e:
    # 모든 예외를 동일하게 처리 (재시도 없음)
    raise PartialUploadException(...)
```

**문제**: 일시적 오류도 즉시 전체 롤백 → 재시도 기회 없음

#### 개선 방안

```python
# 재시도 가능한 예외 정의
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
)

RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]

for page_num, image in enumerate(images, 1):
    retry_count = 0

    while retry_count < MAX_RETRIES:
        try:
            description = self._analyze_page_with_vision(...)
            chunks.append(chunk)
            break  # 성공

        except RETRYABLE_EXCEPTIONS as e:
            # 재시도 가능한 예외
            retry_count += 1
            if retry_count >= MAX_RETRIES:
                raise PartialUploadException(...)
            else:
                time.sleep(2 ** retry_count)  # 지수 백오프
                continue

        except requests.exceptions.HTTPError as e:
            # HTTP 오류 - 상태 코드 확인
            if e.response.status_code in RETRYABLE_STATUS_CODES:
                # 재시도 가능
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    raise PartialUploadException(...)
                else:
                    time.sleep(2 ** retry_count)
                    continue
            else:
                # 재시도 불가능 (401, 400 등) → 즉시 롤백
                raise PartialUploadException(
                    f"페이지 {page_num} API 오류 (재시도 불가): HTTP {e.response.status_code}",
                    failed_page=page_num
                )

        except Exception as e:
            # 재시도 불가능한 예외 (이미지 인코딩 실패 등) → 즉시 롤백
            raise PartialUploadException(
                f"페이지 {page_num} 처리 실패 (재시도 불가): {type(e).__name__}",
                failed_page=page_num
            )
```

**효과**:
- ✅ 일시적 오류는 자동 재시도
- ✅ 치명적 오류는 즉시 실패 (빠른 피드백)
- ✅ 명확한 오류 메시지 (재시도 가능 여부 표시)

**우선순위**: 🔴 최우선 (방안 A에 포함)

---

### 3.3 문제점 3: `failed_pages` 리스트의 의미 불명확 🟡

#### 현재 구현

```python
failed_pages = []  # List[int]

for page_num in range(...):
    try:
        ...
    except Exception:
        failed_pages.append(page_num)  # 추가
        raise PartialUploadException(..., failed_pages=failed_pages)
        # ↑ 여기서 즉시 종료 → failed_pages는 항상 [page_num] (단일 요소)
```

**문제**: `failed_pages`가 리스트지만 항상 단일 요소만 포함

#### 개선 방안

**방안 1: 단일 값으로 변경** (권장)
```python
class PartialUploadException(Exception):
    def __init__(self, message: str, failed_page: int):  # ← int (단일 값)
        super().__init__(message)
        self.failed_page = failed_page

# 사용
raise PartialUploadException(
    f"페이지 {page_num} 처리 실패로 전체 업로드 취소됨",
    failed_page=page_num
)

# UploadWorker
except PartialUploadException as e:
    self.message.emit(f"   실패한 페이지: {e.failed_page}")  # ← 단일 값
```

**효과**:
- ✅ 명확한 의미 (항상 단일 페이지)
- ✅ 코드 간결화

**우선순위**: 🟡 중간 (일관성 개선)

---

## 4. 최종 구현 계획

### 4.1 우선순위 1: 타임아웃 튜플 변경 (5분) 🔴

**파일**: `utils/pdf_chunking_engine.py:1155`

```python
# 변경 전
response = requests.post(api_url, headers=headers, json=payload, timeout=60)

# 변경 후
response = requests.post(api_url, headers=headers, json=payload, timeout=(10, 60))
```

**효과**: 네트워크 문제 시 최대 70초 내 타임아웃 보장

---

### 4.2 우선순위 2: 취소 메커니즘 + 전체 롤백 + 페이지별 재시도 (2-3시간) 🔴

#### 단계 1: 예외 클래스 정의

**파일**: `utils/pdf_chunking_engine.py` (상단)

```python
class CancelledException(Exception):
    """업로드가 취소되었을 때 발생하는 예외"""
    pass

class PartialUploadException(Exception):
    """부분 업로드 발생 시 발생하는 예외 (전체 롤백용)"""
    def __init__(self, message: str, failed_page: int):  # ← 단일 페이지
        super().__init__(message)
        self.failed_page = failed_page  # ← int (단일 값)
```

#### 단계 2: DocumentProcessor 인터페이스 확장

**파일**: `utils/document_processor.py`

```python
def process_document(self,
                    file_path: str,
                    file_name: str,
                    file_type: str,
                    cancel_callback=None,      # ← 추가
                    progress_callback=None):   # ← 추가
    """문서 처리 (취소/진행 상황 콜백 지원)"""

    if file_type == "pdf" and self.pdf_engine:
        return self.pdf_engine.process_pdf_document(
            pdf_path=file_path,
            cancel_callback=cancel_callback,
            progress_callback=progress_callback,
            # ... 기존 파라미터
        )
    # ... 기존 코드
```

#### 단계 3: PDFChunkingEngine 수정 (전체 롤백 + 재시도)

**파일**: `utils/pdf_chunking_engine.py`

```python
def _process_pdf_with_vision(self,
                             pdf_path: str,
                             llm_api_type: str,
                             llm_base_url: str,
                             llm_model: str,
                             llm_api_key: str,
                             cancel_callback=None,      # ← 추가
                             progress_callback=None):   # ← 추가
    """Vision 모드로 PDF 처리 (취소 가능, 전체 롤백, 재시도)"""

    # ... PDF → 이미지 변환 ...

    chunks = []
    document_id = str(uuid.uuid4())
    MAX_RETRIES = 3  # 페이지당 최대 3회 재시도

    # 재시도 가능한 예외 정의
    RETRYABLE_EXCEPTIONS = (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    )
    RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]

    for page_num, image in enumerate(images, 1):
        # ✅ 1. 취소 체크
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
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            # 이미지 인코딩 실패 → 재시도 불가능 → 즉시 롤백
            raise PartialUploadException(
                f"페이지 {page_num} 이미지 인코딩 실패 (재시도 불가)",
                failed_page=page_num
            )

        # ✅ 3. 취소 체크 (API 호출 전)
        if cancel_callback and cancel_callback():
            raise CancelledException(f"페이지 {page_num} API 호출 전 취소됨")

        # ✅ 4. Vision 분석 (재시도 로직 포함)
        retry_count = 0

        while retry_count < MAX_RETRIES:
            try:
                description = self._analyze_page_with_vision(
                    image_base64=image_base64,
                    page_num=page_num,
                    total_pages=page_count,
                    llm_api_type=self.vision_api_type,
                    llm_base_url=self.vision_base_url,
                    llm_api_key=self.vision_api_key,
                    llm_model=self.vision_model
                )

                # Chunk 생성
                chunk = Chunk(
                    id=f"{document_id}_pdf_page_{page_num}",
                    content=description,
                    chunk_type="pdf_page_vision",
                    metadata=ChunkMetadata(...)
                )
                chunks.append(chunk)
                break  # 성공 시 재시도 루프 탈출

            except CancelledException:
                raise  # 취소 예외는 즉시 전파

            except RETRYABLE_EXCEPTIONS as e:
                # 재시도 가능한 예외 (Timeout, ConnectionError)
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    # 최대 재시도 초과 → 전체 롤백
                    raise PartialUploadException(
                        f"페이지 {page_num} 네트워크 오류 ({MAX_RETRIES}회 재시도 실패)",
                        failed_page=page_num
                    )
                else:
                    # 재시도
                    wait_time = 2 ** retry_count  # 지수 백오프: 2초, 4초, 8초
                    print(f"  → 페이지 {page_num} 재시도 중... ({retry_count}/{MAX_RETRIES})")
                    if progress_callback:
                        progress_callback(
                            current=page_num,
                            total=page_count,
                            message=f"페이지 {page_num} 재시도 중 ({retry_count}/{MAX_RETRIES})..."
                        )
                    time.sleep(wait_time)
                    # 재시도 전 취소 체크
                    if cancel_callback and cancel_callback():
                        raise CancelledException(f"페이지 {page_num} 재시도 중 취소됨")

            except requests.exceptions.HTTPError as e:
                # HTTP 오류 - 상태 코드 확인
                if e.response.status_code in RETRYABLE_STATUS_CODES:
                    # 재시도 가능 (429, 503 등)
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        raise PartialUploadException(
                            f"페이지 {page_num} API 과부하 ({MAX_RETRIES}회 재시도 실패)",
                            failed_page=page_num
                        )
                    else:
                        wait_time = 2 ** retry_count
                        print(f"  → 페이지 {page_num} 재시도 중... (API 과부하)")
                        if progress_callback:
                            progress_callback(
                                current=page_num,
                                total=page_count,
                                message=f"페이지 {page_num} 재시도 중 (API 과부하)..."
                            )
                        time.sleep(wait_time)
                        if cancel_callback and cancel_callback():
                            raise CancelledException(f"페이지 {page_num} 재시도 중 취소됨")
                else:
                    # 재시도 불가능 (401, 400 등) → 즉시 롤백
                    raise PartialUploadException(
                        f"페이지 {page_num} API 오류 (재시도 불가): HTTP {e.response.status_code}",
                        failed_page=page_num
                    )

            except Exception as e:
                # 재시도 불가능한 예외 → 즉시 롤백
                raise PartialUploadException(
                    f"페이지 {page_num} 처리 실패 (재시도 불가): {type(e).__name__}",
                    failed_page=page_num
                )

    # ✅ 모든 페이지 성공 시에만 청크 반환
    return chunks
```

#### 단계 4: UploadWorker 수정

**파일**: `ui/document_widget.py`

```python
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
            self.message.emit(f"   실패한 페이지: {e.failed_page}")  # ← 단일 값
            self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
            # 진행률 업데이트 (해당 파일 건너뛰기)
            current_stage = idx * stages_per_file
            self.progress.emit(int(current_stage * 100 / total_stages))
            # 다음 파일 계속 진행
            continue

        except requests.exceptions.Timeout:
            # 타임아웃 (재시도 실패 후)
            self.message.emit(f"❌ 네트워크 타임아웃: {file_name}")
            self.message.emit(f"   서버 응답이 없습니다. 네트워크 연결을 확인하세요.")
            self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
            current_stage = idx * stages_per_file
            self.progress.emit(int(current_stage * 100 / total_stages))
            continue

        except Exception as e:
            # 기타 예외
            error_msg = str(e)
            self.message.emit(f"❌ 오류: {file_name}")
            for line in error_msg.split('\n')[:5]:
                if line.strip():
                    self.message.emit(f"   {line}")
            self.message.emit(f"   ✅ 시스템은 정상 작동합니다. 재시도하세요.")
            import traceback
            traceback.print_exc()
            current_stage = idx * stages_per_file
            self.progress.emit(int(current_stage * 100 / total_stages))
            continue

    # finally는 기존 코드 유지 (캐시 무효화)
```

---

### 4.3 우선순위 3: 예외 처리 강화 (우선순위 2에 포함) 🔴

우선순위 2의 예외 처리 구현에 포함됨.

---

## 5. 테스트 시나리오

### 5.1 정상 시나리오 ✅

**테스트**: 12페이지 PDF 업로드 완료

**예상 결과**:
- 모든 페이지 성공적으로 처리
- 진행 상황 실시간 업데이트: "페이지 1/12", "페이지 2/12", ...
- 최종 메시지: "✅ 완료: test.pdf"

---

### 5.2 네트워크 타임아웃 (재시도 성공) ✅

**테스트**: 4페이지에서 일시적 타임아웃 발생

**시뮬레이션**:
- Vision API 서버에 인위적 지연 추가 (70초)
- 또는 방화벽으로 일시적 차단

**예상 결과**:
1. 페이지 4 API 호출 → 타임아웃 (70초 후)
2. "페이지 4 재시도 중 (1/3)..." 메시지
3. 2초 대기 후 재시도
4. 재시도 성공 → 계속 진행
5. 모든 페이지 성공

---

### 5.3 네트워크 타임아웃 (재시도 실패) 🔴

**테스트**: 4페이지에서 지속적 타임아웃 발생

**시뮬레이션**:
- Vision API 서버 완전 차단

**예상 결과**:
1. 페이지 4 API 호출 → 타임아웃
2. "페이지 4 재시도 중 (1/3)..." → 2초 대기 → 타임아웃
3. "페이지 4 재시도 중 (2/3)..." → 4초 대기 → 타임아웃
4. "페이지 4 재시도 중 (3/3)..." → 8초 대기 → 타임아웃
5. `PartialUploadException` 발생
6. 메시지:
   - "❌ 업로드 실패: test.pdf"
   - "일부 페이지 처리 실패로 전체 업로드가 취소되었습니다."
   - "실패한 페이지: 4"
   - "✅ 시스템은 정상 작동합니다. 재시도하세요."
7. 1-3페이지 청크는 DB 저장 안 됨 (전체 롤백 확인)

---

### 5.4 취소 테스트 (페이지 처리 중) ✅

**테스트**: 3페이지 처리 중 취소 버튼 클릭

**시나리오**:
1. 페이지 1 성공
2. 페이지 2 성공
3. 페이지 3 Vision API 호출 중
4. 사용자가 "업로드 취소" 버튼 클릭

**예상 결과**:
1. 다음 취소 체크 지점에서 `CancelledException` 발생 (최대 1초 이내)
2. 메시지: "⚠️ 업로드 취소됨 (1/1 파일 처리 중)"
3. 1-2페이지 청크는 DB 저장 안 됨 (전체 롤백)
4. 시스템 정상 작동 (다른 작업 가능)

---

### 5.5 취소 테스트 (재시도 중) ✅

**테스트**: 재시도 대기 중 취소 버튼 클릭

**시나리오**:
1. 페이지 4 타임아웃 → 재시도 (1/3)
2. 2초 대기 중
3. 사용자가 "업로드 취소" 버튼 클릭

**예상 결과**:
1. 재시도 전 취소 체크에서 `CancelledException` 발생
2. 메시지: "⚠️ 업로드 취소됨"
3. 전체 롤백
4. 시스템 정상 작동

---

### 5.6 API 인증 오류 (재시도 불가) 🔴

**테스트**: 잘못된 API 키 사용

**시뮬레이션**:
- `vision_api_key` 값을 잘못된 값으로 변경

**예상 결과**:
1. 페이지 1 API 호출 → 401 Unauthorized
2. 재시도 불가능한 오류로 판단
3. `PartialUploadException` 즉시 발생 (재시도 없음)
4. 메시지:
   - "❌ 업로드 실패: test.pdf"
   - "일부 페이지 처리 실패로 전체 업로드가 취소되었습니다."
   - "실패한 페이지: 1"
   - "✅ 시스템은 정상 작동합니다. API 키를 확인하세요."

---

### 5.7 이미지 인코딩 실패 (재시도 불가) 🔴

**테스트**: 손상된 이미지

**시뮬레이션**:
- PDF에 손상된 이미지 포함

**예상 결과**:
1. 페이지 N 이미지 인코딩 → 예외 발생
2. `PartialUploadException` 즉시 발생 (재시도 없음)
3. 메시지:
   - "실패한 페이지: N"
   - "이미지 인코딩 실패 (재시도 불가)"

---

## 6. 최종 정리

### 6.1 변경 사항 요약

| 항목 | 기존 | 변경 후 |
|------|------|---------|
| **부분 업로드 처리** | `continue`로 건너뛰기 (부분 저장) | `PartialUploadException` 발생 (전체 롤백) |
| **재시도 로직** | 없음 | 페이지당 최대 3회 재시도 (지수 백오프) |
| **재시도 가능 예외** | 구분 없음 | Timeout, ConnectionError, 429/503 재시도 |
| **취소 메커니즘** | 파일 단위만 | 페이지 단위 + 재시도 중 취소 가능 |
| **진행 상황 업데이트** | 없음 | 페이지별 + 재시도 상태 실시간 표시 |
| **타임아웃 설정** | 단일 값 (60초) | 튜플 (10초, 60초) |

### 6.2 예상 소요 시간

| 우선순위 | 작업 | 소요 시간 | 난이도 |
|---------|------|---------|--------|
| 1 | 타임아웃 튜플 변경 | 5분 | ⭐ 매우 낮음 |
| 2 | 취소 메커니즘 + 전체 롤백 + 재시도 | 2-3시간 | ⭐⭐⭐ 중상 |
| 3 | 예외 처리 강화 | (우선순위 2에 포함) | - |

**총 예상 소요**: 2-3시간

### 6.3 예상 효과

| 항목 | 개선 전 | 개선 후 |
|------|---------|---------|
| **타임아웃 시** | 무한 대기 | 70초 내 타임아웃 |
| **취소 버튼** | 작동 안 함 | 1초 이내 즉시 취소 |
| **일시적 오류** | 즉시 실패 (전체 재처리) | 자동 재시도 (3회) |
| **진행 상황** | 변화 없음 | 실시간 업데이트 |
| **데이터 일관성** | 부분 데이터 가능 | 전체 성공 또는 전체 실패 |
| **사용자 경험** | 재시작 필요 | 시스템 정상 작동 유지 |

---

## 7. 결론

### 7.1 타당성 검토 결과 ✅

**전체 롤백 전략**: ✅ **타당함**
- ACID 원칙 준수 (원자성 보장)
- 업계 표준과 일치
- 데이터 일관성 보장

**PartialUploadException**: ✅ **타당함** (일부 개선 필요)
- 예외 유형별 처리 가능
- 개선: `failed_pages` → `failed_page` (단일 값)

**즉시 실패 전략**: ✅ **타당함**
- Fail-fast 원칙
- 빠른 피드백

### 7.2 추가 개선 권장사항

1. **페이지별 재시도 로직 추가** 🔴 최우선
   - 일시적 오류 대응
   - 재처리 부담 감소

2. **재시도 가능/불가능 예외 구분** 🔴 최우선
   - 명확한 오류 메시지
   - 빠른 실패 vs 자동 재시도

3. **`failed_pages` → `failed_page` 변경** 🟡 중간
   - 논리적 일관성 개선

### 7.3 다음 단계

1. ✅ 우선순위 1: 타임아웃 튜플 변경 (5분)
2. ✅ 우선순위 2: 취소 메커니즘 + 전체 롤백 + 재시도 (2-3시간)
3. ✅ 테스트 시나리오 실행

**총 예상 소요**: 2-3시간 + 테스트 1시간 = **3-4시간**

---

**검토 완료**: 2025-11-28
**검토자**: Claude Code
**최종 판정**: ✅ **승인** (추가 개선 사항 반영)
