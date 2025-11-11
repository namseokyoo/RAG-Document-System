"""
QuestionClassifier를 RAGChain에 통합하는 예제 코드

기존 rag_chain.py를 수정하지 않고,
래퍼 함수로 간단하게 통합하는 방법을 제공합니다.
"""

from typing import Optional
from utils.question_classifier import QuestionClassifier, create_classifier
from utils.rag_chain import RAGChain


class OptimizedRAGChain:
    """
    QuestionClassifier가 통합된 최적화 RAGChain

    기존 RAGChain을 래핑하여 질문 유형에 따라
    자동으로 파라미터를 최적화합니다.
    """

    def __init__(
        self,
        rag_chain: RAGChain,
        use_classifier: bool = True,
        classifier_llm: Optional[object] = None,
        classifier_verbose: bool = False
    ):
        """
        Args:
            rag_chain: 기존 RAGChain 인스턴스
            use_classifier: 분류기 사용 여부
            classifier_llm: 분류기용 LLM (None이면 규칙만 사용)
            classifier_verbose: 분류기 상세 로그
        """
        self.rag_chain = rag_chain
        self.use_classifier = use_classifier

        if use_classifier:
            # LLM 설정 (rag_chain의 LLM 재사용 가능)
            if classifier_llm is None:
                classifier_llm = rag_chain.llm  # 동일 LLM 사용

            self.classifier = create_classifier(
                llm=classifier_llm,
                use_llm=True,
                verbose=classifier_verbose
            )
        else:
            self.classifier = None

    def query(
        self,
        question: str,
        chat_history: Optional[list] = None,
        stream: bool = False
    ):
        """
        최적화된 질의 처리

        Args:
            question: 사용자 질문
            chat_history: 대화 기록
            stream: 스트리밍 여부

        Returns:
            답변 (dict 또는 generator)
        """

        if self.use_classifier and self.classifier:
            # 1. 질문 분류
            classification = self.classifier.classify(question)

            print(f"\n🎯 질문 분류 결과:")
            print(f"   유형: {classification['type']}")
            print(f"   신뢰도: {classification['confidence']:.0%}")
            print(f"   방법: {classification['method']}")
            print(f"   이유: {classification['reasoning']}")

            # 2. RAGChain 파라미터 동적 조정
            self._apply_optimization(classification)

            print(f"\n⚙️  최적화 파라미터 적용:")
            print(f"   Multi-Query: {classification['multi_query']}")
            print(f"   Max Results: {classification['max_results']}")
            print(f"   Reranker K: {classification['reranker_k']}")
            print(f"   Max Tokens: {classification['max_tokens']}")

        # 3. 기존 RAGChain 실행
        return self.rag_chain.query(
            question=question,
            chat_history=chat_history,
            stream=stream
        )

    def _apply_optimization(self, classification: dict):
        """분류 결과를 RAGChain에 적용"""

        # enable_multi_query
        if hasattr(self.rag_chain, 'enable_multi_query'):
            self.rag_chain.enable_multi_query = classification['multi_query']

        # max_num_results
        if hasattr(self.rag_chain, 'max_num_results'):
            self.rag_chain.max_num_results = classification['max_results']

        # reranker_initial_k
        if hasattr(self.rag_chain, 'reranker_initial_k'):
            self.rag_chain.reranker_initial_k = classification['reranker_k']

        # max_tokens (LLM 설정)
        if hasattr(self.rag_chain, 'max_tokens'):
            self.rag_chain.max_tokens = classification['max_tokens']
        elif hasattr(self.rag_chain.llm, 'max_tokens'):
            self.rag_chain.llm.max_tokens = classification['max_tokens']
        elif hasattr(self.rag_chain.llm, 'num_predict'):
            # Ollama의 경우
            self.rag_chain.llm.num_predict = classification['max_tokens']

    def print_stats(self):
        """분류기 통계 출력"""
        if self.classifier:
            self.classifier.print_stats()


# ============ 사용 예제 ============

def example_usage():
    """사용 예제"""

    from utils.config_manager import ConfigManager
    from utils.vector_store import VectorStoreManager

    # 1. 기존 RAGChain 초기화
    config_manager = ConfigManager()
    vector_store = VectorStoreManager(config_manager)
    rag_chain = RAGChain(config_manager, vector_store)

    # 2. OptimizedRAGChain으로 래핑
    optimized_rag = OptimizedRAGChain(
        rag_chain=rag_chain,
        use_classifier=True,
        classifier_verbose=True  # 상세 로그 보기
    )

    # 3. 질문 처리
    test_questions = [
        "kFRET 값은?",                           # simple → 빠름
        "OLED 효율은?",                          # normal → 표준
        "OLED와 QLED를 비교해줘",                # complex → Multi-Query
        "모든 슬라이드 제목을 나열해줘",         # exhaustive → 100개
    ]

    for question in test_questions:
        print("\n" + "="*60)
        print(f"질문: {question}")
        print("="*60)

        answer = optimized_rag.query(question)

        print(f"\n답변: {answer['answer'][:200]}...")
        print(f"소스 개수: {len(answer.get('source_documents', []))}")

    # 4. 통계 확인
    optimized_rag.print_stats()


# ============ RAGChain 직접 수정 버전 ============

def integrate_into_rag_chain():
    """
    RAGChain에 직접 통합하는 방법 (코드 예시)

    실제 적용 시 rag_chain.py의 _get_context() 메서드 초반에 추가:
    """

    example_code = '''
# rag_chain.py 파일 수정

from utils.question_classifier import create_classifier

class RAGChain:
    def __init__(self, ...):
        # 기존 코드...

        # 질문 분류기 추가
        self.question_classifier = create_classifier(
            llm=self.llm,
            use_llm=True,
            verbose=self.verbose
        )

    def _get_context(self, question: str, ...):
        """컨텍스트 검색 (최적화 버전)"""

        # ========== 추가: 질문 분류 및 파라미터 최적화 ==========
        if hasattr(self, 'question_classifier'):
            classification = self.question_classifier.classify(question)

            if self.verbose:
                print(f"\\n🎯 질문 유형: {classification['type']} "
                      f"(신뢰도: {classification['confidence']:.0%})")
                print(f"   방법: {classification['method']}")

            # 파라미터 동적 조정
            self.enable_multi_query = classification['multi_query']
            self.max_num_results = classification['max_results']
            self.reranker_initial_k = classification['reranker_k']
            self.max_tokens = classification['max_tokens']
        # ========== 추가 끝 ==========

        # 기존 로직 계속...
        if self.enable_multi_query:
            queries = self._generate_multi_query(question)
        else:
            queries = [question]

        # ... 나머지 기존 코드
    '''

    print("RAGChain 직접 통합 코드:")
    print(example_code)


if __name__ == "__main__":
    print("OptimizedRAGChain 사용 예제")
    print("\n사용 방법 1: 래퍼 클래스 사용 (권장)")
    print("-" * 60)
    print("""
from utils.question_classifier_integration import OptimizedRAGChain

# 기존 RAGChain 래핑
optimized_rag = OptimizedRAGChain(rag_chain, use_classifier=True)

# 사용
answer = optimized_rag.query("질문")
    """)

    print("\n사용 방법 2: RAGChain 직접 수정")
    print("-" * 60)
    integrate_into_rag_chain()
