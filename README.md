# 📚 문서 기반 RAG 시스템

범용 LLM API를 지원하는 현대적인 RAG(Retrieval-Augmented Generation) 시스템입니다.

> **LCEL 기반 체인 구조** | **스트리밍 답변** | **대화 컨텍스트 유지** | **범용 API 지원**

**버전**: v2.7 | **개발 기간**: 2025.10.14 - 2024.12.19 | **상태**: ✅ 프로덕션 준비 완료

## ⚡ 빠른 시작 (Ollama 기준)

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. Ollama 모델 다운로드
ollama pull llama3
ollama pull mxbai-embed-large

# 3. 앱 실행
streamlit run app.py

# 4. 브라우저에서 http://localhost:8501 접속
# 5. 사이드바 "📤 업로드"에서 문서 추가
# 6. 질문하고 답변 받기!
```

## 🌟 시스템 특징

- ✅ **LCEL(LangChain Expression Language)** 기반 현대적 아키텍처
- ✅ **실시간 스트리밍 답변** - ChatGPT/Gemini 스타일 UX
- ✅ **대화 이력 기반 컨텍스트** - 후속 질문 이해 가능
- ✅ **3가지 API 타입 지원** - Ollama, OpenAI, 사내 API
- ✅ **유사도 점수 표시** - 검색 결과 신뢰도 확인
- ✅ **세션 관리 시스템** - 과거 대화 저장/불러오기
- ✅ **간이 문서 작성** - 텍스트 직접 입력

## 🎨 UI 미리보기

### 사이드바 구조
```
🎛️ 제어판
├── 💬 세션 관리 [펼침]
│   ├── 현재 세션: 251018_RAG시스템개선
│   ├── 🆕 새 세션 시작
│   └── 📂 과거 세션 (최근 10개)
│
├── 📤 업로드 [접힘]
│   ├── ✍️ 간이 문서 작성
│   ├── 📂 파일 업로드 (PDF, PPT, Excel)
│   └── 📋 업로드된 파일
│
└── ⚙️ 설정 [접힘]
    ├── 🤖 LLM 설정
    ├── 🔍 임베딩 설정
    └── 📄 문서 처리 설정
```

### 채팅 화면
```
💬 대화

                    ┌─────────────────┐ ⭕
                    │ 질문 내용...     │ 👤
                    └─────────────────┘

🤖 AI 답변...
(전체 너비, 스트리밍으로 실시간 생성)
📎 출처 정보 (유사도 점수 포함) ▼
```

## ✨ 주요 기능

### 🎯 핵심 기능
- 📚 **다양한 문서 형식 지원**: PDF, PowerPoint, Excel 파일 + 텍스트 직접 입력
- 🤖 **범용 API 지원**: Ollama, OpenAI, OpenAI 호환 사내 API 모두 지원
- 💬 **대화형 RAG**: 이전 대화를 기억하는 컨텍스트 기반 답변
- ⚡ **스트리밍 답변**: ChatGPT처럼 실시간으로 답변 생성
- 📊 **유사도 점수**: 검색 결과의 신뢰도를 점수로 확인

### 🔧 편의 기능
- 🔍 **로컬 벡터 DB**: ChromaDB를 사용한 로컬 저장소
- ⚙️ **동적 설정**: UI에서 API 타입, 서버, 모델 실시간 변경
- 💾 **세션 관리**: 과거 대화 저장/불러오기/삭제
- 📎 **출처 추적**: 답변의 출처 정보 및 유사도 점수 제공
- ✍️ **간이 문서**: 파일 없이 텍스트 직접 입력으로 문서 추가

## 🛠️ 기술 스택

### 프레임워크
- **UI**: Streamlit 1.50.0+
- **RAG**: LangChain 0.3+ (LCEL 방식)
- **벡터 DB**: ChromaDB 1.1.1+ (로컬 저장)

### LLM & 임베딩
- **Ollama**: 로컬 LLM 서버 (langchain-ollama)
- **OpenAI**: 공식 OpenAI API (langchain-openai)
- **OpenAI Compatible**: vLLM, FastChat 등 호환 API

### 문서 처리
- **PDF**: pypdf 6.1.1+
- **PowerPoint**: python-pptx 1.0.2+
- **Excel**: openpyxl 3.1.5+
- **기타**: unstructured 0.18.15+

### 아키텍처
- **체인 구조**: LCEL (LangChain Expression Language)
- **스트리밍**: 실시간 답변 생성
- **컨텍스트 유지**: 대화 이력 기반 답변

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

### 3. LLM 설정 (옵션 중 하나 선택)

**옵션 A) Ollama 사용 (로컬)**
```bash
# Ollama 설치 후
ollama pull llama3              # LLM 모델
ollama pull mxbai-embed-large   # 임베딩 모델 (한국어 우수)
```

**옵션 B) OpenAI 사용**
- OpenAI API 키 준비
- UI 설정에서 API 키 입력

**옵션 C) 사내 API 사용**
- OpenAI 호환 API 주소 준비
- UI 설정에서 서버 주소 입력

## 🚀 사용 방법

### 1. 앱 실행

```bash
# Ollama 사용 시: Ollama 서버가 실행 중인지 확인
# http://localhost:11434

# Streamlit 앱 실행
streamlit run app.py
```

브라우저에서 `http://localhost:8501`로 접속합니다.

### 2. 초기 설정 (최초 1회)

사이드바 **⚙️ 설정** 섹션:

**🤖 LLM 설정**
- API 타입 선택: `ollama` / `openai` / `openai-compatible`
- 서버 주소: `http://localhost:11434` (Ollama) 또는 사내 API 주소
- 모델명: `llama3`, `gpt-4`, `gpt-3.5-turbo` 등
- API 키: OpenAI 사용 시 필수

**🔍 임베딩 설정**
- API 타입 선택
- 서버 주소
- 모델명: `mxbai-embed-large`, `text-embedding-ada-002` 등
- API 키 (선택사항)

**💾 설정 저장** 버튼 클릭

### 3. 문서 추가 (두 가지 방법)

사이드바 **📤 업로드** 섹션:

**방법 A) 간이 문서 작성**
1. 제목 입력 (예: "프로젝트 가이드")
2. 내용 입력 (메모, 지침서 등)
3. **📝 문서 추가** 클릭

**방법 B) 파일 업로드**
1. PDF, PPT, Excel 파일 선택
2. **📥 업로드 및 처리** 클릭
3. "업로드된 파일" 목록에서 확인

### 4. 대화하기

메인 화면:
1. 질문 입력창에 질문 입력
2. ⚡ 스트리밍으로 실시간 답변 생성
3. 📎 출처 정보 및 유사도 점수 확인
4. 이전 대화를 기억하는 컨텍스트 유지

### 5. 세션 관리

사이드바 **💬 세션 관리** 섹션:

**새 대화 시작**
- **🆕 새 세션 시작** 클릭

**과거 대화 불러오기**
- 과거 세션 목록에서 원하는 세션 선택
- **⋮** 메뉴 → **📂 불러오기**

**세션 삭제**
- **⋮** 메뉴 → **🗑️ 삭제**

## 📁 프로젝트 구조

```
RAG_for_OC_251014/
├── app.py                      # Streamlit 메인 앱 (LCEL 기반)
├── config.py                   # 설정 관리 (ConfigManager)
├── config.json                 # 설정 파일 (자동 생성)
├── requirements.txt            # Python 패키지 목록
├── dev_log.md                 # 개발 로그 (자동 생성, .gitignore)
│
├── utils/                      # 유틸리티 모듈
│   ├── __init__.py
│   ├── document_processor.py  # 문서 로드 및 청킹
│   ├── vector_store.py        # ChromaDB 벡터 저장소 (다중 API 지원)
│   ├── rag_chain.py          # LCEL 기반 RAG 체인 (스트리밍, 컨텍스트 유지)
│   └── chat_history.py       # 대화 이력 관리 (세션별 저장)
│
├── data/                       # 데이터 저장소
│   ├── uploaded_files/        # 업로드된 원본 파일
│   └── chroma_db/            # ChromaDB 벡터 저장소 (로컬)
│
├── chat_history/              # 대화 이력 (세션별 JSON)
│   ├── {session-id-1}.json
│   ├── {session-id-2}.json
│   └── ...
│
└── reference/                 # 참고 자료 (다운로드)
    └── metacode-langchain-RAG-202510/
```

## ⚙️ 설정 파일 (config.json)

첫 실행 시 기본 설정으로 `config.json`이 자동 생성됩니다:

```json
{
  "llm_api_type": "ollama",
  "llm_base_url": "http://localhost:11434",
  "llm_model": "llama3",
  "llm_api_key": "",
  
  "embedding_api_type": "ollama",
  "embedding_base_url": "http://localhost:11434",
  "embedding_model": "nomic-embed-text",
  "embedding_api_key": "",
  
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "top_k": 3
}
```

### API 타입별 설정 예시

**Ollama (로컬)**
```json
{
  "llm_api_type": "ollama",
  "llm_base_url": "http://localhost:11434",
  "llm_model": "llama3",
  "llm_api_key": ""
}
```

**OpenAI**
```json
{
  "llm_api_type": "openai",
  "llm_base_url": "",
  "llm_model": "gpt-4",
  "llm_api_key": "sk-..."
}
```

**사내 API (OpenAI 호환)**
```json
{
  "llm_api_type": "openai-compatible",
  "llm_base_url": "http://your-api:8000",
  "llm_model": "your-model",
  "llm_api_key": "optional"
}
```

## 💡 사용 예시

### 대화 컨텍스트 유지
```
사용자: "이 문서는 어떤 내용인가요?"
AI: "물리학의 파동 간섭 현상에 대한 내용입니다..."

사용자: "그럼 완전 상쇄 간섭은?"  ← "이 문서" 맥락 유지
AI: "앞서 말씀드린 파동 간섭에서, 완전 상쇄 간섭은..."
```

### 후속 질문 이해
```
사용자: "김첨지에 대해 알려줘"
AI: "김첨지는 현진건의 소설 '운수 좋은 날'의 주인공..."

사용자: "그는 어떤 일을 했나요?"  ← "그" = "김첨지"
AI: "김첨지는 인력거꾼으로 일했습니다..."
```

### 간이 문서 활용
```
제목: 프로젝트 규칙
내용: 
1. 코드 리뷰 필수
2. 커밋 메시지 규칙: [타입] 제목
3. 브랜치 전략: feature/기능명

질문: "커밋 메시지는 어떻게 써야 해?"
AI: "커밋 메시지는 [타입] 제목 형식으로 작성해야 합니다..."
```

## 🎯 주요 특징

### 1. LCEL 기반 체인 구조
```python
chain = (
    {"context": retriever | format_docs, "chat_history": ..., "question": ...}
    | prompt
    | llm
    | StrOutputParser()
)
```
- 현대적이고 유연한 파이프라인
- 스트리밍 지원
- 확장 가능한 구조

### 2. 대화 이력 기반 컨텍스트
- 최근 5개 대화 자동 유지
- 후속 질문 이해 (대명사, 문맥)
- 세션별 독립적 관리

### 3. 범용 API 지원
- 동적 클라이언트 생성
- API 타입별 최적화
- 하위 호환성 유지

## 📋 향후 계획

### 우선순위 높음
- [x] LCEL 방식 마이그레이션
- [x] 스트리밍 답변 지원
- [x] 대화 이력 컨텍스트
- [x] 범용 API 지원
- [x] 세션 관리 시스템
- [ ] MMR, Score Threshold 검색

### 우선순위 중간
- [ ] 문서별 네임스페이스 분리
- [ ] 메타데이터 필터링 검색
- [ ] 문서 편집 기능
- [ ] 대화 이력 내보내기

### 우선순위 낮음
- [ ] 클라우드 벡터 DB 지원
- [ ] 더 많은 문서 형식 (Markdown, DOCX)
- [ ] 다중 사용자 관리
- [ ] 웹 크롤링 통합

## 🔧 문제 해결

### LLM 연결 오류

**Ollama 사용 시:**
- Ollama 서버가 실행 중인지 확인: `ollama list`
- 서버 주소 확인: `http://localhost:11434`
- 모델이 다운로드되어 있는지 확인: `ollama pull llama3`

**OpenAI 사용 시:**
- API 키가 올바른지 확인
- 잔액이 충분한지 확인
- 네트워크 연결 확인

**사내 API 사용 시:**
- API 서버 주소가 올바른지 확인
- OpenAI 호환 형식인지 확인 (`/v1/chat/completions`)
- 네트워크 접근 권한 확인

### 문서 처리 오류
- 파일 형식 확인 (PDF, PPTX, XLSX 지원)
- `unstructured` 라이브러리 설치 확인
- 파일 크기 확인 (너무 큰 파일은 시간 소요)

### 의존성 충돌
- 가상환경 사용 권장
- `requirements.txt`의 버전 확인
- 충돌 시: `pip install --upgrade -r requirements.txt`

### 세션 로드 오류
- `chat_history/` 폴더 존재 확인
- JSON 파일 형식 오류 확인
- 권한 문제 확인

### 메모리 부족
- 청크 크기 줄이기 (1000 → 500)
- Top K 줄이기 (3 → 2)
- 파일을 나눠서 업로드

## 📖 참고 자료

- [LangChain 공식 문서](https://python.langchain.com/)
- [ChromaDB 문서](https://docs.trychroma.com/)
- [Ollama 공식 사이트](https://ollama.ai)
- [Streamlit 문서](https://docs.streamlit.io/)

## 🙏 크레딧

- 참고 프로젝트: [metacode-langchain-RAG-202510](https://github.com/namseokyoo/metacode-langchain-RAG-202510)
- LangChain 커뮤니티
- Ollama 프로젝트

## 📈 개발 히스토리

### v2.7 (2024-12-19) - 현재
- ✅ PDF 고급 청킹 시스템 구현 (Small-to-Large 아키텍처)
- ✅ PPTX 고급 청킹 시스템 구현 (paragraph.level 기반 불릿 그룹핑)
- ✅ Layout-Aware 분석 (폰트, 좌표, 계층 구조)
- ✅ 통합 테스트 완료 (PDF + PPTX: 100% 정확도)
- ✅ 가중치 시스템 및 계층적 메타데이터

### v2.6 (2024-12-19)
- ✅ 구조 인식 청킹 전략 개발문서 작성
- ✅ PDF/PPTX/XLSX/Text 4가지 타입별 최적화된 청킹 전략
- ✅ 가중치 시스템 및 메타데이터 풍부화
- ✅ PySide6 기반 데스크톱 앱 완성
- ✅ 출처 표시 점수 형식 통일 및 일관성 개선
- ✅ 하이브리드 검색 + Cross-Encoder Re-ranker 통합

### v2.5 (2025-10-18)
- ✅ 간이 문서 작성 기능
- ✅ ChatGPT 스타일 UI
- ✅ 푸터 하단 고정
- ✅ 사이드바 재구성

### v2.4 (2025-10-18)
- ✅ 세션 관리 시스템 (Popover 메뉴)
- ✅ 과거 세션 목록 및 전환
- ✅ UI 최적화 (글자 크기, 간격)

### v2.3 (2025-10-18)
- ✅ 범용 API 지원 (Ollama, OpenAI, 사내 API)
- ✅ 동적 클라이언트 생성

### v2.2 (2025-10-18)
- ✅ 대화 이력 기반 컨텍스트 유지
- ✅ 세션별 대화 관리

### v2.0 (2025-10-18)
- ✅ LCEL 방식으로 체인 재작성
- ✅ 스트리밍 답변 지원
- ✅ 유사도 점수 표시
- ✅ 프롬프트 최적화

### v1.0 (2025-10-14 - 10-15)
- ✅ 기본 RAG 시스템 구축
- ✅ 문서 처리 파이프라인
- ✅ ChromaDB 통합
- ✅ Streamlit UI

상세한 개발 로그는 `dev_log.md` 참조

## 📄 라이선스

이 프로젝트는 개인 학습 및 연구 목적으로 제작되었습니다.

## 📞 문의

프로젝트 관련 문의나 이슈는 GitHub Issues를 통해 제보해주세요.

---

**🚀 Made with LangChain + ChromaDB + Streamlit** | Powered by LCEL & Streaming

