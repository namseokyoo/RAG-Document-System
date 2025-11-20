# Poppler 설치 가이드 (Windows)

**목적**: pdf2image 라이브러리가 PDF를 이미지로 변환하기 위해 필요한 Poppler 유틸리티 설치

---

## Windows 설치 방법

### 방법 1: 수동 설치 (권장)

#### Step 1: Poppler 다운로드

1. GitHub 릴리즈 페이지 접속:
   https://github.com/oschwartz10612/poppler-windows/releases/

2. 최신 릴리즈에서 다운로드:
   - **Release-XX.XX.X-0.zip** 파일 다운로드
   - 예: `Release-24.08.0-0.zip`

#### Step 2: 압축 해제

1. 다운로드한 파일을 압축 해제
2. 폴더 이름 변경: `poppler-XX.XX.X` → `poppler`
3. 원하는 위치로 이동 (예: `C:\Program Files\poppler`)

**권장 경로**:
```
C:\Program Files\poppler\
├── Library\
│   ├── bin\        ← 실행 파일 (중요!)
│   ├── include\
│   └── lib\
└── ...
```

#### Step 3: 환경 변수 설정

1. **시스템 속성** 열기:
   - `Win + R` → `sysdm.cpl` 입력 → Enter

2. **고급** 탭 → **환경 변수** 클릭

3. **시스템 변수**에서 `Path` 선택 → **편집** 클릭

4. **새로 만들기** → 다음 경로 추가:
   ```
   C:\Program Files\poppler\Library\bin
   ```

5. **확인** → **확인** → **확인** (모든 창 닫기)

#### Step 4: 설치 확인

새 명령 프롬프트 열기 (기존 창은 환경 변수를 인식 못함):

```bash
pdftoppm -v
```

**성공 시 출력 예시**:
```
pdftoppm version 24.08.0
Copyright 2005-2024 The Poppler Developers - http://poppler.freedesktop.org
...
```

**오류 시**:
```
'pdftoppm'은(는) 내부 또는 외부 명령, 실행할 수 있는 프로그램, 또는
배치 파일이 아닙니다.
```
→ 환경 변수 경로 확인 또는 명령 프롬프트 재시작

---

### 방법 2: Chocolatey 사용 (선택)

Chocolatey가 설치되어 있다면:

```bash
choco install poppler
```

---

## Python에서 Poppler 사용

### 기본 사용법

```python
from pdf2image import convert_from_path

# PDF → 이미지 변환
images = convert_from_path('sample.pdf', dpi=150)

# 첫 페이지 저장
images[0].save('page_1.png', 'PNG')
```

### Poppler 경로 명시 (환경 변수 미설정 시)

```python
from pdf2image import convert_from_path

# Poppler 경로 직접 지정
poppler_path = r'C:\Program Files\poppler\Library\bin'

images = convert_from_path(
    'sample.pdf',
    dpi=150,
    poppler_path=poppler_path
)
```

---

## 트러블슈팅

### 1. "Unable to get page count. Is poppler installed and in PATH?"

**원인**: Poppler가 설치되지 않았거나 환경 변수가 설정되지 않음

**해결**:
1. Poppler 설치 확인: `pdftoppm -v` 실행
2. 환경 변수 확인
3. 명령 프롬프트 재시작

### 2. 환경 변수 설정 후에도 인식 안 됨

**해결**:
1. 모든 명령 프롬프트 및 Python 프로세스 종료
2. 새 명령 프롬프트 열기
3. `pdftoppm -v` 재확인

### 3. 권한 문제

**원인**: `C:\Program Files\`에 설치 시 관리자 권한 필요

**해결**:
- 관리자 권한으로 파일 이동
- 또는 `C:\Users\<사용자명>\poppler\`에 설치

---

## RAG 시스템에서 Poppler 사용

### 자동 감지

RAG 시스템의 PDFChunkingEngine은 Poppler를 자동으로 감지합니다:

```python
from utils.pdf_chunking_engine import PDFChunkingEngine

engine = PDFChunkingEngine(config)

# Poppler가 PATH에 있으면 자동으로 사용
chunks = engine.process_pdf_document('document.pdf', enable_vision=True, ...)
```

### 수동 지정 (선택)

config.py에 Poppler 경로 추가 가능:

```python
DEFAULT_CONFIG = {
    # ...
    "poppler_path": r"C:\Program Files\poppler\Library\bin",  # 선택 사항
}
```

---

## 참고 자료

- **Poppler GitHub**: https://github.com/oschwartz10612/poppler-windows
- **pdf2image 문서**: https://github.com/Belval/pdf2image
- **Poppler 공식 사이트**: https://poppler.freedesktop.org/

---

## 요약

1. **다운로드**: https://github.com/oschwartz10612/poppler-windows/releases/
2. **압축 해제**: `C:\Program Files\poppler\`
3. **환경 변수**: `Path`에 `C:\Program Files\poppler\Library\bin` 추가
4. **확인**: 새 CMD에서 `pdftoppm -v` 실행

**설치 완료 후 RAG 시스템에서 PDF Vision 기능 사용 가능** ✅
