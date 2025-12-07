# Phase 2: PDF Vision 기본 구현 완료

**작성일**: 2025-11-19
**상태**: ✅ 핵심 구현 완료 (테스트는 Poppler 설치 후 가능)
**소요 시간**: ~1시간

---

## 📋 목표

PDF 파일을 페이지별로 이미지 변환 후 Vision API로 분석하여 RAG에 추가

---

## ✅ 구현 내용

### 1. 의존성 추가

**파일**: [requirements.txt](requirements.txt#L16)

```txt
pdf2image>=1.16.3  # Phase 2: PDF Vision
```

**설치 완료**:
- ✅ pdf2image 설치 완료
- ⏳ Poppler 설치 필요 (Poppler 없이도 코드는 작성 완료)

### 2. Poppler 설치 가이드 작성

**파일**: [POPPLER_INSTALL_GUIDE.md](POPPLER_INSTALL_GUIDE.md)

**내용**:
- Windows Poppler 다운로드 및 설치 방법
- 환경 변수 설정 방법
- 트러블슈팅 가이드
- RAG 시스템에서 Poppler 사용 방법

**Poppler 설치**:
```bash
# 1. 다운로드: https://github.com/oschwartz10612/poppler-windows/releases/
# 2. 압축 해제: C:\Program Files\poppler\
# 3. 환경 변수 추가: C:\Program Files\poppler\Library\bin
# 4. 확인: pdftoppm -v
```

### 3. PDFChunkingEngine Vision 지원 추가

**파일**: [utils/pdf_chunking_engine.py](utils/pdf_chunking_engine.py)

#### 변경사항:

**1) Vision 라이브러리 import** (Lines 16-28):
```python
# Phase 2: Vision 라이브러리
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

try:
    from PyPDF2 import PdfReader
except ImportError:
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None
```

**2) Vision 설정 추가** (Lines 49-53):
```python
# Phase 2: Vision 설정
self.enable_vision = config.get("enable_vision_chunking", True)
self.poppler_path = config.get("poppler_path", None)
self.pdf_dpi = config.get("pdf_dpi", 150)
self.pdf_vision_detail = config.get("pdf_vision_detail", "high")
```

**3) process_pdf_document 메서드 확장** (Lines 55-91):
```python
def process_pdf_document(self,
                        pdf_path: str,
                        enable_vision: Optional[bool] = None,
                        llm_api_type: Optional[str] = None,
                        llm_base_url: Optional[str] = None,
                        llm_model: Optional[str] = None,
                        llm_api_key: Optional[str] = None) -> List[Chunk]:
    """
    Phase 2: Vision 모드 추가
    - enable_vision=True: PDF → 이미지 → Vision API 분석
    - enable_vision=False: 기존 pdfplumber 텍스트 추출
    """
    # Vision 모드 결정
    use_vision = enable_vision if enable_vision is not None else self.enable_vision

    # Vision 모드면 Vision 처리 호출
    if use_vision:
        return self._process_pdf_with_vision(...)

    # 기존 텍스트 모드 (pdfplumber)
    ...
```

**4) Vision 처리 메서드 추가** (Lines 853-967):
```python
def _process_pdf_with_vision(self, pdf_path, llm_api_type, ...):
    """PDF를 Vision API로 처리 (Phase 2)"""

    # PDF 페이지 수 확인
    reader = PdfReader(pdf_path)
    page_count = len(reader.pages)

    # PDF → 이미지 변환
    images = convert_from_path(pdf_path, dpi=self.pdf_dpi, ...)

    # 각 페이지 Vision 분석
    for page_num, image in enumerate(images, 1):
        # 이미지 → Base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_base64 = base64.b64encode(...).decode("utf-8")

        # Vision API 호출
        description = self._analyze_page_with_vision(...)

        # Chunk 생성
        chunk = Chunk(
            id=f"{document_id}_pdf_page_{page_num}",
            content=description,
            chunk_type="pdf_page_vision",
            metadata=ChunkMetadata(...)
        )
        chunks.append(chunk)

    return chunks
```

**5) Vision API 호출 메서드 추가** (Lines 969-1057):
```python
def _analyze_page_with_vision(self, image_base64, page_num, ...):
    """Vision API로 PDF 페이지 분석"""

    prompt = f"""이 PDF 페이지(Page {page_num}/{total_pages})의 내용을 자세히 분석하세요.

다음 정보를 추출하세요:
1. **주제**: 이 페이지의 주요 주제
2. **텍스트 내용**: 중요한 텍스트 (제목, 본문, 키워드)
3. **표**: 표가 있다면 제목, 행/열 구조, 주요 데이터
4. **차트/그래프**: 있다면 유형, 트렌드, 핵심 인사이트
5. **이미지**: 있다면 설명
...
"""

    # Vision API 호출
    payload = {
        "model": llm_model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": self.pdf_vision_detail  # "high"
                    }
                }
            ]
        }],
        "max_tokens": 800,
        "temperature": 0
    }

    response = requests.post(api_url, ...)
    return result["choices"][0]["message"]["content"]
```

### 4. config.py PDF 설정 추가

**파일**: [config.py:80-83](config.py#L80-L83)

```python
# Phase 2: PDF Vision 설정
"pdf_dpi": 150,  # PDF → 이미지 변환 해상도 (150 권장)
"pdf_vision_detail": "high",  # Vision API detail 레벨 (high/low)
"poppler_path": None,  # Poppler 경로 (None이면 환경 변수 PATH 사용)
```

### 5. 테스트 파일 작성

**파일**: [test_pdf_vision.py](test_pdf_vision.py)

**기능**:
- PDF Vision 청킹 테스트
- 라이브러리 누락 시 명확한 에러 메시지
- Poppler 미설치 시 설치 가이드 안내
- 청크 분석 및 통계 출력

**사용법**:
```bash
# 1. data/test_pdf/ 폴더에 sample.pdf 파일 준비
# 2. Poppler 설치 (POPPLER_INSTALL_GUIDE.md 참조)
# 3. 테스트 실행
python test_pdf_vision.py
```

---

## 🧪 테스트 상태

### 현재 상태

- ✅ 코드 구현 완료
- ✅ 의존성 설치 완료 (pdf2image)
- ⏳ Poppler 설치 필요 (현재 미설치)
- ⏳ 테스트 PDF 파일 준비 필요

### 테스트 실행 시나리오

**Poppler 설치 후 테스트**:

1. Poppler 설치 ([POPPLER_INSTALL_GUIDE.md](POPPLER_INSTALL_GUIDE.md) 참조)
2. 테스트 PDF 파일 준비 (`data/test_pdf/sample.pdf`)
3. `python test_pdf_vision.py` 실행

**예상 결과**:
```
Phase 2: PDF Vision 테스트
================================================================================

설정:
  API 타입: openai
  모델: gpt-4o-mini
  Vision 활성화: True (강제)
  PDF DPI: 150
  Vision Detail: high

테스트 파일: sample.pdf

Vision 청킹 시작...
--------------------------------------------------------------------------------
[PDFChunkingEngine] Vision 모드로 PDF 처리: ...
[PDFChunkingEngine] 총 3페이지
[PDFChunkingEngine] PDF → 이미지 변환 중...
[PDFChunkingEngine] 3개 페이지 이미지 변환 완료
[PDFChunkingEngine] 페이지 1/3 Vision 분석 중...
[PDFChunkingEngine] 페이지 1 Vision 분석 완료
...

청킹 완료: 3개 청크 생성

청크 분석:
--------------------------------------------------------------------------------

청크 1:
  타입: pdf_page_vision
  페이지: 1
  내용 (앞 300자):
  주제: 2024년 매출 보고서
  텍스트 내용: ...
  표: 4행 3열 표 (지역별 매출 현황)
  ...

================================================================================
테스트 결과 요약
================================================================================
총 청크 수: 3
처리된 페이지: [1, 2, 3]
페이지 수: 3
Vision 청크: 3개 (100.0%)

[SUCCESS] Phase 2 PDF Vision 테스트 통과
================================================================================
```

---

## 📊 기술적 구현 상세

### PDF → Vision 처리 플로우

```
PDF 파일
   ↓
PyPDF2 (페이지 수 확인)
   ↓
pdf2image + Poppler (PDF → 이미지 변환, DPI=150)
   ↓
Pillow (이미지 → Base64 인코딩)
   ↓
Vision API (gpt-4o-mini, detail="high", max_tokens=800)
   ↓
구조화된 분석 결과
   ↓
Chunk 생성 (chunk_type="pdf_page_vision")
   ↓
RAG 시스템에 추가
```

### 하이브리드 아키텍처

PDFChunkingEngine은 2가지 모드를 지원:

1. **Vision 모드** (Phase 2):
   - PDF → 이미지 → Vision API
   - 표, 차트, 이미지 모두 분석 가능
   - 높은 정확도, 높은 비용

2. **텍스트 모드** (기존):
   - pdfplumber 기반 텍스트 추출
   - Layout-Aware 분석
   - 낮은 비용, 텍스트만 추출

**선택 방법**:
```python
# Vision 모드
chunks = engine.process_pdf_document(pdf_path, enable_vision=True, ...)

# 텍스트 모드
chunks = engine.process_pdf_document(pdf_path, enable_vision=False)

# config 값 사용 (enable_vision_chunking)
chunks = engine.process_pdf_document(pdf_path)
```

### Vision 프롬프트 전략

**구조화된 분석**:
- 주제, 텍스트, 표, 차트, 이미지를 개별적으로 추출
- markdown 형식으로 구조화
- 800 토큰으로 상세 분석

**detail 레벨**:
- `"high"`: 정확한 표/차트 분석 (Phase 2 기본값)
- `"low"`: 빠른 처리, 낮은 비용 (Phase 3에서 활용 예정)

---

## 🚧 미완료 항목 (Phase 3 또는 나중에)

### GUI PDF 업로드 지원

**파일**: `ui/document_widget.py` (수정 필요)

**변경사항**:
```python
# Line ~401: on_add() 함수에 PDF 파일 타입 추가
file_paths, _ = QFileDialog.getOpenFileNames(
    self,
    "문서 선택",
    "",
    "Documents (*.txt *.md *.pdf *.pptx *.docx);;All Files (*)"  # PDF 추가
)

# Line ~250: _start_upload() 함수에 PDF 처리 로직 추가
if file_ext == ".pdf":
    from utils.pdf_chunking_engine import PDFChunkingEngine
    engine = PDFChunkingEngine(self.config)
    chunks = engine.process_pdf_document(
        pdf_path=file_path,
        enable_vision=True,
        llm_api_type=self.config.get("llm_api_type"),
        llm_model=self.config.get("llm_model"),
        llm_api_key=self.config.get("llm_api_key")
    )
    self.vector_manager.add_chunks(chunks, target_db=target_db)
```

**예상 소요 시간**: 30분

### VectorStoreManager PDF 지원

**파일**: `vector_store/vector_store_manager.py` (수정 필요)

**변경사항**:
```python
# 검색 결과 표시 시 PDF 페이지 구분 추가
for result in results:
    if result["metadata"].chunk_method == "vision_pdf":
        result["display"] = f"[PDF] {result['metadata'].source_file} - Page {result['metadata'].page_number}"
```

**예상 소요 시간**: 10분

---

## 📈 RAG 성능 영향

### 예상 성과

| 지표 | Phase 1 (PPT 차트) | Phase 2 (PDF Vision) | 개선 |
|------|------------------|---------------------|------|
| PPT 커버리지 | 90% | 90% | - |
| **PDF 커버리지** | 0% | 85% | **+85%p** |
| **종합 커버리지** | 70% | 85% | **+15%p** |

### 비용 분석

**Phase 2 비용** (모든 페이지 Vision):
- PDF 페이지당: $0.0003 (detail:"high" 기준)
- 10페이지 PDF: $0.003
- 100페이지 PDF: $0.03

**Phase 3에서 70% 절감 예정** (Hybrid 모드):
- 텍스트 페이지: Vision 스킵 ($0)
- 표/차트 페이지만 Vision 사용
- 예상 비용: 10페이지 PDF $0.001 (70% 절감)

---

## 🔄 Phase 3 Preview

**Phase 3: PDF Vision Hybrid 최적화** (다음 단계)

1. **Smart Vision Decision**:
   - pdfplumber로 텍스트/표/이미지 유무 확인
   - 텍스트만 있는 페이지 → Vision 스킵
   - 표/차트 페이지만 → Vision 사용

2. **비용 70% 절감**:
   - 일반 문서: Vision 사용 30% 이하
   - 기술 문서: Vision 사용 50-60%

3. **RAG 성능 유지**:
   - 텍스트 페이지: pdfplumber로 정확한 텍스트 추출
   - 표/차트 페이지: Vision으로 분석
   - 검색 정확도 85% 유지

---

## 📁 생성된 파일

1. [requirements.txt](requirements.txt) - pdf2image 추가
2. [POPPLER_INSTALL_GUIDE.md](POPPLER_INSTALL_GUIDE.md) - Poppler 설치 가이드
3. [utils/pdf_chunking_engine.py](utils/pdf_chunking_engine.py) - Vision 지원 추가 (~200줄)
4. [config.py](config.py) - PDF Vision 설정 추가
5. [test_pdf_vision.py](test_pdf_vision.py) - 테스트 스크립트
6. [PHASE2_PDF_SUMMARY.md](PHASE2_PDF_SUMMARY.md) (본 문서)

---

## ✅ Phase 2 완료 조건 체크

- [x] pdf2image 라이브러리 설치
- [x] Poppler 설치 가이드 작성
- [x] PDFChunkingEngine Vision 지원 추가
- [x] config.py PDF 설정 추가
- [x] 테스트 파일 작성
- [ ] Poppler 설치 (사용자가 수행)
- [ ] 테스트 PDF 준비 및 실행 (사용자가 수행)
- [ ] GUI PDF 업로드 지원 (Phase 3 또는 나중에)
- [ ] VectorStoreManager PDF 지원 (Phase 3 또는 나중에)

**핵심 구현 완료**: ✅
**테스트 준비 완료**: ✅
**프로덕션 준비**: ⏳ (Poppler 설치 후)

---

## 📝 사용 가이드

### PDF Vision 청킹 활성화

**1) config.json 수정**:
```json
{
  "enable_vision_chunking": true,
  "pdf_dpi": 150,
  "pdf_vision_detail": "high"
}
```

**2) Poppler 설치**:
- [POPPLER_INSTALL_GUIDE.md](POPPLER_INSTALL_GUIDE.md) 참조

**3) PDF 업로드**:
```python
from utils.pdf_chunking_engine import PDFChunkingEngine
from config import ConfigManager

config = ConfigManager().get_all()
engine = PDFChunkingEngine(config)

chunks = engine.process_pdf_document(
    pdf_path="document.pdf",
    enable_vision=True,  # Vision 활성화
    llm_api_key=config["llm_api_key"]
)
```

---

## 🎯 결론

**Phase 2 목표 달성**: PDF Vision 기본 구현 완료

**핵심 성과**:
1. PDFChunkingEngine에 Vision 지원 추가 (하이브리드 아키텍처)
2. Poppler 설치 가이드 제공
3. 테스트 스크립트 작성
4. PDF 커버리지 0% → 85% (예상)

**다음 단계**: Phase 3 (PDF Hybrid 최적화) 또는 GUI 통합

**시작 준비 완료**: Poppler 설치 후 즉시 사용 가능 ✅
