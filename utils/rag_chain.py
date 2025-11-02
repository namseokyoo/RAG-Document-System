from typing import List, Dict, Any, Optional, Iterator
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from utils.reranker import get_reranker
from utils.request_llm import RequestLLM
from utils.small_to_large_search import SmallToLargeSearch
import json
import re
import time


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
                 enable_multi_query: bool = True,
                 multi_query_num: int = 3):
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
        self.multi_query_num = max(0, multi_query_num)
        self.enable_multi_query = enable_multi_query and self.multi_query_num > 0
        
        # Small-to-Large 검색 초기화
        self.small_to_large_search = SmallToLargeSearch(vectorstore)
        
        # 도메인 용어 사전 (엔티티 감지용)
        self._domain_lexicon = {
            "TADF", "ACRSA", "DABNA1", "HF", "OLED", "EQE", 
            "FRET", "PLQY", "DMAC-TRZ", "AZB-TRZ", "ν-DABNA"
        }
        
        # Retriever 설정 - vectorstore는 이미 Chroma 인스턴스
        self.retriever = vectorstore.as_retriever(
            search_kwargs={"k": max(self.top_k * 8, 24)}
        )
        
        # 기본 프롬프트 템플릿 (상용 서비스 수준 개선)
        self.base_prompt_template = """당신은 문서 분석 전문가입니다. 제공된 문서 내용을 기반으로만 답변해야 합니다.

⚠️ 중요 규칙:
1. **문서 우선 원칙**: 반드시 제공된 문서에서 정보를 찾아 답변하세요.
2. **일반 지식 금지**: 문서에 없는 내용은 절대 추측하거나 일반 지식으로 답변하지 마세요.
3. **정보 없음 금지**: 문서가 제공된 경우 "정보를 찾을 수 없습니다"는 절대 사용하지 마세요.
4. **문서 인용 의무**: 답변할 때 반드시 문서의 구체적 내용을 인용하세요.

이전 대화 내용:
{chat_history}

참고 문서:
{context}

현재 질문: {question}

답변 절차:
1단계: 제공된 문서를 모두 꼼꼼히 읽으세요.
2단계: 질문과 관련된 정보를 문서에서 모두 찾으세요 (동의어, 약어도 고려).
3단계: 찾은 정보를 정리하여 구체적으로 답변하세요.
4단계: 답변에 반드시 문서의 내용을 인용하세요 (예: "문서에 따르면...", "제공된 문서의 X 페이지에...").

답변 형식:
- 문서에서 찾은 정보를 먼저 제시하세요
- 구체적인 수치, 이름, 날짜 등은 원문 그대로 인용하세요
- 문서의 어떤 부분(페이지/섹션)에서 정보를 얻었는지 명시하세요
- 문서에 명시되지 않은 내용은 추측하지 마세요

답변:"""
        
        # 질문 타입별 프롬프트 템플릿
        self.prompt_templates = {
            "specific_info": """당신은 문서에서 구체적인 정보를 추출하는 전문가입니다. 제공된 문서에서 정확한 사실, 수치, 이름, 구조 등을 찾아 답변해주세요.

⚠️ 핵심 규칙:
- 제공된 문서에서만 정보를 찾으세요 (일반 지식 사용 금지)
- "정보를 찾을 수 없습니다"는 절대 사용하지 마세요
- 문서에 관련 정보가 있으면 반드시 찾아 제시하세요

이전 대화 내용:
{chat_history}

참고 문서:
{context}

현재 질문: {question}

Few-Shot 예시:

[좋은 답변 예시]
질문: "논문에서 사용한 TADF 재료는 무엇인가?"
답변: "제공된 문서에 따르면, 논문에서 ACRSA (spiro-linked TADF molecule)를 사용했습니다. 문서의 일부에서 'ACRSA-based device'라고 명시되어 있으며, 비교 실험을 위해 DABNA1도 언급되어 있습니다. 정확한 화합물명은 문서에서 확인된 그대로 인용합니다."

[나쁜 답변 예시]
질문: "논문에서 사용한 TADF 재료는 무엇인가?"
답변: "죄송하지만 제공된 문서에서는 TADF 재료에 대한 구체적인 언급을 찾을 수 없습니다." (❌ 이렇게 답변하지 마세요)

답변 절차:
1. 제공된 문서의 모든 내용을 꼼꼼히 읽으세요.
2. 질문의 핵심 키워드를 식별하고, 동의어나 약어도 고려하여 문서에서 검색하세요.
3. 관련된 모든 정보를 찾아 나열하세요 (여러 곳에 있으면 모두 포함).
4. 각 정보마다 원문을 인용하고, 페이지/섹션 정보를 명시하세요.
5. 구체적인 수치, 이름, 날짜는 원문 그대로 정확히 인용하세요.
6. 부분적으로만 찾은 경우, 찾은 부분을 명시하고 "추가 정보는 문서의 다른 부분에 있을 수 있습니다"라고 언급하세요.

답변:""",
            
            "summary": """당신은 문서를 요약하는 전문가입니다. 제공된 문서의 핵심 내용을 체계적으로 요약해주세요.

⚠️ 핵심 규칙:
- 제공된 문서 내용만을 바탕으로 요약하세요 (일반 지식 추가 금지)
- 문서의 구체적인 내용을 인용하여 요약하세요
- "문서에 정보가 없습니다"는 사용하지 마세요

이전 대화 내용:
{chat_history}

참고 문서:
{context}

현재 질문: {question}

답변 절차:
1. 제공된 문서의 구조를 파악하세요 (제목, 섹션, 하위 섹션 등).
2. 각 섹션의 핵심 내용을 문서에서 직접 추출하세요.
3. 주요 발견, 결론, 수치 등은 문서의 원문을 인용하세요.
4. 논리적 순서로 구성하되, 모든 내용은 문서에 근거해야 합니다.
5. 문서에 명시되지 않은 내용은 추가하지 마세요.

답변:""",
            
            "comparison": """당신은 문서를 비교 분석하는 전문가입니다. 제공된 문서에서 비교 대상들을 찾아 차이점과 특징을 설명해주세요.

⚠️ 핵심 규칙:
- 제공된 문서에서만 비교 정보를 찾으세요
- 문서에 명시된 비교 내용을 정확히 인용하세요
- 일반적인 비교 지식은 사용하지 마세요

이전 대화 내용:
{chat_history}

참고 문서:
{context}

현재 질문: {question}

답변 절차:
1. 문서에서 비교 대상들을 식별하세요 (명시적으로 비교된 항목들).
2. 각 대상의 특징을 문서에서 직접 추출하여 나열하세요.
3. 문서에서 언급된 차이점과 공통점을 정확히 인용하여 설명하세요.
4. 수치적 비교가 문서에 있으면 해당 수치를 그대로 인용하세요.
5. 직접적인 비교 정보가 없으면, 문서에서 관련 정보를 찾아 제시하세요.

답변:""",
            
            "relationship": """당신은 문서에서 관계와 인과관계를 분석하는 전문가입니다. 제공된 문서에서 요소들 간의 관계를 분석하여 설명해주세요.

⚠️ 핵심 규칙:
- 제공된 문서에서만 관계 정보를 찾으세요
- 문서에 명시된 관계를 정확히 인용하세요
- 일반적인 원리나 추론은 문서 근거 없이 사용하지 마세요

이전 대화 내용:
{chat_history}

참고 문서:
{context}

현재 질문: {question}

답변 절차:
1. 문서에서 관련된 요소들을 식별하세요.
2. 문서에서 명시된 요소들 간의 관계, 영향, 메커니즘을 찾아 인용하세요.
3. 문서에서 언급된 인과관계나 상관관계를 정확히 설명하세요.
4. 문서에서 발견된 경향성이나 패턴을 원문을 인용하며 설명하세요.
5. 직접적인 관계 정보가 없으면, 문서에서 관련 정보를 찾아 제시하되, 일반적인 추론은 최소화하세요.

답변:""",
            
            "general": self.base_prompt_template
        }
        
        # 기본 프롬프트 (나중에 질문 타입에 따라 동적으로 선택)
        self.prompt_template = self.base_prompt_template
        
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
        """문서를 구조화된 형식으로 포맷팅 (상용 서비스 수준 개선)"""
        formatted_sections = []
        
        for i, doc in enumerate(docs, 1):
            metadata = doc.metadata or {}
            file_name = metadata.get('file_name', 'Unknown')
            page_number = metadata.get('page_number', 'Unknown')
            chunk_type = metadata.get('chunk_type', 'unknown')
            section_title = metadata.get('section_title', '')
            
            # 문서 번호와 메타데이터
            header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            header += f"📄 문서 #{i}\n"
            header += f"   파일명: {file_name}\n"
            header += f"   페이지: {page_number}\n"
            if chunk_type != 'unknown':
                header += f"   청크 타입: {chunk_type}\n"
            if section_title:
                header += f"   섹션: {section_title}\n"
            header += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # 문서 내용
            content = doc.page_content.strip()
            
            formatted_sections.append(header + content)
        
        return "\n\n".join(formatted_sections)

    def _unique_by_file(self, pairs: List[tuple], k: int) -> List[tuple]:
        """(Document, score) 리스트에서 파일명 기준으로 중복을 제거하며 최대 k개 반환
        개선: PPTX는 슬라이드 단위, PDF는 페이지 단위로 중복 제거"""
        seen = set()
        results: List[tuple] = []
        file_chunk_counts = {}  # 파일별 청크 개수 추적
        
        for doc, score in pairs:
            file_name = doc.metadata.get("file_name", "")
            chunk_type = doc.metadata.get("chunk_type", "")
            
            # PPTX: 슬라이드 단위 중복 제거, PDF: 페이지 단위 중복 제거
            # slide_number 또는 page_number가 있으면 사용, 없으면 file_name만 사용
            slide_number = doc.metadata.get("slide_number")
            page_number = doc.metadata.get("page_number")
            
            if slide_number is not None:
                # PPTX: file_name + slide_number 조합으로 중복 제거
                key = f"{file_name}_slide_{slide_number}"
            elif page_number is not None:
                # PDF: file_name + page_number 조합으로 중복 제거
                key = f"{file_name}_page_{page_number}"
            else:
                # 메타데이터가 없으면 파일명만 사용 (기존 방식)
                key = file_name
            
            # 파일당 최대 청크 수 제한 (너무 많은 청크 방지)
            # 목록 나열 질문의 경우 더 많이 허용
            max_per_file = 10  # 기본값: 파일당 최대 10개 청크
            
            if key in seen:
                # 이미 본 조합이면 건너뛰기 (동일 슬라이드/페이지는 1개만)
                continue
            
            # 파일당 청크 개수 체크
            if file_name in file_chunk_counts:
                if file_chunk_counts[file_name] >= max_per_file:
                    continue
                file_chunk_counts[file_name] += 1
            else:
                file_chunk_counts[file_name] = 1
            
            seen.add(key)
            results.append((doc, score))
            if len(results) >= k:
                break
        return results

    def _search_candidates(self, question: str) -> List[tuple]:
        """하이브리드(키워드+벡터) → Re-ranker 입력 후보 확보 (Phase 3: 엔티티 boost 추가)"""
        try:
            # 하이브리드로 넉넉히 후보 확보 (설정된 reranker_initial_k 사용)
            initial_k = max(self.reranker_initial_k, max(self.top_k * 8, 60))
            hybrid = self.vectorstore.similarity_search_hybrid(
                question, initial_k=initial_k, top_k=initial_k
            )
            
            # Phase 3: 엔티티 매칭 청크에 boost 적용
            if hasattr(self.vectorstore, 'entity_index') and self.vectorstore.entity_index:
                hybrid = self._apply_entity_boost(question, hybrid)
            
            return hybrid
        except Exception:
            # 폴백: 벡터 검색
            return self.vectorstore.similarity_search_with_score(question, k=max(self.reranker_initial_k, 60))
    
    def _apply_entity_boost(self, question: str, candidates: List[tuple], boost_factor: float = 1.5) -> List[tuple]:
        """엔티티 매칭 청크에 boost 점수 적용 (Phase 3)"""
        # 쿼리에서 엔티티 감지 (도메인 용어 사전 활용)
        detected_entities = []
        question_lower = question.lower()
        
        # 도메인 용어 사전에서 엔티티 추출
        for key in self._domain_lexicon.keys():
            if key.lower() in question_lower:
                detected_entities.append(key)
        
        # 감지된 엔티티가 없으면 그대로 반환
        if not detected_entities:
            return candidates
        
        # 엔티티 매칭 청크 ID 수집
        matching_chunk_ids = set()
        for entity in detected_entities:
            chunk_ids = self.vectorstore.search_by_entity(entity)
            matching_chunk_ids.update(chunk_ids)
        
        if not matching_chunk_ids:
            return candidates
        
        # 매칭되는 청크에 boost 적용
        boosted_candidates = []
        boost_count = 0
        for doc, score in candidates:
            chunk_id = doc.metadata.get('chunk_id') or doc.metadata.get('id')
            if chunk_id in matching_chunk_ids:
                boosted_score = score * boost_factor
                boosted_candidates.append((doc, boosted_score))
                boost_count += 1
            else:
                boosted_candidates.append((doc, score))
        
        if boost_count > 0:
            print(f"✨ 엔티티 boost 적용: {boost_count}개 청크 (감지된 엔티티: {', '.join(detected_entities)})")
        
        return boosted_candidates

    def _detect_query_type(self, question: str) -> str:
        """쿼리 타입 감지 (구체적 정보 추출, 요약, 비교, 관계 분석 등)"""
        question_lower = question.lower()
        
        # 구체적 정보 추출 키워드
        specific_keywords = ["무엇인가", "얼마인가", "누구인가", "언제", "어디", 
                           "어떤", "나열", "추출", "수치", "값", "이름", "구조"]
        if any(keyword in question_lower for keyword in specific_keywords):
            return "specific_info"
        
        # 요약 키워드
        summary_keywords = ["요약", "정리", "핵심", "주요 내용", "개요", "개요"]
        if any(keyword in question_lower for keyword in summary_keywords):
            return "summary"
        
        # 비교 분석 키워드
        comparison_keywords = ["비교", "차이", "대비", "어느 것이", "vs", "versus"]
        if any(keyword in question_lower for keyword in comparison_keywords):
            return "comparison"
        
        # 관계 분석 키워드
        relationship_keywords = ["관계", "상관관계", "경향", "영향", "메커니즘", "원인"]
        if any(keyword in question_lower for keyword in relationship_keywords):
            return "relationship"
        
        # 기본값
        return "general"
    
    def _get_context(self, question: str) -> str:
        context_start = time.perf_counter()
        # 쿼리 타입 감지
        query_type = self._detect_query_type(question)
        
        # 구체적 정보 추출 모드: Small-to-Large 검색 활용
        if query_type == "specific_info":
            try:
                # 1단계: Small-to-Large 검색으로 정확한 청크 찾기
                stl_results = self.small_to_large_search.search_with_context_expansion(
                    question, top_k=20, max_parents=5, partial_context_size=300
                )
                
                if stl_results:
                    # Small-to-Large 결과를 (doc, score) 형식으로 변환
                    # 가중치 기반 점수 계산
                    weighted_results = []
                    for doc in stl_results:
                        # 청크 타입별 가중치 적용
                        chunk_type_weight = doc.metadata.get("chunk_type_weight", 1.0)
                        # 기본 점수 (Small-to-Large는 정확한 매칭을 우선하므로 높은 점수)
                        base_score = 0.8 * chunk_type_weight
                        weighted_results.append((doc, base_score))
                    
                    # Re-ranking 적용 (있는 경우)
                    if self.use_reranker and len(weighted_results) > 0:
                        docs_for_rerank = [{
                            "page_content": d.page_content,
                            "metadata": d.metadata,
                            "vector_score": s,
                            "document": d
                        } for d, s in weighted_results]
                        reranked = self.reranker.rerank(question, docs_for_rerank, top_k=min(15, len(docs_for_rerank)))
                        pairs = [(d["document"], d.get("rerank_score", 0.8)) for d in reranked]
                    else:
                        pairs = weighted_results
                    
                    # 중복 제거
                    dedup = self._unique_by_file(pairs, self.top_k * 2)
                    self._last_retrieved_docs = dedup[:self.top_k]
                    docs = [d for d, _ in self._last_retrieved_docs]
                    elapsed = time.perf_counter() - context_start
                    print(f"[Timing] context retrieval (Small-to-Large, type={query_type}): {elapsed:.2f}s")
                    print(f"🔍 구체적 정보 추출 모드: Small-to-Large 검색 (쿼리 타입: {query_type})")
                    return self._format_docs(docs)
            except Exception as e:
                print(f"Small-to-Large 검색 실패, 기본 검색으로 폴백: {e}")
                # 폴백: 기본 검색 계속 진행
        
        # 요약 모드: 더 많은 문서 검색
        if query_type == "summary":
            # 요약은 더 많은 컨텍스트 필요
            original_top_k = self.top_k
            self.top_k = min(10, original_top_k * 2)
            try:
                context = self._get_context_standard(question)
                elapsed = time.perf_counter() - context_start
                print(f"[Timing] context retrieval (summary, type={query_type}): {elapsed:.2f}s")
                self.top_k = original_top_k
                return context
            except:
                self.top_k = original_top_k
                return ""
        
        # 기본 검색 (기존 로직)
        context = self._get_context_standard(question)
        elapsed = time.perf_counter() - context_start
        print(f"[Timing] context retrieval (standard, type={query_type}): {elapsed:.2f}s")
        return context
    
    def _get_context_standard(self, question: str) -> str:
        """표준 컨텍스트 검색 (기존 로직)"""
        overall_start = time.perf_counter()
        
        # 🆕 동적 top_k 결정 (질문 특성 분석)
        dynamic_top_k = self.determine_optimal_top_k(question)
        print(f"🔍 질문 특성 분석: top_k = {dynamic_top_k} (기본: {self.top_k})")
        
        # Multi-Query Rewriting 적용
        if self.enable_multi_query:
            mq_start = time.perf_counter()
            queries = self.generate_rewritten_queries(question, num_queries=self.multi_query_num)
            print(f"[Timing] multi_query_generate: {time.perf_counter() - mq_start:.2f}s (queries={len(queries)})")
            all_retrieved_chunks = []
            chunk_id_set = set()
            
            # 모든 쿼리에 대해 검색 수행
            for idx, query in enumerate(queries, start=1):
                query_start = time.perf_counter()
                try:
                    results = []
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
                    print(f"[Timing] retrieval[{idx}/{len(queries)}]: {time.perf_counter() - query_start:.2f}s (docs={len(results)})")
                    
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
                    rerank_start = time.perf_counter()
                    docs_for_final_rerank = [{
                        "page_content": d.page_content,
                        "metadata": d.metadata,
                        "vector_score": s,
                        "document": d
                    } for d, s in all_retrieved_chunks]
                    final_reranked = self.reranker.rerank(question, docs_for_final_rerank, top_k=max(self.top_k * 2, 20))
                    pairs = [(d["document"], d.get("rerank_score", 0)) for d in final_reranked]
                    print(f"[Timing] final_rerank (multi-query): {time.perf_counter() - rerank_start:.2f}s (candidates={len(all_retrieved_chunks)})")
                else:
                    pairs = all_retrieved_chunks
                
                dedup = self._unique_by_file(pairs, dynamic_top_k)  # 동적 top_k 사용
                self._last_retrieved_docs = dedup
                docs = [d for d, _ in dedup]
                print(f"[Timing] context_standard total: {time.perf_counter() - overall_start:.2f}s (mode=multi-query, top_k={dynamic_top_k})")
                return self._format_docs(docs)
        
        # 폴백: 단일 쿼리 검색 (동의어 확장 포함)
        syn_start = time.perf_counter()
        expanded_question = self.expand_query_with_synonyms(question)
        print(f"[Timing] synonym_expand: {time.perf_counter() - syn_start:.2f}s")
        
        if self.use_reranker:
            retrieval_start = time.perf_counter()
            base = self._search_candidates(expanded_question)
            if not base:
                self._last_retrieved_docs = []
                print(f"[Timing] context_standard total: {time.perf_counter() - overall_start:.2f}s (mode=fallback, docs=0)")
                return ""
            # base 는 (doc, score) 형태
            docs_for_rerank = [{
                "page_content": d.page_content,
                "metadata": d.metadata,
                "vector_score": s,
                "document": d
            } for d, s in base]
            print(f"[Timing] candidate_retrieval (fallback): {time.perf_counter() - retrieval_start:.2f}s (candidates={len(base)})")
            rerank_start = time.perf_counter()
            reranked = self.reranker.rerank(expanded_question, docs_for_rerank, top_k=max(self.top_k * 8, 40))
            pairs = [(d["document"], d.get("rerank_score", 0)) for d in reranked]
            dedup = self._unique_by_file(pairs, dynamic_top_k)  # 동적 top_k 사용
            
            # 캐시 저장: 실제 사용된 문서와 점수
            self._last_retrieved_docs = dedup  # [(doc, score), ...]
            
            docs = [d for d, _ in dedup]
            print(f"[Timing] final_rerank (fallback): {time.perf_counter() - rerank_start:.2f}s (selected={len(dedup)})")
        else:
            retrieval_start = time.perf_counter()
            pairs = self.vectorstore.similarity_search_with_score(expanded_question, k=max(self.top_k * 8, 40))
            dedup = self._unique_by_file(pairs, dynamic_top_k)  # 동적 top_k 사용
            
            # 캐시 저장
            self._last_retrieved_docs = dedup
            
            docs = [d for d, _ in dedup]
            print(f"[Timing] candidate_retrieval (vector fallback): {time.perf_counter() - retrieval_start:.2f}s (selected={len(dedup)})")
        print(f"[Timing] context_standard total: {time.perf_counter() - overall_start:.2f}s (mode=fallback, top_k={dynamic_top_k})")
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

    def determine_optimal_top_k(self, question: str) -> int:
        """질문 특성에 따라 최적의 top_k 값을 동적으로 결정"""
        try:
            prompt = f"""당신은 RAG 검색 최적화 전문가입니다. 사용자의 질문을 분석하여 필요한 문서 개수를 추천해주세요.

질문: "{question}"

다음 질문들에 대해 분석하세요:
1. 이 질문은 단일 사실 찾기인가? (예: "무엇", "얼마", "누구" - 간단한 답변)
2. 이 질문은 목록 나열인가? (예: "모두", "전체", "나열", "목록", "제목들" - 여러 항목)
3. 이 질문은 비교/분석인가? (예: "차이", "비교", "관계" - 여러 관점)
4. 이 질문은 종합 정보인가? (예: "요약", "핵심", "개요" - 전체 컨텍스트)

필요한 문서 개수:
- 단일 사실: 3-5개
- 목록 나열: 20-30개 (중복 제거 후 적절한 수)
- 비교/분석: 10-20개
- 종합 정보: 10-15개

결과는 숫자로만 응답하세요. 범위: 3~30
예시: 5, 15, 20"""

            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 숫자 추출
            numbers = re.findall(r'\d+', response_text)
            if numbers:
                top_k = int(numbers[0])
                top_k = max(3, min(30, top_k))  # 3~30 범위 제한
                print(f"🎯 동적 top_k 결정: {top_k} (질문 유형 분석)")
                return top_k
        except Exception as e:
            print(f"동적 top_k 결정 실패: {e}")
        
        # 폴백: 기본값
        return self.top_k
    
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
            
            # 쿼리 타입 감지 및 프롬프트 선택
            query_type = self._detect_query_type(question)
            if query_type in self.prompt_templates:
                selected_template = self.prompt_templates[query_type]
                self.prompt = PromptTemplate(
                    template=selected_template,
                    input_variables=["chat_history", "context", "question"]
                )
                # 체인 재구성 (프롬프트 변경 반영)
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
            
            # 컨텍스트 가져오기 (_last_retrieved_docs 업데이트됨)
            context = self._get_context(question)
            
            # 답변 생성
            answer = self.chain.invoke({
                "question": question,
                "chat_history": formatted_history
            })
            
            # Phase 2: 답변 검증 및 재생성 (상용 서비스 수준)
            docs_for_confidence = [d for d, _ in self._last_retrieved_docs[:self.top_k]]
            verification_result = self._verify_answer_quality(question, answer, docs_for_confidence)
            
            if not verification_result["is_valid"]:
                print(f"⚠️ 답변 검증 실패: {verification_result['reason']}")
                print(f"🔄 문서 기반 재생성 시도...")
                
                # 문서 기반 재생성
                regenerated_answer = self._regenerate_answer(question, answer, docs_for_confidence, formatted_history)
                if regenerated_answer:
                    answer = regenerated_answer
                    print(f"✅ 답변 재생성 완료")
                else:
                    print(f"⚠️ 재생성 실패, 원본 답변 사용")
            
            # 캐시된 문서에서 출처 정보 생성
            sources = []
            docs_for_confidence = []
            
            for doc, score in self._last_retrieved_docs[:self.top_k]:
                docs_for_confidence.append(doc)
                source_info = {
                    "file_name": doc.metadata.get("file_name", "Unknown"),
                    "page_number": doc.metadata.get("page_number", "Unknown"),
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "similarity_score": float(round(score * 100, 1))  # 0-100 스케일로 변환
                }
                sources.append(source_info)
            
            # 신뢰도 점수 계산
            confidence = self._calculate_confidence_score(question, answer, docs_for_confidence)
            
            return {
                "answer": answer,
                "sources": sources,
                "confidence": confidence,
                "success": True
            }
        except Exception as e:
            print(f"❌ query() 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                "answer": f"오류가 발생했습니다: {str(e)}",
                "sources": [],
                "confidence": 0.0,
                "success": False
            }
    
    def _verify_answer_quality(self, question: str, answer: str, docs: List[Document]) -> Dict[str, Any]:
        """답변 품질 검증 (Phase 2: 상용 서비스 수준)
        
        Returns:
            {
                "is_valid": bool,
                "reason": str,
                "scores": {
                    "no_forbidden_phrases": float,
                    "has_citation": float,
                    "content_match": float,
                    "specificity": float
                }
            }
        """
        if not docs or not answer:
            return {
                "is_valid": False,
                "reason": "문서 또는 답변이 없음",
                "scores": {}
            }
        
        answer_lower = answer.lower()
        doc_contents = " ".join([d.page_content.lower() for d in docs])
        doc_metadata = [(d.metadata.get("file_name", ""), d.metadata.get("page_number", "")) for d in docs]
        
        scores = {}
        
        # 1. 금지 구문 검사
        forbidden_phrases = [
            "정보를 찾을 수 없습니다",
            "정보가 없습니다",
            "찾을 수 없습니다",
            "없습니다",
            "정보 부족",
            "확인할 수 없습니다",
            "cannot find",
            "not found",
            "no information"
        ]
        has_forbidden = any(phrase in answer_lower for phrase in forbidden_phrases)
        scores["no_forbidden_phrases"] = 0.0 if has_forbidden else 1.0
        
        # 2. 문서 인용 검사 (페이지 번호, 파일명 등 메타데이터 언급)
        has_citation = False
        citation_keywords = ["페이지", "page", "문서", "파일", "섹션", "section"]
        has_citation_keywords = any(keyword in answer_lower for keyword in citation_keywords)
        
        # 파일명이나 페이지 번호 직접 언급 확인
        for file_name, page_num in doc_metadata:
            if file_name and file_name.lower() in answer_lower:
                has_citation = True
                break
            if page_num and str(page_num) in answer:
                has_citation = True
                break
        
        scores["has_citation"] = 1.0 if (has_citation or has_citation_keywords) else 0.3
        
        # 3. 문서 내용과의 일치 검사 (키워드 매칭)
        question_keywords = set(re.findall(r'\w+', question.lower()))
        doc_keywords = set(re.findall(r'\w+', doc_contents[:1000]))  # 처음 1000자만
        
        # 답변에 문서 키워드가 얼마나 포함되는지
        matching_keywords = question_keywords.intersection(doc_keywords)
        answer_has_keywords = sum(1 for kw in matching_keywords if kw in answer_lower)
        content_match_score = min(1.0, answer_has_keywords / max(len(matching_keywords), 1))
        scores["content_match"] = content_match_score
        
        # 4. 구체성 검사 (일반화된 답변 감지)
        # 일반화된 구문 패턴
        generic_phrases = [
            "일반적으로",
            "보통",
            "대부분의 경우",
            "일반적으로 알려진",
            "일반적인 원리",
            "일반적으로 사용되는"
        ]
        has_generic = any(phrase in answer_lower for phrase in generic_phrases)
        
        # 문서 특정 내용 (수치, 이름, 고유명사 등) 포함 여부
        has_specifics = bool(re.search(r'\d+[.%]?', answer)) or len([w for w in answer.split() if len(w) > 5]) > 3
        specificity_score = 0.5 if has_generic else 1.0
        if has_specifics:
            specificity_score = min(1.0, specificity_score + 0.3)
        scores["specificity"] = specificity_score
        
        # 종합 검증
        total_score = (
            scores["no_forbidden_phrases"] * 0.4 +
            scores["has_citation"] * 0.3 +
            scores["content_match"] * 0.2 +
            scores["specificity"] * 0.1
        )
        
        is_valid = total_score >= 0.6 and scores["no_forbidden_phrases"] > 0
        
        reasons = []
        if not is_valid:
            if scores["no_forbidden_phrases"] == 0:
                reasons.append("금지 구문 사용")
            if scores["has_citation"] < 0.5:
                reasons.append("문서 인용 부족")
            if scores["content_match"] < 0.3:
                reasons.append("문서 내용과 불일치")
            if scores["specificity"] < 0.5:
                reasons.append("일반화된 답변")
        
        return {
            "is_valid": is_valid,
            "reason": ", ".join(reasons) if reasons else "정상",
            "total_score": total_score,
            "scores": scores
        }
    
    def _regenerate_answer(self, question: str, original_answer: str, docs: List[Document], 
                          chat_history: str) -> Optional[str]:
        """검증 실패 시 문서 기반 재생성 (Phase 2)"""
        if not docs:
            return None
        
        try:
            # 재생성 전용 프롬프트
            context = self._format_docs(docs)
            
            regeneration_prompt = f"""이전에 생성된 답변이 문서 기반이 아니었습니다. 제공된 문서만을 사용하여 다시 답변하세요.

⚠️ 중요 규칙:
1. **문서 우선**: 반드시 제공된 문서에서만 정보를 찾으세요
2. **금지 구문**: "정보를 찾을 수 없습니다", "없습니다"는 절대 사용하지 마세요
3. **문서 인용**: 반드시 문서의 내용을 인용하고 페이지/파일 정보를 명시하세요
4. **구체성**: 문서의 구체적인 수치, 이름, 내용을 정확히 인용하세요

이전 대화:
{chat_history}

제공된 문서:
{context}

질문:
{question}

이전 답변 (참고용, 개선 필요):
{original_answer}

위 이전 답변을 개선하여, 제공된 문서에 근거한 구체적이고 명확한 답변을 작성하세요.

답변:"""
            
            # LLM 재생성
            regenerated = self.llm.invoke(regeneration_prompt)
            
            # 응답 파싱
            if hasattr(regenerated, 'content'):
                return regenerated.content.strip()
            elif hasattr(regenerated, 'text'):
                return regenerated.text.strip()
            else:
                return str(regenerated).strip()
                
        except Exception as e:
            print(f"⚠️ 재생성 오류: {e}")
            return None
    
    def _calculate_confidence_score(self, question: str, answer: str, docs: List[Document]) -> float:
        """답변 신뢰도 점수 계산 (0-100)"""
        if not docs:
            return 0.0
        
        # 1. 문서 개수 기반 점수 (더 많은 출처 = 높은 신뢰도)
        doc_score = min(len(docs) / 5.0, 1.0)  # 5개 이상이면 만점
        
        # 2. 답변 길이 점수 (너무 짧거나 길면 감점)
        answer_length = len(answer)
        if answer_length < 50:
            length_score = 0.3
        elif answer_length < 100:
            length_score = 0.6
        elif answer_length < 500:
            length_score = 1.0
        elif answer_length < 1000:
            length_score = 0.9
        else:
            length_score = 0.8
        
        # 3. "정보 없음" 키워드 감지
        negative_keywords = ["찾을 수 없습니다", "확인할 수 없습니다", "정보가 없습니다", "죄송합니다"]
        has_negative = any(keyword in answer for keyword in negative_keywords)
        negative_penalty = 0.5 if has_negative else 1.0
        
        # 최종 신뢰도 점수 (0-100)
        confidence = (doc_score * 0.4 + length_score * 0.4 + negative_penalty * 0.2) * 100
        return round(confidence, 1)
    
    def query_stream(self, question: str, chat_history: List[Dict[str, str]] = None) -> Iterator[str]:
        overall_start = time.perf_counter()
        try:
            formatted_history = self._format_chat_history(chat_history or [])

            # 컨텍스트 구성 (로그 포함)
            context = self._get_context(question)

            # 최종 프롬프트 조합 후 로그 출력
            prompt_text = self.prompt.format(
                chat_history=formatted_history,
                context=context,
                question=question
            )
            print("[Prompt] ---------- START ----------")
            print(prompt_text)
            print("[Prompt] ----------- END -----------")

            chain_start = time.perf_counter()
            first_chunk = True
            for chunk in self.llm.stream(prompt_text):
                # chunk 타입별로 텍스트 추출
                if hasattr(chunk, "content") and isinstance(chunk.content, str):
                    text = chunk.content
                elif hasattr(chunk, "text") and isinstance(chunk.text, str):
                    text = chunk.text
                else:
                    text = str(chunk)

                if text:
                    if first_chunk:
                        print(f"[Timing] LLM first token delay: {time.perf_counter() - chain_start:.2f}s")
                        first_chunk = False
                    yield text

            print(f"[Timing] LLM streaming total: {time.perf_counter() - chain_start:.2f}s")
            print(f"[Timing] query_stream total: {time.perf_counter() - overall_start:.2f}s")
        except Exception as e:
            print(f"[Timing] query_stream total: {time.perf_counter() - overall_start:.2f}s (error)")
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
        """(doc, raw_score) -> 0~100% 확률형 점수로 보정 (개선 버전)
        - reranker: Z-score 정규화 후 Min-Max로 [0, 1] 변환
        - vector:   하이퍼볼릭 변환 + Min-Max 정규화 후 softmax
        """
        import math
        import statistics
        
        if not pairs:
            return []
        
        raw = [float(s) for _, s in pairs]
        
        if is_reranker:
            # Reranker 점수: 일반적으로 양수이며 큰 값이 좋음
            # 음수 값 필터링 및 정규화
            filtered_scores = [s for s in raw if s > 0]
            
            if not filtered_scores:
                # 모든 점수가 0 이하인 경우 균등 분배
                return [50.0] * len(pairs)
            
            # Z-score 정규화
            mean_score = statistics.mean(filtered_scores)
            try:
                stdev_score = statistics.stdev(filtered_scores) if len(filtered_scores) > 1 else 1.0
            except:
                stdev_score = 1.0
            
            z_scores = []
            for s in raw:
                if s > 0 and stdev_score > 0:
                    z = (s - mean_score) / stdev_score
                    z_scores.append(z)
                else:
                    z_scores.append(-2.0)  # 음수 점수는 낮은 Z-score
            
            # Z-score를 [0, 1] 범위로 Min-Max 정규화
            min_z = min(z_scores)
            max_z = max(z_scores)
            z_range = max_z - min_z if max_z > min_z else 1.0
            
            normalized = []
            for z in z_scores:
                if z_range > 0:
                    norm_val = (z - min_z) / z_range
                else:
                    norm_val = 0.5
                normalized.append(max(0.0, min(1.0, norm_val)))
            
            # Softmax 적용 (더 부드러운 확률 분포)
            mx = max(normalized)
            exps = [math.exp(v - mx) for v in normalized]
            Z = sum(exps) or 1.0
            probs = [min(100.0, max(0.0, 100.0 * v / Z)) for v in exps]
        else:
            # Vector 검색: 거리 기반 점수 (작을수록 좋음)
            # 음수 값 처리 및 하이퍼볼릭 변환
            sims = []
            for s in raw:
                if s >= 0:
                    # 거리 → 유사도 변환: similarity = 1 / (1 + distance)
                    sim = 1.0 / (1.0 + s)
                else:
                    # 음수 거리는 비정상 → 낮은 유사도
                    sim = 0.01
                sims.append(sim)
            
            # Min-Max 정규화
            min_sim = min(sims)
            max_sim = max(sims)
            sim_range = max_sim - min_sim if max_sim > min_sim else 1.0
            
            normalized = []
            for sim in sims:
                if sim_range > 0:
                    norm_val = (sim - min_sim) / sim_range
                else:
                    norm_val = 0.5
                normalized.append(max(0.0, min(1.0, norm_val)))
            
            # Softmax 적용
            mx = max(normalized)
            exps = [math.exp(v - mx) for v in normalized]
            Z = sum(exps) or 1.0
            probs = [min(100.0, max(0.0, 100.0 * v / Z)) for v in exps]
        
        return probs

