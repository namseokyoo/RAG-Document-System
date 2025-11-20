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

    # Phase 2: PDF Vision 설정
    "pdf_dpi": 150,  # PDF → 이미지 변환 해상도 (150 권장)
    "pdf_vision_detail": "high",  # Vision API detail 레벨 (high/low)
    "poppler_path": _get_poppler_path(),  # Poppler 경로 (자동 감지: libs/poppler 또는 PATH)

    # Phase 3: PDF Hybrid 모드 설정
    "enable_pdf_hybrid": True,  # Hybrid 모드 사용 여부 (True: Smart Decision, False: 모든 페이지 Vision)

    # 공유 DB 설정
    "shared_db_enabled": False,  # 공유 DB 사용 여부
    "shared_db_path": "",  # 공유 DB 경로 (자동 탐색됨)
    "shared_db_drive_letter": "",  # 공유 DB 드라이브 문자 (예: "U")
    "default_search_mode": "integrated",  # integrated | personal | shared

    # UI 설정
    "theme": "dark",  # dark | light (사용자 마지막 선택 테마)
}


class ConfigManager:
    def __init__(self):
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """설정 파일 로드 또는 기본값 반환"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
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

