# -*- mode: python ; coding: utf-8 -*-

# 불필요한 모듈 제외 (용량 최적화)
excluded_modules = [
    # Streamlit 관련 (데스크톱 앱에서 불필요)
    'streamlit',
    'streamlit_webrtc',
    'streamlit_option_menu',
    'altair',  # Streamlit 차트 라이브러리
    'pydeck',  # Streamlit 맵 라이브러리
    
    # 개발/테스트 도구
    'pytest',
    'IPython',
    'jupyter',
    'notebook',
    
    # 미사용 라이브러리
    'unstructured',  # requirements.txt에 없음
    'unstructured-client',
    'docx',  # requirements.txt에 없음
    'pypdfium2',  # requirements.txt에 없음
    
    # Pandas 대체재들
    'polars',
    'modin',
    
    # 불필요한 ML/데이터 라이브러리
    'tensorflow',
    'tflite_runtime',
    'keras',
    'xgboost',
    'lightgbm',
    
    # GUI 프레임워크 (PySide6만 사용)
    'wx',
    'tkinter',  # 일부 의존성이 필요하지만 대부분 제외
    'matplotlib',  # 이미지 시각화 불필요
    
    # 웹 프레임워크
    'flask',
    'django',
    'fastapi',
    'uvicorn',
    
    # 불필요한 유틸리티
    'pandas.io.excel.xlsxwriter',
    'pandas.io.excel.xlrd',
]

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources', 'resources'),  # 아이콘 등
        ('config.json.example', '.'),  # 설정 예제
        ('models', 'models'),  # Re-ranker 모델
    ],
    hiddenimports=[
        'win32timezone',
        'sentencepiece',
        'win32com.client',
        'PIL._tkinter_finder',  # PIL이 필요할 수 있음
        # ChromaDB 핵심 모듈
        'chromadb',  # ChromaDB 벡터 스토어
        'chromadb.config',  # ChromaDB 설정
        'chromadb.types',  # ChromaDB 타입 정의
        'chromadb.errors',  # ChromaDB 에러 정의
        'chromadb.base_types',  # ChromaDB 기본 타입
        # ChromaDB API 모듈
        'chromadb.api.rust',  # ChromaDB Rust 클라이언트
        'chromadb.api.shared_system_client',  # 공유 시스템 클라이언트
        'chromadb.api.models.Collection',  # Collection 모델
        'chromadb.api.types',  # API 타입
        # ChromaDB 인증 모듈
        'chromadb.auth',  # 인증 관련
        'chromadb.auth.utils',  # 인증 유틸리티
        # ChromaDB 데이터베이스 모듈 (PersistentClient에서 사용)
        'chromadb.db',  # 데이터베이스 인터페이스
        'chromadb.db.impl.sqlite',  # SQLite 구현
        'chromadb.db.system',  # 시스템 DB
        # ChromaDB 세그먼트 모듈
        'chromadb.segment',  # 세그먼트 인터페이스
        'chromadb.segment.impl.manager.local',  # 로컬 세그먼트 매니저
        # ChromaDB 실행 모듈
        'chromadb.execution',  # 실행 인터페이스
        'chromadb.execution.executor.local',  # 로컬 실행자
        'chromadb.execution.executor.abstract',  # 추상 실행자
        'chromadb.execution.expression.plan',  # 실행 계획
        'chromadb.execution.expression.operator',  # 실행 연산자
        # ChromaDB 텔레메트리 모듈
        'chromadb.telemetry',  # ChromaDB 텔레메트리
        'chromadb.telemetry.product',  # ChromaDB 텔레메트리 제품
        'chromadb.telemetry.product.posthog',  # ChromaDB 텔레메트리 PostHog
        'chromadb.telemetry.product.events',  # ChromaDB 텔레메트리 이벤트
        'chromadb.telemetry.opentelemetry',  # ChromaDB OpenTelemetry 통합
        # ChromaDB 기타 모듈 (선택적이지만 안전을 위해)
        'chromadb.quota.simple_quota_enforcer',  # 할당량 강제
        'chromadb.rate_limit.simple_rate_limit',  # 속도 제한
        'chromadb.utils',  # 유틸리티
        'chromadb.utils.embedding_functions',  # 임베딩 함수
        # ChromaDB Rust 바인딩
        'chromadb_rust_bindings',  # ChromaDB Rust 바인딩
        # LangChain 통합
        'langchain_chroma',  # LangChain Chroma 통합
        # LangChain Core 모듈
        'langchain_core',  # LangChain Core
        'langchain_core.runnables',  # Runnable 인터페이스
        'langchain_core.runnables.config',  # Runnable 설정
        'langchain_core.output_parsers',  # 출력 파서
        'langchain_core.output_parsers.str',  # 문자열 파서
        'langchain_core.embeddings',  # 임베딩 인터페이스
        'langchain_core.callbacks',  # 콜백
        'langchain_core.language_models',  # 언어 모델
        'langchain_core.outputs',  # 출력 타입
        # LangChain Community 모듈
        'langchain_community',  # LangChain Community
        'langchain_community.document_loaders',  # 문서 로더
        'langchain_community.document_loaders.pdf',  # PDF 로더 (PyPDFLoader)
        'langchain_community.document_loaders.powerpoint',  # PowerPoint 로더 (UnstructuredPowerPointLoader)
        'langchain_community.document_loaders.excel',  # Excel 로더 (UnstructuredExcelLoader)
        'langchain_community.document_loaders.unstructured',  # Unstructured 로더
        # LangChain 기타
        'langchain.schema',  # Schema 정의
        'langchain.prompts',  # 프롬프트 템플릿
        'langchain.text_splitter',  # 텍스트 분할
        # Sentence Transformers 모듈
        'sentence_transformers',  # Sentence Transformers
        'sentence_transformers.cross_encoder',  # CrossEncoder
        'sentence_transformers.cross_encoder.CrossEncoder',  # CrossEncoder 클래스
        'sentence_transformers.cross_encoder.fit_mixin',  # FitMixin
        'sentence_transformers.cross_encoder.util',  # CrossEncoder 유틸리티
        'sentence_transformers.cross_encoder.model_card',  # 모델 카드
        'sentence_transformers.backend',  # 백엔드 모듈
        'sentence_transformers.models',  # 모델 정의
        'sentence_transformers.util',  # 유틸리티
        # Transformers 모듈 (CrossEncoder 의존성)
        'transformers',  # Transformers
        'transformers.modeling_utils',  # 모델 유틸리티
        'transformers.configuration_utils',  # 설정 유틸리티
        'transformers.tokenization_utils',  # 토크나이저 유틸리티
        'transformers.utils',  # Transformers 유틸리티
        # HuggingFace Hub 모듈
        'huggingface_hub',  # HuggingFace Hub
        'huggingface_hub.utils',  # Hub 유틸리티
        # PyMuPDF (fitz) 모듈
        'fitz',  # PyMuPDF 메인 모듈
        # python-pptx 모듈
        'pptx',  # python-pptx 메인 모듈
        'pptx.enum.shapes',  # Shape 열거형
        # openpyxl 모듈 (Excel 처리)
        'openpyxl',  # openpyxl 메인 모듈
        'openpyxl.cell',  # Cell 모듈
        'openpyxl.workbook',  # Workbook 모듈
        # rank-bm25 모듈 (선택적)
        'rank_bm25',  # BM25 구현
        # 기타 유틸리티
        'requests',  # HTTP 요청
        'requests.auth',  # 인증
        'requests.adapters',  # 어댑터
        'urllib3',  # URL 처리
        'urllib3.util',  # URL 유틸리티
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules + ['magic', 'python-magic', 'python-magic-bin'],  # magic 라이브러리 제외 (Windows DLL 문제)
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RAG_Document_System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # UPX 압축 사용
    console=True,  # 터미널 표시
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='oc.ico',  # 아이콘 파일
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RAG_Document_System',
)
