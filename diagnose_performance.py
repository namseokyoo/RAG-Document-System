"""
RAG 시스템 성능 진단 스크립트

각 단계의 입출력을 상세히 로깅하여 문제점을 파악합니다.
"""

import json
import sys
from datetime import datetime
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import create_rag_chain
from utils.question_classifier import QuestionClassifier
from langchain_ollama import ChatOllama

def print_section(title):
    """섹션 제목 출력"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def diagnose_question(question: str, rag_chain, classifier, vector_store):
    """질문에 대한 전체 진단 수행"""

    print_section(f"질문: {question}")

    # ============ 1단계: 질문 분류 ============
    print_section("1단계: 질문 분류")
    classification = classifier.classify(question)
    print(json.dumps(classification, indent=2, ensure_ascii=False))

    # ============ 2단계: 검색 (유사도 검색) ============
    print_section("2단계: 초기 유사도 검색")

    # reranker_k 값 확인
    reranker_k = classification.get('reranker_k', 60)
    print(f"검색할 문서 수 (reranker_k): {reranker_k}")

    # 직접 검색 수행
    try:
        # 벡터 스토어에서 직접 검색
        initial_docs = vector_store.vectorstore.similarity_search_with_score(
            question,
            k=min(reranker_k, 100)  # 최대 100개
        )

        print(f"\n검색된 문서 수: {len(initial_docs)}")
        print("\n상위 5개 문서 미리보기:")
        for i, (doc, score) in enumerate(initial_docs[:5], 1):
            print(f"\n[{i}] 유사도: {score:.4f}")
            print(f"  파일: {doc.metadata.get('source', 'N/A')}")
            print(f"  페이지: {doc.metadata.get('page_number', 'N/A')}")
            print(f"  내용 미리보기: {doc.page_content[:100]}...")

        # 점수 분포 확인
        scores = [score for _, score in initial_docs]
        if scores:
            print(f"\n점수 통계:")
            print(f"  최소: {min(scores):.4f}")
            print(f"  최대: {max(scores):.4f}")
            print(f"  평균: {sum(scores)/len(scores):.4f}")

    except Exception as e:
        print(f"검색 중 오류: {e}")
        initial_docs = []

    # ============ 3단계: RAG 체인 실행 (리랭킹 + 필터링 포함) ============
    print_section("3단계: RAG 체인 실행 (리랭킹 + 필터링)")

    try:
        # RAG 체인 실행
        response = rag_chain.invoke({
            "question": question,
            "chat_history": []
        })

        # 응답 분석
        print(f"\n최종 답변 길이: {len(response.get('answer', ''))} 글자")
        print(f"\n최종 답변:\n{response.get('answer', 'N/A')}")

        # 사용된 컨텍스트 확인
        context_docs = response.get('context', [])
        print(f"\n\n최종 사용된 컨텍스트 문서 수: {len(context_docs)}")

        if context_docs:
            print("\n컨텍스트 문서 상세:")
            for i, doc in enumerate(context_docs, 1):
                print(f"\n[{i}] {doc.metadata.get('source', 'N/A')} - 페이지 {doc.metadata.get('page_number', 'N/A')}")
                print(f"  내용 미리보기: {doc.page_content[:150]}...")

                # 리랭킹 점수가 있다면 출력
                if 'reranker_score' in doc.metadata:
                    print(f"  리랭킹 점수: {doc.metadata['reranker_score']:.4f}")

        # 인용 정보 확인
        citations = response.get('citations', [])
        print(f"\n\n인용 수: {len(citations)}")
        if citations:
            print("인용 정보:")
            for cite in citations[:5]:  # 상위 5개만
                print(f"  - {cite}")

    except Exception as e:
        print(f"RAG 체인 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80 + "\n")


def main():
    """메인 진단 함수"""

    print_section("RAG 시스템 성능 진단 시작")
    print(f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 설정 로드
    config_manager = ConfigManager()
    config = config_manager.get_all()

    print("\n주요 설정:")
    print(f"  - Chunk Size: {config.get('chunk_size')}")
    print(f"  - Reranker: {config.get('use_reranker')}")
    print(f"  - Score Filtering: {config.get('enable_score_filtering')}")
    print(f"  - Question Classifier: {config.get('enable_question_classifier')}")
    print(f"  - Multi Query: {config.get('enable_multi_query')}")

    # 컴포넌트 초기화
    print_section("컴포넌트 초기화")

    try:
        # 벡터 스토어
        print("벡터 스토어 로딩 중...")
        vector_store_manager = VectorStoreManager(config)

        # LLM
        print("LLM 초기화 중...")
        llm = ChatOllama(
            model=config.get("llm_model", "gemma3:4b"),
            base_url=config.get("llm_base_url", "http://localhost:11434"),
            temperature=config.get("temperature", 0.7)
        )

        # Question Classifier
        print("Question Classifier 초기화 중...")
        classifier = QuestionClassifier(
            llm=llm,
            use_llm_fallback=config.get("classifier_use_llm", True),
            verbose=True  # 상세 로그 활성화
        )

        # RAG Chain
        print("RAG Chain 생성 중...")
        rag_chain = create_rag_chain(
            vector_store_manager=vector_store_manager,
            config=config,
            chat_history=[]
        )

        print("✓ 모든 컴포넌트 초기화 완료")

    except Exception as e:
        print(f"초기화 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return

    # 테스트 질문들
    test_questions = [
        "OLED는 무엇인가?",
        "TADF의 효율은?",
        "kFRET 값은?",
        "OLED와 QLED를 비교 분석해줘",
        # "모든 슬라이드 제목을 나열해줘",
    ]

    # 사용자 입력으로 질문 추가 가능
    print_section("테스트 질문 목록")
    for i, q in enumerate(test_questions, 1):
        print(f"{i}. {q}")

    print("\n추가 질문을 입력하거나 Enter를 눌러 시작하세요:")
    user_input = input().strip()
    if user_input:
        test_questions.append(user_input)

    # 각 질문 진단
    for i, question in enumerate(test_questions, 1):
        print(f"\n\n{'#' * 80}")
        print(f"테스트 {i}/{len(test_questions)}")
        print(f"{'#' * 80}")

        diagnose_question(
            question=question,
            rag_chain=rag_chain,
            classifier=classifier,
            vector_store=vector_store_manager
        )

        # 다음 질문 전에 대기
        if i < len(test_questions):
            print("\n다음 질문으로 계속하려면 Enter를 누르세요...")
            input()

    # 분류기 통계 출력
    print_section("Question Classifier 통계")
    classifier.print_stats()

    print_section("진단 완료")
    print(f"종료 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
