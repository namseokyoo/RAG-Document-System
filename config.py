import json
import os
import sys
from typing import Dict, Any
from pathlib import Path

CONFIG_FILE = "config.json"

# Poppler 경로 자동 감지 (번들링 지원)
def _get_poppler_path():
    """번들된 Poppler 경로 자동 감지"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 실행 파일
        base_dir = Path(sys._MEIPASS)
    else:
        # 개발 환경
        base_dir = Path(__file__).parent

    # libs/poppler/Library/bin 경로 확인
    poppler_path = base_dir / "libs" / "poppler" / "Library" / "bin"
    if poppler_path.exists():
        return str(poppler_path)

    # 환경 변수 PATH 사용 (Poppler가 시스템에 설치된 경우)
    return None

DEFAULT_CONFIG = {
    # LLM 설정
    "llm_api_type": "request",  # ollama, openai, openai-compatible, request
    "llm_base_url": "http://localhost:11434",
    "llm_model": "gemma3:latest",
    "llm_api_key": "",  # OpenAI API 키 (ollama/request는 불필요)
    "temperature": 0.3,  # 0.0 - 2.0 (창의성 vs 일관성) - 기본값 통일

    # 임베딩 설정
    "embedding_api_type": "ollama",  # ollama, request, openai, openai-compatible
    "embedding_base_url": "http://localhost:11434",
    "embedding_model": "mxbai-embed-large",
    "embedding_api_key": "",  # OpenAI API 키 (ollama/request는 불필요)

    # 문서 처리 설정
    "chunk_size": 1500,    # 권장 설정 (표/수식 완전 포함)
    "chunk_overlap": 200,  # chunk_size의 13%
    "top_k": 5,
    "multi_query_num": 3,

    # ChromaDB 설정
    "chroma_distance_function": "cosine",  # l2, cosine, ip (정규화된 임베딩은 cosine 권장)

    # Re-ranker 설정 (기본 활성화)
    "use_reranker": True,  # Re-ranker 사용 여부 (고정)
    "reranker_model": "multilingual-mini",  # multilingual-mini로 통일 (base 모델 미사용)
    "reranker_top_k": 3,  # 최종 반환 문서 수 (deprecated, score filtering으로 대체)
    "reranker_initial_k": 30,  # Re-ranking할 초기 후보 수 (테스트 검증된 최적값)

    # Score-based Filtering 설정 (OpenAI 스타일)
    "enable_score_filtering": True,  # Score 기반 필터링 사용 여부
    "reranker_score_threshold": 0.5,  # 최소 reranker 점수 (0.0~1.0)
    "max_num_results": 20,  # 최대 문서 수 (OpenAI 기본값)
    "min_num_results": 3,  # 최소 문서 수 (안전망)
    "enable_adaptive_threshold": True,  # 동적 threshold 계산 사용 여부
    "adaptive_threshold_percentile": 0.6,  # top1 대비 비율 (60%)

    # Exhaustive Retrieval 설정 (대량 문서 처리)
    "enable_exhaustive_retrieval": True,  # "모든/전체" 키워드 감지
    "exhaustive_max_results": 100,  # Exhaustive mode 최대 문서 수
    "enable_single_file_optimization": True,  # 단일 파일 전체 조회 최적화

    # Diversity Penalty 설정 (다문서 합성 개선)
    "diversity_penalty": 0.3,  # 동일 출처 문서 패널티 (0.0~1.0, 테스트 검증된 최적값)
    "diversity_source_key": "source",  # 출처 식별 메타데이터 키

    # File Aggregation 설정 (Phase 3: Exhaustive Query 파일 리스트 반환)
    "enable_file_aggregation": False,  # 파일 단위 집계 기능 (기본 비활성화, 안정성 우선)
    "file_aggregation_strategy": "weighted",  # max | mean | weighted | count (weighted 권장)
    "file_aggregation_top_n": 20,  # 반환할 최대 파일 수
    "file_aggregation_min_chunks": 1,  # 파일 포함 최소 매칭 청크 수

    # Query Expansion 설정
    "enable_synonym_expansion": False,  # 동의어 확장 사용 여부 (테스트 결과 비활성화 권장)
    "enable_multi_query": True,  # 다중 쿼리 재작성 사용 여부
    
    # HyDE (Hypothetical Document Embeddings) 설정
    "enable_hyde": True,  # HyDE 사용 여부 (복잡 질문 처리 정확도 향상)
    
    # Query Decomposition 설정
    "enable_query_decomposition": True,  # 질문 분해 사용 여부 (다단계 질문 처리 정확도 향상)

    # Small-to-Large 설정
    "small_to_large_context_size": 800,  # Partial context 추출 크기 (자식 청크 전후)

    # Question Classifier 설정 (Phase 2: Quick Wins)
    "enable_question_classifier": True,  # 질문 분류기 사용 여부
    "classifier_use_llm": True,  # LLM 하이브리드 모드 (False: 규칙만)
    "classifier_verbose": False,  # 상세 로그 출력 (디버그용)

    # 로컬 모델 설정
    "use_local_models": True,  # 로컬 모델 캐시 사용 여부
    "offline_mode": True,  # 오프라인 모드 활성화

    # 비전 임베딩 설정 (자동 활성화 - 품질 최우선)
    "enable_vision_chunking": True,  # PPTX/PDF Vision 청킹 (기본 활성화)
    "vision_enabled": True,  # 비전 임베딩 기능 사용 여부
    "vision_mode": "auto",  # auto | ollama | openai-compatible

    # BM25 최적화 설정 (AB 테스트 결과: 개선 효과 없음, 제거됨)
    # "enable_bm25_optimization": False,  # 제거됨
    # "bm25_enable_case_normalization": False,  # 제거됨
    # "bm25_enable_entity_variations": False,  # 제거됨

    # Phase 2: PDF Vision 설정
    "pdf_dpi": 150,  # PDF → 이미지 변환 해상도 (150 권장)
    "pdf_vision_detail": "high",  # Vision API detail 레벨 (high/low)
    "poppler_path": _get_poppler_path(),  # Poppler 경로 (자동 감지: libs/poppler 또는 PATH)

    # Vision API 설정 (LLM과 동일한 엔드포인트 사용)
    "vision_api_type": "request",  # request | openai | ollama | openai-compatible (생산: request 사용)
    "vision_base_url": "http://localhost:11434",  # Vision API Base URL (LLM과 동일)
    "vision_model": "gemma3:latest",  # Vision 모델 (생산: Llama-4-scout, 개발: gpt-4o-mini)
    "vision_api_key": "",  # Vision API 키 (비어있으면 llm_api_key 사용)

    # Phase 3: PDF Hybrid 모드 설정
    "enable_pdf_hybrid": True,  # Hybrid 모드 사용 여부 (True: Smart Decision, False: 모든 페이지 Vision)

    # 공유 DB 설정
    "shared_db_enabled": False,  # 공유 DB 사용 여부
    "shared_db_path": "",  # 공유 DB 경로 (자동 탐색됨)
    "shared_db_drive_letter": "",  # 공유 DB 드라이브 문자 (예: "U")
    "default_search_mode": "integrated",  # integrated | personal | shared

    # UI 설정
    "theme": "dark",  # dark | light (사용자 마지막 선택 테마)

    # LLM 타임아웃 설정 (질문 스트리밍 상위 안전망)
    # - max_llm_stream_seconds: 한 질문에 대한 LLM 스트리밍 최대 시간 (초)
    "max_llm_stream_seconds": 90.0,

    # 업로드 타임아웃 설정
    # - max_upload_file_seconds: 파일 하나를 처리하는 최대 시간 (초)
    "max_upload_file_seconds": 300.0,
    
    # 페이지 단위 비정상 감지 설정
    # - max_page_processing_seconds: 페이지당 최대 허용 처리 시간 (초, 절대값)
    # - abnormal_time_multiplier: 평균 처리 시간의 몇 배까지 허용 (상대값)
    "max_page_processing_seconds": 120.0,
    "abnormal_time_multiplier": 3.0,

    # PPTX → PDF 자동 변환 설정
    "auto_convert_pptx_to_pdf": True,  # PPTX 자동 변환 활성화 여부 (기본값: True)
    "pptx_conversion_tool": "com",  # 변환 도구 (Windows COM 사용)

    # 참고문서 표시 임계값 설정 (Phase 1: 동적 임계값)
    "source_threshold_exhaustive": 0.2,  # 전체 조회 질문 임계값 (20%)
    "source_threshold_complex": 0.3,  # 복잡한 질문 임계값 (30%)
    "source_threshold_normal": 0.25,  # 일반 질문 임계값 (25%)
    "source_threshold_simple": 0.3,  # 간단한 질문 임계값 (30%)
    "source_min_documents": 1,  # 최소 표시 문서 수 (안전망)
}


class ConfigManager:
    def __init__(self):
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """설정 파일 로드 또는 기본값 반환"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Poppler 경로는 항상 재계산 (배포 시 경로가 달라지므로)
                    config['poppler_path'] = _get_poppler_path()
                    return config
            except Exception as e:
                print(f"설정 파일 로드 실패: {e}")
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """설정을 파일에 저장"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.config = config
            return True
        except Exception as e:
            print(f"설정 파일 저장 실패: {e}")
            return False
    
    def get(self, key: str, default=None):
        """설정 값 가져오기"""
        return self.config.get(key, default)
    
    def update(self, key: str, value: Any):
        """설정 값 업데이트"""
        self.config[key] = value
    
    def get_all(self) -> Dict[str, Any]:
        """모든 설정 반환"""
        return self.config.copy()

