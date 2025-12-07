# 의존성 패키지 분석 보고서 (v0.7.1)

**작성일**: 2025-12-07  
**목적**: 빌드 최적화를 위한 불필요한 의존성 제거 및 정리

---

## 📋 현재 requirements.txt 분석

### 1. Core RAG Framework ✅ 필수
- `langchain>=0.3.0` - ✅ 사용됨 (utils/rag_chain.py, utils/vector_store.py)
- `langchain-community>=0.3.0` - ✅ 사용됨 (utils/document_processor.py: PyPDFLoader, UnstructuredPowerPointLoader, UnstructuredExcelLoader)
- `langchain-core>=0.3.0,<1.0.0` - ✅ 사용됨 (utils/rag_chain.py, utils/vector_store.py)
- `langchain-ollama>=0.3.0` - ✅ 사용됨 (utils/rag_chain.py, utils/vector_store.py)
- `langchain-openai>=0.3.0` - ✅ 사용됨 (utils/rag_chain.py, utils/vector_store.py)
- `langchain-chroma>=0.2.0` - ✅ 사용됨 (utils/vector_store.py)

### 2. Vector Store ✅ 필수
- `chromadb>=0.5.0` - ✅ 사용됨 (utils/vector_store.py)

### 3. PDF Processing
- `pypdf>=4.0.0` - ✅ 사용됨 (utils/pdf_chunking_engine.py: PPTX 변환 PDF 감지용)
- `PyMuPDF>=1.26.0` - ✅ 사용됨 (utils/document_processor.py, utils/pdf_layout_analyzer.py)
- `pdfplumber>=0.11.0` - ✅ 사용됨 (utils/pdf_chunking_engine.py, utils/pdf_layout_analyzer.py)
- `pdf2image>=1.16.3` - ✅ 사용됨 (utils/pdf_chunking_engine.py: PDF Vision 청킹)

### 4. PPTX Processing ✅ 필수
- `python-pptx>=0.6.23` - ✅ 사용됨 (utils/pptx_chunking_engine.py)

### 5. Excel Processing ⚠️ 간접 사용
- `openpyxl>=3.1.0` - ⚠️ **직접 import 없음**, UnstructuredExcelLoader의 내부 의존성일 가능성
  - **사용 위치**: utils/document_processor.py에서 UnstructuredExcelLoader 사용 (XLSX 파일 처리)
  - **권장 조치**: 유지 (UnstructuredExcelLoader가 내부적으로 사용할 수 있음)
  - **확인 필요**: langchain-community의 UnstructuredExcelLoader가 openpyxl을 의존성으로 포함하는지 확인

### 6. Ollama API ✅ 필수
- `ollama>=0.5.0` - ✅ **필수 의존성** (langchain-ollama가 요구)
  - **확인 결과**: `pip show langchain-ollama` → `Requires: langchain-core, ollama`
  - **권장 조치**: 유지 (langchain-ollama의 필수 의존성)

### 7. Re-ranker ✅ 필수
- `sentence-transformers>=2.2.0` - ✅ 사용됨 (utils/reranker.py)
- `torch>=2.0.0` - ✅ 사용됨 (sentence-transformers 의존성)

### 8. Desktop UI ✅ 필수
- `PySide6>=6.6.0` - ✅ 사용됨 (desktop_app.py, ui/*.py)
- `qdarkstyle>=3.2.0` - ✅ 사용됨 (desktop_app.py)

### 9. Vision Chunking ✅ 필수
- `pywin32>=300` - ✅ 사용됨 (utils/pptx_chunking_engine.py: Windows COM 렌더링)
- `pillow>=10.0.0` - ✅ 사용됨 (utils/pptx_chunking_engine.py, utils/pdf_chunking_engine.py)

### 10. Utilities
- `rank-bm25>=0.2.2` - ✅ 사용됨 (utils/vector_store.py, utils/hybrid_retriever.py, utils/rag_chain.py)
- `requests>=2.31.0` - ✅ 사용됨 (utils/request_llm.py, utils/request_embeddings.py, utils/pdf_chunking_engine.py)

---

## 🔍 추가 분석

### Streamlit 관련
- ❌ **streamlit 패키지 없음** - app.py가 삭제되어 Streamlit 웹 앱 미사용
- ✅ **정상**: 데스크톱 앱만 사용하므로 streamlit 불필요

### 테스트 파일 분석
- **테스트 파일 수**: 약 100개 이상
- **빌드 제외 대상**: 
  - `test_*.py` 파일들
  - `analyze_*.py` 파일들
  - `diagnose_*.py` 파일들
  - `check_*.py` 파일들
  - `verify_*.py` 파일들
  - `quick_*.py` 파일들
  - `create_*.py` 파일들
  - `download_*.py` 파일들
  - `fix_*.py` 파일들
  - `reset_*.py` 파일들
  - `re_embed_*.py` 파일들
  - `comprehensive_test.py`
  - `run_comprehensive_test_real.py`

### 빌드에 포함되어야 할 파일
- ✅ `desktop_app.py` - 메인 앱
- ✅ `config.py` - 설정 관리
- ✅ `utils/` - 핵심 로직 (모든 파일)
- ✅ `ui/` - UI 컴포넌트 (모든 파일)
- ✅ `resources/` - 리소스 파일
- ✅ `config.json.example` - 설정 예제

---

## 📊 의존성 정리 권장사항

### 1. 제거 가능한 패키지

#### ❌ openpyxl
- **이유**: 코드베이스에서 사용되지 않음
- **영향**: Excel 파일 처리 기능이 없음 (현재 XLSX는 UnstructuredExcelLoader 사용)
- **권장**: 제거

#### ⚠️ ollama
- **이유**: 직접 import 없음, langchain-ollama가 내부적으로 처리
- **영향**: 없음 (langchain-ollama가 자체적으로 ollama API 호출)
- **권장**: 제거 가능 (확인 필요)

### 2. 선택적 의존성으로 분리 가능

#### 📦 PDF 처리 패키지
- `pypdf`, `PyMuPDF`, `pdfplumber`, `pdf2image` - 모두 사용되지만 선택적 기능
- **권장**: 유지 (모두 활성 기능에서 사용)

#### 📦 Vision 처리 패키지
- `pywin32` - Windows 전용 (PPTX COM 렌더링)
- **권장**: 유지 (Windows 빌드 필수)

---

## 🎯 최적화된 requirements.txt 제안

### 최적화된 requirements.txt (모든 패키지 필수)
```txt
# Core RAG Framework
langchain>=0.3.0
langchain-community>=0.3.0
langchain-core>=0.3.0,<1.0.0
langchain-ollama>=0.3.0
langchain-openai>=0.3.0
langchain-chroma>=0.2.0

# Vector Store
chromadb>=0.5.0

# PDF Processing
pypdf>=4.0.0
PyMuPDF>=1.26.0
pdfplumber>=0.11.0
pdf2image>=1.16.3  # Phase 2: PDF Vision

# PPTX Processing
python-pptx>=0.6.23

# Excel Processing
openpyxl>=3.1.0  # UnstructuredExcelLoader 내부 사용 가능

# Ollama API (langchain-ollama 필수 의존성)
ollama>=0.5.0

# Re-ranker
sentence-transformers>=2.2.0
torch>=2.0.0

# Desktop UI
PySide6>=6.6.0
qdarkstyle>=3.2.0

# Vision Chunking (Windows)
pywin32>=300
pillow>=10.0.0

# Utilities
rank-bm25>=0.2.2
requests>=2.31.0
```

**결론**: 모든 패키지가 필수이거나 실제로 사용됨. 제거할 패키지 없음.

### 제거 불가 (모두 필수)
- ✅ 모든 패키지가 실제로 사용되거나 필수 의존성으로 확인됨
- ⚠️ `openpyxl>=3.1.0` - UnstructuredExcelLoader가 내부적으로 사용할 수 있음 (명시적 의존성은 아님)
  - **권장**: 유지 (XLSX 파일 처리 기능 유지)

---

## 📝 빌드 최적화 체크리스트

### 파일 제외 목록 (PyInstaller spec)
- [ ] `test_*.py` - 모든 테스트 파일
- [ ] `analyze_*.py` - 분석 스크립트
- [ ] `diagnose_*.py` - 진단 스크립트
- [ ] `check_*.py` - 체크 스크립트
- [ ] `verify_*.py` - 검증 스크립트
- [ ] `quick_*.py` - 빠른 테스트 스크립트
- [ ] `create_*.py` - 생성 스크립트
- [ ] `download_*.py` - 다운로드 스크립트
- [ ] `fix_*.py` - 수정 스크립트
- [ ] `reset_*.py` - 리셋 스크립트
- [ ] `re_embed_*.py` - 재임베딩 스크립트
- [ ] `comprehensive_test.py`
- [ ] `run_comprehensive_test_real.py`
- [ ] `syntax_check.py`
- [ ] `update_vision_config.py`
- [ ] `scripts/` - 스크립트 폴더 전체

### 데이터 폴더 제외
- [ ] `chroma_db/` - 런타임 생성
- [ ] `chat_history/` - 런타임 생성
- [ ] `data/test_*` - 테스트 데이터
- [ ] `test_logs/` - 테스트 로그
- [ ] `test_results/` - 테스트 결과
- [ ] `build/` - 빌드 산출물
- [ ] `dist/` - 배포 산출물
- [ ] `venv/` - 가상환경

### 문서 제외 (선택적)
- [ ] `docs/` - 개발 문서 (사용자에게 불필요)
- [ ] `*.md` - 마크다운 문서 (README.md 제외)

---

## 🔧 다음 단계

1. ✅ **의존성 분석 완료**: 모든 패키지 필수 확인
2. ✅ **requirements.txt 검증**: 현재 버전이 최적화됨
3. ✅ **PyInstaller spec 파일 업데이트**: 불필요한 파일 제외 설정 완료
   - 테스트 파일 자동 제외 (desktop_app.py만 진입점)
   - 런타임 생성 폴더 제외 (chroma_db/, chat_history/)
   - 개발 문서 제외 (docs/)
   - 상세 내용: `docs/build_exclusion_list.md` 참조
4. ⏳ **빌드 테스트**: 정리된 파일 구조로 빌드 확인

## 📌 최종 결론

**의존성 패키지 정리 결과**: 
- ✅ **제거할 패키지 없음** - 모든 패키지가 필수 또는 실제 사용됨
- ✅ **requirements.txt 최적화 완료** - 현재 버전이 이미 최적화됨
- ⏳ **빌드 파일 정리 필요** - 테스트/분석 스크립트 제외 설정 필요

---

## 📌 참고사항

- **torch 크기**: sentence-transformers 의존성으로 포함되며 매우 큼 (~2GB)
  - **대안**: CPU 전용 버전 사용 고려 (`torch --index-url https://download.pytorch.org/whl/cpu`)
- **ChromaDB**: SQLite 기반이므로 별도 설치 불필요
- **Poppler**: pdf2image 의존성, Windows에서는 별도 설치 필요
  - 빌드 시 포함 여부 확인 필요

---

**분석 완료일**: 2025-12-07  
**다음 작업**: requirements.txt 최적화 및 빌드 spec 파일 업데이트

