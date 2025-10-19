"""
일반 HTTP Request 방식으로 LLM API 호출
LangChain의 Runnable 인터페이스 구현으로 LCEL 호환
"""
import requests
from typing import Any, Iterator, List, Optional
from langchain_core.runnables import Runnable
from langchain_core.callbacks import CallbackManagerForLLMRun


class RequestLLM(Runnable):
    """
    일반 HTTP Request 방식의 LLM 클래스
    - LangChain 래퍼보다 메모리 효율적
    - 스트리밍/버퍼링 제어 가능
    - GPU 메모리 오류 회피
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gemma:2b",
        temperature: float = 0.7,
        timeout: int = 60,
        num_ctx: int = 2048,
        num_predict: int = 512,
        **kwargs
    ):
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.extra_params = kwargs
        
        # API 타입 자동 감지
        if "ollama" in base_url or ":11434" in base_url:
            self.api_type = "ollama"
            self.endpoint = f"{self.base_url}/api/generate"
        else:
            # OpenAI 호환 API로 가정
            self.api_type = "openai"
            self.endpoint = f"{self.base_url}/v1/chat/completions"
    
    def invoke(self, input: Any, config: Optional[dict] = None) -> str:
        """
        동기 방식 호출 (LCEL 체인 호환)
        """
        # input이 문자열이면 그대로, PromptValue면 text 추출
        if hasattr(input, 'text'):
            prompt = input.text
        elif hasattr(input, 'to_string'):
            prompt = input.to_string()
        else:
            prompt = str(input)
        
        try:
            if self.api_type == "ollama":
                return self._call_ollama(prompt)
            else:
                return self._call_openai_compatible(prompt)
        except Exception as e:
            raise RuntimeError(f"LLM 호출 실패: {str(e)}")
    
    def stream(self, input: Any, config: Optional[dict] = None) -> Iterator[str]:
        """
        스트리밍 방식 호출
        """
        if hasattr(input, 'text'):
            prompt = input.text
        elif hasattr(input, 'to_string'):
            prompt = input.to_string()
        else:
            prompt = str(input)
        
        try:
            if self.api_type == "ollama":
                yield from self._stream_ollama(prompt)
            else:
                yield from self._stream_openai_compatible(prompt)
        except Exception as e:
            yield f"스트리밍 오류: {str(e)}"
    
    def _call_ollama(self, prompt: str) -> str:
        """Ollama API 동기 호출"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict
            }
        }
        
        response = requests.post(
            self.endpoint,
            json=payload,
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama API 오류 ({response.status_code}): {response.text}"
            )
        
        result = response.json()
        return result.get("response", "")
    
    def _stream_ollama(self, prompt: str) -> Iterator[str]:
        """Ollama API 스트리밍 호출"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict
            }
        }
        
        response = requests.post(
            self.endpoint,
            json=payload,
            stream=True,
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            yield f"Ollama API 오류 ({response.status_code}): {response.text}"
            return
        
        for line in response.iter_lines():
            if line:
                import json
                try:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
                except json.JSONDecodeError:
                    continue
    
    def _call_openai_compatible(self, prompt: str) -> str:
        """OpenAI 호환 API 동기 호출"""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.num_predict,
            "stream": False
        }
        
        response = requests.post(
            self.endpoint,
            json=payload,
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            raise RuntimeError(
                f"OpenAI API 오류 ({response.status_code}): {response.text}"
            )
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _stream_openai_compatible(self, prompt: str) -> Iterator[str]:
        """OpenAI 호환 API 스트리밍 호출"""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.num_predict,
            "stream": True
        }
        
        response = requests.post(
            self.endpoint,
            json=payload,
            stream=True,
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            yield f"OpenAI API 오류 ({response.status_code}): {response.text}"
            return
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    import json
                    try:
                        data = json.loads(line_str[6:])
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue

