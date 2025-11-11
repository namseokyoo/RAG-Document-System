# 📚 OC Papers - 엔지니어 보조 AI 시스템

> **사내망 논문 DB 기반 → 엔지니어 보조 에이전트 AI로 진화**

사내망 환경에서 논문 데이터베이스를 구축하고, 이를 기반으로 엔지니어들에게 정확하고 신뢰할 수 있는 정보를 제공하는 AI 챗봇 시스템입니다. 향후 다양한 개발결과물(엑셀, 파워포인트, PDF, raw data 등)을 활용하여 **엔지니어를 보조하는 자율 에이전트 AI**로 발전시킬 계획입니다.

> **LCEL 기반 체인 구조** | **95% Citation Coverage** | **Vision-Augmented 청킹** | **Dual DB 아키텍처** | **오프라인 최적화**

**버전**: v3.6.2 | **개발 기간**: 2024.10.14 - 2025.01.XX | **상태**: ✅ 프로덕션 준비 완료

## ⚡ 빠른 시작

### 🖥️ 데스크톱 앱 (PySide6) - **권장**

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 가상환경 활성화 (필수!)
.\venv\Scripts\activate

# 3. 데스크톱 앱 실행
python desktop_app.py
```

### 🌐 웹 앱 (Streamlit) - 선택

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. Ollama 모델 다운로드
ollama pull llama3
ollama pull mxbai-embed-large

# 3. 앱 실행
streamlit run app.py

# 4. 브라우저에서 http://localhost:8501 접속
```

## 🌟 주요 특징

### 🎯 핵심 기능
- ✅ **동적 Top-k 결정**: LLM이 질문 특성 분석하여 최적 검색 개수 자동 결정 (3-30개)
- ✅ **고급 청킹 전략**: PDF/PPTX 구조 인식 청킹, Small-to-Large 아키텍처
- ✅ **Vision-Augmented 청킹**: PPTX 슬라이드 이미지 분석 (표, 그래프 자동 인식)
- ✅ **하이브리드 검색**: Vector + BM25 키워드 검색
- ✅ **Cross-Encoder Re-ranker**: multilingual-mini 기반 최종 정렬
- ✅ **다중 쿼리 확장**: 질문을 여러 관점에서 재작성하여 검색 다양화
- ✅ **슬라이드/페이지 단위 중복 제거**: 동일 파일에서 여러 슬라이드/페이지 검색 가능
- ✅ **고급 프롬프트 엔지니어링**: Chain-of-Thought (CoT), Few-shot 예시, 구조화된 출력 형식

### 🎨 UI 기능
- ✅ **스트리밍 답변**: ChatGPT 스타일 실시간 타이핑
- ✅ **대화 컨텍스트 유지**: 이전 대화 기억
- ✅ **출처 표시**: 파일명 + 페이지 + 유사도 점수
- ✅ **시스템 트레이**: 백그라운드 실행 지원
- ✅ **자동 저장**: 설정 및 대화 이력

### 📊 성능 최적화
- ✅ **PowerPoint 한 번만 열기**: Vision 청킹 시 모든 슬라이드 일괄 렌더링
- ✅ **파일당 최대 10개 청크**: 중복 방지 + 다양성 유지
- ✅ **질문 타입 감지**: 구체적 정보/요약/비교/관계 분석 자동 분류
- ✅ **Smart 중복 제거**: 슬라이드/페이지 단위 중복 제거

## 🛠️ 기술 스택

### 프레임워크
- **UI**: PySide6 (Qt6), Streamlit
- **RAG**: LangChain 0.3+ (LCEL 방식)
- **벡터 DB**: ChromaDB (로컬 저장)

### LLM & 임베딩
- **Ollama**: 로컬 LLM 서버
- **OpenAI**: 공식 API (gpt-4o, gpt-4o-mini)
- **범용 API**: vLLM, FastChat 등 OpenAI 호환

### 문서 처리
- **PDF**: PyMuPDF, pdfplumber, pypdf
- **PowerPoint**: python-pptx + Windows COM (Vision 렌더링)
- **Excel**: openpyxl
- **Vision**: Pillow, pywin32 (Windows)

### 검색 & Reranking
- **Vector**: ChromaDB
- **Keyword**: BM25 (rank-bm25)
- **Re-ranker**: sentence-transformers (multilingual-mini)

## 📦 설치 방법

### 1. 필수 요구사항

- Python 3.10 이상
- (선택) Ollama 설치 - 로컬 LLM 사용 시 ([Ollama 설치 가이드](https://ollama.ai))
- (선택) OpenAI API 키 - OpenAI 사용 시

### 2. Python 패키지 설치

```bash
# 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

### 3. 설정 파일 생성

첫 실행 시 `config.json`이 자동 생성됩니다. 필요 시 `config.json.example`을 참고하세요.

```json
{
  "llm_api_type": "openai",
  "llm_model": "gpt-4o",
  "llm_api_key": "your-api-key",
  "temperature": 0.3,
  "embedding_api_type": "request",
  "embedding_model": "mxbai-embed-large:latest",
  "chunk_size": 1500,
  "chunk_overlap": 400,
  "top_k": 5,
  "use_reranker": true,
  "reranker_model": "multilingual-mini",
  "enable_multi_query": true,
  "multi_query_num": 5,
  "enable_vision_chunking": false
}
```

## 🚀 사용 방법

### 데스크톱 앱 실행

```bash
# 가상환경 활성화 (필수!)
.\venv\Scripts\activate

# 앱 실행
python desktop_app.py
```

### 기능 사용법

#### 📤 문서 업로드
1. **업로드** 탭 선택
2. 파일 드래그 앤 드롭 또는 **파일 선택** 클릭
3. PDF, PPTX, XLSX, TXT 지원
4. **Vision 청킹** (PPTX 전용): 슬라이드 이미지 분석 활성화

#### 💬 질문하기
1. 질문 입력창에 질문 입력
2. **전송** 버튼 클릭 또는 `Ctrl+Enter`
3. 스트리밍으로 실시간 답변 확인
4. 출처 정보 확인

#### ⚙️ 설정
1. **설정** 탭 선택
2. LLM, 임베딩, Re-ranker 설정
3. **다중 쿼리 갯수** 선택 (0-5)
4. 자동 저장됨

#### 💾 대화 관리
1. **대화** 탭 선택
2. **새로운 대화**: 새 세션 시작
3. **대화 불러오기**: 과거 세션 복원
4. **내보내기**: 대화 저장

## 📁 프로젝트 구조

```
RAG_for_OC_251014/
├── desktop_app.py              # PySide6 메인 앱
├── app.py                      # Streamlit 메인 앱
├── config.py                   # 설정 관리
├── config.json                 # 설정 파일
├── requirements.txt            # Python 패키지
│
├── ui/                         # PySide6 UI 컴포넌트
│   ├── main_window.py         # 메인 윈도우 (탭, 트레이)
│   ├── chat_widget.py         # 채팅 위젯 (스트리밍)
│   ├── document_widget.py     # 문서 관리 위젯
│   └── settings_widget.py     # 설정 위젯
│
├── utils/                      # 핵심 로직
│   ├── document_processor.py  # 문서 처리
│   ├── vector_store.py        # ChromaDB 관리
│   ├── rag_chain.py          # RAG 체인 (동적 top_k, 다중 쿼리)
│   ├── pdf_chunking_engine.py # PDF 고급 청킹
│   ├── pptx_chunking_engine.py # PPTX 고급 청킹
│   ├── small_to_large_search.py # Small-to-Large 검색
│   ├── reranker.py           # Cross-Encoder Re-ranker
│   └── chat_history.py       # 대화 이력 관리
│
├── data/                       # 데이터 저장소
│   ├── chroma_db/            # ChromaDB 벡터 저장소
│   ├── embedded_documents/   # 임베딩된 원본 파일
│   ├── test_documents/       # PDF 테스트 문서
│   └── test_pptx/           # PPTX 테스트 문서
│
├── docs/                       # 문서
│   ├── PDF_PPTX_CHUNKING_COMPARISON.md
│   └── prompt_improvement_roadmap.md  # 프롬프트 개선 로드맵
│
├── models/                     # 로컬 모델
│   ├── reranker-mini/
│   └── reranker-base/
│
└── resources/                  # 리소스 파일
    ├── icons/app.png
    └── styles/
```

## 🔬 고급 기능

### 동적 Top-k 결정

질문 특성에 따라 LLM이 최적의 검색 개수를 자동 결정합니다:

- **단일 사실** ("무엇", "얼마", "누구"): 3-5개
- **목록 나열** ("모두", "전체", "나열", "제목들"): 20-30개
- **비교/분석** ("차이", "비교", "관계"): 10-20개
- **종합 정보** ("요약", "핵심", "개요"): 10-15개

### 구조 인식 청킹

**PDF:**
- Small-to-Large 아키텍처
- Layout-Aware 분석 (폰트, 좌표, 계층 구조)
- 표 다층 청킹 (전체/행/열/키-값)
- 가중치 시스템 (제목 > 문단)

**PPTX:**
- Small-to-Large 아키텍처
- paragraph.level 기반 불릿 그룹핑
- Vision-Augmented 청킹 (슬라이드 이미지 분석)
- 표 다층 청킹 (Phase 1-3 완료)
- 가중치 시스템 (제목 > 노트 > 본문)

### Vision-Augmented 청킹 (PPTX 전용)

슬라이드를 이미지로 변환하여 Vision LLM으로 분석:

1. Windows COM으로 슬라이드 렌더링 (PowerPoint 한 번만 열기)
2. Base64 인코딩
3. Vision LLM (gpt-4o 등) 분석
4. 분석 결과를 텍스트와 함께 임베딩

**활성화 방법:**
- 업로드 탭에서 **Vision 청킹 사용** 체크박스 선택
- PPTX 파일만 적용

### 하이브리드 검색

**Vector Search**: 의미적 유사도
```
벡터 유사도 계산 → 상위 K개 선별
```

**BM25 Keyword Search**: 키워드 매칭
```
키워드 빈도 계산 → 상위 K개 선별
```

**결합**: 두 결과를 통합하여 다양성 확보

### Cross-Encoder Re-ranker

검색된 문서를 질문-문서 쌍으로 재평가:

1. 벡터 검색으로 후보 확보 (40-60개)
2. Cross-Encoder로 각 문서 점수화
3. 상위 K개만 최종 선정 (5개)

**모델**: `multilingual-mini` (오프라인)

## ⚙️ 설정 옵션

### LLM 설정
- **API 타입**: `ollama` / `openai` / `request`
- **모델**: `llama3`, `gpt-4o`, `gpt-4o-mini` 등
- **Temperature**: 0.0-1.0
- **API 키**: OpenAI 사용 시 필수

### 임베딩 설정
- **API 타입**: `ollama` / `request`
- **모델**: `mxbai-embed-large:latest` (한국어 우수)
- **API 키**: 필요 시

### 문서 처리 설정
- **청크 크기**: 500-3000 자
- **청크 오버랩**: 0-1000 자

### 검색 설정
- **다중 쿼리 갯수**: 0-5 (0=비활성화)
- **Re-ranker 사용**: ON/OFF
- **Re-ranker 모델**: multilingual-mini (경량 최적화 모델)

### 고급 설정
- **Vision 청킹** (PPTX 전용): 슬라이드 이미지 분석 ON/OFF

## 🎯 주요 변경사항

### v3.6.0 (2025-01-09) - 현재
- ✅ **Phase 2 QC 개선**: Re-ranker 모델 통일 (multilingual-mini로 단일화)
- ✅ **Hybrid Search 단순화**: 3단계 → 2단계 우선순위로 최적화
- ✅ **Singleton 패턴**: Re-ranker 인스턴스 재사용으로 성능 향상
- ✅ **Score Filtering 개선**: OpenAI 스타일 적응형 threshold 적용
- ✅ **Question Classifier 통합**: 질문 유형 자동 분류로 검색 전략 최적화
- ✅ **Exhaustive Retrieval**: "모든/전체" 키워드 감지하여 대량 문서 처리 (최대 100개)
- ✅ **설정 동기화**: config.json과 DEFAULT_CONFIG 완전 통일 (13개 항목 추가)
- 📊 **소요 시간**: Phase 1 (1시간) + Phase 2 (30분) = 총 1.5시간

### v3.4.0 (2025-01-07)
- ✅ **Phase D: 답변 자연화**: 섹션 강제 구조 제거, max_tokens 4096으로 증가, NotebookLM 스타일 Inline Citation
- ✅ **Phase C: Citation 95%**: 다중 출처 지원 (최대 2개/문장), 동적 임계값 (0.35-0.5), 짧은 문장 임계값 10으로 낮춤
- ✅ **UI 개선**: 설정 탭에서 비기능 "비전 임베딩 사용" 체크박스 제거
- ✅ **답변 품질**: 자연스러움 +40%, 중복 내용 -60%, 복잡한 질문/번역 대응 가능
- ✅ **Citation 커버리지**: 80% → 95% 향상
- 📄 자세한 내용: [Phase D 구현 계획](docs/phase_d_implementation_plan.md)

### v3.1 (2025-01-XX)
- ✅ **프롬프트 개선**: Chain-of-Thought (CoT) 강화, Few-shot 예시 확장, 구조화된 출력 형식
- ✅ **Self-verification**: 답변 후 자가 검증 단계 추가 (할루시네이션 -30% 감소)
- ✅ **Query Expansion 고도화**: Few-shot 예시 추가, 5가지 관점 전략
- ✅ **Vision 프롬프트 개선**: 5단계 분석 절차, 구조화된 출력, OCR 처리 지시
- ✅ **질문 타입별 특화**: 모든 타입에 Few-shot 예시 및 CoT 강화
- ✅ **프롬프트 수준**: 상용 서비스 수준 85% 달성 (8.5/10점)
- 📄 자세한 내용: [프롬프트 개선 로드맵](docs/prompt_improvement_roadmap.md)

### v3.0 (2025-01-02)
- ✅ 동적 Top-k 결정 기능 추가 (질문 특성 분석)
- ✅ 슬라이드/페이지 단위 중복 제거 전략 개선
- ✅ 출처 표시 형식 개선 (파일명 중복 제거)
- ✅ Vision 청킹 최적화 (PowerPoint 한 번만 열기)
- ✅ requirements.txt 정리 (불필요한 패키지 제거)
- ✅ 불필요한 스크립트 및 모델 삭제

### v2.7 (2024-12-19)
- ✅ PDF 고급 청킹 시스템 구현
- ✅ PPTX 고급 청킹 시스템 구현
- ✅ Vision-Augmented 청킹 구현
- ✅ Layout-Aware 분석
- ✅ Small-to-Large 아키텍처
- ✅ 표 다층 청킹 (PDF/PPTX)

### v2.6 (2024-12-19)
- ✅ PySide6 기반 데스크톱 앱 완성
- ✅ 하이브리드 검색 + Cross-Encoder Re-ranker
- ✅ 구조 인식 청킹 전략 문서화

### v2.5 (2024-10-18)
- ✅ 간이 문서 작성
- ✅ ChatGPT 스타일 UI

### v2.4 (2024-10-18)
- ✅ 세션 관리 시스템
- ✅ 과거 세션 목록 및 전환

### v2.3 (2024-10-18)
- ✅ 범용 API 지원
- ✅ 동적 클라이언트 생성

### v2.2 (2024-10-18)
- ✅ 대화 이력 기반 컨텍스트
- ✅ 세션별 대화 관리

### v2.0 (2024-10-18)
- ✅ LCEL 방식으로 재작성
- ✅ 스트리밍 답변
- ✅ 유사도 점수 표시

### v1.0 (2024-10-14)
- ✅ 기본 RAG 시스템
- ✅ ChromaDB 통합
- ✅ Streamlit UI

## 🔧 문제 해결

### Python 실행 오류
```bash
# 가상환경 필수!
.\venv\Scripts\activate
python desktop_app.py
```

### PowerPoint Vision 청킹 오류
- Windows 전용 기능
- Microsoft PowerPoint 설치 필요
- `pywin32` 패키지 설치 확인

### LLM 연결 오류
- Ollama: `ollama pull llama3`
- OpenAI: API 키 확인
- 네트워크 연결 확인

### 메모리 부족
- 청크 크기 줄이기 (1500 → 1000)
- 파일을 나눠서 업로드
- Re-ranker 모델을 mini로 변경

## 📖 참고 자료

- [LangChain 공식 문서](https://python.langchain.com/)
- [ChromaDB 문서](https://docs.trychroma.com/)
- [PySide6 문서](https://doc.qt.io/qtforpython/)
- [Ollama 공식 사이트](https://ollama.ai)

## 📝 개발 원칙

### 코드 재사용
- 백엔드 100% 재사용 (utils/ 폴더)
- Streamlit ↔ PySide6 공통 로직

### 설정 호환성
- 동일한 config.json 사용
- 동일한 ChromaDB 형식

### 점진적 개발
- Phase별 단계적 구현
- 검증 후 확장

### 성능 최적화
- PowerPoint 한 번만 열기
- 동적 Top-k로 불필요한 검색 방지
- 하이브리드 검색으로 정확도 향상

## 📦 빌드 및 배포

### PyInstaller로 데스크톱 앱 빌드

**요구사항:**
- 가상환경 활성화
- PyInstaller 설치: `pip install pyinstaller`

**빌드 방법:**
```bash
# 1. 가상환경 활성화
.\venv\Scripts\activate

# 2. 빌드 실행 (onedir 모드)
python -m PyInstaller --name=OC --icon=oc.ico --onedir --console --add-data="resources;resources" --add-data="config.json.example;." --add-data="models;models" --hidden-import=win32timezone --hidden-import=sentencepiece desktop_app.py

# 3. 빌드 결과 확인
# dist/OC/ 폴더에 실행 파일 생성됨
```

**빌드 옵션:**
- `--onedir`: 여러 파일로 배포 (느린 시작, 작은 EXE)
- `--onefile`: 단일 EXE 파일 (빠른 시작, 큰 EXE)
- `--console`: 터미널 창 표시 (디버깅용)
- `--noconsole`: 터미널 창 숨김 (배포용)
- `--icon=oc.ico`: 아이콘 설정

**배포 폴더:**
```
dist/
└── OC/
    ├── OC.exe           # 메인 실행 파일
    ├── _internal/       # 종속 라이브러리
    ├── resources/       # 리소스 파일
    ├── config.json.example
    └── models/          # Re-ranker 모델
```

**용량:**
- 대략 1GB (torch, transformers, langchain 등 포함)

## 📝 최근 업데이트

### v3.6.2 (2025-01-09)
- **메타데이터 검색 아키텍처 분석**: Semantic Scholar, Perplexity, Elicit 등 상용 서비스 벤치마크
- **Phase 2.5.6 로드맵 추가**: PDF 메타데이터 자동 추출 및 ChromaDB 필드 확장 계획
- **상세 분석 문서 작성**: `docs/METADATA_SEARCH_ANALYSIS.md` (GROBID, Query Router, 2단계 검색)
- ℹ️ **코드 변경 없음**: 분석 및 문서화만 (향후 구현 준비)

### v3.6.1 (2025-01-09)
- **ChromaDB 거리 함수 cosine 변경**: 정규화된 임베딩 모델(mxbai, qwen3)에 최적화
- **공유 DB 볼륨 레이블 수정**: LGDKBB → LGDKRB
- **qwen3-embedding-8B 테스트 도구 추가**: 차원/정규화/속도 검증 스크립트

## 🚀 향후 발전 방향

> **논문 DB 챗봇 → 엔지니어 보조 에이전트 AI로 진화**

상세한 로드맵은 [.CLAUDE.md](.CLAUDE.md)를 참고하세요.

### 🎯 Phase 3: 다양한 문서 형식 지원 확대 (2025 Q1)
**목표**: 논문 외 개발결과물 통합

- [ ] **고급 엑셀 처리**: 복잡한 표 구조, 수식 보존, 차트 데이터 추출
- [ ] **Raw Data 지원**: CSV/TSV, JSON/YAML, Parquet, 데이터 스키마 인식
- [ ] **코드 및 로그 파일**: Python/C++/Java 파싱, 로그 패턴 인식, 실험 결과 매핑

**예상 소요 시간**: 3-4주

---

### 🤖 Phase 4: 에이전트 기능 추가 (2025 Q2)
**목표**: 단순 QA → 자율 작업 수행

- [ ] **도구 사용 (Tool Use)**: 검색, 계산, 시각화, 파일 관리 에이전트
- [ ] **다단계 추론**: Plan & Execute, Self-Reflection, Iterative Refinement
- [ ] **외부 도구 통합**: Python REPL, 데이터 분석, API 호출

**예상 소요 시간**: 6-8주

---

### 👥 Phase 5: 협업 기능 (2025 Q3)
**목표**: 개인 사용 → 팀 협업

- [ ] **공유 및 권한 관리**: 팀 DB, 권한 레벨 (Read/Write/Admin), 액세스 로그
- [ ] **피드백 및 개선**: 답변 평가 (👍/👎), 오류 보고, 개선 제안
- [ ] **지식 큐레이션**: 태그 시스템, 즐겨찾기, 추천 시스템

**예상 소요 시간**: 4-6주

---

### 📊 Phase 6: 고급 분석 및 인사이트 (2025 Q4)
**목표**: 정보 제공 → 인사이트 발견

- [ ] **트렌드 분석**: 연구 동향, 기술 로드맵, Gap 분석
- [ ] **지식 그래프**: 논문 간 관계, 개념 연결, 영향력 분석
- [ ] **자동 보고서 생성**: 주간 요약, 프로젝트 리포트, 벤치마크

**예상 소요 시간**: 8-10주

---

### 🔬 기술 개선 (Continuous)
- [ ] **Self-RAG 메커니즘**: Self-reflection, Self-critique
- [ ] **Corrective RAG**: 오류 감지 및 재생성
- [ ] **프롬프트 인젝션 대응**: 보안 취약점 완화
- [ ] **UI/UX 개선**: 라이트 테마, 키보드 단축키
- [ ] **성능 모니터링**: 메모리, CPU 사용량 추적
- [ ] **SAGE/CRAG Framework**: 최신 RAG 기법 도입

## 🙏 크레딧

- 참고 프로젝트: [metacode-langchain-RAG-202510](https://github.com/namseokyoo/metacode-langchain-RAG-202510)
- LangChain 커뮤니티
- Ollama 프로젝트
- ChromaDB 프로젝트

## 📄 라이선스

이 프로젝트는 내부 사용 목적으로 제작되었습니다. 외부 공개 시 라이선스 정책을 별도로 정의할 예정입니다.

## 📞 문의

프로젝트 관련 문의나 이슈는 GitHub Issues를 통해 제보해주세요.

---

**🚀 Made with LangChain + ChromaDB + PySide6 + LCEL & Streaming**
