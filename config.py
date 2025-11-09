import json
import os
from typing import Dict, Any

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    # LLM 설정
    "llm_api_type": "request",  # ollama, openai, openai-compatible, request
    "llm_base_url": "http://localhost:11434",
    "llm_model": "gemma3:4b",
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
    "top_k": 3,
    "multi_query_num": 3,

    # Re-ranker 설정 (기본 활성화)
    "use_reranker": True,  # Re-ranker 사용 여부 (고정)
    "reranker_model": "multilingual-mini",  # multilingual-mini로 통일 (base 모델 미사용)
    "reranker_top_k": 3,  # 최종 반환 문서 수 (deprecated, score filtering으로 대체)
    "reranker_initial_k": 60,  # Re-ranking할 초기 후보 수 (리콜 향상)

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

    # Query Expansion 설정
    "enable_synonym_expansion": True,  # 동의어 확장 사용 여부
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

    # 비전 임베딩 설정
    "enable_vision_chunking": False,  # PPTX Vision 청킹 사용 여부
    "vision_enabled": True,  # 비전 임베딩 기능 사용 여부
    "vision_mode": "auto",  # auto | ollama | openai-compatible

    # 공유 DB 설정
    "shared_db_enabled": False,  # 공유 DB 사용 여부
    "shared_db_path": "",  # 공유 DB 경로 (자동 탐색됨)
    "shared_db_drive_letter": "",  # 공유 DB 드라이브 문자 (예: "U")
    "default_search_mode": "integrated",  # integrated | personal | shared
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

