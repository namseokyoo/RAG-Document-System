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
    "temperature": 0.7,  # 0.0 - 2.0 (창의성 vs 일관성)
    
    # 임베딩 설정
    "embedding_api_type": "ollama",  # ollama, openai, openai-compatible
    "embedding_base_url": "http://localhost:11434",
    "embedding_model": "nomic-embed-text",
    "embedding_api_key": "",  # OpenAI API 키 (ollama는 불필요)
    
    # 문서 처리 설정
    "chunk_size": 500,    # 정확도 최우선 설정
    "chunk_overlap": 100,  # chunk_size의 20%
    "top_k": 3,
    
    # Re-ranker 설정 (기본 활성화)
    "use_reranker": True,  # Re-ranker 사용 여부 (고정)
    "reranker_model": "multilingual-mini",  # multilingual-mini, multilingual-base, korean
    "reranker_top_k": 3,  # 최종 반환 문서 수
    "reranker_initial_k": 20,  # Re-ranking할 초기 후보 수
    
    # Query Expansion 설정
    "enable_synonym_expansion": True,  # 동의어 확장 사용 여부
    "enable_multi_query": True,  # 다중 쿼리 재작성 사용 여부
    
    # 로컬 모델 설정
    "use_local_models": True,  # 로컬 모델 캐시 사용 여부
    "offline_mode": True,  # 오프라인 모드 활성화
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

