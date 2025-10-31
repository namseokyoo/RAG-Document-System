"""
일반 HTTP Request 방식으로 임베딩 API 호출
LangChain의 Embeddings 인터페이스 구현으로 호환성 확보
"""
import requests
import json
from typing import List, Optional
from langchain_core.embeddings import Embeddings


class RequestEmbeddings(Embeddings):
    """
    일반 HTTP Request 방식의 임베딩 클래스
    - LangChain 래퍼보다 메모리 효율적
    - Ollama 및 OpenAI 호환 API 지원
    - 폐쇄망 환경에서 안전한 실행
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mxbai-embed-large",
        timeout: int = 60,
        **kwargs
    ):
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.extra_params = kwargs
        
        # API 타입 자동 감지
        if "ollama" in base_url or ":11434" in base_url:
            self.api_type = "ollama"
            self.endpoint = f"{self.base_url}/api/embeddings"
        else:
            # OpenAI 호환 API로 가정
            self.api_type = "openai"
            self.endpoint = f"{self.base_url}/v1/embeddings"
        
        # 초기 연결 상태 검증
        self._validate_connection()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """문서 리스트를 임베딩으로 변환"""
        embeddings = []
        
        for text in texts:
            try:
                if self.api_type == "ollama":
                    embedding = self._ollama_embed(text)
                else:
                    embedding = self._openai_embed(text)
                
                embeddings.append(embedding)
                
            except Exception as e:
                print(f"임베딩 생성 실패: {e}")
                # 실패 시 예외를 그대로 전달 (더미 임베딩 반환하지 않음)
                raise Exception(f"임베딩 생성 실패: {e}")
        
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """단일 쿼리를 임베딩으로 변환"""
        return self.embed_documents([text])[0]
    
    def _ollama_embed(self, text: str) -> List[float]:
        """Ollama API로 임베딩 생성"""
        payload = {
            "model": self.model,
            "prompt": text
        }
        
        try:
            print(f"[Embeddings] 요청 모델: {self.model}")
            print(f"[Embeddings] 엔드포인트: {self.endpoint}")
            print(f"[Embeddings] 텍스트 길이: {len(text)}자")
            
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"[Embeddings] 응답 상태: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                embedding = result.get("embedding", [])
                print(f"[Embeddings] 임베딩 성공: {len(embedding)}차원")
                return embedding
            else:
                error_msg = f"Ollama 임베딩 API 오류: {response.status_code} - {response.text}"
                print(f"[Embeddings][ERROR] {error_msg}")
                raise Exception(error_msg)
                
        except requests.exceptions.RequestException as e:
            error_msg = f"임베딩 네트워크 오류: {e}"
            print(f"[Embeddings][NETWORK] {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"임베딩 처리 오류: {e}"
            print(f"[Embeddings][WARN] {error_msg}")
            raise Exception(error_msg)
    
    def _openai_embed(self, text: str) -> List[float]:
        """OpenAI 호환 API로 임베딩 생성"""
        payload = {
            "model": self.model,
            "input": text
        }
        
        # API 키가 있는 경우 헤더에 추가
        headers = {"Content-Type": "application/json"}
        if hasattr(self, 'api_key') and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        response = requests.post(
            self.endpoint,
            json=payload,
            timeout=self.timeout,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("data", [{}])[0].get("embedding", [])
        else:
            raise Exception(f"OpenAI API 오류: {response.status_code} - {response.text}")
    
    def set_api_key(self, api_key: str):
        """API 키 설정 (OpenAI 호환 API용)"""
        self.api_key = api_key
    
    def _validate_connection(self):
        """연결 상태 및 모델 가용성 검증"""
        try:
            if self.api_type == "ollama":
                # Ollama 서비스 상태 확인
                health_url = f"{self.base_url}/api/tags"
                response = requests.get(health_url, timeout=10)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [model.get("name", "") for model in models]
                    if self.model not in model_names:
                        print(f"[Embeddings][WARN] 모델 '{self.model}'이 Ollama에 로드되지 않았습니다.")
                        print(f"[Embeddings] 사용 가능한 모델: {model_names}")
                        print(f"[Embeddings] 해결 방법: ollama pull {self.model}")
                    else:
                        print(f"[Embeddings] 모델 '{self.model}' 확인됨")
                else:
                    print(f"[Embeddings][WARN] Ollama 서비스에 연결할 수 없습니다. (상태: {response.status_code})")
            else:
                # OpenAI 호환 API 상태 확인
                health_url = f"{self.base_url}/v1/models"
                response = requests.get(health_url, timeout=10)
                if response.status_code != 200:
                    print(f"[Embeddings][WARN] OpenAI 호환 API에 연결할 수 없습니다. (상태: {response.status_code})")
        except Exception as e:
            print(f"[Embeddings][WARN] 임베딩 연결 검증 실패: {e}")
