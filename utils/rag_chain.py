from typing import List, Dict, Any, Optional, Iterator
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from utils.reranker import get_reranker
from utils.request_llm import RequestLLM
import json
import re


class RAGChain:
    def __init__(self, vectorstore, 
                 llm_api_type: str = "ollama",
                 llm_base_url: str = "http://localhost:11434", 
                 llm_model: str = "llama3",
                 llm_api_key: str = "",
                 temperature: float = 0.3,
                 top_k: int = 3,
                 use_reranker: bool = True,
                 reranker_model: str = "multilingual-mini",
                 reranker_initial_k: int = 20,
                 enable_synonym_expansion: bool = True,
                 enable_multi_query: bool = True):
        self.llm_api_type = llm_api_type
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.temperature = temperature
        self.top_k = top_k
        self.vectorstore = vectorstore
        
        # Re-ranker 설정 (기본 활성화)
        self.use_reranker = use_reranker
        self.reranker_model = reranker_model
        self.reranker_initial_k = max(reranker_initial_k, top_k * 5)
        
        # Re-ranker 초기화 (사용 시)
        if self.use_reranker:
            self.reranker = get_reranker(model_name=reranker_model)
        
        # 마지막 검색 결과 캐시 (출처 표시용)
        self._last_retrieved_docs = []
        
        # LLM 초기화 - API 타입에 따라 다른 클라이언트 사용
        self.llm = self._create_llm()
        
        # 동의어 확장 설정
        self.enable_synonym_expansion = enable_synonym_expansion
        self.enable_multi_query = enable_multi_query
        
        # Retriever 설정 - vectorstore는 이미 Chroma 인스턴스
        self.retriever = vectorstore.as_retriever(
            search_kwargs={"k": max(self.top_k * 8, 24)}
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
5. 자체적으로 추론하여 대답하는 내용은 추론한 내용이라는 것을 언급하세요.
6. 문서에 전혀 관련 없는 내용만 있을 경우에만 "죄송합니다. 제공된 문서에서 관련 정보를 찾을 수 없습니다"라고 답변하세요.
7. 친근하면서도 전문적인 톤으로 답변하세요.

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
        if self.llm_api_type == "request":
            return RequestLLM(
                base_url=self.llm_base_url,
                model=self.llm_model,
                temperature=self.temperature,
                timeout=60
            )
        elif self.llm_api_type == "ollama":
            return OllamaLLM(
                base_url=self.llm_base_url,
                model=self.llm_model,
                temperature=self.temperature
            )
        elif self.llm_api_type == "openai":
            kwargs = {
                "model": self.llm_model,
                "temperature": self.temperature,
                "api_key": self.llm_api_key if self.llm_api_key else "not-needed"
            }
            return ChatOpenAI(**kwargs)
        elif self.llm_api_type == "openai-compatible":
            kwargs = {
                "model": self.llm_model,
                "temperature": self.temperature,
                "base_url": self.llm_base_url,
                "api_key": self.llm_api_key if self.llm_api_key else "not-needed"
            }
            return ChatOpenAI(**kwargs)
        else:
            raise ValueError(f"지원하지 않는 API 타입: {self.llm_api_type}")

    def _format_docs(self, docs: List[Document]) -> str:
        return "\n\n".join([
            f"문서 {i+1} (출처: {doc.metadata.get('file_name', 'Unknown')}, "
            f"페이지: {doc.metadata.get('page_number', 'Unknown')}):\n{doc.page_content}"
            for i, doc in enumerate(docs)
        ])

    def _unique_by_file(self, pairs: List[tuple], k: int) -> List[tuple]:
        """(Document, score) 리스트에서 파일명 기준으로 중복을 제거하며 최대 k개 반환"""
        seen = set()
        results: List[tuple] = []
        for doc, score in pairs:
            file_name = doc.metadata.get("file_name", "")
            if file_name in seen:
                continue
            seen.add(file_name)
            results.append((doc, score))
            if len(results) >= k:
                break
        return results

    def _search_candidates(self, question: str) -> List[tuple]:
        """하이브리드(키워드+벡터) → Re-ranker 입력 후보 확보"""
        try:
            # 하이브리드로 넉넉히 후보 확보
            hybrid = self.vectorstore.similarity_search_hybrid(
                question, initial_k=max(self.top_k * 8, 40), top_k=max(self.top_k * 8, 40)
            )
            return hybrid
        except Exception:
            # 폴백: 벡터 검색
            return self.vectorstore.similarity_search_with_score(question, k=max(self.top_k * 8, 40))

    def _get_context(self, question: str) -> str:
        # Multi-Query Rewriting 적용
        if self.enable_multi_query:
            queries = self.generate_rewritten_queries(question, num_queries=3)
            all_retrieved_chunks = []
            chunk_id_set = set()
            
            # 모든 쿼리에 대해 검색 수행
            for query in queries:
                try:
                    if self.use_reranker:
                        base = self._search_candidates(query)
                        if base:
                            docs_for_rerank = [{
                                "page_content": d.page_content,
                                "metadata": d.metadata,
                                "vector_score": s,
                                "document": d
                            } for d, s in base]
                            reranked = self.reranker.rerank(query, docs_for_rerank, top_k=max(self.top_k * 3, 15))
                            results = [(d["document"], d.get("rerank_score", 0)) for d in reranked]
                        else:
                            results = []
                    else:
                        results = self.vectorstore.similarity_search_with_score(query, k=max(self.top_k * 3, 15))
                    
                    # 중복 제거 (문서 내용 기준)
                    for doc, score in results:
                        doc_id = f"{doc.metadata.get('source', '')}_{doc.page_content[:50]}"
                        if doc_id not in chunk_id_set:
                            all_retrieved_chunks.append((doc, score))
                            chunk_id_set.add(doc_id)
                            
                except Exception as e:
                    print(f"쿼리 '{query}' 검색 실패: {e}")
                    continue
            
            if all_retrieved_chunks:
                # 원본 쿼리로 재순위 매김
                if self.use_reranker:
                    docs_for_final_rerank = [{
                        "page_content": d.page_content,
                        "metadata": d.metadata,
                        "vector_score": s,
                        "document": d
                    } for d, s in all_retrieved_chunks]
                    final_reranked = self.reranker.rerank(question, docs_for_final_rerank, top_k=max(self.top_k * 2, 20))
                    pairs = [(d["document"], d.get("rerank_score", 0)) for d in final_reranked]
                else:
                    pairs = all_retrieved_chunks
                
                dedup = self._unique_by_file(pairs, self.top_k)
                self._last_retrieved_docs = dedup
                docs = [d for d, _ in dedup]
                return self._format_docs(docs)
        
        # 폴백: 단일 쿼리 검색 (동의어 확장 포함)
        expanded_question = self.expand_query_with_synonyms(question)
        
        if self.use_reranker:
            base = self._search_candidates(expanded_question)
            if not base:
                self._last_retrieved_docs = []
                return ""
            # base 는 (doc, score) 형태
            docs_for_rerank = [{
                "page_content": d.page_content,
                "metadata": d.metadata,
                "vector_score": s,
                "document": d
            } for d, s in base]
            reranked = self.reranker.rerank(expanded_question, docs_for_rerank, top_k=max(self.top_k * 8, 40))
            pairs = [(d["document"], d.get("rerank_score", 0)) for d in reranked]
            dedup = self._unique_by_file(pairs, self.top_k)
            
            # 캐시 저장: 실제 사용된 문서와 점수
            self._last_retrieved_docs = dedup  # [(doc, score), ...]
            
            docs = [d for d, _ in dedup]
        else:
            pairs = self.vectorstore.similarity_search_with_score(expanded_question, k=max(self.top_k * 8, 40))
            dedup = self._unique_by_file(pairs, self.top_k)
            
            # 캐시 저장
            self._last_retrieved_docs = dedup
            
            docs = [d for d, _ in dedup]
        return self._format_docs(docs)

    def expand_query_with_synonyms(self, original_query: str) -> str:
        """LLM을 사용하여 원본 쿼리에 대한 동의어/연관어를 생성하고 확장된 쿼리를 반환"""
        if not self.enable_synonym_expansion:
            return original_query
            
        try:
            prompt = f"""
사용자의 검색 쿼리: "{original_query}"

이 쿼리와 관련된 동의어 또는 밀접하게 연관된 검색 용어 3개를 생성해 줘.
결과는 JSON 리스트 형식으로만 응답해 줘.
예시: ["용어1", "용어2", "용어3"]
"""
            
            response = self.llm.invoke(prompt)
            
            # 응답을 문자열로 변환
            if hasattr(response, 'content'):
                response_text = response.content
            elif hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)
            
            # JSON 파싱 시도
            try:
                # 응답에서 JSON 부분만 추출
                json_match = re.search(r'\[.*?\]', response_text)
                if json_match:
                    related_terms = json.loads(json_match.group())
                else:
                    # JSON 형식이 아닌 경우 텍스트에서 추출
                    lines = response_text.strip().split('\n')
                    related_terms = []
                    for line in lines:
                        line = line.strip().strip('"[]')
                        if line and len(line) > 1:
                            related_terms.append(line)
                    related_terms = related_terms[:3]  # 최대 3개
                
                # 원본 쿼리와 연관어를 결합
                if related_terms:
                    expanded_query = f"{original_query} (관련 용어: {', '.join(related_terms)})"
                    print(f"🔍 동의어 확장: {original_query} → {expanded_query}")
                    return expanded_query
                    
            except (json.JSONDecodeError, ValueError) as e:
                print(f"동의어 파싱 실패: {e}")
                
        except Exception as e:
            print(f"동의어 확장 실패: {e}")
        
        return original_query

    def generate_rewritten_queries(self, original_query: str, num_queries: int = 3) -> List[str]:
        """LLM을 사용하여 원본 쿼리를 여러 관점에서 재작성한 대안 쿼리 리스트를 생성"""
        if not self.enable_multi_query:
            return [original_query]
            
        try:
            prompt = f"""
당신은 사용자의 질문을 더 나은 검색 결과로 이끄는 전문 검색 엔지니어입니다.
다음 원본 쿼리를 {num_queries}개의 서로 다른 관점에서 재작성해 주십시오.

- 원본 쿼리는 그대로 유지하십시오.
- 쿼리들은 서로 다른 접근 방식(예: 기술적 질문, 개념적 질문, 문제 해결)을 반영해야 합니다.

원본 쿼리: "{original_query}"

결과는 JSON 리스트 형식으로만 응답해 주십시오. 
예시: ["쿼리1", "쿼리2", "쿼리3"]
"""
            
            response = self.llm.invoke(prompt)
            
            # 응답을 문자열로 변환
            if hasattr(response, 'content'):
                response_text = response.content
            elif hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)
            
            # JSON 파싱 시도
            try:
                # 응답에서 JSON 부분만 추출
                json_match = re.search(r'\[.*?\]', response_text)
                if json_match:
                    rewritten_queries = json.loads(json_match.group())
                else:
                    # JSON 형식이 아닌 경우 텍스트에서 추출
                    lines = response_text.strip().split('\n')
                    rewritten_queries = []
                    for line in lines:
                        line = line.strip().strip('"[]')
                        if line and len(line) > 1:
                            rewritten_queries.append(line)
                    rewritten_queries = rewritten_queries[:num_queries]  # 최대 num_queries개
                
                # 원본 쿼리가 포함되지 않았다면, 리스트의 맨 앞에 추가
                if original_query not in rewritten_queries:
                    rewritten_queries.insert(0, original_query)
                    
                print(f"🔄 다중 쿼리 생성: {original_query} → {len(rewritten_queries)}개 쿼리")
                return rewritten_queries
                    
            except (json.JSONDecodeError, ValueError) as e:
                print(f"다중 쿼리 파싱 실패: {e}")
                
        except Exception as e:
            print(f"다중 쿼리 생성 실패: {e}")
        
        return [original_query]

    def _format_chat_history(self, messages: List[Dict[str, str]], max_messages: int = 5) -> str:
        if not messages:
            return "이전 대화 없음"
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
        try:
            formatted_history = self._format_chat_history(chat_history or [])
            answer = self.chain.invoke({
                "question": question,
                "chat_history": formatted_history
            })
            docs_with_scores = self.vectorstore.similarity_search_with_score(
                question, k=max(self.top_k * 5, 20)
            )
            dedup = self._unique_by_file(docs_with_scores, self.top_k)
            probs = self._normalize_scores(dedup, is_reranker=False)
            sources = []
            for (doc, score), p in zip(dedup, probs):
                if p < 15.0:
                    continue
                    source_info = {
                        "file_name": doc.metadata.get("file_name", "Unknown"),
                        "page_number": doc.metadata.get("page_number", "Unknown"),
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "similarity_score": float(round(p, 1))
                    }
                    sources.append(source_info)
            return {
                "answer": answer,
                "sources": sources[: self.top_k],
                "success": True
            }
        except Exception as e:
            return {
                "answer": f"오류가 발생했습니다: {str(e)}",
                "sources": [],
                "success": False
            }
    
    def query_stream(self, question: str, chat_history: List[Dict[str, str]] = None) -> Iterator[str]:
        try:
            formatted_history = self._format_chat_history(chat_history or [])
            for chunk in self.chain.stream({
                "question": question,
                "chat_history": formatted_history
            }):
                yield chunk
        except Exception as e:
            yield f"오류가 발생했습니다: {str(e)}"
    
    def get_source_documents(self, question: str = None) -> List[Dict[str, Any]]:
        """캐시된 검색 결과를 출처로 반환 (답변 생성에 실제 사용된 문서)"""
        try:
            if not self._last_retrieved_docs:
                return []
            
            # 캐시된 문서에 점수 정규화 적용
            is_reranker = self.use_reranker
            probs = self._normalize_scores(self._last_retrieved_docs, is_reranker=is_reranker)
            
            sources = []
            for (doc, raw_score), normalized_score in zip(self._last_retrieved_docs, probs):
                # 15% 임계값 제거 - 실제 사용된 문서는 모두 표시
                sources.append({
                    "file_name": doc.metadata.get("file_name", "Unknown"),
                    "page_number": doc.metadata.get("page_number", "Unknown"),
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "similarity_score": float(round(normalized_score, 1)),
                    "raw_score": float(round(raw_score, 4))  # 디버깅용
                })
            
            return sources
        except Exception as e:
            print(f"출처 문서 검색 실패: {e}")
            return []
    
    def clear_memory(self):
        pass
    
    def update_llm(self, llm_api_type: str, llm_base_url: str, llm_model: str, 
                   llm_api_key: str = "", temperature: float = 0.7):
        self.llm_api_type = llm_api_type
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.temperature = temperature
        self.llm = self._create_llm()
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
        self.vectorstore = vectorstore
        self.top_k = top_k
        self.retriever = vectorstore.as_retriever(
            search_kwargs={"k": max(top_k * 5, 20)}
        )
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

    def _to_percentage(self, scores: List[float], is_reranker: bool) -> List[float]:
        """점수 리스트를 0~100%로 정규화"""
        if not scores:
            return []
        if is_reranker:
            mn = min(scores)
            mx = max(scores)
            if abs(mx - mn) < 1e-9:
                return [50.0 for _ in scores]
            return [max(0.0, min(100.0, (s - mn) / (mx - mn) * 100.0)) for s in scores]
        # 벡터 검색: 거리가 0~2 (작을수록 유사) 가정 → 유사도로 변환
        return [max(0.0, min(100.0, (2.0 - s) / 2.0 * 100.0)) for s in scores]

    def _normalize_scores(self, pairs: List[tuple], is_reranker: bool) -> List[float]:
        """(doc, raw_score) -> 0~100% 확률형 점수로 보정
        - reranker: softmax(raw)
        - vector:   softmax(sim) with sim=exp(-alpha*distance), alpha=1.5
        """
        import math
        if not pairs:
            return []
        raw = [s for _, s in pairs]
        if is_reranker:
            mx = max(raw)
            exps = [math.exp(s - mx) for s in raw]
        else:
            # distance -> similarity (큰값 좋게) 후 softmax
            alpha = 1.5
            sims = [math.exp(-alpha * max(0.0, s)) for s in raw]
            mx = max(sims)
            exps = [math.exp(v - mx) for v in sims]
        Z = sum(exps) or 1.0
        probs = [min(100.0, max(0.0, 100.0 * v / Z)) for v in exps]
        return probs

