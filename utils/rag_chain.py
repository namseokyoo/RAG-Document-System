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
                 max_tokens: int = 4096,  # Phase D: 복잡한 질문/번역 대응
                 top_k: int = 3,
                 use_reranker: bool = True,
                 reranker_model: str = "multilingual-mini",
                 reranker_initial_k: int = 20,
                 enable_synonym_expansion: bool = True,
                 enable_multi_query: bool = True,
                 multi_query_num: int = 3,
                 # Phase 4: Hybrid Search (BM25 + Vector)
                 enable_hybrid_search: bool = True,
                 hybrid_bm25_weight: float = 0.5,
                 # Small-to-Large context size
                 small_to_large_context_size: int = 800,  # 기본값 통일 (300 → 800)
                 # Diversity Penalty (다문서 합성 개선)
                 diversity_penalty: float = 0.0,  # 동일 출처 문서 패널티 (0.0~1.0)
                 diversity_source_key: str = "source",  # 출처 식별 메타데이터 키
                 # Phase 3: File Aggregation (Exhaustive Query 파일 리스트 반환)
                 enable_file_aggregation: bool = False,  # 파일 단위 집계 (기본 비활성화)
                 file_aggregation_strategy: str = "weighted",  # max | mean | weighted | count
                 file_aggregation_top_n: int = 20,  # 반환할 최대 파일 수
                 file_aggregation_min_chunks: int = 1,  # 파일 포함 최소 매칭 청크 수
                 # Phase A-3: Self-Consistency Check
                 enable_self_consistency: bool = False,
                 self_consistency_n: int = 3,
                 # Phase 3.5: Session Context + Intent Detection
                 session_context=None,  # SessionContext 인스턴스
                 enable_session_priority: bool = True,  # 세션 기반 우선순위 활성화
                 session_relevance_threshold: float = 0.7):  # 세션 문서 relevance 임계값
        self.llm_api_type = llm_api_type
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.temperature = temperature
        self.max_tokens = max_tokens  # Phase D
        self.top_k = top_k
        self.vectorstore = vectorstore
        self.vectorstore_manager = vectorstore  # ChatWidget에서 접근용

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

        # Small-to-Large 컨텍스트 크기 설정
        self.small_to_large_context_size = small_to_large_context_size

        # Diversity Penalty 설정 (다문서 합성 개선)
        self.diversity_penalty = diversity_penalty
        self.diversity_source_key = diversity_source_key

        # Phase 3: File Aggregation 설정 (Exhaustive Query 파일 리스트 반환)
        self.enable_file_aggregation = enable_file_aggregation
        self.file_aggregation_strategy = file_aggregation_strategy
        self.file_aggregation_top_n = file_aggregation_top_n
        self.file_aggregation_min_chunks = file_aggregation_min_chunks
        self.file_aggregator = None
        if self.enable_file_aggregation:
            try:
                from utils.file_aggregator import FileAggregator
                self.file_aggregator = FileAggregator(strategy=file_aggregation_strategy)
                logger.info(f"File Aggregation 활성화 (strategy={file_aggregation_strategy}, top_n={file_aggregation_top_n})")
            except Exception as e:
                logger.warning(f"File Aggregation 초기화 실패: {e}, 비활성화됨")
                self.enable_file_aggregation = False
                self.file_aggregator = None

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

        # Phase A-3: Self-Consistency Check 설정
        self.enable_self_consistency = enable_self_consistency
        self.self_consistency_n = max(2, self_consistency_n)  # 최소 2회
        if self.enable_self_consistency:
            logger.info(f"Self-Consistency Check 활성화 (n={self.self_consistency_n})")
        else:
            logger.info("Self-Consistency Check 비활성화 (단일 생성)")

        # Phase 3.5: Session Context + Intent Detection
        self.session_context = session_context
        self.enable_session_priority = enable_session_priority and session_context is not None
        self.session_relevance_threshold = session_relevance_threshold

        # Intent Detector 초기화
        self.intent_detector = None
        if self.enable_session_priority:
            try:
                from utils.intent_detector import IntentDetector
                self.intent_detector = IntentDetector()
                logger.info(f"Session Context + Intent Detection 활성화 (threshold={session_relevance_threshold})")
            except Exception as e:
                logger.warning(f"Intent Detector 초기화 실패: {e}, 비활성화됨")
                self.enable_session_priority = False
                self.intent_detector = None

        # Score-based Filtering 설정 (OpenAI 스타일)
        self.enable_score_filtering = True  # 항상 활성화
        self.score_threshold = 0.5  # 최소 점수 (config에서 설정 가능)
        self.max_num_results = 20  # 최대 문서 수
        self.min_num_results = 3   # 최소 문서 수 (안전망)
        self.enable_adaptive_threshold = True  # 동적 threshold
        self.adaptive_threshold_percentile = 0.6  # top1 대비 비율
        logger.info(f"Score-based Filtering 활성화 (threshold={self.score_threshold}, max={self.max_num_results})")

        # Exhaustive Retrieval 설정 (대량 문서 처리)
        self.enable_exhaustive_retrieval = True  # "모든/전체" 키워드 감지
        self.exhaustive_max_results = 100  # Exhaustive mode 최대 문서 수
        self.enable_single_file_optimization = True  # 단일 파일 최적화
        logger.info(f"Exhaustive Retrieval 활성화 (max={self.exhaustive_max_results})")

        # 도메인 용어 사전 (엔티티 감지용)
        self._domain_lexicon = {
            "TADF", "ACRSA", "DABNA1", "HF", "OLED", "EQE",
            "FRET", "PLQY", "DMAC-TRZ", "AZB-TRZ", "ν-DABNA"
        }
        
        # Retriever 설정 - vectorstore는 VectorStoreManager 인스턴스
        self.retriever = vectorstore.vectorstore.as_retriever(
            search_kwargs={"k": max(self.top_k * 8, 24)}
        )
        
        # 기본 프롬프트 템플릿 (Phase D: Answer Naturalization)
        self.base_prompt_template = """당신은 문서 기반 AI 어시스턴트입니다. 제공된 문서를 바탕으로 정확하고 유용한 답변을 제공하세요.

제공된 문서:
{context}

이전 대화:
{chat_history}

질문:
{question}

---

답변 가이드:

1. **자연스러운 형식**:
   - 섹션 제목 없이 자연스러운 문단으로 작성
   - 질문이 간단하면 짧게 (1-2문장), 복잡하면 여러 문단으로
   - 사용자 의도에 맞게 답변 (번역/요약/설명 등)
   - **수식, 수치, 기호가 있으면 반드시 원문 그대로 정확히 추출하여 포함** (예: R ~ t^(1/3), Pe_C = χ_0 / M_0)

2. **출처 표시**:
   - 파일명은 자연스럽게 언급할 수 있습니다 (예: "Display_1801.pdf에 따르면...")
   - 다만 "출처:", "Source:", "참고:" 같은 명시적 레이블은 사용하지 마세요
   - 번호 citation([1], [2] 등)은 사용하지 마세요
   - 참고문서 목록은 시스템이 자동으로 추가합니다

3. **예시**:

질문: "kFRET 값은?"
답변: 제공된 문서에 따르면, kFRET 값은 약 87.8%입니다. 이는 형광 도펀트와 호스트 간의 에너지 전달 효율을 나타냅니다.

질문: "TADF란 무엇인가?"
답변: TADF(Thermally Activated Delayed Fluorescence)는 삼중항 여기자를 열적으로 활성화하여 일중항으로 재변환하는 발광 메커니즘입니다. 이를 통해 OLED에서 이론적으로 100%의 내부 양자 효율을 달성할 수 있습니다.

질문: "서론 번역해줘"
답변: 하이브리드 형광 OLED는 TADF 보조 호스트와 형광 도펀트를 결합한 새로운 아키텍처입니다. 이 접근법은 TADF의 높은 효율과 형광 도펀트의 우수한 색순도를 동시에 달성합니다.

질문: "Pe_C는 무엇을 나타내나?"
답변: 화학주성 Péclet 수(Pe_C)는 방향성 있는 화학주성과 방향성 없는 활성 확산 사이의 경쟁을 나타냅니다. Pe_C ≡ χ_0 / M_0로 정의됩니다.

질문: "합성 온도는?"
답변: 문서에서는 유기 합성 과정을 설명하고 있지만, 구체적인 합성 온도는 명시되어 있지 않습니다.

4. **중요**:
   - 문서에 근거하지 않은 추측은 하지 마세요. 문서의 내용만을 바탕으로 답변하세요.
   - 수학 공식, 부등식, 관계식이 있으면 반드시 정확히 인용하세요.

답변:"""
        
        # 질문 타입별 프롬프트 템플릿
        self.prompt_templates = {
            "specific_info": """당신은 문서 기반 AI 어시스턴트입니다. 제공된 문서를 바탕으로 정확하고 유용한 답변을 제공하세요.

제공된 문서:
{context}

이전 대화:
{chat_history}

질문:
{question}

---

답변 가이드:

1. **자연스러운 형식**:
   - 섹션 제목 없이 자연스러운 문단으로 작성
   - 구체적인 정보를 간결하게 제시
   - **수치, 이름, 수식, 기호는 원문 그대로 정확히 인용** (과학적 표기법, 지수, 특수문자 포함)

2. **출처 표시**:
   - 파일명은 자연스럽게 언급할 수 있습니다 (예: "Display_1801.pdf에 따르면...")
   - 다만 "출처:", "Source:", "참고:" 같은 명시적 레이블은 사용하지 마세요
   - 번호 citation([1], [2] 등)은 사용하지 마세요
   - 참고문서 목록은 시스템이 자동으로 추가합니다

3. **예시**:

질문: "kFRET 값은?"
답변: 제공된 문서에 따르면, kFRET 값은 1.81×10^7 s^-1입니다.

질문: "사용한 TADF 재료는?"
답변: 논문에서 ACRSA (spiro-linked TADF molecule)를 사용했습니다. 비교 실험을 위해 DABNA1도 언급되어 있습니다.

질문: "Pe_C 정의는?"
답변: Pe_C ≡ χ_0 / M_0로 정의됩니다.

4. **중요**:
   - 문서에 근거하지 않은 추측은 하지 마세요. 문서의 내용만을 바탕으로 답변하세요.
   - 수학 공식이나 수치는 절대 생략하거나 추측하지 마세요.

답변:""",
            
            "summary": """당신은 문서 기반 AI 어시스턴트입니다. 제공된 문서를 바탕으로 정확하고 유용한 답변을 제공하세요.

제공된 문서:
{context}

이전 대화:
{chat_history}

질문:
{question}

---

답변 가이드:

1. **자연스러운 형식**:
   - 섹션 제목 없이 자연스러운 문단으로 작성
   - 요약은 간결하고 핵심만 제시
   - 주요 내용을 논리적 순서로 구성

2. **출처 표시**:
   - 파일명은 자연스럽게 언급할 수 있습니다 (예: "Display_1801.pdf에 따르면...")
   - 다만 "출처:", "Source:", "참고:" 같은 명시적 레이블은 사용하지 마세요
   - 번호 citation([1], [2] 등)은 사용하지 마세요
   - 참고문서 목록은 시스템이 자동으로 추가합니다

3. **예시**:

질문: "핵심 내용 요약해줘"
답변: 이 논문은 TADF 재료를 사용한 OLED의 효율 개선에 관한 연구입니다. ACRSA 기반 디바이스를 통해 높은 발광 효율을 달성했으며, 기존 재료 대비 우수한 성능을 보였습니다.

4. **중요**:
   문서에 근거하지 않은 추측은 하지 마세요. 문서의 내용만을 바탕으로 답변하세요.

답변:""",
            
            "comparison": """당신은 문서 기반 AI 어시스턴트입니다. 제공된 문서를 바탕으로 정확하고 유용한 답변을 제공하세요.

제공된 문서:
{context}

이전 대화:
{chat_history}

질문:
{question}

---

답변 가이드:

1. **자연스러운 형식**:
   - 섹션 제목 없이 자연스러운 문단으로 작성
   - 비교 대상들의 차이점과 공통점을 논리적으로 설명
   - **수식, 수치, 기호가 있으면 반드시 원문 그대로 정확히 추출하여 포함** (예: Pe_C >= Pe_C,crit, R ~ t^(1/3), α <= α_crit)
   - 구체적인 조건, 기준, 임계값을 명시

2. **출처 표시**:
   - 파일명은 자연스럽게 언급할 수 있습니다 (예: "Display_1801.pdf에 따르면...")
   - 다만 "출처:", "Source:", "참고:" 같은 명시적 레이블은 사용하지 마세요
   - 번호 citation([1], [2] 등)은 사용하지 마세요
   - 참고문서 목록은 시스템이 자동으로 추가합니다

3. **예시**:

질문: "ACRSA와 DABNA1의 차이점은?"
답변: ACRSA와 DABNA1은 둘 다 TADF 재료이지만 구조적 차이가 있습니다. ACRSA는 spiro-linked 구조를 가지고 있어 분자 간 상호작용을 최소화하며, 이를 통해 높은 발광 효율을 달성합니다. 반면 DABNA1은 다른 분자 구조를 가지며, 비교 실험에서 ACRSA보다 낮은 효율을 보였습니다.

질문: "MIPS 억제 기준은?"
답변: 화학주성이 MIPS를 억제하기 위해서는 두 가지 기준이 동시에 만족되어야 합니다. 첫째, 환원된 화학주성 Péclet 수가 임계값보다 크거나 같아야 합니다 (Pe_C' >= Pe_C,crit'). 둘째, 유효 집단 확산도 비율 α가 임계값보다 작거나 같아야 합니다 (α <= α_crit).

4. **중요**:
   - 문서에 근거하지 않은 추측은 하지 마세요. 문서의 내용만을 바탕으로 답변하세요.
   - 수학 공식, 부등식, 관계식이 있으면 반드시 정확히 인용하세요.

답변:""",
            
            "relationship": """당신은 문서 기반 AI 어시스턴트입니다. 제공된 문서를 바탕으로 정확하고 유용한 답변을 제공하세요.

제공된 문서:
{context}

이전 대화:
{chat_history}

질문:
{question}

---

답변 가이드:

1. **자연스러운 형식**:
   - 섹션 제목 없이 자연스러운 문단으로 작성
   - 요소들 간의 관계, 인과관계, 메커니즘을 논리적으로 설명
   - 구체적인 영향이나 결과를 명확히 제시
   - **수식이나 수치로 관계가 표현되면 반드시 정확히 포함** (예: J = -M∇φ + χ∇c)

2. **출처 표시**:
   - 파일명은 자연스럽게 언급할 수 있습니다 (예: "Display_1801.pdf에 따르면...")
   - 다만 "출처:", "Source:", "참고:" 같은 명시적 레이블은 사용하지 마세요
   - 번호 citation([1], [2] 등)은 사용하지 마세요
   - 참고문서 목록은 시스템이 자동으로 추가합니다

3. **예시**:

질문: "TADF 재료의 구조가 발광 효율에 미치는 영향은?"
답변: 문서에 따르면, TADF 재료의 spiro-linked 구조는 분자 간 상호작용을 최소화하는 역할을 합니다. 이러한 구조적 특성은 분자들 사이의 에너지 손실을 줄이며, 결과적으로 높은 발광 효율을 달성할 수 있게 합니다. TADF 메커니즘을 통한 에너지 전달이 최적화되면서, 전체적인 디바이스 성능이 향상됩니다.

질문: "화학주성이 입자 플럭스에 미치는 영향은?"
답변: 입자 플럭스(J)는 활성 브라운 운동 항과 화학주성 항의 두 가지로 구성됩니다. 화학주성 항은 J = -χ∇f(c)로 표현되며, 입자가 화학유인물질 구배를 따라 이동하도록 만듭니다.

4. **중요**:
   - 문서에 근거하지 않은 추측은 하지 마세요. 문서의 내용만을 바탕으로 답변하세요.
   - 관계를 나타내는 수식이 있으면 반드시 정확히 인용하세요.

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

        # Question Classifier 초기화 (Quick Wins: 질문 유형별 최적화)
        from utils.question_classifier import create_classifier
        try:
            self.question_classifier = create_classifier(
                llm=self.llm,
                use_llm=True,  # 하이브리드 모드
                verbose=False  # 배포 시 False
            )
            logger.info("Question Classifier 초기화 완료 (하이브리드 모드)")
        except Exception as e:
            logger.warning(f"Question Classifier 초기화 실패: {e}, 기본 파라미터 사용")
            self.question_classifier = None

    def _create_llm(self):
        """API 타입에 따라 적절한 LLM 클라이언트 생성"""
        if self.llm_api_type == "request":
            return RequestLLM(
                base_url=self.llm_base_url,
                model=self.llm_model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,  # Phase D
                timeout=60
            )
        elif self.llm_api_type == "ollama":
            return OllamaLLM(
                base_url=self.llm_base_url,
                model=self.llm_model,
                temperature=self.temperature,
                num_predict=self.max_tokens  # Phase D: Ollama는 num_predict 사용
            )
        elif self.llm_api_type == "openai":
            kwargs = {
                "model": self.llm_model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,  # Phase D
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

    def _search_candidates(self, question: str, search_mode: str = "integrated") -> List[tuple]:
        """
        Hybrid Search 단일 진입점 (BM25 + Vector Search)

        우선순위:
        1. search_with_mode (듀얼 DB 지원) - 최우선, 가장 기능이 풍부
        2. similarity_search_hybrid (폴백) - 단일 DB 하이브리드 검색
        """
        try:
            # Question Classifier가 설정한 값 사용 (동적 조정)
            # 분류기가 없으면 기존 로직 사용
            if hasattr(self, '_last_classification') and self._last_classification:
                initial_k = self.reranker_initial_k  # 분류기가 설정한 값 사용
            else:
                initial_k = max(self.reranker_initial_k, max(self.top_k * 8, 60))  # 기존 로직

            # 우선순위 1: 듀얼 DB 통합 검색 (최신, 가장 기능 풍부)
            if hasattr(self.vectorstore, 'search_with_mode'):
                print(f"[SEARCH] 듀얼 DB 검색 모드: {search_mode}, initial_k={initial_k}")
                hybrid = self.vectorstore.search_with_mode(
                    query=question,
                    search_mode=search_mode,
                    initial_k=initial_k,
                    top_k=initial_k,
                    use_reranker=self.use_reranker,
                    reranker_model=self.reranker_model
                )
            # 우선순위 2: 폴백 - 기본 하이브리드 검색
            else:
                print(f"[SEARCH] 기본 Hybrid Search (BM25+Vector) 사용 (initial_k={initial_k})")
                hybrid = self.vectorstore.similarity_search_hybrid(
                    question, initial_k=initial_k, top_k=initial_k
                )

            # Phase 3: 엔티티 매칭 청크에 boost 적용
            if hasattr(self.vectorstore, 'entity_index') and self.vectorstore.entity_index:
                hybrid = self._apply_entity_boost(question, hybrid)

            return hybrid
        except Exception as e:
            print(f"[WARN] Hybrid Search 오류: {e}, 폴백 모드로 전환")
            # 폴백: 벡터 검색 (분류기 설정값 사용)
            if hasattr(self, '_last_classification') and self._last_classification:
                fallback_k = self.reranker_initial_k  # 분류기가 설정한 값
            else:
                fallback_k = max(self.reranker_initial_k, 60)  # 기존 로직
            return self.vectorstore.similarity_search_with_score(question, k=fallback_k)
    
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

            # Re-ranking 수행 (diversity penalty 포함)
            reranked = self.reranker.rerank(
                query,
                docs_for_rerank,
                top_k=len(docs_for_rerank),
                diversity_penalty=self.diversity_penalty,
                diversity_source_key=self.diversity_source_key
            )

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

    def _score_based_filtering(self, candidates: List[tuple], question: str = "") -> List[tuple]:
        """OpenAI 스타일 Score-based Filtering (점수 + 개수 하이브리드 + Adaptive)

        Args:
            candidates: (Document, score) 튜플 리스트 (점수 내림차순 정렬 가정)
            question: 사용자 질문 (adaptive max results 계산용)

        Returns:
            필터링된 (Document, score) 튜플 리스트
        """
        if not self.enable_score_filtering or not candidates:
            return candidates

        try:
            # 1단계: 동적 threshold 계산 (활성화된 경우)
            threshold = self.score_threshold

            if self.enable_adaptive_threshold and len(candidates) > 0:
                scores = [float(score) for _, score in candidates]
                top_score = scores[0]

                # 동적 threshold: top1의 N% 또는 고정 threshold 중 큰 값
                adaptive_threshold = top_score * self.adaptive_threshold_percentile
                threshold = max(self.score_threshold, adaptive_threshold)

                print(f"[SCORE] 동적 Threshold: {threshold:.4f} (top1={top_score:.4f} × {self.adaptive_threshold_percentile})")
            else:
                print(f"[SCORE] 고정 Threshold: {threshold:.4f}")

            # 2단계: 점수 기반 필터링
            filtered = []
            for doc, score in candidates:
                if score >= threshold:
                    filtered.append((doc, score))
                else:
                    # 점수가 threshold 아래로 떨어지면 중단 (내림차순 가정)
                    break

            # 3단계: Adaptive 최대 개수 계산 (질문 유형 기반)
            if question:
                max_results = self._adaptive_max_results(question, candidates)
            else:
                max_results = self.max_num_results

            # 4단계: 최대 개수 제한
            if len(filtered) > max_results:
                removed = len(filtered) - max_results
                print(f"[SCORE] 최대 개수 제한: {removed}개 제거 (max={max_results})")
                filtered = filtered[:max_results]

            # 5단계: 최소 개수 보장 (안전망)
            if len(filtered) < self.min_num_results and len(candidates) >= self.min_num_results:
                print(f"[SCORE] 최소 개수 보장: threshold 무시하고 {self.min_num_results}개 선택")
                filtered = candidates[:self.min_num_results]

            # 6단계: 결과 로깅
            removed_count = len(candidates) - len(filtered)
            if removed_count > 0:
                print(f"[SCORE] Score-based 필터링: {removed_count}개 문서 제거 (threshold={threshold:.4f})")
                print(f"       최종 선택: {len(filtered)}개 문서 (점수 범위: {filtered[0][1]:.4f} ~ {filtered[-1][1]:.4f})")

            return filtered

        except Exception as e:
            print(f"[WARN] Score-based 필터링 오류: {e}, 원본 반환")
            import traceback
            traceback.print_exc()
            return candidates

    def _detect_exhaustive_query(self, question: str) -> bool:
        """전체 문서가 필요한 쿼리인지 감지 (Option 1: 키워드 기반)

        Args:
            question: 사용자 질문

        Returns:
            True if exhaustive retrieval needed
        """
        if not self.enable_exhaustive_retrieval:
            return False

        # 우선순위 높은 키워드 (명확한 전체 요구)
        high_priority_keywords = [
            "모든 ", "전체 ", "모두 ", "각각의 ", "전부 ",
            "모든페이지", "모든슬라이드", "전체목록", "전체내용",
            "모든제목", "각페이지", "각슬라이드"
        ]

        # 중간 우선순위 키워드 (문맥상 전체 의미)
        medium_priority_keywords = [
            "전체적으로", "리스트", "목록", "각각"
        ]

        question_lower = question.lower()

        # 고우선순위 키워드 체크 (공백 포함으로 오탐 방지)
        for keyword in high_priority_keywords:
            if keyword in question_lower:
                print(f"[EXHAUSTIVE] 키워드 감지: '{keyword}' → 대량 문서 모드")
                return True

        # 중간 우선순위 키워드 체크 (문맥 확인)
        for keyword in medium_priority_keywords:
            # 키워드 앞뒤로 공백이 있거나, 시작/끝에 있는 경우 매칭
            padded_question = f" {question_lower} "
            if f" {keyword} " in padded_question or f" {keyword}" in padded_question:
                print(f"[EXHAUSTIVE] 키워드 감지: '{keyword}' → 대량 문서 모드")
                return True

        return False

    def _is_single_file_query(self, question: str, candidates: List[tuple]) -> bool:
        """단일 파일에 대한 전체 조회인지 판단 (Option 2: 파일 기반)

        Args:
            question: 사용자 질문
            candidates: 검색된 문서 후보

        Returns:
            True if single file complete retrieval needed
        """
        if not self.enable_single_file_optimization or not candidates:
            return False

        # "이 슬라이드", "해당 파일", "이 문서" 등의 키워드
        file_specific_keywords = [
            "이 슬라이드", "해당 슬라이드", "현재 슬라이드",
            "이 파일", "해당 파일", "현재 파일",
            "이 문서", "해당 문서", "현재 문서",
            "이 논문", "해당 논문"
        ]

        has_file_keyword = any(kw in question for kw in file_specific_keywords)

        # 모든 후보가 같은 파일에서 온 것인지 확인
        file_names = set()
        for doc, _ in candidates:
            file_name = doc.metadata.get("file_name", "")
            if file_name:
                file_names.add(file_name)

        is_single_file = len(file_names) == 1

        if has_file_keyword and is_single_file:
            file_name = list(file_names)[0]
            print(f"[SINGLE_FILE] 단일 파일 전체 조회 감지: '{file_name}'")
            return True

        return False

    def _count_file_chunks(self, candidates: List[tuple], file_name: str = None) -> int:
        """특정 파일의 총 청크 수 계산

        Args:
            candidates: 검색된 문서 후보
            file_name: 파일명 (None이면 첫 번째 문서의 파일)

        Returns:
            청크 수
        """
        if not candidates:
            return 0

        if file_name is None:
            file_name = candidates[0][0].metadata.get("file_name", "")

        chunk_count = sum(
            1 for doc, _ in candidates
            if doc.metadata.get("file_name", "") == file_name
        )

        return chunk_count

    def _adaptive_max_results(self, question: str, candidates: List[tuple]) -> int:
        """질문 유형에 따라 동적으로 최대 문서 수 결정 (3단계 폴백 전략)

        Args:
            question: 사용자 질문
            candidates: 검색된 문서 후보

        Returns:
            최대 문서 수
        """
        # 안전장치: candidates가 비어있으면 기본값 반환
        if not candidates:
            return self.max_num_results

        # 우선순위 1: Exhaustive query 감지 (Option 1)
        if self._detect_exhaustive_query(question):
            max_results = min(self.exhaustive_max_results, len(candidates))
            # 최소값 보장 (exhaustive이지만 후보가 적을 수 있음)
            max_results = max(max_results, self.min_num_results)
            print(f"[ADAPTIVE] Exhaustive mode → max={max_results}")
            return max_results

        # 우선순위 2: 단일 파일 전체 조회 (Option 2)
        if self._is_single_file_query(question, candidates):
            file_chunks = self._count_file_chunks(candidates)
            max_results = min(file_chunks, self.exhaustive_max_results)
            # 최소값 보장
            max_results = max(max_results, self.min_num_results)
            print(f"[ADAPTIVE] Single file mode → max={max_results} (file chunks)")
            return max_results

        # 우선순위 3: Question Classifier 결과 활용
        if hasattr(self, '_last_classification') and self._last_classification:
            # Question Classifier의 max_results 사용
            max_results = self._last_classification.get('max_results', self.max_num_results)
            print(f"[ADAPTIVE] Classifier mode → max={max_results} (type={self._last_classification.get('type', 'unknown')})")
            return max_results

        # 우선순위 4: determine_optimal_top_k 결과 활용 (폴백)
        if hasattr(self, '_last_dynamic_top_k') and self._last_dynamic_top_k:
            max_results = self._last_dynamic_top_k
            print(f"[ADAPTIVE] LLM dynamic mode → max={max_results}")
            return max_results

        # 최종 폴백: 기본값 사용
        print(f"[ADAPTIVE] Default mode → max={self.max_num_results}")
        return self.max_num_results

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

    def _is_exhaustive_query(self, question: str) -> bool:
        """Exhaustive query 감지 (파일 리스트 요청 감지)

        Exhaustive query: "모든 논문", "전체 문서", "모든 파일" 등 대량 문서 요청

        Returns:
            bool: Exhaustive query 여부
        """
        question_lower = question.lower()

        # Exhaustive 키워드 (한글 + 영문)
        exhaustive_keywords = [
            # 한글
            "모든", "전체", "모두", "전부", "모음",
            "모든 문서", "모든 논문", "모든 파일", "모든 자료",
            "전체 문서", "전체 논문", "전체 파일",
            "몇 개", "몇 편", "몇 건",
            "개수", "수량",
            "찾아줘", "찾아주", "찾아", "검색",
            "리스트", "목록", "list",
            # 영문
            "all", "every", "entire", "whole",
            "how many", "count", "number of",
            "list", "find all", "show all"
        ]

        # 조합 패턴 (강한 신호)
        strong_patterns = [
            ("모든", "논문"), ("모든", "문서"), ("모든", "파일"),
            ("전체", "논문"), ("전체", "문서"), ("전체", "파일"),
            ("몇", "개"), ("몇", "편"), ("몇", "건"),
            ("list", "all"), ("find", "all"), ("show", "all")
        ]

        # 강한 신호 우선 확인
        for pattern in strong_patterns:
            if all(keyword in question_lower for keyword in pattern):
                logger.info(f"[Exhaustive Query] 강한 패턴 감지: {pattern}")
                return True

        # 단일 키워드 확인
        for keyword in exhaustive_keywords:
            if keyword in question_lower:
                logger.info(f"[Exhaustive Query] 키워드 감지: {keyword}")
                return True

        return False

    def _handle_exhaustive_query(self, question: str, formatted_history: str) -> Dict[str, Any]:
        """Exhaustive query 처리 → 파일 리스트 반환

        Args:
            question: 사용자 질문
            formatted_history: 포맷된 대화 히스토리

        Returns:
            {
                "answer": str (Markdown table 형식 파일 리스트),
                "sources": list (빈 리스트, 파일 리스트이므로 개별 출처 없음),
                "confidence": float (항상 1.0, 검색 결과 신뢰도),
                "success": bool,
                "query_type": "exhaustive"  # 응답 타입 구분
            }
        """
        try:
            logger.info(f"[Exhaustive Query] 파일 리스트 생성 시작: {question}")

            # 1. 대량 검색 (k=100)
            logger.info(f"[Step 1] Hybrid Search (k=100)...")
            if self.enable_hybrid_search and self.hybrid_retriever:
                # Hybrid Search (BM25 + Vector)
                chunks_with_scores = self.hybrid_retriever.search(
                    query=question,
                    top_k=100
                )
            else:
                # 기본 Vector Search
                chunks_with_scores = self.vectorstore.vectorstore.similarity_search_with_score(
                    query=question,
                    k=100
                )

            logger.info(f"  검색된 청크 수: {len(chunks_with_scores)}")

            if not chunks_with_scores:
                return {
                    "answer": "검색 결과가 없습니다.",
                    "sources": [],
                    "confidence": 0.0,
                    "success": False,
                    "query_type": "exhaustive"
                }

            # 2. Reranking (reranker 활성화 시)
            if self.use_reranker and self.reranker:
                logger.info(f"[Step 2] Reranking...")
                chunks = [doc for doc, _ in chunks_with_scores]
                reranked_docs = self.reranker.rerank(
                    query=question,
                    documents=chunks,
                    top_k=100,  # 전체 rerank
                    diversity_penalty=self.diversity_penalty,
                    diversity_source_key=self.diversity_source_key
                )

                # Reranked docs are Document objects with scores in metadata
                # FileAggregator just needs Document list, so use directly
                chunks = reranked_docs

                logger.info(f"  Reranking 완료: {len(chunks)}개 청크")
            else:
                # No reranking, just extract documents from chunks_with_scores
                chunks = [doc for doc, _ in chunks_with_scores]

            # 3. File Aggregation
            logger.info(f"[Step 3] File Aggregation...")

            file_results = self.file_aggregator.aggregate_chunks_to_files(
                chunks,
                top_n=self.file_aggregation_top_n,
                min_chunks=self.file_aggregation_min_chunks
            )

            logger.info(f"  집계된 파일 수: {len(file_results)}")

            # 4. Format as Markdown table
            answer = self._format_file_list_response(file_results, question)

            return {
                "answer": answer,
                "sources": [],  # 파일 리스트이므로 개별 출처 없음
                "confidence": 1.0,  # 검색 결과 신뢰도
                "success": True,
                "query_type": "exhaustive"
            }

        except Exception as e:
            logger.error(f"[Exhaustive Query] 오류: {e}")
            import traceback
            traceback.print_exc()

            return {
                "answer": f"파일 리스트 생성 중 오류가 발생했습니다: {str(e)}",
                "sources": [],
                "confidence": 0.0,
                "success": False,
                "query_type": "exhaustive"
            }

    def _format_file_list_response(self, file_results: List[Dict], question: str) -> str:
        """파일 리스트를 Markdown table로 포맷

        Args:
            file_results: FileAggregator.aggregate_chunks_to_files() 결과
            question: 사용자 질문 (헤더에 표시)

        Returns:
            Markdown table 형식 문자열
        """
        if not file_results:
            return "검색 결과가 없습니다."

        # 헤더
        lines = [
            f"## 검색 결과: \"{question}\"",
            f"",
            f"총 **{len(file_results)}개** 파일이 발견되었습니다.",
            f"",
            "| 순위 | 파일명 | 관련도 | 매칭 청크 수 |",
            "|------|--------|--------|--------------|"
        ]

        # 파일 리스트
        for i, file_info in enumerate(file_results, 1):
            file_name = file_info['file_name']

            # 파일명만 추출 (경로 제거)
            if '\\' in file_name:
                file_name = file_name.split('\\')[-1]
            elif '/' in file_name:
                file_name = file_name.split('/')[-1]

            score = file_info['relevance_score']
            num_chunks = file_info['num_matching_chunks']

            # 관련도를 별표로 시각화 (0.0~1.0 → 0~5 stars)
            stars = int(score * 5)
            stars_str = "⭐" * stars if stars > 0 else "-"

            lines.append(
                f"| {i} | {file_name} | {score:.3f} {stars_str} | {num_chunks} |"
            )

        # 푸터 (안내 메시지)
        lines.extend([
            "",
            "---",
            "**안내**: 관련도가 높은 순서로 정렬되었습니다. 특정 파일에 대한 상세 정보가 필요하면 파일명을 포함하여 질문해주세요.",
            ""
        ])

        return "\n".join(lines)

    def _detect_question_category(self, question: str) -> List[str]:
        """LLM을 사용하여 질문의 카테고리를 감지

        Args:
            question: 사용자 질문

        Returns:
            카테고리 리스트 (technical/business/hr/safety/reference)
            여러 카테고리가 관련될 수 있으므로 리스트 반환
        """
        # TEMPORARY: 카테고리 필터링 비활성화
        print(f"  [INFO] 카테고리 필터링 비활성화됨")
        return []

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
                print(f"  [OK] 질문 카테고리 감지: {', '.join(filtered_categories)}")
                return filtered_categories
            else:
                # 유효하지 않은 응답이면 모든 카테고리 반환 (필터링 없음)
                print(f"  [WARN] 알 수 없는 카테고리 응답 '{categories_str}', 필터링 비활성화")
                return []

        except Exception as e:
            print(f"  [WARN] 카테고리 감지 실패 ({e}), 필터링 비활성화")
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
            print(f"  [WARN] 카테고리 필터링 결과 부족 ({len(filtered_results)}개), 필터링 비활성화")
            return results

        print(f"  [OK] 카테고리 필터링: {len(results)}개 → {len(filtered_results)}개 (카테고리: {', '.join(target_categories)})")
        return filtered_results

    def _extract_file_mention(self, question: str) -> Optional[str]:
        """질문에서 @파일명 패턴 추출

        Args:
            question: 사용자 질문

        Returns:
            멘션된 파일명 (없으면 None)

        Examples:
            "@paper.pdf의 결론은?" → "paper.pdf"
            "@OLED연구.docx에서" → "OLED연구.docx"
            "일반 질문" → None
        """
        import re

        # @파일명 패턴: @ 뒤에 파일명 (공백, 한글, 영문, 숫자, 특수문자 허용)
        # 파일 확장자까지 포함 (.pdf, .docx, .txt 등)
        pattern = r'@([^\s]+\.(?:pdf|docx?|txt|pptx?|xlsx?|hwp|md|py|json|csv))\b'

        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            filename = match.group(1)
            return filename

        return None

    def _get_context_from_mentioned_file(self, filename: str, question: str, context_start: float) -> str:
        """멘션된 파일의 모든 청크를 컨텍스트로 반환

        Args:
            filename: 멘션된 파일명
            question: 원본 질문
            context_start: 타이밍 측정용 시작 시간

        Returns:
            파일의 모든 청크를 포함한 컨텍스트 문자열
        """
        try:
            # VectorStore에서 해당 파일의 모든 청크 검색
            # metadata의 'source' 필드에 파일명이 포함되어 있음
            all_chunks = []

            if hasattr(self.vectorstore, 'get_all_documents'):
                # 모든 문서 가져오기 (VectorStoreManager에 메서드가 있다면)
                all_docs = self.vectorstore.get_all_documents()
            else:
                # 폴백: 더미 검색으로 많은 문서 가져오기
                all_docs = self.vectorstore.similarity_search("", k=10000)

            # 파일명 매칭 (경로 포함 여부 고려)
            for doc in all_docs:
                source = doc.metadata.get('source', '')
                # 경로에서 파일명만 추출하여 비교
                source_filename = source.split('\\')[-1].split('/')[-1]

                if source_filename == filename or source.endswith(filename):
                    all_chunks.append(doc)

            if not all_chunks:
                logger.warning(f"📎 파일 '{filename}' 청크를 찾을 수 없습니다.")
                print(f"[FILE MENTION] 파일 '{filename}' 없음 → 일반 검색으로 폴백")
                # 폴백: 일반 검색 수행
                return self._get_context_standard(question, categories=[], search_mode="integrated")

            # 청크 개수 제한 (너무 많으면 LLM 컨텍스트 초과)
            max_chunks = 100
            if len(all_chunks) > max_chunks:
                logger.warning(f"📎 파일 청크가 {len(all_chunks)}개로 많아 상위 {max_chunks}개만 사용")

                # Re-ranker로 관련성 높은 청크 선택
                if self.use_reranker and self.reranker:
                    docs_for_rerank = [{
                        "page_content": doc.page_content,
                        "metadata": doc.metadata,
                        "vector_score": 1.0,
                        "document": doc
                    } for doc in all_chunks]

                    reranked = self.reranker.rerank(question, docs_for_rerank, top_k=max_chunks)
                    all_chunks = [d["document"] for d in reranked]
                else:
                    # Re-ranker 없으면 앞에서부터
                    all_chunks = all_chunks[:max_chunks]

            # 캐시 저장
            self._last_retrieved_docs = [(doc, 1.0) for doc in all_chunks]

            elapsed = time.perf_counter() - context_start
            print(f"[FILE MENTION] 파일 '{filename}': {len(all_chunks)}개 청크 사용 ({elapsed:.2f}s)")

            return self._format_docs(all_chunks)

        except Exception as e:
            logger.error(f"📎 파일 멘션 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            # 폴백: 일반 검색
            return self._get_context_standard(question, categories=[], search_mode="integrated")

    def _get_context(self, question: str, chat_history: List[Dict] = None, search_mode: str = "integrated") -> str:
        context_start = time.perf_counter()

        # ========== File Mention 감지: @파일명 패턴 ==========
        mentioned_file = self._extract_file_mention(question)
        if mentioned_file:
            logger.info(f"📎 파일 멘션 감지: {mentioned_file}")
            return self._get_context_from_mentioned_file(mentioned_file, question, context_start)

        # ========== Phase 3.5: Intent Detection + Session Context ==========
        if self.enable_session_priority and self.intent_detector:
            # 2순위: Intent Detection (filename.pdf 명시적 언급)
            intent_result = self.intent_detector.detect_document_reference(question)

            if intent_result['has_reference']:
                # 파일명 명시적 언급 있음
                if intent_result['mentioned_filename']:
                    logger.info(f"📄 Intent: 파일명 명시 - {intent_result['mentioned_filename']}")
                    return self._get_context_from_mentioned_file(
                        intent_result['mentioned_filename'],
                        question,
                        context_start
                    )

                # 문서 참조 패턴 감지 ("이 문서", "방금 올린 파일" 등)
                elif intent_result['confidence'] >= 0.7:
                    # 세션 활성화 여부 확인
                    if self.session_context and self.session_context.is_active():
                        active_doc_ids = self.session_context.get_active_document_ids()
                        logger.info(f"📎 Intent: 문서 참조 감지 (신뢰도={intent_result['confidence']:.2f}), "
                                  f"세션 문서={len(active_doc_ids)}개")

                        # 세션 문서 내에서 검색
                        try:
                            context = self._get_context_from_document_ids(
                                active_doc_ids,
                                question,
                                context_start
                            )
                            if context:
                                return context
                        except Exception as e:
                            logger.warning(f"Intent-based 검색 실패: {e}, 일반 검색으로 진행")

            # 3순위: Session Context (자동 - 업로드 5분 이내, 참조 패턴 없음)
            elif self.session_context and self.session_context.is_active():
                active_doc_ids = self.session_context.get_active_document_ids()
                most_recent = self.session_context.get_most_recent_document()

                logger.debug(f"🕒 Session: 활성 문서 {len(active_doc_ids)}개 "
                           f"(최근: {most_recent.file_name if most_recent else 'None'})")

                # 세션 문서 내에서 검색 (relevance threshold 적용)
                try:
                    context = self._get_context_from_document_ids(
                        active_doc_ids,
                        question,
                        context_start,
                        apply_threshold=True
                    )
                    if context:
                        logger.info(f"✅ Session 문서에서 관련 내용 발견, 우선 사용")
                        return context
                    else:
                        logger.debug(f"Session 문서 relevance 부족 (threshold={self.session_relevance_threshold}), "
                                   f"전체 DB 검색으로 진행")
                except Exception as e:
                    logger.warning(f"Session-based 검색 실패: {e}, 일반 검색으로 진행")
        # ===================================================================

        # ========== Quick Wins: 질문 분류 및 파라미터 최적화 ==========
        if hasattr(self, 'question_classifier') and self.question_classifier:
            try:
                classification = self.question_classifier.classify(question)

                # 분류 결과 저장 (UI 표시용)
                self._last_classification = classification

                # 로깅 (verbose 모드에서만 상세 출력)
                logger.info(f"🎯 질문 유형: {classification['type']} "
                           f"(신뢰도: {classification['confidence']:.0%}, "
                           f"방법: {classification['method']})")

                # 파라미터 동적 조정
                self.enable_multi_query = classification['multi_query']
                self.max_num_results = classification['max_results']
                self.reranker_initial_k = classification['reranker_k']
                self.max_tokens = classification['max_tokens']

                # LLM max_tokens 설정 (API 타입별)
                if hasattr(self.llm, 'max_tokens'):
                    self.llm.max_tokens = classification['max_tokens']
                elif hasattr(self.llm, 'num_predict'):
                    # Ollama의 경우
                    self.llm.num_predict = classification['max_tokens']

                logger.info(f"⚙️  최적화: Multi-Query={classification['multi_query']}, "
                           f"MaxResults={classification['max_results']}, "
                           f"RerankK={classification['reranker_k']}, "
                           f"MaxTokens={classification['max_tokens']}")
            except Exception as e:
                logger.warning(f"질문 분류 실패, 기본 파라미터 사용: {e}")
                self._last_classification = None
        else:
            self._last_classification = None
        # ================================================================

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
                    question, top_k=20, max_parents=5, partial_context_size=self.small_to_large_context_size
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
                    print(f"[SEARCH] 구체적 정보 추출 모드: Small-to-Large 검색 (쿼리 타입: {query_type})")
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
                context = self._get_context_standard(question, categories, search_mode)
                elapsed = time.perf_counter() - context_start
                print(f"[Timing] context retrieval (summary, type={query_type}): {elapsed:.2f}s")
                self.top_k = original_top_k
                return context
            except:
                self.top_k = original_top_k
                return ""

        # 기본 검색 (기존 로직)
        context = self._get_context_standard(question, categories, search_mode)
        elapsed = time.perf_counter() - context_start
        print(f"[Timing] context retrieval (standard, type={query_type}): {elapsed:.2f}s")
        return context

    def _get_context_standard(self, question: str, categories: List[str] = None, search_mode: str = "integrated") -> str:
        """표준 컨텍스트 검색"""
        if categories is None:
            categories = []
        overall_start = time.perf_counter()
        
        # 🆕 동적 top_k 결정 (질문 특성 분석) - Question Classifier가 없을 때 폴백으로 사용
        if not hasattr(self, '_last_classification') or not self._last_classification:
            dynamic_top_k = self.determine_optimal_top_k(question)
            self._last_dynamic_top_k = dynamic_top_k  # 저장
            print(f"[SEARCH] 질문 특성 분석 (LLM): top_k = {dynamic_top_k} (기본: {self.top_k})")
        else:
            # Question Classifier 사용 중이면 skip
            self._last_dynamic_top_k = None
            print(f"[SEARCH] 질문 특성 분석: Question Classifier 사용 중")
        
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
                        base = self._search_candidates(query, search_mode=search_mode)
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
                        # 듀얼 DB 지원: search_with_mode 사용 가능 시 사용
                        if hasattr(self.vectorstore, 'search_with_mode'):
                            temp_results = self.vectorstore.search_with_mode(
                                query=query,
                                search_mode=search_mode,
                                initial_k=max(self.top_k * 3, 15),
                                top_k=max(self.top_k * 3, 15),
                                use_reranker=False,  # 이미 reranker는 외부에서 처리
                                reranker_model=self.reranker_model
                            )
                            results = temp_results if temp_results else []
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

                # 🆕 Score-based 필터링 파이프라인 (OpenAI 스타일 + Adaptive)
                filter_start = time.perf_counter()

                # 1단계: 통계 기반 이상치 제거 (이상 점수 제거)
                pairs = self._statistical_outlier_removal(pairs, method='mad')

                # 2단계: Score-based filtering (점수 + 개수 하이브리드 + Adaptive)
                pairs = self._score_based_filtering(pairs, question=question)

                print(f"[Timing] score_filtering: {time.perf_counter() - filter_start:.2f}s")

                # 중복 제거 (파일 단위)
                dedup = self._unique_by_file(pairs, len(pairs))  # score filtering에서 이미 개수 제한
                self._last_retrieved_docs = dedup
                docs = [d for d, _ in dedup]
                print(f"[Timing] context_standard total: {time.perf_counter() - overall_start:.2f}s (mode=multi-query, docs={len(docs)})")
                return self._format_docs(docs)
        
        # 폴백: 단일 쿼리 검색 (동의어 확장 포함)
        syn_start = time.perf_counter()
        expanded_question = self.expand_query_with_synonyms(question)
        print(f"[Timing] synonym_expand: {time.perf_counter() - syn_start:.2f}s")
        
        if self.use_reranker:
            retrieval_start = time.perf_counter()
            base = self._search_candidates(expanded_question, search_mode=search_mode)
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

            # 🆕 Score-based 필터링 파이프라인 (OpenAI 스타일 + Adaptive)
            filter_start = time.perf_counter()

            # 1단계: 통계 기반 이상치 제거 (이상 점수 제거)
            pairs = self._statistical_outlier_removal(pairs, method='mad')

            # 2단계: Score-based filtering (점수 + 개수 하이브리드 + Adaptive)
            pairs = self._score_based_filtering(pairs, question=question)

            print(f"[Timing] score_filtering: {time.perf_counter() - filter_start:.2f}s")

            # 중복 제거 (파일 단위)
            dedup = self._unique_by_file(pairs, len(pairs))  # score filtering에서 이미 개수 제한

            # 캐시 저장: 실제 사용된 문서와 점수
            self._last_retrieved_docs = dedup  # [(doc, score), ...]

            docs = [d for d, _ in dedup]
            print(f"[Timing] deduplication: {time.perf_counter() - rerank_start:.2f}s (selected={len(dedup)})")
        else:
            retrieval_start = time.perf_counter()
            # 듀얼 DB 지원: search_with_mode 사용 가능 시 사용
            if hasattr(self.vectorstore, 'search_with_mode'):
                pairs = self.vectorstore.search_with_mode(
                    query=expanded_question,
                    search_mode=search_mode,
                    initial_k=max(self.top_k * 8, 40),
                    top_k=max(self.top_k * 8, 40),
                    use_reranker=False,
                    reranker_model=self.reranker_model
                )
                if not pairs:
                    pairs = []
            else:
                pairs = self.vectorstore.similarity_search_with_score(expanded_question, k=max(self.top_k * 8, 40))
            # 도메인 필터링 적용

            # 🆕 Score-based 필터링 파이프라인 (OpenAI 스타일 + Adaptive)
            filter_start = time.perf_counter()

            # 1단계: 통계 기반 이상치 제거 (이상 점수 제거)
            pairs = self._statistical_outlier_removal(pairs, method='mad')

            # 2단계: Score-based filtering (점수 + 개수 하이브리드 + Adaptive)
            pairs = self._score_based_filtering(pairs, question=question)

            print(f"[Timing] score_filtering: {time.perf_counter() - filter_start:.2f}s")

            # 중복 제거 (파일 단위)
            dedup = self._unique_by_file(pairs, len(pairs))  # score filtering에서 이미 개수 제한

            # 캐시 저장
            self._last_retrieved_docs = dedup

            docs = [d for d, _ in dedup]
            print(f"[Timing] candidate_retrieval (vector fallback): {time.perf_counter() - retrieval_start:.2f}s (selected={len(dedup)})")

        # dynamic_top_k가 정의되지 않은 경우 처리 (Question Classifier 사용 시)
        top_k_info = self._last_dynamic_top_k if hasattr(self, '_last_dynamic_top_k') and self._last_dynamic_top_k else len(docs)
        print(f"[Timing] context_standard total: {time.perf_counter() - overall_start:.2f}s (mode=fallback, docs={len(docs)}, top_k_ref={top_k_info})")
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
                    
                    print(f"[SEARCH] 동의어 확장: {original_query} → {expanded_query}")
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
                    
                    print(f"[SEARCH] 동의어 확장: {original_query} → {expanded_query}")
                    return expanded_query
                    
            except (json.JSONDecodeError, ValueError) as e:
                print(f"동의어 파싱 실패: {e}")
                
        except Exception as e:
            print(f"동의어 확장 실패: {e}")
        
        return original_query

    def determine_optimal_top_k(self, question: str) -> int:
        """질문 특성에 따라 최적의 top_k 값을 동적으로 결정 (Option 3: LLM 판단)"""
        try:
            prompt = f"""당신은 RAG 검색 최적화 전문가입니다. 질문 특성을 분석하여 최적의 문서 검색 개수를 결정하세요.

**질문**: "{question}"

**분석 절차**:
1단계 [질문 유형 분류]:
   - 단일 사실 찾기: "무엇", "얼마", "누구", "언제", "어디" (명확한 하나의 답변)
   - 목록 나열 (소량): "나열", "목록" (10~30개 항목)
   - 목록 나열 (대량): "모든", "전체", "각각" (30개 이상 항목)
   - 비교/분석: "차이", "비교", "vs", "대비", "관계" (다각도 분석)
   - 종합 정보: "요약", "핵심", "개요", "정리" (전체 컨텍스트)
   - 복합 질문: 여러 유형이 혼합된 경우

2단계 [복잡도 평가]:
   - 낮음: 단순한 사실 확인 (3-5개)
   - 중간: 비교/분석, 기본 종합 (10-20개)
   - 높음: 목록 나열 (소량), 복합 질문 (30-50개)
   - 매우 높음: 전체 목록 나열, 슬라이드/페이지 전체 (50-100개)

**Few-shot 예시**:
[예시 1]
질문: "OLED 효율은 얼마인가?"
유형: 단일 사실 찾기
복잡도: 낮음
추천 개수: 5

[예시 2]
질문: "논문에서 사용한 재료를 나열해주세요."
유형: 목록 나열 (소량)
복잡도: 높음
추천 개수: 30

[예시 3]
질문: "모든 슬라이드의 제목을 알려줘."
유형: 목록 나열 (대량)
복잡도: 매우 높음
추천 개수: 80

[예시 4]
질문: "각 페이지의 주요 내용을 정리해줘."
유형: 전체 페이지 종합
복잡도: 매우 높음
추천 개수: 100

**출력 형식**: 숫자만 출력 (범위: 3-100)

**분석 결과**:"""

            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # 숫자 추출
            numbers = re.findall(r'\d+', response_text)
            if numbers:
                top_k = int(numbers[0])
                top_k = max(3, min(100, top_k))  # 3~100 범위 제한 (확장)
                print(f"[LLM-TOPK] 동적 top_k 결정: {top_k} (질문 유형 분석)")
                return top_k
        except Exception as e:
            print(f"[WARN] 동적 top_k 결정 실패: {e}")

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
                    
                print(f"[REWRITE] 다중 쿼리 생성: {original_query} → {len(rewritten_queries)}개 쿼리")
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

            # Phase 3: Response Strategy Selector (Exhaustive Query → File List)
            if self.enable_file_aggregation and self._is_exhaustive_query(question):
                logger.info("[Phase 3] Exhaustive query 감지 → 파일 리스트 반환 모드")
                return self._handle_exhaustive_query(question, formatted_history)

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

            # Phase A-3: Self-Consistency Check 적용
            consistency_score = 1.0  # 기본값
            if self.enable_self_consistency:
                # Self-Consistency 답변 생성
                sc_result = self._generate_with_self_consistency(
                    question=question,
                    context=context,
                    chat_history=formatted_history,
                    n=self.self_consistency_n,
                    enable=True
                )
                answer = sc_result['answer']
                consistency_score = sc_result['consistency']

                print(f"  [OK] Self-Consistency 적용 완료 (일관성: {consistency_score:.2%})")

            else:
                # 기존 방식: 단일 답변 생성
                answer = self.chain.invoke({
                    "question": question,
                    "chat_history": formatted_history
                })

            # Phase 2: 답변 검증 및 재생성 (상용 서비스 수준)
            # Self-Consistency가 활성화된 경우, 일관성이 높으면 검증 Skip 가능
            skip_verification = self.enable_self_consistency and consistency_score > 0.8

            if not skip_verification:
                docs_for_confidence = [d for d, _ in self._last_retrieved_docs[:self.top_k]]
                verification_result = self._verify_answer_quality(question, answer, docs_for_confidence)

                if not verification_result["is_valid"]:
                    print(f"[WARN] 답변 검증 실패: {verification_result['reason']}")
                    print(f"[INFO] 문서 기반 재생성 시도...")

                    # 문서 기반 재생성
                    regenerated_answer = self._regenerate_answer(question, answer, docs_for_confidence, formatted_history)
                    if regenerated_answer:
                        answer = regenerated_answer
                        print(f"[OK] 답변 재생성 완료")
                    else:
                        print(f"[WARN] 재생성 실패, 원본 답변 사용")
            else:
                print(f"  [OK] 높은 일관성 ({consistency_score:.2%}), 검증 Skip")

            # Phase A-2: NotebookLM 스타일 인라인 Citation 추가
            # 캐시된 문서에서 Document 객체 추출
            source_docs = [doc for doc, _ in self._last_retrieved_docs[:self.top_k]]
            used_sources = []  # 실제 사용된 문서

            if source_docs:
                # Citation 생성 및 답변에 통합 (실제 사용된 문서 반환)
                answer, used_sources = self._generate_source_citations(answer, source_docs)

            # 실제 사용된 문서의 점수를 매핑
            doc_to_score = {}
            for doc, score in self._last_retrieved_docs[:self.top_k]:
                doc_id = (doc.metadata.get("file_name", ""), doc.metadata.get("page_number", ""))
                doc_to_score[doc_id] = score

            # 실제 사용된 문서만 sources에 추가 (인라인 citation과 일치)
            sources = []
            docs_for_confidence = []

            for doc in used_sources:
                doc_id = (doc.metadata.get("file_name", ""), doc.metadata.get("page_number", ""))
                score = doc_to_score.get(doc_id, 0.0)  # 매핑된 점수 사용

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
            print(f"[ERROR] query() 오류: {e}")
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
            print(f"[WARN] 재생성 오류: {e}")
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
    
    def query_stream(self, question: str, chat_history: List[Dict[str, str]] = None, search_mode: str = "integrated") -> Iterator[str]:
        overall_start = time.perf_counter()
        try:
            formatted_history = self._format_chat_history(chat_history or [])

            # 컨텍스트 구성 (로그 포함)
            context = self._get_context(question, chat_history, search_mode)

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

    def get_last_classification(self) -> Optional[Dict[str, Any]]:
        """마지막 질문 분류 결과 반환 (UI 표시용)"""
        return getattr(self, '_last_classification', None)

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
            print(f"    [WARN] 임베딩 실패: {e}")
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

    def _find_multiple_sources_for_sentence(self, sentence: str, sources: List[Document]) -> List[Document]:
        """문장과 관련된 여러 출처 찾기 (Phase C: Citation 95%)

        방법:
        1. 모든 출처와 유사도 계산
        2. 동적 임계값 이상인 출처 모두 선택
        3. 최대 2개까지 반환 (과도한 Citation 방지)

        Args:
            sentence: 분석할 문장
            sources: 후보 출처 문서들

        Returns:
            관련된 출처 리스트 (최대 2개)
        """
        if not sources or not sentence:
            return []

        # 1. 문장 임베딩
        sentence_embedding = self._embed_text(sentence)

        # 2. 모든 출처와 유사도 계산
        relevant_sources = []

        for source in sources:
            # 출처 텍스트 임베딩
            source_text = source.page_content[:500] if len(source.page_content) > 500 else source.page_content
            source_embedding = self._embed_text(source_text)

            # 코사인 유사도
            similarity = self._cosine_similarity(sentence_embedding, source_embedding)

            # 동적 임계값 이상이면 모두 추가
            threshold = self._get_adaptive_threshold(sentence, sources)
            if similarity > threshold:
                relevant_sources.append((source, similarity))

        # 3. 유사도 순 정렬
        relevant_sources.sort(key=lambda x: x[1], reverse=True)

        # 4. 최대 2개까지 반환
        return [src for src, _ in relevant_sources[:2]]

    def _get_adaptive_threshold(self, sentence: str, sources: List[Document]) -> float:
        """동적 임계값 계산 (Phase C)

        문장 길이와 복잡도에 따라 임계값 조정:
        - 짧은 문장 (10-20자): 0.5 (높은 확신 필요)
        - 중간 문장 (20-40자): 0.4 (기본)
        - 긴 문장 (40+자): 0.35 (더 관대하게)

        Args:
            sentence: 분석할 문장
            sources: 후보 출처 문서들

        Returns:
            동적 임계값
        """
        sentence_length = len(sentence)

        if sentence_length < 20:
            return 0.5  # 짧은 문장은 높은 확신 필요
        elif sentence_length < 40:
            return 0.4  # 기본 임계값
        else:
            return 0.35  # 긴 문장은 더 관대하게

    def _generate_source_citations(self, answer: str, sources: List[Document]) -> tuple[str, List[Document]]:
        """NotebookLM 스타일 출처 인라인 표시 (Phase C: 95% 목표)

        Args:
            answer: 생성된 답변
            sources: 사용된 출처 문서들

        Returns:
            (출처가 인라인으로 표시된 답변, 실제 사용된 문서 리스트)
        """
        if not sources or not answer:
            return answer, []

        print(f"  [CITE] Citation 생성 중... (문서 {len(sources)}개)")

        # 1. 답변을 문장 단위로 분리
        sentences = self._split_sentences(answer)
        print(f"    [OK] 문장 분리: {len(sentences)}개")

        # 2. 각 문장에 출처 매칭
        cited_sentences = []
        citation_count = 0
        used_sources_set = set()  # 실제 사용된 문서 추적 (중복 제거)

        for i, sentence in enumerate(sentences):
            # Phase C: 짧은 문장 임계값 낮춤 (15 → 10)
            if len(sentence) < 10:
                cited_sentences.append(sentence)
                continue

            # Phase C: 여러 출처 허용 (최대 2개)
            relevant_sources = self._find_multiple_sources_for_sentence(sentence, sources)

            if relevant_sources:
                # 여러 출처를 인라인으로 결합
                citations = [self._format_citation(src) for src in relevant_sources]
                cited_sentence = f"{sentence.strip()} {''.join(citations)}"
                citation_count += 1

                # 실제 사용된 문서 추가
                for src in relevant_sources:
                    # Document 객체의 ID를 사용 (page_content와 metadata 조합)
                    src_id = (src.metadata.get("file_name", ""), src.metadata.get("page_number", ""))
                    if src_id not in used_sources_set:
                        used_sources_set.add(src_id)
            else:
                cited_sentence = sentence.strip()

            cited_sentences.append(cited_sentence)

        print(f"    [OK] Citation 추가: {citation_count}/{len(sentences)}개 문장")

        # 실제 사용된 문서만 필터링 (원본 순서 유지)
        used_sources = []
        for src in sources:
            src_id = (src.metadata.get("file_name", ""), src.metadata.get("page_number", ""))
            if src_id in used_sources_set:
                used_sources.append(src)

        return " ".join(cited_sentences), used_sources

    # ============================================
    # Phase A-3: Self-Consistency Check
    # ============================================

    def _generate_answer_internal(self, question: str, context: str, chat_history: str = "") -> str:
        """내부 답변 생성 메서드 (Self-Consistency용)

        Args:
            question: 사용자 질문
            context: 검색된 문맥
            chat_history: 대화 이력 (formatted)

        Returns:
            생성된 답변 문자열
        """
        try:
            # LangChain invoke 사용
            answer = self.chain.invoke({
                "question": question,
                "context": context,
                "chat_history": chat_history if chat_history else "이전 대화 없음"
            })

            # 응답 타입에 따라 문자열 추출
            if hasattr(answer, 'content'):
                return answer.content
            elif hasattr(answer, 'text'):
                return answer.text
            else:
                return str(answer)

        except Exception as e:
            print(f"    [ERROR] 답변 생성 실패: {e}")
            return ""

    def _calculate_answer_consistency(self, answers: List[str]) -> float:
        """답변들 간의 일관성 점수 계산 (Jaccard 유사도)

        Args:
            answers: 생성된 답변들

        Returns:
            일관성 점수 (0.0 ~ 1.0)
        """
        from itertools import combinations

        if len(answers) < 2:
            return 1.0

        # 모든 쌍의 유사도 계산
        similarities = []

        for ans1, ans2 in combinations(answers, 2):
            # 토큰화 (단순 공백 기준)
            tokens1 = set(ans1.lower().split())
            tokens2 = set(ans2.lower().split())

            # Jaccard 유사도: |교집합| / |합집합|
            if len(tokens1.union(tokens2)) == 0:
                similarity = 0.0
            else:
                similarity = len(tokens1.intersection(tokens2)) / len(tokens1.union(tokens2))

            similarities.append(similarity)

        # 평균 유사도 반환
        return sum(similarities) / len(similarities) if similarities else 0.0

    def _extract_common_info(self, answers: List[str]) -> str:
        """여러 답변에서 공통 정보 추출

        Args:
            answers: 생성된 답변들

        Returns:
            공통 정보를 통합한 답변
        """
        if not answers:
            return ""

        if len(answers) == 1:
            return answers[0]

        # 간단한 전략: 가장 긴 답변 선택 (정보가 많음)
        # 향후 개선: 실제 공통 문장 추출 로직 구현 가능
        longest_answer = max(answers, key=lambda a: len(a))

        return longest_answer

    def _generate_with_self_consistency(
        self,
        question: str,
        context: str,
        chat_history: str = "",
        n: int = 3,
        enable: bool = True
    ) -> Dict[str, Any]:
        """Self-Consistency Check: 여러 번 생성 후 일관성 검증

        Args:
            question: 사용자 질문
            context: 검색된 문맥
            chat_history: 대화 이력
            n: 생성 횟수 (기본 3회)
            enable: Self-Consistency 활성화 여부

        Returns:
            {
                'answer': 최종 답변,
                'consistency': 일관성 점수 (0-1),
                'variants': 생성된 답변들,
                'method': 'self_consistency' or 'single'
            }
        """
        # Self-Consistency 비활성화 시 단일 생성
        if not enable:
            answer = self._generate_answer_internal(question, context, chat_history)
            return {
                'answer': answer,
                'consistency': 1.0,
                'variants': [answer],
                'method': 'single'
            }

        print(f"  [REWRITE] Self-consistency check: {n}회 생성 중...")

        # 1. N번 독립적으로 답변 생성
        original_temp = self.temperature
        self.temperature = 0.5  # 약간 다양성 추가

        answers = []
        for i in range(n):
            answer = self._generate_answer_internal(question, context, chat_history)
            if answer:  # 빈 답변 제외
                answers.append(answer)
                print(f"    [OK] {i+1}번째 생성 완료 ({len(answer)} chars)")

        self.temperature = original_temp

        # 생성 실패 시
        if not answers:
            print(f"    [ERROR] 모든 생성 실패")
            return {
                'answer': "답변 생성에 실패했습니다.",
                'consistency': 0.0,
                'variants': [],
                'method': 'self_consistency_failed'
            }

        # 2. 답변 간 일관성 점수 계산
        consistency_score = self._calculate_answer_consistency(answers)
        print(f"    [OK] 일관성 점수: {consistency_score:.2%}")

        # 3. 일관성에 따라 처리
        if consistency_score > 0.8:
            # 높은 일관성: 가장 상세한 답변 선택
            best_answer = max(answers, key=lambda a: len(a))
            print(f"    [OK] 높은 일관성: 최상 답변 선택")

        elif consistency_score > 0.5:
            # 중간 일관성: 공통 정보 추출
            best_answer = self._extract_common_info(answers)
            # 신뢰도 표시는 선택적으로 추가 (사용자 혼란 방지)
            # best_answer = f"[WARN] 중간 신뢰도 (일관성: {consistency_score:.1%})\n\n{best_answer}"
            print(f"    [WARN] 중간 일관성: 공통 정보 추출")

        else:
            # 낮은 일관성: 경고와 함께 첫 번째 답변
            best_answer = answers[0]
            # 신뢰도 표시는 선택적으로 추가
            # best_answer = f"[WARN] 낮은 신뢰도 (일관성: {consistency_score:.1%})\n제공된 문서에서 명확한 답변을 찾기 어렵습니다.\n\n{answers[0]}"
            print(f"    [WARN] 낮은 일관성: 경고 표시")

        return {
            'answer': best_answer,
            'consistency': consistency_score,
            'variants': answers,
            'method': 'self_consistency'
        }

    def _get_context_from_document_ids(self, document_ids: List[str], question: str,
                                      context_start: float, apply_threshold: bool = False) -> Optional[str]:
        """특정 document_id 리스트 내에서만 검색

        Args:
            document_ids: 검색 대상 document_id 리스트
            question: 사용자 질문
            context_start: 시작 시간 (타이밍 측정용)
            apply_threshold: relevance threshold 적용 여부 (Session Context용)

        Returns:
            검색된 context 문자열, threshold 미달 시 None
        """
        if not document_ids:
            return None

        try:
            # ChromaDB filter를 사용한 검색
            filter_condition = {"document_id": {"$in": document_ids}}

            # Multi-query expansion 적용 여부 확인
            if self.enable_multi_query and self.multi_query_num > 0:
                # Multi-query로 검색
                multi_queries = self.generate_rewritten_queries(question, num_queries=self.multi_query_num)
                all_docs = []

                for query in multi_queries:
                    docs = self.vectorstore.vectorstore.similarity_search(
                        query,
                        k=self.reranker_initial_k,
                        filter=filter_condition
                    )
                    all_docs.extend(docs)

                # 중복 제거 (chunk_id 기준)
                unique_docs = {}
                for doc in all_docs:
                    chunk_id = doc.metadata.get('chunk_id', id(doc))
                    if chunk_id not in unique_docs:
                        unique_docs[chunk_id] = doc

                retrieved_docs = list(unique_docs.values())
            else:
                # 단일 쿼리 검색
                retrieved_docs = self.vectorstore.vectorstore.similarity_search(
                    question,
                    k=self.reranker_initial_k,
                    filter=filter_condition
                )

            if not retrieved_docs:
                logger.debug(f"문서 ID 필터 검색 결과 없음: {len(document_ids)}개 문서")
                return None

            logger.debug(f"문서 ID 필터 검색: {len(retrieved_docs)}개 청크 발견")

            # Reranking
            if self.use_reranker and self.reranker:
                try:
                    reranked_docs = self.reranker.rerank(question, retrieved_docs, top_k=self.top_k)
                    logger.debug(f"Reranking: {len(retrieved_docs)}개 -> {len(reranked_docs)}개")
                except Exception as e:
                    logger.warning(f"Reranking 실패: {e}, 원본 결과 사용")
                    reranked_docs = retrieved_docs[:self.top_k]
            else:
                reranked_docs = retrieved_docs[:self.top_k]

            if not reranked_docs:
                return None

            # Relevance threshold 체크 (apply_threshold=True일 때만)
            if apply_threshold and self.session_relevance_threshold > 0:
                # Reranker 점수 확인 (negative score, 낮을수록 좋음)
                top_score = getattr(reranked_docs[0], 'score', None)

                if top_score is not None:
                    # Negative score를 [0, 1] range로 변환
                    # -1 이하: 매우 관련있음 (1.0), 0 부근: 관련없음 (0.0)
                    normalized_score = max(0.0, min(1.0, (-top_score + 1.0) / 2.0))

                    if normalized_score < self.session_relevance_threshold:
                        logger.debug(f"Session 문서 relevance 부족: {normalized_score:.3f} < {self.session_relevance_threshold}")
                        return None

            # Context 생성
            context = "\n\n".join([
                f"[문서: {doc.metadata.get('file_name', 'unknown')}, 페이지: {doc.metadata.get('page_number', '?')}]\n{doc.page_content}"
                for doc in reranked_docs
            ])

            # 마지막 검색 결과 캐시 (출처 표시용)
            # (doc, score) 튜플 형태로 저장 (기존 코드와 호환성 유지)
            self._last_retrieved_docs = [(doc, getattr(doc, 'score', 0.0)) for doc in reranked_docs]

            # Session Context 검색 디버깅 로그
            logger.debug(f"Session Context 검색 완료: {len(reranked_docs)}개 문서")
            for doc in reranked_docs[:3]:
                logger.debug(f"  - {doc.metadata.get('file_name', 'UNKNOWN')} (p.{doc.metadata.get('page_number', '?')})")

            # 타이밍 측정
            elapsed = time.perf_counter() - context_start
            logger.info(f"[Timing] document_id 필터 검색: {elapsed:.2f}s (docs={len(reranked_docs)})")

            return context

        except Exception as e:
            logger.error(f"Document ID 필터 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            return None
