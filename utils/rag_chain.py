from typing import List, Dict, Any, Optional, Iterator
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser


class RAGChain:
    def __init__(self, vectorstore, 
                 llm_api_type: str = "ollama",
                 llm_base_url: str = "http://localhost:11434", 
                 llm_model: str = "llama3",
                 llm_api_key: str = "",
                 top_k: int = 3):
        self.llm_api_type = llm_api_type
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.top_k = top_k
        self.vectorstore = vectorstore
        
        # LLM 초기화 - API 타입에 따라 다른 클라이언트 사용
        self.llm = self._create_llm()
        
        # Retriever 설정 - vectorstore는 이미 Chroma 인스턴스
        self.retriever = vectorstore.as_retriever(
            search_kwargs={"k": top_k}
        )
        
        # 프롬프트 템플릿 - 대화 이력 포함 버전
        self.prompt_template = """당신은 친절하고 전문적인 AI 어시스턴트입니다. 제공된 문서 내용과 이전 대화 내용을 기반으로 사용자의 질문에 정확하고 상세하게 답변해주세요.

이전 대화 내용:
{chat_history}

참고 문서:
{context}

현재 질문: {question}

답변 지침:
1. 이전 대화 내용을 참고하여 문맥에 맞는 답변을 제공하세요.
2. 문서에서 찾은 정보를 바탕으로 명확하고 자세하게 설명하세요.
3. 가능한 경우 문서의 어느 부분에서 정보를 얻었는지 자연스럽게 언급하세요.
4. 문서에 관련 정보가 있다면 추론하여 도움이 되는 답변을 제공하세요.
5. 문서에 전혀 관련 없는 내용만 있을 경우에만 "죄송합니다. 제공된 문서에서 관련 정보를 찾을 수 없습니다"라고 답변하세요.
6. 친근하면서도 전문적인 톤으로 답변하세요.

답변:"""

        self.prompt = PromptTemplate(
            template=self.prompt_template,
            input_variables=["chat_history", "context", "question"]
        )
        
        # LCEL 방식으로 체인 구성 (대화 이력 포함)
        self.chain = (
            {
                "context": lambda x: self._get_context(x["question"]),
                "chat_history": lambda x: x.get("chat_history", "이전 대화 없음"),
                "question": lambda x: x["question"]
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
    
    def _create_llm(self):
        """API 타입에 따라 적절한 LLM 클라이언트 생성"""
        if self.llm_api_type == "ollama":
            # Ollama 로컬 서버
            return OllamaLLM(
                base_url=self.llm_base_url,
                model=self.llm_model,
                temperature=0.7
            )
        elif self.llm_api_type in ["openai", "openai-compatible"]:
            # OpenAI 또는 OpenAI 호환 API
            kwargs = {
                "model": self.llm_model,
                "temperature": 0.7
            }
            
            # OpenAI 공식 API가 아닌 경우 base_url 설정
            if self.llm_api_type == "openai-compatible":
                kwargs["base_url"] = self.llm_base_url
            
            # API 키가 있는 경우만 설정
            if self.llm_api_key:
                kwargs["api_key"] = self.llm_api_key
            else:
                # API 키가 없으면 환경변수나 기본값 사용
                kwargs["api_key"] = "not-needed"  # 일부 로컬 API는 키 불필요
            
            return ChatOpenAI(**kwargs)
        else:
            raise ValueError(f"지원하지 않는 API 타입: {self.llm_api_type}")
    
    def _format_docs(self, docs: List[Document]) -> str:
        """문서 리스트를 포맷팅하여 문자열로 변환"""
        return "\n\n".join([
            f"문서 {i+1} (출처: {doc.metadata.get('file_name', 'Unknown')}, "
            f"페이지: {doc.metadata.get('page_number', 'Unknown')}):\n{doc.page_content}"
            for i, doc in enumerate(docs)
        ])
    
    def _get_context(self, question: str) -> str:
        """질문에 대한 컨텍스트 문서를 검색하여 포맷팅"""
        docs = self.retriever.invoke(question)
        return self._format_docs(docs)
    
    def _format_chat_history(self, messages: List[Dict[str, str]], max_messages: int = 5) -> str:
        """대화 이력을 포맷팅 (최근 N개만 유지)"""
        if not messages:
            return "이전 대화 없음"
        
        # 최근 max_messages개만 사용
        recent_messages = messages[-max_messages * 2:] if len(messages) > max_messages * 2 else messages
        
        formatted = []
        for msg in recent_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                formatted.append(f"사용자: {content}")
            elif role == "assistant":
                formatted.append(f"어시스턴트: {content}")
        
        return "\n".join(formatted) if formatted else "이전 대화 없음"
    
    def query(self, question: str, chat_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """질문에 대한 답변 생성 (유사도 점수 포함, 대화 이력 고려)"""
        try:
            # 대화 이력 포맷팅
            formatted_history = self._format_chat_history(chat_history or [])
            
            # LCEL 체인으로 답변 생성
            answer = self.chain.invoke({
                "question": question,
                "chat_history": formatted_history
            })
            
            # 유사도 점수와 함께 출처 문서 검색
            docs_with_scores = self.vectorstore.similarity_search_with_score(
                question, k=self.top_k
            )
            
            # 출처 정보 추출 (유사도 점수 포함)
            sources = []
            for doc, score in docs_with_scores:
                source_info = {
                    "file_name": doc.metadata.get("file_name", "Unknown"),
                    "page_number": doc.metadata.get("page_number", "Unknown"),
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "similarity_score": float(score)  # 유사도 점수 추가
                }
                sources.append(source_info)
            
            return {
                "answer": answer,
                "sources": sources,
                "success": True
            }
        except Exception as e:
            return {
                "answer": f"오류가 발생했습니다: {str(e)}",
                "sources": [],
                "success": False
            }
    
    def query_stream(self, question: str, chat_history: List[Dict[str, str]] = None) -> Iterator[str]:
        """스트리밍 방식으로 답변 생성 (대화 이력 고려)"""
        try:
            # 대화 이력 포맷팅
            formatted_history = self._format_chat_history(chat_history or [])
            
            # 스트리밍 답변 생성
            for chunk in self.chain.stream({
                "question": question,
                "chat_history": formatted_history
            }):
                yield chunk
        except Exception as e:
            yield f"오류가 발생했습니다: {str(e)}"
    
    def get_source_documents(self, question: str) -> List[Dict[str, Any]]:
        """질문에 대한 출처 문서만 반환 (유사도 점수 포함)"""
        try:
            docs_with_scores = self.vectorstore.similarity_search_with_score(
                question, k=self.top_k
            )
            
            sources = []
            for doc, score in docs_with_scores:
                source_info = {
                    "file_name": doc.metadata.get("file_name", "Unknown"),
                    "page_number": doc.metadata.get("page_number", "Unknown"),
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "similarity_score": float(score)
                }
                sources.append(source_info)
            
            return sources
        except Exception as e:
            print(f"출처 문서 검색 실패: {e}")
            return []
    
    def clear_memory(self):
        """대화 메모리 초기화 (호환성 유지)"""
        # LCEL 방식에서는 메모리가 없지만 호환성을 위해 메서드 유지
        pass
    
    def update_llm(self, llm_api_type: str, llm_base_url: str, llm_model: str, llm_api_key: str = ""):
        """LLM 설정 업데이트"""
        self.llm_api_type = llm_api_type
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        
        # LLM 재생성
        self.llm = self._create_llm()
        
        # LCEL 체인 재구성 (대화 이력 포함)
        self.chain = (
            {
                "context": lambda x: self._get_context(x["question"]),
                "chat_history": lambda x: x.get("chat_history", "이전 대화 없음"),
                "question": lambda x: x["question"]
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
    
    def update_retriever(self, vectorstore, top_k: int = 3):
        """Retriever 업데이트"""
        self.vectorstore = vectorstore
        self.top_k = top_k
        self.retriever = vectorstore.as_retriever(
            search_kwargs={"k": top_k}
        )
        
        # LCEL 체인 재구성 (대화 이력 포함)
        self.chain = (
            {
                "context": lambda x: self._get_context(x["question"]),
                "chat_history": lambda x: x.get("chat_history", "이전 대화 없음"),
                "question": lambda x: x["question"]
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )

