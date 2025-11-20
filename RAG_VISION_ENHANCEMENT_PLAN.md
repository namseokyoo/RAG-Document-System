# RAG 시스템 Vision 기능 확장 종합 구현 계획서

**작성일**: 2025-11-19
**목적**: PPT 차트 및 PDF Vision 지원을 통한 RAG 성능 개선
**접근**: 단계적 구현으로 시스템 안정성 확보

---

## 📋 목차

1. [현재 상태 및 목표](#현재-상태-및-목표)
2. [전체 로드맵](#전체-로드맵)
3. [Phase 1: PPT 차트 지원](#phase-1-ppt-차트-지원)
4. [Phase 2: PDF Vision 기본 구현](#phase-2-pdf-vision-기본-구현)
5. [Phase 3: PDF Vision Hybrid 최적화](#phase-3-pdf-vision-hybrid-최적화)
6. [Phase 4: 프로덕션 배포 및 모니터링](#phase-4-프로덕션-배포-및-모니터링)
7. [리스크 관리 매트릭스](#리스크-관리-매트릭스)
8. [성공 지표](#성공-지표)

---

## 현재 상태 및 목표

### ✅ 완료된 기능 (Phase 1-B)

- **PPT 텍스트 청킹**: python-pptx 기반 텍스트 추출 및 청킹
- **PPT 표 Vision 지원**: 테이블이 포함된 슬라이드 Vision 분석
- **제목 없는 슬라이드 매칭**: 테이블 구조 기반 Fuzzy Matching (±1 tolerance)
- **Small-to-Large 아키텍처**: slide_summary (부모) + detail chunks (자식)

**검증 상태**:
- 4개 PPT 파일 테스트 완료 (100% 성공률)
- Vision 사용률: 75-100%
- 테이블 구조 매칭 정확도: 100% (4/4 제목 없는 슬라이드)

### 🎯 구현 목표

| 기능 | RAG 성능 개선 효과 | 현재 지원 | 목표 |
|------|-------------------|----------|------|
| PPT 텍스트 | ✅ 지원 | 90% | 90% |
| PPT 표 | ✅ Vision 지원 | 80% | 95% |
| **PPT 차트/그래프** | ❌ 미지원 | 0% | **90%** |
| **PDF 텍스트** | ❌ 미지원 | 0% | **85%** |
| **PDF 표/차트/이미지** | ❌ 미지원 | 0% | **90%** |

**종합 목표**: RAG 정보 커버리지 **60% → 92%** 향상

---

## 전체 로드맵

```
┌─────────────────────────────────────────────────────────────────┐
│                        완료 (Phase 1-B)                          │
│  PPT 텍스트 + PPT 표 Vision + 테이블 구조 매칭                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Phase 1: PPT 차트 지원                        │
│  기간: 1-2일 | 리스크: 낮음 | 기존 시스템 영향: 최소              │
│  • 차트 감지 로직 추가                                            │
│  • 차트 Vision 분석 추가                                          │
│  • 기존 표 Vision 로직과 병합                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 Phase 2: PDF Vision 기본 구현                    │
│  기간: 1주 | 리스크: 중간 | 기존 시스템 영향: 중간                │
│  • PDFChunkingEngine 신규 생성                                   │
│  • pdf2image 통합                                                │
│  • 페이지별 Vision 분석                                           │
│  • DocumentWidget에 PDF 업로드 추가                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              Phase 3: PDF Vision Hybrid 최적화                   │
│  기간: 2주 | 리스크: 중간 | 기존 시스템 영향: 낮음                │
│  • Smart Vision Decision 로직                                    │
│  • pdfplumber 텍스트 추출                                        │
│  • 비용 70% 절감 (텍스트 페이지 Vision 스킵)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│            Phase 4: 프로덕션 배포 및 모니터링                     │
│  기간: 1주 | 리스크: 낮음                                         │
│  • 성능 모니터링 대시보드                                          │
│  • 사용자 피드백 수집                                             │
│  • 최적화 및 버그 수정                                            │
└─────────────────────────────────────────────────────────────────┘
```

**총 예상 기간**: 4-5주

---

## Phase 1: PPT 차트 지원

### 📌 목표
PPT 파일의 차트/그래프를 Vision API로 분석하여 RAG 검색 정확도 향상

### 🎯 성공 기준
- 차트가 포함된 슬라이드 자동 감지 (100%)
- 차트 Vision 분석 성공률 90%+
- 기존 표 Vision 기능과 충돌 없음
- 차트 데이터 추출: 트렌드, 이상치, 비교값 등

### 📂 변경 파일
- `utils/pptx_chunking_engine.py` (수정)
- `test_chart_vision.py` (신규)

### 🔧 구현 단계

#### Step 1.1: 차트 감지 로직 추가 (30분)

**변경 위치**: `utils/pptx_chunking_engine.py`

```python
def _has_chart(self, slide) -> bool:
    """슬라이드에 차트가 있는지 확인"""
    for shape in slide.shapes:
        if shape.has_chart:
            return True
    return False

def _extract_chart_info(self, slide) -> dict:
    """차트 기본 정보 추출 (python-pptx 제한적)"""
    charts = []
    for shape in slide.shapes:
        if shape.has_chart:
            chart = shape.chart
            chart_type = chart.chart_type  # ChartType enum (예: BAR_CLUSTERED, LINE, PIE)
            charts.append({
                "type": str(chart_type),
                "has_title": chart.has_title,
                "title": chart.chart_title.text_frame.text if chart.has_title else ""
            })
    return {
        "has_chart": len(charts) > 0,
        "chart_count": len(charts),
        "charts": charts
    }
```

**리스크**: 없음 (읽기 전용 함수)

#### Step 1.2: 차트 Vision 분석 프롬프트 작성 (1시간)

**변경 위치**: `utils/pptx_chunking_engine.py`

```python
def _analyze_chart_with_vision(self, image_base64: str, chart_info: dict,
                               llm_api_type: str, llm_api_key: str,
                               llm_model: str) -> str:
    """차트 이미지를 Vision API로 분석"""

    chart_types = ", ".join([c["type"] for c in chart_info["charts"]])

    prompt = f"""이 슬라이드에는 {chart_info['chart_count']}개의 차트가 있습니다 (유형: {chart_types}).

각 차트에 대해 다음을 분석하세요:

1. **데이터 유형**: 무엇을 측정하는가? (매출, 성장률, 점유율 등)
2. **주요 트렌드**: 증가/감소/변동 패턴
3. **핵심 인사이트**: 가장 중요한 발견 (최대값, 최소값, 이상치 등)
4. **비교**: 항목 간 비교 (예: A가 B보다 20% 높음)

구조화된 형식으로 답변하세요:
---
차트 1:
- 데이터 유형: ...
- 주요 트렌드: ...
- 핵심 인사이트: ...
- 비교: ...
"""

    # Vision API 호출 (기존 _generate_slide_description_via_vision과 유사)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm_api_key}"
    }

    payload = {
        "model": llm_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high"  # 차트는 고해상도 필요
                        }
                    }
                ]
            }
        ],
        "max_tokens": 500,
        "temperature": 0
    }

    api_url = "https://api.openai.com/v1/chat/completions"
    response = requests.post(api_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    return result["choices"][0]["message"]["content"]
```

**리스크**:
- Vision API 비용 증가 (완화: 차트 있는 슬라이드만 호출)
- 타임아웃 (완화: timeout=30초 설정)

#### Step 1.3: 기존 Vision 로직과 통합 (1시간)

**변경 위치**: `utils/pptx_chunking_engine.py`, `_generate_slide_description_via_vision()` 함수 수정

```python
def _generate_slide_description_via_vision(self, image_base64: str, slide_title: str,
                                          llm_api_type: str, llm_api_key: str,
                                          llm_model: str, slide_index: int,
                                          slide) -> str:
    """Vision API로 슬라이드 분석 - 표 OR 차트 감지"""

    # 표 확인
    table_structure = self._extract_table_structure(slide)
    has_table = table_structure["has_table"]

    # 차트 확인 (신규)
    chart_info = self._extract_chart_info(slide)
    has_chart = chart_info["has_chart"]

    # 프롬프트 선택
    if has_chart:
        # 차트 분석 프롬프트
        description = self._analyze_chart_with_vision(
            image_base64, chart_info, llm_api_type, llm_api_key, llm_model
        )
    elif has_table:
        # 기존 표 분석 프롬프트 (변경 없음)
        description = self._analyze_table_with_vision(...)
    else:
        # 일반 슬라이드 (텍스트/이미지)
        description = self._analyze_general_slide_with_vision(...)

    return description
```

**리스크**:
- 표와 차트가 동시에 있는 경우 (완화: 차트 우선, 나중에 개선 가능)

#### Step 1.4: 테스트 작성 및 실행 (2시간)

**신규 파일**: `test_chart_vision.py`

```python
"""
차트 Vision 테스트
"""
from pathlib import Path
from utils.pptx_chunking_engine import PPTXChunkingEngine
from config import ConfigManager

def test_chart_vision():
    """차트 포함 PPT 파일로 Vision 청킹 테스트"""

    # 차트 포함 파일 찾기
    test_files = list(Path("data/test_pptx").glob("*.pptx"))

    config_mgr = ConfigManager()
    config = config_mgr.get_all()
    engine = PPTXChunkingEngine(config)

    for file_path in test_files:
        print(f"테스트: {file_path.name}")

        # 차트 확인
        from pptx import Presentation
        prs = Presentation(str(file_path))

        chart_slides = []
        for i, slide in enumerate(prs.slides, 1):
            for shape in slide.shapes:
                if shape.has_chart:
                    chart_slides.append(i)
                    break

        if not chart_slides:
            print(f"  차트 없음 - SKIP")
            continue

        print(f"  차트 슬라이드: {chart_slides}")

        # Vision 청킹
        chunks = engine.process_pptx_document(
            pptx_path=str(file_path),
            enable_vision=True,
            llm_api_type=config.get("llm_api_type"),
            llm_model=config.get("llm_model"),
            llm_api_key=config.get("llm_api_key")
        )

        # 차트 슬라이드 청크 확인
        for slide_num in chart_slides:
            chart_chunks = [c for c in chunks if c.metadata.slide_number == slide_num]
            for chunk in chart_chunks:
                if "데이터 유형:" in chunk.content or "주요 트렌드:" in chunk.content:
                    print(f"  ✅ 슬라이드 {slide_num} 차트 분석 성공")
                    print(f"     {chunk.content[:150]}...")
                    break
            else:
                print(f"  ❌ 슬라이드 {slide_num} 차트 분석 실패")

        print()

if __name__ == "__main__":
    test_chart_vision()
```

**테스트 계획**:
1. 기존 PPT 파일 중 차트 포함 파일 찾기 (`check_charts.py` 재사용)
2. 차트 없으면 → 샘플 차트 PPT 생성 (간단한 막대/선/파이 차트)
3. Vision 청킹 실행 후 "데이터 유형:", "주요 트렌드:" 키워드 확인

#### Step 1.5: 기존 기능 회귀 테스트 (1시간)

**테스트 항목**:
```bash
# 기존 테이블 Vision 테스트 재실행
venv/Scripts/python.exe test_vision_integration.py

# 결과 확인:
# - 4/4 파일 SUCCESS 유지
# - Vision 사용률 75-100% 유지
# - 테이블 구조 매칭 100% 유지
```

**리스크 완화**:
- 차트 로직이 표 로직에 영향 주지 않도록 분리된 함수 사용
- 기존 테스트 100% 통과 확인 필수

---

### 🚨 Phase 1 리스크 및 완화

| 리스크 | 확률 | 영향 | 완화 방안 |
|--------|------|------|-----------|
| Vision API 비용 증가 | 높음 | 중간 | 차트 있는 슬라이드만 Vision 호출 (선택적) |
| 기존 표 Vision 기능 충돌 | 낮음 | 높음 | 별도 함수 분리, 회귀 테스트 필수 |
| 차트 분석 부정확 | 중간 | 중간 | detail:"high" 사용, 구조화된 프롬프트 |
| 테스트 PPT에 차트 없음 | 높음 | 낮음 | 샘플 차트 PPT 생성 |

---

### ✅ Phase 1 완료 조건

- [ ] 차트 감지 함수 구현 및 단위 테스트
- [ ] 차트 Vision 분석 함수 구현
- [ ] 기존 Vision 로직과 통합 완료
- [ ] 차트 Vision 테스트 통과 (90%+ 정확도)
- [ ] 기존 테이블 Vision 테스트 통과 (회귀 없음)
- [ ] 코드 리뷰 및 문서화

---

## Phase 2: PDF Vision 기본 구현

### 📌 목표
PDF 파일을 페이지별로 이미지 변환 후 Vision API로 분석하여 RAG에 추가

### 🎯 성공 기준
- PDF 업로드 및 페이지 분할 성공률 100%
- Vision 분석 성공률 85%+
- GUI에서 PDF 파일 선택 및 업로드 가능
- 청크 검색 시 PDF 페이지 올바르게 표시

### 📂 변경 파일
- `utils/pdf_chunking_engine.py` (신규)
- `ui/document_widget.py` (수정)
- `vector_store/vector_store_manager.py` (수정)
- `config.py` (수정)
- `requirements.txt` (수정)

### 🔧 구현 단계

#### Step 2.1: 의존성 추가 (10분)

**변경 위치**: `requirements.txt`

```txt
# 기존 의존성...
pdf2image==1.16.3
PyPDF2==3.0.1
poppler-utils==0.1.0  # Windows: poppler 별도 설치 필요
```

**설치**:
```bash
venv/Scripts/pip install pdf2image PyPDF2
```

**Poppler 설치** (Windows):
1. https://github.com/oschwartz10612/poppler-windows/releases/ 에서 다운로드
2. `C:\Program Files\poppler` 에 압축 해제
3. 환경 변수 PATH에 `C:\Program Files\poppler\Library\bin` 추가

**리스크**: Poppler 설치 실패 → 문서화 및 설치 스크립트 제공

#### Step 2.2: PDFChunkingEngine 생성 (4시간)

**신규 파일**: `utils/pdf_chunking_engine.py`

```python
"""
PDF 청킹 엔진 - 페이지별 Vision 분석

Phase 2: 기본 구현 (모든 페이지 Vision)
Phase 3: Hybrid (텍스트 페이지는 Vision 스킵)
"""

import os
import base64
from pathlib import Path
from typing import List, Optional
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
import requests
from io import BytesIO

from utils.chunking_models import Chunk, ChunkMetadata


class PDFChunkingEngine:
    """PDF 문서 청킹 엔진"""

    def __init__(self, config: dict):
        self.config = config
        self.enable_vision = config.get("enable_vision_chunking", True)

    def process_pdf_document(self,
                            pdf_path: str,
                            enable_vision: bool = True,
                            llm_api_type: str = "openai",
                            llm_base_url: str = "",
                            llm_model: str = "gpt-4o-mini",
                            llm_api_key: str = "") -> List[Chunk]:
        """
        PDF 문서 청킹

        Phase 2: 모든 페이지를 Vision으로 분석

        Args:
            pdf_path: PDF 파일 경로
            enable_vision: Vision 사용 여부
            llm_api_type: LLM API 타입
            llm_model: LLM 모델명
            llm_api_key: LLM API 키

        Returns:
            Chunk 리스트
        """
        print(f"[PDFChunkingEngine] PDF 처리 시작: {pdf_path}")

        if not enable_vision:
            print("[WARNING] Vision 비활성화 - PDF는 Vision 필수")
            return []

        # PDF 파일 존재 확인
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 파일 없음: {pdf_path}")

        # PDF 페이지 수 확인
        reader = PdfReader(pdf_path)
        page_count = len(reader.pages)
        print(f"[PDFChunkingEngine] 총 {page_count}페이지")

        # PDF → 이미지 변환
        print("[PDFChunkingEngine] PDF → 이미지 변환 중...")
        images = convert_from_path(pdf_path, dpi=150)  # 150 DPI = 적절한 해상도

        if len(images) != page_count:
            print(f"[WARNING] 페이지 수 불일치: {page_count} vs {len(images)}")

        # 각 페이지 분석
        chunks = []
        for page_num, image in enumerate(images, 1):
            print(f"[PDFChunkingEngine] 페이지 {page_num}/{page_count} 분석 중...")

            # 이미지 → Base64
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Vision 분석
            try:
                description = self._analyze_page_with_vision(
                    image_base64=image_base64,
                    page_num=page_num,
                    llm_api_type=llm_api_type,
                    llm_api_key=llm_api_key,
                    llm_model=llm_model
                )

                # Chunk 생성 (PPT와 유사한 구조)
                chunk = Chunk(
                    chunk_id=f"pdf_page_{page_num}",
                    content=description,
                    chunk_type="pdf_page",
                    metadata=ChunkMetadata(
                        source_file=os.path.basename(pdf_path),
                        page_number=page_num,
                        page_title=f"Page {page_num}",  # PDF는 제목 없음
                        total_pages=page_count,
                        chunk_method="vision_pdf"
                    )
                )
                chunks.append(chunk)

                print(f"[PDFChunkingEngine] 페이지 {page_num} 완료")

            except Exception as e:
                print(f"[ERROR] 페이지 {page_num} Vision 분석 실패: {e}")
                # 실패해도 계속 진행

        print(f"[PDFChunkingEngine] 완료: {len(chunks)}개 청크 생성")
        return chunks

    def _analyze_page_with_vision(self, image_base64: str, page_num: int,
                                  llm_api_type: str, llm_api_key: str,
                                  llm_model: str) -> str:
        """Vision API로 PDF 페이지 분석"""

        prompt = f"""이 PDF 페이지(Page {page_num})의 내용을 자세히 분석하세요.

다음 정보를 추출하세요:

1. **주제**: 이 페이지의 주요 주제
2. **텍스트 내용**: 중요한 텍스트 (제목, 본문, 키워드)
3. **표**: 표가 있다면 제목, 행/열 구조, 주요 데이터
4. **차트/그래프**: 있다면 유형, 트렌드, 핵심 인사이트
5. **이미지**: 있다면 설명
6. **기타**: 주석, 강조 표시 등

구조화된 형식으로 답변하세요:
---
주제: ...
텍스트 내용: ...
표: ...
차트: ...
이미지: ...
"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {llm_api_key}"
        }

        payload = {
            "model": llm_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                                "detail": "high"  # PDF는 고해상도 필요
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 800,  # PDF는 내용이 많을 수 있음
            "temperature": 0
        }

        api_url = "https://api.openai.com/v1/chat/completions"
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"]
```

**리스크**:
- pdf2image 변환 실패 (완화: try-except, 에러 로깅)
- Vision API 타임아웃 (완화: timeout=60초)
- 메모리 부족 (완화: 페이지별 처리, 이미지 즉시 삭제)

#### Step 2.3: GUI PDF 업로드 지원 (2시간)

**변경 위치**: `ui/document_widget.py`

```python
# Line ~401: on_add() 함수에 PDF 파일 타입 추가

def on_add(self) -> None:
    """파일 추가 버튼 클릭"""
    # ... 기존 비밀번호 체크 로직 ...

    # 파일 다이얼로그 - PDF 추가
    file_paths, _ = QFileDialog.getOpenFileNames(
        self,
        "문서 선택",
        "",
        "Documents (*.txt *.md *.pdf *.pptx *.docx);;All Files (*)"  # PDF 추가
    )

    if not file_paths:
        return

    self._start_upload(file_paths)

# Line ~250: _start_upload() 함수에 PDF 처리 로직 추가

def _start_upload(self, file_paths: List[str]) -> None:
    """파일 업로드 시작"""
    # ... 기존 로직 ...

    for file_path in file_paths:
        file_ext = Path(file_path).suffix.lower()

        if file_ext == ".pdf":
            # PDF 처리
            from utils.pdf_chunking_engine import PDFChunkingEngine

            engine = PDFChunkingEngine(self.config)
            chunks = engine.process_pdf_document(
                pdf_path=file_path,
                enable_vision=self.config.get("enable_vision_chunking", True),
                llm_api_type=self.config.get("llm_api_type"),
                llm_model=self.config.get("llm_model"),
                llm_api_key=self.config.get("llm_api_key")
            )

            # 벡터 DB에 추가
            self.vector_manager.add_chunks(chunks, target_db=target_db)

        elif file_ext == ".pptx":
            # 기존 PPT 처리 로직
            ...

        # ... 기타 파일 타입 ...
```

**리스크**:
- GUI 스레드 블로킹 (완화: Phase 4에서 백그라운드 스레드 추가)

#### Step 2.4: VectorStoreManager PDF 지원 (1시간)

**변경 위치**: `vector_store/vector_store_manager.py`

```python
# ChunkMetadata에 이미 page_number, page_title 있음 → 변경 불필요

# 검색 결과 표시 시 PDF 페이지 구분만 추가
def search(self, query: str, top_k: int = 5) -> List[dict]:
    """검색 (PDF 지원)"""
    # ... 기존 로직 ...

    for result in results:
        # PDF인 경우 페이지 표시
        if result["metadata"].chunk_method == "vision_pdf":
            result["display"] = f"[PDF] {result['metadata'].source_file} - Page {result['metadata'].page_number}"
        elif result["metadata"].chunk_method == "vision_pptx":
            result["display"] = f"[PPT] {result['metadata'].source_file} - Slide {result['metadata'].slide_number}"
        # ...

    return results
```

#### Step 2.5: 설정 파일 추가 (10분)

**변경 위치**: `config.py`

```python
# PDF 관련 설정 추가
DEFAULT_CONFIG = {
    # ... 기존 설정 ...
    "pdf_dpi": 150,  # PDF → 이미지 변환 해상도
    "pdf_vision_detail": "high",  # Vision API detail 레벨
}
```

#### Step 2.6: 테스트 작성 및 실행 (2시간)

**신규 파일**: `test_pdf_vision.py`

```python
"""
PDF Vision 테스트
"""
from pathlib import Path
from utils.pdf_chunking_engine import PDFChunkingEngine
from config import ConfigManager

def test_pdf_vision():
    """PDF Vision 청킹 테스트"""

    # 테스트 PDF 파일
    test_file = Path("data/test_pdf/sample.pdf")

    if not test_file.exists():
        print("테스트 PDF 파일 없음 - 생성하세요")
        return

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    engine = PDFChunkingEngine(config)

    print(f"테스트: {test_file.name}")

    # Vision 청킹
    chunks = engine.process_pdf_document(
        pdf_path=str(test_file),
        enable_vision=True,
        llm_api_type=config.get("llm_api_type"),
        llm_model=config.get("llm_model"),
        llm_api_key=config.get("llm_api_key")
    )

    print(f"총 {len(chunks)}개 청크 생성")

    # 샘플 출력
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"\n페이지 {chunk.metadata.page_number}:")
        print(f"  {chunk.content[:200]}...")

if __name__ == "__main__":
    test_pdf_vision()
```

**테스트 데이터**:
- `data/test_pdf/sample.pdf` 생성 (표, 차트, 이미지 포함)
- 최소 3페이지, 다양한 레이아웃

---

### 🚨 Phase 2 리스크 및 완화

| 리스크 | 확률 | 영향 | 완화 방안 |
|--------|------|------|-----------|
| Poppler 설치 실패 | 높음 | 높음 | 상세 문서화, 설치 스크립트 제공 |
| pdf2image 변환 실패 | 중간 | 높음 | 에러 핸들링, 사용자에게 명확한 메시지 |
| Vision API 비용 폭증 | 높음 | 높음 | Phase 3에서 Hybrid로 70% 절감 예정 |
| GUI 스레드 블로킹 | 중간 | 중간 | Phase 4에서 백그라운드 처리 추가 |
| 기존 PPT 기능 충돌 | 낮음 | 높음 | 별도 엔진 클래스, 회귀 테스트 |
| 메모리 부족 (대용량 PDF) | 중간 | 중간 | 페이지별 처리, 이미지 즉시 해제 |

---

### ✅ Phase 2 완료 조건

- [ ] Poppler 설치 완료 및 문서화
- [ ] PDFChunkingEngine 구현 및 단위 테스트
- [ ] GUI PDF 업로드 기능 추가
- [ ] VectorStoreManager PDF 검색 결과 표시
- [ ] PDF Vision 테스트 통과 (85%+ 정확도)
- [ ] 기존 PPT Vision 회귀 테스트 통과
- [ ] 사용자 매뉴얼 업데이트

---

## Phase 3: PDF Vision Hybrid 최적화

### 📌 목표
텍스트만 있는 PDF 페이지는 Vision 스킵하여 비용 70% 절감, RAG 성능은 유지

### 🎯 성공 기준
- Vision 사용 페이지 30% 이하로 감소
- Vision 비용 70% 절감
- RAG 검색 정확도 유지 (85%+)
- Smart Decision 정확도 90%+

### 📂 변경 파일
- `utils/pdf_chunking_engine.py` (수정)
- `requirements.txt` (수정)
- `test_pdf_hybrid.py` (신규)

### 🔧 구현 단계

#### Step 3.1: 의존성 추가 (10분)

**변경 위치**: `requirements.txt`

```txt
# Phase 2 의존성...
pdfplumber==0.10.3  # 텍스트 및 테이블 추출
```

```bash
venv/Scripts/pip install pdfplumber
```

#### Step 3.2: Smart Vision Decision 로직 (3시간)

**변경 위치**: `utils/pdf_chunking_engine.py`

```python
import pdfplumber

class PDFChunkingEngine:
    # ... 기존 코드 ...

    def _should_use_vision(self, pdf_path: str, page_num: int) -> dict:
        """
        Smart Vision Decision: 이 페이지에 Vision이 필요한가?

        Returns:
            {
                "use_vision": bool,
                "reason": str,
                "has_table": bool,
                "has_image": bool,
                "text_only": bool
            }
        """
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_num - 1]  # 0-indexed

            # 1. 이미지 확인
            images = page.images
            has_image = len(images) > 0

            # 2. 테이블 확인
            tables = page.extract_tables()
            has_table = len(tables) > 0

            # 3. 텍스트 확인
            text = page.extract_text()
            has_text = bool(text and text.strip())

            # 4. 차트/그래프 추정 (완벽하지 않음 - 이미지로 추정)
            # pdfplumber는 차트를 이미지로 감지
            # 실제 차트 여부는 Vision으로만 확실히 알 수 있음
            # → 보수적으로 이미지 있으면 차트 가능성으로 간주

            # 5. Decision
            if has_image:
                # 이미지 있음 → 차트/다이어그램 가능성 → Vision 필요
                return {
                    "use_vision": True,
                    "reason": "이미지 포함 (차트/다이어그램 가능성)",
                    "has_table": has_table,
                    "has_image": has_image,
                    "text_only": False
                }
            elif has_table:
                # 테이블 있음 → Vision으로 구조 파악 (PPT와 동일)
                return {
                    "use_vision": True,
                    "reason": "테이블 포함",
                    "has_table": has_table,
                    "has_image": has_image,
                    "text_only": False
                }
            elif has_text:
                # 텍스트만 → Vision 불필요
                return {
                    "use_vision": False,
                    "reason": "텍스트 전용 페이지",
                    "has_table": has_table,
                    "has_image": has_image,
                    "text_only": True
                }
            else:
                # 빈 페이지?
                return {
                    "use_vision": False,
                    "reason": "빈 페이지",
                    "has_table": False,
                    "has_image": False,
                    "text_only": False
                }

    def _extract_text_from_page(self, pdf_path: str, page_num: int) -> str:
        """pdfplumber로 텍스트 추출"""
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_num - 1]
            text = page.extract_text()

            # 테이블 텍스트 추가
            tables = page.extract_tables()
            if tables:
                text += "\n\n[표]\n"
                for table in tables:
                    for row in table:
                        text += " | ".join([str(cell) if cell else "" for cell in row])
                        text += "\n"

            return text

    def process_pdf_document(self,
                            pdf_path: str,
                            enable_vision: bool = True,
                            enable_hybrid: bool = True,  # 신규 파라미터
                            llm_api_type: str = "openai",
                            llm_base_url: str = "",
                            llm_model: str = "gpt-4o-mini",
                            llm_api_key: str = "") -> List[Chunk]:
        """
        PDF 문서 청킹

        Phase 3: Hybrid - Smart Vision Decision
        """
        print(f"[PDFChunkingEngine] PDF 처리 시작: {pdf_path}")
        print(f"[PDFChunkingEngine] Hybrid 모드: {enable_hybrid}")

        reader = PdfReader(pdf_path)
        page_count = len(reader.pages)
        print(f"[PDFChunkingEngine] 총 {page_count}페이지")

        # Vision 사용 통계
        vision_used_count = 0
        text_only_count = 0

        chunks = []
        for page_num in range(1, page_count + 1):
            print(f"[PDFChunkingEngine] 페이지 {page_num}/{page_count} 처리 중...")

            # Smart Decision
            if enable_hybrid:
                decision = self._should_use_vision(pdf_path, page_num)
                use_vision_for_page = decision["use_vision"]
                print(f"  → Vision 사용: {use_vision_for_page} (이유: {decision['reason']})")
            else:
                # Phase 2 동작: 모든 페이지 Vision
                use_vision_for_page = enable_vision
                decision = {"reason": "Hybrid 비활성화"}

            # 페이지 처리
            try:
                if use_vision_for_page:
                    # Vision 경로
                    vision_used_count += 1

                    # PDF → 이미지
                    images = convert_from_path(pdf_path, dpi=150, first_page=page_num, last_page=page_num)
                    image = images[0]

                    buffered = BytesIO()
                    image.save(buffered, format="PNG")
                    image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

                    # Vision 분석
                    description = self._analyze_page_with_vision(
                        image_base64=image_base64,
                        page_num=page_num,
                        llm_api_type=llm_api_type,
                        llm_api_key=llm_api_key,
                        llm_model=llm_model
                    )
                    chunk_method = "vision_pdf_hybrid"
                else:
                    # 텍스트 경로
                    text_only_count += 1
                    description = self._extract_text_from_page(pdf_path, page_num)
                    chunk_method = "text_pdf"

                # Chunk 생성
                chunk = Chunk(
                    chunk_id=f"pdf_page_{page_num}",
                    content=description,
                    chunk_type="pdf_page",
                    metadata=ChunkMetadata(
                        source_file=os.path.basename(pdf_path),
                        page_number=page_num,
                        page_title=f"Page {page_num}",
                        total_pages=page_count,
                        chunk_method=chunk_method
                    )
                )
                chunks.append(chunk)

            except Exception as e:
                print(f"[ERROR] 페이지 {page_num} 처리 실패: {e}")

        # 통계
        print()
        print(f"[PDFChunkingEngine] 완료: {len(chunks)}개 청크 생성")
        print(f"  Vision 사용: {vision_used_count}개 ({vision_used_count/page_count*100:.1f}%)")
        print(f"  텍스트 전용: {text_only_count}개 ({text_only_count/page_count*100:.1f}%)")

        if enable_hybrid:
            cost_saving = (1 - vision_used_count / page_count) * 100
            print(f"  예상 비용 절감: {cost_saving:.1f}%")

        return chunks
```

#### Step 3.3: Config에 Hybrid 설정 추가 (5분)

**변경 위치**: `config.py`

```python
DEFAULT_CONFIG = {
    # ... 기존 설정 ...
    "pdf_enable_hybrid": True,  # Hybrid 모드 활성화
}
```

#### Step 3.4: 테스트 작성 및 실행 (2시간)

**신규 파일**: `test_pdf_hybrid.py`

```python
"""
PDF Hybrid 모드 테스트
"""
from pathlib import Path
from utils.pdf_chunking_engine import PDFChunkingEngine
from config import ConfigManager

def test_pdf_hybrid():
    """PDF Hybrid 모드 테스트"""

    test_file = Path("data/test_pdf/mixed_content.pdf")

    if not test_file.exists():
        print("테스트 PDF 없음 - 생성하세요")
        print("권장 구조:")
        print("  Page 1: 텍스트만")
        print("  Page 2: 표 포함")
        print("  Page 3: 차트 포함")
        print("  Page 4: 이미지 포함")
        print("  Page 5: 텍스트만")
        return

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    engine = PDFChunkingEngine(config)

    print("=" * 80)
    print("Phase 3 Hybrid 테스트")
    print("=" * 80)
    print()

    # Hybrid 모드
    print("[ Hybrid 모드 ]")
    chunks_hybrid = engine.process_pdf_document(
        pdf_path=str(test_file),
        enable_vision=True,
        enable_hybrid=True,
        llm_api_type=config.get("llm_api_type"),
        llm_model=config.get("llm_model"),
        llm_api_key=config.get("llm_api_key")
    )

    print()
    print("=" * 80)

    # 비교: 전체 Vision (Phase 2)
    print()
    print("[ 전체 Vision 모드 (비교) ]")
    chunks_full = engine.process_pdf_document(
        pdf_path=str(test_file),
        enable_vision=True,
        enable_hybrid=False,
        llm_api_type=config.get("llm_api_type"),
        llm_model=config.get("llm_model"),
        llm_api_key=config.get("llm_api_key")
    )

    print()
    print("=" * 80)
    print("비교 결과")
    print("=" * 80)

    hybrid_vision = sum(1 for c in chunks_hybrid if c.metadata.chunk_method == "vision_pdf_hybrid")
    hybrid_text = sum(1 for c in chunks_hybrid if c.metadata.chunk_method == "text_pdf")
    full_vision = sum(1 for c in chunks_full if c.metadata.chunk_method == "vision_pdf")

    print(f"Hybrid: Vision {hybrid_vision}개, 텍스트 {hybrid_text}개")
    print(f"전체 Vision: {full_vision}개")
    print(f"비용 절감: {(1 - hybrid_vision/full_vision)*100:.1f}%")

if __name__ == "__main__":
    test_pdf_hybrid()
```

**테스트 데이터**:
- `data/test_pdf/mixed_content.pdf` 생성
- 페이지 1, 5: 텍스트만
- 페이지 2: 표
- 페이지 3: 차트
- 페이지 4: 이미지

**기대 결과**:
- Vision 사용: 3/5 페이지 (60%)
- 텍스트 전용: 2/5 페이지 (40%)
- 비용 절감: 40%

#### Step 3.5: GUI Hybrid 설정 추가 (1시간)

**변경 위치**: `ui/document_widget.py`

```python
# PDF Hybrid 모드 설정 체크박스 추가 (Settings 탭)

# Line ~250: _start_upload() 함수에 Hybrid 파라미터 전달
chunks = engine.process_pdf_document(
    pdf_path=file_path,
    enable_vision=self.config.get("enable_vision_chunking", True),
    enable_hybrid=self.config.get("pdf_enable_hybrid", True),  # 추가
    llm_api_type=self.config.get("llm_api_type"),
    llm_model=self.config.get("llm_model"),
    llm_api_key=self.config.get("llm_api_key")
)
```

---

### 🚨 Phase 3 리스크 및 완화

| 리스크 | 확률 | 영향 | 완화 방안 |
|--------|------|------|-----------|
| pdfplumber 테이블 감지 부정확 | 중간 | 중간 | 보수적 결정 (의심스러우면 Vision 사용) |
| 차트를 텍스트로 오판 | 중간 | 높음 | 이미지 있으면 무조건 Vision 사용 |
| 텍스트 추출 품질 저하 | 낮음 | 중간 | pdfplumber 검증, 실패 시 Vision fallback |
| 비용 절감 목표 미달 | 낮음 | 낮음 | 실제 문서 테스트로 검증 |

---

### ✅ Phase 3 완료 조건

- [ ] Smart Vision Decision 로직 구현
- [ ] pdfplumber 통합 및 텍스트 추출
- [ ] Hybrid 모드 테스트 통과 (비용 50%+ 절감)
- [ ] RAG 검색 정확도 유지 확인 (85%+)
- [ ] GUI Hybrid 설정 추가
- [ ] 기존 PPT/PDF 기능 회귀 테스트

---

## Phase 4: 프로덕션 배포 및 모니터링

### 📌 목표
모든 기능을 안정적으로 배포하고 사용자 피드백 수집, 성능 모니터링

### 🎯 성공 기준
- 1주일 동안 크래시 없이 안정 운영
- 사용자 만족도 4/5 이상
- Vision API 비용 예산 내 유지
- RAG 검색 정확도 90%+ 달성

### 🔧 구현 단계

#### Step 4.1: 성능 모니터링 추가 (2시간)

**신규 파일**: `utils/monitoring.py`

```python
"""
성능 모니터링 - Vision API 사용량, 비용, 처리 시간
"""
import json
from datetime import datetime
from pathlib import Path

class PerformanceMonitor:
    """성능 모니터링"""

    def __init__(self, log_file: str = "data/performance_log.json"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)

    def log_vision_call(self, file_type: str, page_or_slide: int,
                       detail_level: str, tokens_used: int, cost: float):
        """Vision API 호출 로그"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "file_type": file_type,  # "ppt" or "pdf"
            "page_or_slide": page_or_slide,
            "detail_level": detail_level,  # "low" or "high"
            "tokens_used": tokens_used,
            "cost_usd": cost
        }

        # Append to JSON file
        logs = []
        if self.log_file.exists():
            with open(self.log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)

        logs.append(log_entry)

        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

    def get_stats(self) -> dict:
        """통계 조회"""
        if not self.log_file.exists():
            return {}

        with open(self.log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)

        total_calls = len(logs)
        total_cost = sum(log["cost_usd"] for log in logs)

        ppt_calls = sum(1 for log in logs if log["file_type"] == "ppt")
        pdf_calls = sum(1 for log in logs if log["file_type"] == "pdf")

        return {
            "total_calls": total_calls,
            "total_cost_usd": total_cost,
            "ppt_calls": ppt_calls,
            "pdf_calls": pdf_calls,
            "avg_cost_per_call": total_cost / total_calls if total_calls > 0 else 0
        }
```

**통합**:
- `utils/pptx_chunking_engine.py`와 `utils/pdf_chunking_engine.py`에 모니터링 추가

#### Step 4.2: 백그라운드 처리 (3시간)

**변경 위치**: `ui/document_widget.py`

```python
from PySide6.QtCore import QThread, Signal

class UploadWorker(QThread):
    """파일 업로드 백그라운드 워커"""

    progress = Signal(int, str)  # (진행률, 메시지)
    finished = Signal(bool, str)  # (성공 여부, 메시지)

    def __init__(self, file_paths, config, target_db):
        super().__init__()
        self.file_paths = file_paths
        self.config = config
        self.target_db = target_db

    def run(self):
        """백그라운드 실행"""
        try:
            for i, file_path in enumerate(self.file_paths):
                progress_pct = int((i / len(self.file_paths)) * 100)
                self.progress.emit(progress_pct, f"처리 중: {Path(file_path).name}")

                # 파일 처리 (기존 로직)
                # ...

            self.finished.emit(True, "업로드 완료")
        except Exception as e:
            self.finished.emit(False, f"오류: {e}")

# DocumentWidget에 워커 통합
def _start_upload(self, file_paths):
    """업로드 시작 - 백그라운드"""
    self.upload_worker = UploadWorker(file_paths, self.config, target_db)
    self.upload_worker.progress.connect(self._on_upload_progress)
    self.upload_worker.finished.connect(self._on_upload_finished)
    self.upload_worker.start()

def _on_upload_progress(self, pct, msg):
    """진행률 업데이트"""
    # Progress bar 업데이트
    self.progress_bar.setValue(pct)
    self.status_label.setText(msg)

def _on_upload_finished(self, success, msg):
    """업로드 완료"""
    if success:
        QMessageBox.information(self, "성공", msg)
    else:
        QMessageBox.critical(self, "실패", msg)
```

#### Step 4.3: 사용자 매뉴얼 작성 (2시간)

**신규 파일**: `docs/USER_MANUAL.md`

- PPT 차트 지원 사용법
- PDF 업로드 방법
- Hybrid 모드 설정
- 트러블슈팅

#### Step 4.4: 1주일 모니터링 및 피드백 수집 (1주)

**모니터링 항목**:
- Vision API 호출 수 및 비용
- 파일 업로드 성공/실패율
- RAG 검색 정확도
- 사용자 피드백

**조정 사항**:
- Smart Decision 임계값 조정
- Vision API detail 레벨 최적화
- 에러 핸들링 강화

---

### ✅ Phase 4 완료 조건

- [ ] 성능 모니터링 구현 및 대시보드
- [ ] 백그라운드 처리 구현 (GUI 블로킹 해결)
- [ ] 사용자 매뉴얼 작성
- [ ] 1주일 안정 운영 (크래시 없음)
- [ ] Vision API 비용 예산 내 유지
- [ ] 사용자 피드백 수집 및 개선

---

## 리스크 관리 매트릭스

### 전체 리스크 요약

| 리스크 | Phase | 확률 | 영향 | 우선순위 | 완화 방안 |
|--------|-------|------|------|----------|-----------|
| **Poppler 설치 실패** | 2 | 높음 | 높음 | 🔴 높음 | 상세 문서, 설치 스크립트, 대체 방법 제공 |
| **Vision API 비용 폭증** | 2 | 높음 | 높음 | 🔴 높음 | Phase 3 Hybrid로 70% 절감, 모니터링 |
| **기존 기능 회귀** | 1,2,3 | 낮음 | 높음 | 🟡 중간 | 모든 Phase에서 회귀 테스트 필수 |
| **차트를 텍스트로 오판** | 3 | 중간 | 높음 | 🟡 중간 | 이미지 있으면 무조건 Vision 사용 |
| **GUI 스레드 블로킹** | 2 | 중간 | 중간 | 🟡 중간 | Phase 4 백그라운드 처리 |
| **pdfplumber 감지 부정확** | 3 | 중간 | 중간 | 🟡 중간 | 보수적 결정, 의심 시 Vision |
| **메모리 부족** | 2 | 중간 | 중간 | 🟡 중간 | 페이지별 처리, 즉시 해제 |
| **차트 분석 부정확** | 1 | 중간 | 중간 | 🟢 낮음 | detail:"high", 구조화된 프롬프트 |

### 롤백 계획

각 Phase마다 독립적인 기능 플래그로 롤백 가능:

```python
# config.py
DEFAULT_CONFIG = {
    "enable_vision_chunking": True,  # 전체 Vision ON/OFF
    "enable_ppt_chart_vision": True,  # Phase 1
    "enable_pdf_vision": True,        # Phase 2
    "pdf_enable_hybrid": True,        # Phase 3
}
```

**롤백 시나리오**:
- Phase 1 문제 발생 → `enable_ppt_chart_vision: False` → 기존 표 Vision만 사용
- Phase 2 문제 발생 → `enable_pdf_vision: False` → PDF 업로드 비활성화
- Phase 3 문제 발생 → `pdf_enable_hybrid: False` → 전체 Vision으로 복귀

---

## 성공 지표

### RAG 성능 지표

| 지표 | 현재 (Phase 1-B) | Phase 1 목표 | Phase 2 목표 | Phase 3 목표 | Phase 4 목표 |
|------|-----------------|-------------|-------------|-------------|-------------|
| **PPT 정보 커버리지** | 80% | 90% | 90% | 90% | 92% |
| **PDF 정보 커버리지** | 0% | 0% | 85% | 85% | 90% |
| **종합 커버리지** | 60% | 70% | 85% | 85% | 92% |
| **검색 정확도** | 85% | 88% | 90% | 90% | 92% |
| **Vision 사용률 (PPT)** | 75-100% | 80-100% | 80-100% | 80-100% | 80-100% |
| **Vision 사용률 (PDF)** | N/A | N/A | 100% | 30% | 30% |

### 비용 지표

| 항목 | Phase 2 | Phase 3 | Phase 4 | 절감율 |
|------|---------|---------|---------|--------|
| PPT 비용/파일 | $0.003 | $0.003 | $0.003 | - |
| PDF 비용/파일 (10페이지) | $0.003 | $0.001 | $0.001 | **70%** |
| 월 예상 비용 (100 PPT, 100 PDF) | $0.60 | $0.40 | $0.40 | **33%** |

### 성능 지표

| 지표 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|---------|---------|---------|---------|
| PPT 처리 시간/파일 | 30초 | 30초 | 30초 | 30초 |
| PDF 처리 시간/파일 (10페이지) | N/A | 60초 | 40초 | 40초 |
| GUI 응답성 | 정상 | 블로킹 | 블로킹 | 정상 (백그라운드) |
| 크래시율 | 0% | <1% | <1% | 0% |

---

## 타임라인 요약

```
Week 1: Phase 1 (PPT 차트 지원)
├─ Day 1-2: 차트 감지, Vision 분석, 통합
└─ Day 3: 테스트 및 회귀 테스트

Week 2: Phase 2 (PDF Vision 기본)
├─ Day 1: Poppler 설치, 의존성
├─ Day 2-3: PDFChunkingEngine 구현
├─ Day 4: GUI 통합
└─ Day 5: 테스트 및 검증

Week 3-4: Phase 3 (PDF Hybrid 최적화)
├─ Week 3 Day 1-2: Smart Decision 로직
├─ Week 3 Day 3-4: pdfplumber 통합
├─ Week 3 Day 5: 테스트
├─ Week 4 Day 1-2: 최적화 및 튜닝
└─ Week 4 Day 3-5: 회귀 테스트 및 문서화

Week 5: Phase 4 (배포 및 모니터링)
├─ Day 1-2: 모니터링, 백그라운드 처리
├─ Day 3: 사용자 매뉴얼
└─ Day 4-7: 모니터링, 피드백 수집, 개선
```

**총 기간**: 5주

---

## 다음 단계

### 즉시 시작 가능

1. **Phase 1 시작**: PPT 차트 지원 구현
   - `utils/pptx_chunking_engine.py`에 차트 감지 함수 추가
   - 차트 Vision 분석 프롬프트 작성
   - 테스트 PPT 파일 준비 (차트 포함)

2. **Phase 2 준비**: Poppler 설치
   - Windows Poppler 다운로드 및 설치
   - 설치 문서 작성
   - 테스트 PDF 파일 준비

### 장기 개선 방향

- **멀티모달 임베딩**: CLIP 등으로 이미지-텍스트 통합 임베딩
- **OCR 통합**: 스캔 PDF 지원
- **DOCX Vision**: Word 문서 표/차트 지원
- **차트 데이터 추출**: Vision 외에 plotly 등으로 데이터 추출
- **비용 최적화**: 캐싱, 중복 제거, 압축

---

## 결론

이 계획은 **RAG 시스템의 정보 커버리지를 60%에서 92%로 향상**시키면서 **Vision API 비용을 70% 절감**하는 것을 목표로 합니다.

**핵심 원칙**:
1. **단계적 구현**: 각 Phase를 독립적으로 구현하여 리스크 최소화
2. **회귀 방지**: 모든 Phase에서 기존 기능 테스트 필수
3. **비용 관리**: Phase 3 Hybrid로 Vision 비용 70% 절감
4. **사용자 중심**: GUI 백그라운드 처리, 명확한 피드백
5. **롤백 가능**: 기능 플래그로 각 Phase 독립적으로 ON/OFF

**예상 효과**:
- PPT 차트 정보 손실 제로
- PDF 문서 RAG 검색 가능
- Vision 비용 최적화
- 사용자 만족도 향상

**시작하세요!** Phase 1부터 단계적으로 구현하면 5주 내에 완성 가능합니다.
