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
from utils.hybrid_retriever import HybridRetriever  # Phase 4: Hybrid Search
import json
import re
import time
import logging
import statistics
import numpy as np

logger = logging.getLogger(__name__)


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
                 multi_query_num: int = 3,
                 # Phase 4: Hybrid Search (BM25 + Vector)
                 enable_hybrid_search: bool = True,
                 hybrid_bm25_weight: float = 0.5):
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
        self.reranker = None
        if self.use_reranker:
            try:
                self.reranker = get_reranker(model_name=reranker_model)
                logger.info(f"Re-ranker 모델 로딩 완료: {reranker_model}")
            except Exception as e:
                # 에러 메시지에서 중복 제거 (reranker.py에서 이미 상세 메시지 출력)
                error_msg = str(e)
                if "오프라인 모드에서" in error_msg or "모델 파일을 찾을 수 없습니다" in error_msg:
                    # 이미 포맷된 에러 메시지이므로 간단히만 로깅
                    logger.warning(f"Re-ranker 모델 로딩 실패 ({reranker_model}): 모델 파일이 없습니다.")
                else:
                    logger.warning(f"Re-ranker 모델 로딩 실패 ({reranker_model}): {error_msg}")
                logger.warning("Re-ranker 없이 계속 진행합니다.")
                self.use_reranker = False
                self.reranker = None
        
        # 마지막 검색 결과 캐시 (출처 표시용)
        self._last_retrieved_docs = []
        
        # Chat history 캐시 (도메인 감지용)
        self._chat_history_cache = []
        
        # LLM 초기화 - API 타입에 따라 다른 클라이언트 사용
        self.llm = self._create_llm()
        
        # 동의어 확장 설정
        self.enable_synonym_expansion = enable_synonym_expansion
        self.multi_query_num = max(0, multi_query_num)
        self.enable_multi_query = enable_multi_query and self.multi_query_num > 0
        
        # Small-to-Large 검색 초기화
        self.small_to_large_search = SmallToLargeSearch(vectorstore)

        # Phase 4: Hybrid Search (BM25 + Vector) 초기화
        self.enable_hybrid_search = enable_hybrid_search
        self.hybrid_retriever = None
        if self.enable_hybrid_search:
            try:
                self.hybrid_retriever = HybridRetriever(
                    vector_manager=vectorstore,
                    bm25_weight=hybrid_bm25_weight
                )
                # BM25 인덱스 구축
                self.hybrid_retriever.build_bm25_index()
                logger.info(f"Hybrid Search 초기화 완료 (BM25: {hybrid_bm25_weight}, Vector: {1-hybrid_bm25_weight})")
            except Exception as e:
                logger.warning(f"Hybrid Search 초기화 실패: {e}, 기본 검색 모드로 진행")
                self.enable_hybrid_search = False
                self.hybrid_retriever = None

        # 도메인 용어 사전 (엔티티 감지용)
        self._domain_lexicon = {
            "TADF", "ACRSA", "DABNA1", "HF", "OLED", "EQE",
            "FRET", "PLQY", "DMAC-TRZ", "AZB-TRZ", "ν-DABNA"
        }
        
        # Retriever 설정 - vectorstore는 VectorStoreManager 인스턴스
        self.retriever = vectorstore.vectorstore.as_retriever(
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

답변 절차 (단계별로 생각 과정을 명시하세요):
1단계 [문서 분석]:
   - 각 문서의 주제와 핵심 내용을 파악하세요.
   - 질문과 관련된 키워드를 문서에서 찾으세요.
   - 동의어, 약어, 전문 용어 변형도 고려하세요.

2단계 [정보 추출]:
   - 질문에 직접 답하는 정보를 식별하세요.
   - 수치, 날짜, 이름 등 구체적 사실을 추출하세요.
   - 여러 문서에 관련 정보가 있으면 모두 포함하세요.

3단계 [정보 통합]:
   - 추출한 정보를 논리적으로 구성하세요.
   - 관련성이 높은 정보를 우선 배치하세요.
   - 정보 간의 관계나 비교가 필요한지 판단하세요.

4단계 [답변 생성]:
   - 문서에서 확인된 사실만 사용하여 답변하세요.
   - 각 사실마다 출처를 명시하세요 (문서 번호, 페이지/섹션).
   - 추측이나 일반 지식은 절대 사용하지 마세요.

5단계 [검증]:
   - 답변이 질문에 직접적으로 답하는지 확인하세요.
   - 모든 사실이 문서에 근거하는지 재검토하세요.
   - 출처 정보가 충분한지 확인하세요.

답변 형식 (다음 구조를 반드시 따르세요):

## 답변
[질문에 대한 직접적인 답변을 1-2문장으로 요약]

## 상세 설명
[답변의 근거와 배경 설명]

## 참조 정보
각 사실마다 다음 형식으로 출처를 명시하세요:
- [사실 1]: 문서 #1, 페이지 X / 섹션 "Y"
- [사실 2]: 문서 #2, 페이지 Z / 섹션 "W"

## 관련 추가 정보
[질문과 관련 있지만 직접 답변에 포함되지 않은 추가 정보 (선택적)]

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
답변: 
## 답변
제공된 문서에 따르면, 논문에서 ACRSA (spiro-linked TADF molecule)를 사용했습니다. 비교 실험을 위해 DABNA1도 언급되어 있습니다.

## 상세 설명
문서에서 TADF 재료로 ACRSA가 명시적으로 사용되었다고 나와 있으며, 'ACRSA-based device'라는 표현으로 확인할 수 있습니다.

## 참조 정보
- ACRSA 사용: 문서 #1, 페이지 3 / 섹션 "재료 및 방법"
- DABNA1 비교: 문서 #1, 페이지 4 / 섹션 "실험 결과"

[나쁜 답변 예시]
질문: "논문에서 사용한 TADF 재료는 무엇인가?"
답변: "죄송하지만 제공된 문서에서는 TADF 재료에 대한 구체적인 언급을 찾을 수 없습니다." (❌ 이렇게 답변하지 마세요)

답변 절차:
1단계 [키워드 식별]: 질문의 핵심 키워드를 식별하고, 동의어나 약어도 고려하여 문서에서 검색하세요.
2단계 [정보 검색]: 제공된 문서의 모든 내용을 꼼꼼히 읽고 관련 정보를 찾으세요.
3단계 [정보 추출]: 관련된 모든 정보를 찾아 나열하세요 (여러 곳에 있으면 모두 포함).
4단계 [출처 명시]: 각 정보마다 원문을 인용하고, 페이지/섹션 정보를 명시하세요.
5단계 [정확성 확인]: 구체적인 수치, 이름, 날짜는 원문 그대로 정확히 인용하세요.
6단계 [부분 정보 처리]: 부분적으로만 찾은 경우, 찾은 부분을 명시하고 "추가 정보는 문서의 다른 부분에 있을 수 있습니다"라고 언급하세요.

답변 형식 (구조화된 형식 사용):
## 답변
[1-2문장 요약]

## 상세 설명
[구체적 사실 나열]

## 참조 정보
- [사실 1]: [출처]
- [사실 2]: [출처]

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

Few-Shot 예시:

[좋은 요약 예시]
질문: "이 논문의 핵심 내용을 요약해주세요."
답변:
## 답변
이 논문은 TADF 재료를 사용한 OLED 디바이스의 효율 개선에 관한 연구로, ACRSA 기반 디바이스를 통해 높은 발광 효율을 달성했다고 보고합니다.

## 상세 설명
논문은 다음과 같은 주요 내용을 포함합니다:
1. TADF 재료의 특성과 장점
2. ACRSA 재료를 사용한 디바이스 제작
3. 발광 효율 측정 결과 및 분석
4. 기존 재료 대비 성능 비교

## 참조 정보
- TADF 재료 특성: 문서 #1, 페이지 2 / 섹션 "서론"
- ACRSA 디바이스: 문서 #1, 페이지 3 / 섹션 "재료 및 방법"
- 효율 측정: 문서 #1, 페이지 5 / 섹션 "결과 및 토론"

답변 절차:
1단계 [구조 파악]: 제공된 문서의 구조를 파악하세요 (제목, 섹션, 하위 섹션 등).
2단계 [핵심 추출]: 각 섹션의 핵심 내용을 문서에서 직접 추출하세요.
3단계 [내용 정리]: 주요 발견, 결론, 수치 등을 논리적 순서로 정리하세요.
4단계 [출처 명시]: 모든 내용에 원문 출처를 명시하세요 (페이지/섹션).
5단계 [일관성 확인]: 문서에 명시되지 않은 내용이 포함되지 않았는지 확인하세요.

답변 형식:
## 답변
[핵심 내용 1-2문장 요약]

## 상세 설명
1. [주요 내용 1]
2. [주요 내용 2]
3. [주요 내용 3]

## 참조 정보
- [내용 1]: [출처]
- [내용 2]: [출처]

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

Few-Shot 예시:

[좋은 비교 예시]
질문: "ACRSA와 DABNA1의 차이점은 무엇인가?"
답변:
## 답변
ACRSA와 DABNA1은 둘 다 TADF 재료이지만, ACRSA는 spiro-linked 구조를 가지고 있고, DABNA1은 다른 분자 구조를 가집니다. 발광 효율 측면에서도 차이가 있습니다.

## 상세 설명
문서에 따르면:
- **ACRSA**: spiro-linked TADF molecule 구조, 높은 발광 효율 달성
- **DABNA1**: 다른 분자 구조, 비교 실험에서 사용

## 참조 정보
- ACRSA 구조: 문서 #1, 페이지 3 / 섹션 "재료 특성"
- DABNA1 비교: 문서 #1, 페이지 4 / 섹션 "결과 비교"

답변 절차:
1단계 [대상 식별]: 문서에서 비교 대상들을 식별하세요 (명시적으로 비교된 항목들).
2단계 [특징 추출]: 각 대상의 특징을 문서에서 직접 추출하여 나열하세요.
3단계 [차이점 분석]: 문서에서 언급된 차이점과 공통점을 정확히 인용하여 설명하세요.
4단계 [수치 비교]: 수치적 비교가 문서에 있으면 해당 수치를 그대로 인용하세요.
5단계 [정보 보완]: 직접적인 비교 정보가 없으면, 문서에서 관련 정보를 찾아 제시하세요.

답변 형식:
## 답변
[비교 대상과 주요 차이점 요약]

## 상세 설명
**비교 대상 1**: [특징]
**비교 대상 2**: [특징]
**주요 차이점**: [차이점]
**공통점**: [공통점]

## 참조 정보
- [비교 내용 1]: [출처]
- [비교 내용 2]: [출처]

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

Few-Shot 예시:

[좋은 관계 분석 예시]
질문: "TADF 재료의 구조가 발광 효율에 미치는 영향은?"
답변:
## 답변
문서에 따르면, TADF 재료의 spiro-linked 구조는 분자 간 상호작용을 최소화하여 발광 효율을 향상시킵니다.

## 상세 설명
문서에서 확인된 관계:
1. **구조적 특성**: spiro-linked 구조 → 분자 간 상호작용 감소
2. **효율 향상**: 상호작용 감소 → 높은 발광 효율 달성
3. **메커니즘**: TADF 메커니즘을 통한 에너지 전달 최적화

## 참조 정보
- 구조-효율 관계: 문서 #1, 페이지 3 / 섹션 "재료 설계"
- 메커니즘 설명: 문서 #1, 페이지 4 / 섹션 "작동 원리"

답변 절차:
1단계 [요소 식별]: 문서에서 관련된 요소들을 식별하세요.
2단계 [관계 찾기]: 문서에서 명시된 요소들 간의 관계, 영향, 메커니즘을 찾아 인용하세요.
3단계 [인과관계 분석]: 문서에서 언급된 인과관계나 상관관계를 정확히 설명하세요.
4단계 [패턴 파악]: 문서에서 발견된 경향성이나 패턴을 원문을 인용하며 설명하세요.
5단계 [정보 보완]: 직접적인 관계 정보가 없으면, 문서에서 관련 정보를 찾아 제시하되, 일반적인 추론은 최소화하세요.

답변 형식:
## 답변
[요소 간 관계 요약]

## 상세 설명
**요소 1**: [설명]
**요소 2**: [설명]
**관계/메커니즘**: [관계 설명]
**영향/결과**: [영향 설명]

## 참조 정보
- [관계 설명 1]: [출처]
- [관계 설명 2]: [출처]

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
                file_chunk_counts[file_name] = 1
            else:
                file_chunk_counts[file_name] = 1
            
            seen.add(key)
            results.append((doc, score))
            if len(results) >= k:
                break
        return results

    def _search_candidates(self, question: str) -> List[tuple]:
        """하이브리드(키워드+벡터) → Re-ranker 입력 후보 확보 (Phase 3: 엔티티 boost, Phase 4: BM25+Vector)"""
        try:
            # Phase 4: Hybrid Search (BM25 + Vector) 사용
            if self.enable_hybrid_search and self.hybrid_retriever:
                initial_k = max(self.reranker_initial_k, max(self.top_k * 8, 60))
                print(f"🔍 [Phase 4] Hybrid Search (BM25+Vector) 사용 (top_k={initial_k})")

                # HybridRetriever.search() 결과: List[(doc_dict, score)]
                hybrid_results = self.hybrid_retriever.search(question, top_k=initial_k)

                # Convert to (Document, score) format
                hybrid = []
                for doc_dict, score in hybrid_results:
                    # doc_dict는 {'id', 'content', 'metadata'} 형식
                    doc = Document(
                        page_content=doc_dict['content'],
                        metadata=doc_dict['metadata']
                    )
                    hybrid.append((doc, score))
            else:
                # 기존 하이브리드 검색 (vectorstore의 메서드)
                initial_k = max(self.reranker_initial_k, max(self.top_k * 8, 60))
                hybrid = self.vectorstore.similarity_search_hybrid(
                    question, initial_k=initial_k, top_k=initial_k
                )

            # Phase 3: 엔티티 매칭 청크에 boost 적용
            if hasattr(self.vectorstore, 'entity_index') and self.vectorstore.entity_index:
                hybrid = self._apply_entity_boost(question, hybrid)

            return hybrid
        except Exception as e:
            print(f"⚠️ Hybrid Search 오류: {e}, 폴백 모드로 전환")
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

    def rerank_documents(self, query: str, docs: List[tuple]) -> List[tuple]:
        """Re-ranker를 사용하여 문서 재순위화

        Args:
            query: 검색 쿼리
            docs: (Document, score) 튜플 리스트

        Returns:
            Re-ranking된 (Document, rerank_score) 튜플 리스트
        """
        if not self.use_reranker or not self.reranker:
            print("[INFO] Re-ranker가 비활성화되어 있거나 로드되지 않았습니다. 원본 반환.")
            return docs

        if not docs:
            return docs

        try:
            # Re-ranker 입력 형식으로 변환
            docs_for_rerank = [{
                "document": doc,
                "chunk_id": idx,
                "raw_score": score
            } for idx, (doc, score) in enumerate(docs)]

            # Re-ranking 수행
            reranked = self.reranker.rerank(query, docs_for_rerank, top_k=len(docs_for_rerank))

            # 결과를 (Document, score) 튜플 리스트로 변환
            pairs = [(d["document"], d.get("rerank_score", 0.0)) for d in reranked]

            print(f"[Re-ranker] {len(docs)}개 문서 재순위화 완료")
            return pairs

        except Exception as e:
            print(f"[WARN] Re-ranking 오류: {e}, 원본 반환")
            return docs

    def _semantic_similarity_filter(self, query: str, candidates: List[tuple], threshold: float = 0.5) -> List[tuple]:
        """의미론적 유사도 기반 필터링 (Solution #1)

        쿼리와 각 문서의 임베딩 유사도를 계산하여 threshold 이하 문서 제거

        Args:
            query: 검색 쿼리
            candidates: (Document, score) 튜플 리스트
            threshold: 최소 유사도 임계값 (0~1, 기본값 0.5)

        Returns:
            필터링된 (Document, score) 튜플 리스트
        """
        if not candidates or len(candidates) < 2:
            return candidates

        try:
            # 쿼리 임베딩 생성
            query_embedding = self.vectorstore.embeddings.embed_query(query)

            filtered = []
            removed_count = 0

            for doc, score in candidates:
                # 문서 임베딩 생성
                doc_embedding = self.vectorstore.embeddings.embed_query(doc.page_content)

                # 코사인 유사도 계산
                similarity = np.dot(query_embedding, doc_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
                )

                if similarity >= threshold:
                    filtered.append((doc, score))
                else:
                    removed_count += 1

            # 필터링 결과가 너무 적으면 threshold 완화
            if len(filtered) < max(2, len(candidates) // 3):
                print(f"[WARN] Semantic 필터링 결과 부족, threshold 완화 ({threshold} -> {threshold * 0.7})")
                return self._semantic_similarity_filter(query, candidates, threshold * 0.7)

            if removed_count > 0:
                print(f"[SEMANTIC] 의미론적 유사도 필터링: {removed_count}개 문서 제거 (threshold={threshold:.2f})")

            return filtered

        except Exception as e:
            print(f"[WARN] Semantic 필터링 오류: {e}, 원본 반환")
            return candidates

    def _keyword_based_filter(self, query: str, candidates: List[tuple], min_overlap: float = 0.2) -> List[tuple]:
        """키워드 중복도 기반 필터링 (Solution #2)

        쿼리와 문서의 키워드 중복도를 측정하여 min_overlap 이하 문서 제거

        Args:
            query: 검색 쿼리
            candidates: (Document, score) 튜플 리스트
            min_overlap: 최소 키워드 중복도 (0~1, 기본값 0.2)

        Returns:
            필터링된 (Document, score) 튜플 리스트
        """
        if not candidates or len(candidates) < 2:
            return candidates

        try:
            # 쿼리에서 키워드 추출 (간단한 토큰화)
            query_keywords = set(query.lower().split())
            # 불용어 제거 (간단한 영어 불용어)
            stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'was', 'were'}
            query_keywords = query_keywords - stopwords

            if len(query_keywords) == 0:
                return candidates

            filtered = []
            removed_count = 0

            for doc, score in candidates:
                # 문서에서 키워드 추출
                doc_text = doc.page_content.lower()
                doc_keywords = set(doc_text.split()) - stopwords

                # Jaccard 유사도 계산 (교집합 / 합집합)
                if len(doc_keywords) == 0:
                    overlap = 0
                else:
                    intersection = query_keywords & doc_keywords
                    union = query_keywords | doc_keywords
                    overlap = len(intersection) / len(union) if len(union) > 0 else 0

                if overlap >= min_overlap:
                    filtered.append((doc, score))
                else:
                    removed_count += 1

            # 필터링 결과가 너무 적으면 threshold 완화
            if len(filtered) < max(2, len(candidates) // 3):
                print(f"[WARN] Keyword 필터링 결과 부족, threshold 완화 ({min_overlap} -> {min_overlap * 0.5})")
                return self._keyword_based_filter(query, candidates, min_overlap * 0.5)

            if removed_count > 0:
                print(f"[KEYWORD] 키워드 중복도 필터링: {removed_count}개 문서 제거 (min_overlap={min_overlap:.2f})")

            return filtered

        except Exception as e:
            print(f"[WARN] Keyword 필터링 오류: {e}, 원본 반환")
            return candidates

    def _statistical_outlier_removal(self, candidates: List[tuple], method: str = 'mad', mad_threshold: float = 3.0) -> List[tuple]:
        """통계 기반 이상치 제거 (개선안 3)

        Args:
            candidates: (Document, score) 튜플 리스트
            method: 'mad' (Median Absolute Deviation) 또는 'iqr' (Interquartile Range) 또는 'zscore'
            mad_threshold: MAD 방식에서 사용할 threshold 배수 (기본값: 3.0)

        Returns:
            필터링된 (Document, score) 튜플 리스트
        """
        if not candidates or len(candidates) < 3:
            return candidates

        try:
            scores = [float(score) for _, score in candidates]

            if method == 'mad':
                # MAD (Median Absolute Deviation) - 가장 견고한 방법
                median = np.median(scores)
                mad = np.median([abs(s - median) for s in scores])

                # MAD가 0이면 모든 값이 동일 (필터링 불필요)
                if mad < 1e-9:
                    return candidates

                # 중앙값에서 mad_threshold * MAD 이상 떨어진 것 제거
                threshold = median - mad_threshold * mad
                filtered = [(doc, s) for doc, s in candidates if s >= threshold]

            elif method == 'iqr':
                # IQR (Interquartile Range)
                q1 = np.percentile(scores, 25)
                q3 = np.percentile(scores, 75)
                iqr = q3 - q1

                if iqr < 1e-9:
                    return candidates

                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                filtered = [(doc, s) for doc, s in candidates if lower_bound <= s <= upper_bound]

            elif method == 'zscore':
                # Z-score
                mean = np.mean(scores)
                std = np.std(scores)

                if std < 1e-9:
                    return candidates

                # Z-score가 2 이내인 것만 선택
                filtered = [(doc, s) for doc, s in candidates if abs((s - mean) / std) < 2]

            else:
                return candidates

            # 필터링 결과가 너무 적으면 원본 반환 (최소 3개 또는 원본의 50%)
            min_required = max(3, len(candidates) // 2)
            if len(filtered) < min_required:
                print(f"[WARN] 통계 필터링 결과 부족 ({len(filtered)}개), 원본 유지")
                return candidates

            removed_count = len(candidates) - len(filtered)
            if removed_count > 0:
                print(f"[STAT] 통계 기반 이상치 제거: {removed_count}개 문서 필터링 ({method.upper()} 방식)")

            return filtered

        except Exception as e:
            print(f"[WARN] 통계 필터링 오류: {e}, 원본 반환")
            return candidates

    def _reranker_gap_based_cutoff(self, candidates: List[tuple], min_docs: int = 3, gap_threshold_multiplier: float = 2.0) -> List[tuple]:
        """Re-ranker 점수 Gap 기반 동적 컷오프 (개선안 5)

        주제가 다른 문서는 점수 차이가 크게 나타나는 특성을 이용하여
        가장 큰 점수 gap이 나타나는 지점에서 자동으로 컷오프

        Args:
            candidates: (Document, score) 튜플 리스트 (점수 내림차순 정렬 가정)
            min_docs: 최소 반환 문서 수
            gap_threshold_multiplier: Gap threshold 배수 (기본값: 2.0, 낮을수록 더 엄격하게 필터링)

        Returns:
            필터링된 (Document, score) 튜플 리스트
        """
        if not candidates or len(candidates) <= min_docs:
            return candidates

        try:
            scores = [float(score) for _, score in candidates]

            # 점수 차이(gap) 계산
            gaps = [scores[i] - scores[i+1] for i in range(len(scores)-1)]

            if not gaps:
                return candidates

            # 가장 큰 gap 찾기
            max_gap = max(gaps)
            max_gap_idx = gaps.index(max_gap)

            # Gap의 통계 분석
            mean_gap = statistics.mean(gaps)

            # Gap이 충분히 큰 경우에만 컷오프 적용
            # 조건: Gap이 평균의 gap_threshold_multiplier배 이상 && 컷오프 위치가 min_docs 이상
            if max_gap > mean_gap * gap_threshold_multiplier and max_gap_idx >= min_docs - 1:
                cutoff = max_gap_idx + 1
                filtered = candidates[:cutoff]

                removed_count = len(candidates) - cutoff
                print(f"[CUT] Re-ranker Gap 기반 컷오프: {removed_count}개 문서 필터링")
                print(f"   - Gap 위치: {cutoff}번째 문서 (최대 Gap: {max_gap:.4f}, 평균 Gap: {mean_gap:.4f})")

                return filtered

            # Gap이 충분하지 않으면 원본 반환
            return candidates

        except Exception as e:
            print(f"[WARN] Gap 기반 필터링 오류: {e}, 원본 반환")
            return candidates

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

    def _detect_question_category(self, question: str) -> List[str]:
        """LLM을 사용하여 질문의 카테고리를 감지

        Args:
            question: 사용자 질문

        Returns:
            카테고리 리스트 (technical/business/hr/safety/reference)
            여러 카테고리가 관련될 수 있으므로 리스트 반환
        """
        # Few-shot 프롬프트 구성
        prompt = f"""다음 질문이 어떤 카테고리의 문서를 필요로 하는지 분석하세요.

**카테고리 정의:**
- technical: 과학, 기술, 연구, OLED, 디스플레이, 공학, 학술 내용
- business: 사업, 뉴스, 제품 발표, 마케팅, 시장 분석
- hr: 인사, 교육, 출결 관리, 직원 관리
- safety: 안전, 규정, 위험 관리, 보건
- reference: 일반 참고 자료

**분류 예시:**
1. 질문: "TADF 재료의 양자 효율은?"
   카테고리: technical

2. 질문: "LG디스플레이의 신제품 출시일은?"
   카테고리: business

3. 질문: "출결 시스템 로그인 방법은?"
   카테고리: hr

4. 질문: "작업장 안전 수칙은?"
   카테고리: safety

5. 질문: "분자 구조와 성능의 관계는?"
   카테고리: technical

6. 질문: "HRD-Net 시스템 사용법은?"
   카테고리: hr

**분석 대상:**
질문: {question}

**지시사항:**
1. 질문의 주제와 의도를 분석하여 가장 적합한 카테고리를 선택하세요
2. 여러 카테고리가 관련될 수 있으면 모두 나열하세요 (최대 2개)
3. 응답은 카테고리 이름만 쉼표로 구분하여 출력하세요 (소문자, 추가 설명 없이)
4. 예: "technical" 또는 "technical,business"

카테고리:"""

        try:
            # LLM 호출 (LLM의 invoke 메서드 사용)
            response = self.llm.invoke(prompt)

            # 응답에서 카테고리 추출
            categories_str = response.strip().lower()
            categories = [c.strip() for c in categories_str.split(",")]

            # 유효한 카테고리만 필터링
            valid_categories = ["technical", "business", "hr", "safety", "reference"]
            filtered_categories = [c for c in categories if c in valid_categories]

            if filtered_categories:
                print(f"  ✓ 질문 카테고리 감지: {', '.join(filtered_categories)}")
                return filtered_categories
            else:
                # 유효하지 않은 응답이면 모든 카테고리 반환 (필터링 없음)
                print(f"  ⚠ 알 수 없는 카테고리 응답 '{categories_str}', 필터링 비활성화")
                return []

        except Exception as e:
            print(f"  ⚠ 카테고리 감지 실패 ({e}), 필터링 비활성화")
            return []

    def _filter_by_category(self, results: List[tuple], target_categories: List[str]) -> List[tuple]:
        """카테고리 기반으로 검색 결과 필터링

        Args:
            results: (Document, score) 튜플 리스트
            target_categories: 대상 카테고리 리스트

        Returns:
            필터링된 (Document, score) 튜플 리스트
        """
        # 카테고리가 비어있으면 필터링 하지 않음
        if not target_categories:
            return results

        filtered_results = []
        for doc, score in results:
            doc_category = doc.metadata.get("category", "reference")

            # 문서 카테고리가 대상 카테고리 중 하나와 일치하면 포함
            if doc_category in target_categories:
                filtered_results.append((doc, score))

        # 필터링 결과가 너무 적으면 (3개 미만) 원본 반환 (너무 엄격한 필터링 방지)
        if len(filtered_results) < 3:
            print(f"  ⚠ 카테고리 필터링 결과 부족 ({len(filtered_results)}개), 필터링 비활성화")
            return results

        print(f"  ✓ 카테고리 필터링: {len(results)}개 → {len(filtered_results)}개 (카테고리: {', '.join(target_categories)})")
        return filtered_results

    def _get_context(self, question: str, chat_history: List[Dict] = None) -> str:
        context_start = time.perf_counter()
        # Chat history 캐시 업데이트
        if chat_history:
            self._chat_history_cache = chat_history

        # 카테고리 감지 (Phase 1: 주제 일관성 검증)
        categories = self._detect_question_category(question)

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
                    
                    # 카테고리 필터링 적용 (Phase 1)
                    weighted_results = self._filter_by_category(weighted_results, categories)

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
                context = self._get_context_standard(question, categories)
                elapsed = time.perf_counter() - context_start
                print(f"[Timing] context retrieval (summary, type={query_type}): {elapsed:.2f}s")
                self.top_k = original_top_k
                return context
            except:
                self.top_k = original_top_k
                return ""

        # 기본 검색 (기존 로직)
        context = self._get_context_standard(question, categories)
        elapsed = time.perf_counter() - context_start
        print(f"[Timing] context retrieval (standard, type={query_type}): {elapsed:.2f}s")
        return context

    def _get_context_standard(self, question: str, categories: List[str] = None) -> str:
        """표준 컨텍스트 검색"""
        if categories is None:
            categories = []
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

                    # 카테고리 필터링 적용
                    results = self._filter_by_category(results, categories)

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
                # 카테고리 필터링 적용 (최종 통합)
                all_retrieved_chunks = self._filter_by_category(all_retrieved_chunks, categories)

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

                # 🆕 알고리즘 기반 필터링 파이프라인
                filter_start = time.perf_counter()

                # 1단계: 통계 기반 이상치 제거 (개선안 3)
                pairs = self._statistical_outlier_removal(pairs, method='mad')

                # 2단계: Re-ranker Gap 기반 컷오프 (개선안 5)
                pairs = self._reranker_gap_based_cutoff(pairs, min_docs=self.top_k)

                print(f"[Timing] smart_filtering: {time.perf_counter() - filter_start:.2f}s")

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
            print(f"[Timing] final_rerank (fallback): {time.perf_counter() - rerank_start:.2f}s")

            # 🆕 알고리즘 기반 필터링 파이프라인
            filter_start = time.perf_counter()

            # 1단계: 통계 기반 이상치 제거 (개선안 3)
            pairs = self._statistical_outlier_removal(pairs, method='mad')

            # 2단계: Re-ranker Gap 기반 컷오프 (개선안 5)
            pairs = self._reranker_gap_based_cutoff(pairs, min_docs=self.top_k)

            print(f"[Timing] smart_filtering: {time.perf_counter() - filter_start:.2f}s")

            dedup = self._unique_by_file(pairs, dynamic_top_k)  # 동적 top_k 사용

            # 캐시 저장: 실제 사용된 문서와 점수
            self._last_retrieved_docs = dedup  # [(doc, score), ...]

            docs = [d for d, _ in dedup]
            print(f"[Timing] deduplication: {time.perf_counter() - rerank_start:.2f}s (selected={len(dedup)})")
        else:
            retrieval_start = time.perf_counter()
            pairs = self.vectorstore.similarity_search_with_score(expanded_question, k=max(self.top_k * 8, 40))
            # 도메인 필터링 적용

            # 🆕 알고리즘 기반 필터링 파이프라인
            filter_start = time.perf_counter()

            # 1단계: 통계 기반 이상치 제거 (개선안 3)
            pairs = self._statistical_outlier_removal(pairs, method='mad')

            # 2단계: Re-ranker Gap 기반 컷오프 (개선안 5)
            pairs = self._reranker_gap_based_cutoff(pairs, min_docs=self.top_k)

            print(f"[Timing] smart_filtering: {time.perf_counter() - filter_start:.2f}s")

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
            prompt = f"""당신은 전문 검색 엔지니어입니다. 사용자 쿼리의 검색 효과를 높이기 위해 동의어와 연관어를 생성하세요.

**원본 쿼리**: "{original_query}"

**생성 규칙**:
1. 동의어: 쿼리의 핵심 개념과 동일한 의미의 다른 표현
2. 상위어: 더 일반적인 개념
3. 하위어: 더 구체적인 개념
4. 관련어: 밀접하게 연관된 개념

**Few-shot 예시**:
[예시 1]
원본: "OLED 효율"
동의어: ["유기발광다이오드 효율", "OLED 성능", "발광 효율"]

[예시 2]
원본: "TADF 재료"
동의어: ["열활성화 지연 형광 재료", "thermally activated delayed fluorescence", "TADF 소재"]

[예시 3]
원본: "발광 효율 측정"
동의어: ["광출력 측정", "luminescence efficiency", "발광 성능 평가"]

**출력 형식**: JSON 리스트
{{"synonyms": ["용어1", "용어2", "용어3"], "related_terms": ["관련어1", "관련어2"]}}

**생성**:"""
            
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
                # 응답에서 JSON 부분만 추출 (멀티라인 JSON 지원)
                json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
                if json_match:
                    expansion_data = json.loads(json_match.group())
                    synonyms = expansion_data.get("synonyms", [])
                    related_terms = expansion_data.get("related_terms", [])
                    
                    # 모든 용어를 결합
                    all_terms = synonyms + related_terms
                    if all_terms:
                        expanded_query = f"{original_query} ({', '.join(all_terms)})"
                    else:
                        expanded_query = original_query
                    
                    print(f"🔍 동의어 확장: {original_query} → {expanded_query}")
                    return expanded_query
                else:
                    # JSON 형식이 아닌 경우 텍스트에서 추출
                    lines = response_text.strip().split('\n')
                    all_terms = []
                    for line in lines:
                        line = line.strip().strip('"[],')
                        if line and len(line) > 1 and not line.startswith('동의어') and not line.startswith('관련어'):
                            all_terms.append(line)
                    
                    if all_terms:
                        expanded_query = f"{original_query} ({', '.join(all_terms[:5])})"  # 최대 5개
                    else:
                        expanded_query = original_query
                    
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
            prompt = f"""당신은 RAG 검색 최적화 전문가입니다. 질문 특성을 분석하여 최적의 문서 검색 개수를 결정하세요.

**질문**: "{question}"

**분석 절차**:
1단계 [질문 유형 분류]:
   - 단일 사실 찾기: "무엇", "얼마", "누구", "언제", "어디" (명확한 하나의 답변)
   - 목록 나열: "모두", "전체", "나열", "목록", "제목들" (여러 항목)
   - 비교/분석: "차이", "비교", "vs", "대비", "관계" (다각도 분석)
   - 종합 정보: "요약", "핵심", "개요", "정리" (전체 컨텍스트)
   - 복합 질문: 여러 유형이 혼합된 경우

2단계 [복잡도 평가]:
   - 낮음: 단순한 사실 확인 (3-5개)
   - 중간: 비교/분석, 기본 종합 (10-15개)
   - 높음: 목록 나열, 복합 질문 (20-30개)

**Few-shot 예시**:
[예시 1]
질문: "OLED 효율은 얼마인가?"
유형: 단일 사실 찾기
복잡도: 낮음
추천 개수: 5

[예시 2]
질문: "논문에서 사용한 모든 재료를 나열해주세요."
유형: 목록 나열
복잡도: 높음
추천 개수: 25

[예시 3]
질문: "OLED와 LED의 차이점을 비교해주세요."
유형: 비교/분석
복잡도: 중간
추천 개수: 12

**출력 형식**: 숫자만 출력 (범위: 3-30)

**분석 결과**:"""

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
            prompt = f"""당신은 검색 최적화 전문가입니다. 원본 쿼리를 다양한 관점에서 재작성하여 검색 리콜을 향상시키세요.

**원본 쿼리**: "{original_query}"

**재작성 전략** (각각 1개씩 생성):
1. **기술적 관점**: 구체적인 기술 용어와 방법론 중심
2. **개념적 관점**: 추상적 개념과 이론 중심  
3. **응용 관점**: 실제 사용 사례와 적용 중심
4. **비교 관점**: 비교 분석 질문 형태 (적용 가능한 경우)
5. **문제 해결 관점**: 문제 정의 및 해결책 중심 (적용 가능한 경우)

**Few-shot 예시**:
[원본] "OLED 효율 향상 방법"
[재작성]
1. 기술적: "OLED 발광 효율(luminous efficacy) 개선 기술"
2. 개념적: "유기발광다이오드의 광출력 향상 원리"
3. 응용: "OLED 디스플레이 효율 최적화 사례"
4. 비교: "OLED 효율 비교: 다른 디스플레이 기술 대비"
5. 문제해결: "OLED 효율 저하 원인 및 해결책"

**출력 형식**: JSON 리스트
["쿼리1", "쿼리2", "쿼리3"]

**재작성**:"""
            
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
            context = self._get_context(question, chat_history)
            
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

            # Phase A-2: NotebookLM 스타일 인라인 Citation 추가
            # 캐시된 문서에서 Document 객체 추출
            source_docs = [doc for doc, _ in self._last_retrieved_docs[:self.top_k]]

            if source_docs:
                # Citation 생성 및 답변에 통합
                answer = self._generate_source_citations(answer, source_docs)

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

    # ========================================
    # Phase A-2: Source Citation Enhancement
    # NotebookLM-style inline citations
    # ========================================

    def _split_sentences(self, text: str) -> List[str]:
        """답변을 문장 단위로 분리

        한글/영문 문장 구분 고려:
        - 마침표(.), 물음표(?), 느낌표(!)
        - 단, "Dr.", "Mr.", "etc." 등은 제외

        Args:
            text: 분리할 텍스트

        Returns:
            문장 리스트
        """
        if not text:
            return []

        # 1. 특수 케이스 보호 (Dr., Mr. 등)
        text = re.sub(r'(Dr|Mr|Ms|Mrs|etc)\.', r'\1<DOT>', text)

        # 2. 문장 분리 (., ?, !) - 구분자도 함께 캡처
        sentences = re.split(r'([.!?])\s+', text)

        # 3. 재조합 (구분자와 문장을 다시 합침)
        result = []
        for i in range(0, len(sentences)-1, 2):
            if i+1 < len(sentences):
                sentence = sentences[i] + sentences[i+1]
            else:
                sentence = sentences[i]
            result.append(sentence)

        # 마지막 문장 추가 (구분자 없이 끝나는 경우)
        if len(sentences) % 2 == 1:
            result.append(sentences[-1])

        # 4. <DOT> 복원
        result = [s.replace('<DOT>', '.') for s in result]

        # 5. 빈 문장 제거 및 trim
        return [s.strip() for s in result if s.strip()]

    def _embed_text(self, text: str) -> np.ndarray:
        """텍스트를 임베딩 벡터로 변환

        기존 vectorstore의 임베딩 모델 재사용

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터 (numpy array)
        """
        if not text:
            return np.zeros(1024)  # 기본 차원 (mxbai-embed-large)

        try:
            # VectorStoreManager의 임베딩 모델 사용
            embedding_model = self.vectorstore.embeddings

            # 텍스트 임베딩
            embedding = embedding_model.embed_query(text)
            return np.array(embedding)
        except Exception as e:
            print(f"    ⚠️ 임베딩 실패: {e}")
            return np.zeros(1024)  # 기본 차원

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """코사인 유사도 계산

        Args:
            vec1: 첫 번째 벡터
            vec2: 두 번째 벡터

        Returns:
            코사인 유사도 (0.0 ~ 1.0)
        """
        # 영벡터 체크
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # 코사인 유사도 계산
        similarity = np.dot(vec1, vec2) / (norm1 * norm2)

        # 0~1 범위로 clipping
        return float(max(0.0, min(1.0, similarity)))

    def _format_citation(self, source: Document) -> str:
        """출처를 NotebookLM 스타일로 포맷

        형식: [파일명, p.페이지, 신뢰도: 점수]

        Args:
            source: 출처 문서

        Returns:
            포맷된 출처 문자열
        """
        # 메타데이터 추출
        file_name = source.metadata.get('file_name', 'Unknown')
        page = source.metadata.get('page_number', '?')

        # Document tuple에서 score 추출 시도
        score = source.metadata.get('score', 0.0)

        # 짧은 파일명 추출 (확장자 제거)
        short_name = file_name.rsplit('.', 1)[0]

        # 너무 길면 자르기 (30자 제한)
        if len(short_name) > 30:
            short_name = short_name[:27] + "..."

        # 출처 포맷
        citation = f"[{short_name}, p.{page}]"

        return citation

    def _find_best_source_for_sentence(self, sentence: str, sources: List[Document]) -> Optional[Document]:
        """문장과 가장 관련된 출처 찾기

        방법:
        1. 문장과 각 출처의 코사인 유사도 계산
        2. 가장 유사도가 높은 출처 선택
        3. 유사도가 임계값(0.4) 이하면 None 반환

        Args:
            sentence: 분석할 문장
            sources: 후보 출처 문서들

        Returns:
            가장 관련된 출처 (또는 None)
        """
        if not sources or not sentence:
            return None

        # 1. 문장 임베딩
        sentence_embedding = self._embed_text(sentence)

        # 2. 각 출처와 유사도 계산
        best_source = None
        best_similarity = 0.0

        for source in sources:
            # 출처 텍스트 임베딩 (처음 500자만 - 성능 최적화)
            source_text = source.page_content[:500] if len(source.page_content) > 500 else source.page_content
            source_embedding = self._embed_text(source_text)

            # 코사인 유사도
            similarity = self._cosine_similarity(sentence_embedding, source_embedding)

            # 임계값 체크 (0.4)
            if similarity > best_similarity and similarity > 0.4:
                best_similarity = similarity
                best_source = source

        return best_source

    def _generate_source_citations(self, answer: str, sources: List[Document]) -> str:
        """NotebookLM 스타일 출처 인라인 표시

        Args:
            answer: 생성된 답변
            sources: 사용된 출처 문서들

        Returns:
            출처가 인라인으로 표시된 답변
        """
        if not sources or not answer:
            return answer

        print(f"  📎 Citation 생성 중... (문서 {len(sources)}개)")

        # 1. 답변을 문장 단위로 분리
        sentences = self._split_sentences(answer)
        print(f"    ✓ 문장 분리: {len(sentences)}개")

        # 2. 각 문장에 출처 매칭
        cited_sentences = []
        citation_count = 0

        for i, sentence in enumerate(sentences):
            # 문장이 너무 짧으면 skip (접속사, 전환어 등)
            if len(sentence) < 15:
                cited_sentences.append(sentence)
                continue

            # 문장과 가장 관련된 출처 찾기
            best_source = self._find_best_source_for_sentence(sentence, sources)

            if best_source:
                # 인라인 출처 생성
                citation = self._format_citation(best_source)
                cited_sentence = f"{sentence.strip()} {citation}"
                citation_count += 1
            else:
                cited_sentence = sentence.strip()

            cited_sentences.append(cited_sentence)

        print(f"    ✓ Citation 추가: {citation_count}/{len(sentences)}개 문장")

        return " ".join(cited_sentences)

