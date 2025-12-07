"""HyDE와 Query Decomposition 기능 간단 테스트"""
import sys
import os

# UTF-8 출력 설정 (Windows 콘솔 호환)
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_hyde_decomposition():
    print("=" * 80)
    print("HyDE 및 Query Decomposition 기능 테스트")
    print("=" * 80)
    
    # 설정 로드
    config_manager = ConfigManager()
    config = config_manager.get_all()
    
    print("\n[1단계] 설정 확인")
    print(f"  - enable_hyde: {config.get('enable_hyde', True)}")
    print(f"  - enable_query_decomposition: {config.get('enable_query_decomposition', True)}")
    print(f"  - enable_multi_query: {config.get('enable_multi_query', True)}")
    print(f"  - multi_query_num: {config.get('multi_query_num', 3)}")
    
    # VectorStore 초기화
    print("\n[2단계] VectorStore 초기화")
    try:
        vector_manager = VectorStoreManager(
            persist_directory="data/chroma_db",
            embedding_api_type=config.get("embedding_api_type", "request"),
            embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
            embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
            embedding_api_key=config.get("embedding_api_key", ""),
        )
        print("  ✓ VectorStore 초기화 완료")
    except Exception as e:
        print(f"  ✗ VectorStore 초기화 실패: {e}")
        return False
    
    # RAGChain 초기화
    print("\n[3단계] RAGChain 초기화 (HyDE 및 Query Decomposition 포함)")
    try:
        multi_query_num = int(config.get("multi_query_num", 3))
        enable_multi_query = config.get("enable_multi_query", True) and multi_query_num > 0
        
        rag_chain = RAGChain(
            vectorstore=vector_manager,
            llm_api_type=config.get("llm_api_type", "request"),
            llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
            llm_model=config.get("llm_model", "gemma3:latest"),
            llm_api_key=config.get("llm_api_key", ""),
            temperature=config.get("temperature", 0.3),
            top_k=config.get("top_k", 5),
            use_reranker=config.get("use_reranker", True),
            reranker_model=config.get("reranker_model", "multilingual-mini"),
            reranker_initial_k=config.get("reranker_initial_k", 30),
            enable_synonym_expansion=config.get("enable_synonym_expansion", False),
            enable_multi_query=enable_multi_query,
            multi_query_num=multi_query_num,
            enable_hyde=config.get("enable_hyde", True),
            enable_query_decomposition=config.get("enable_query_decomposition", True),
        )
        print("  ✓ RAGChain 초기화 완료")
        print(f"    - enable_hyde: {rag_chain.enable_hyde}")
        print(f"    - enable_query_decomposition: {rag_chain.enable_query_decomposition}")
    except Exception as e:
        print(f"  ✗ RAGChain 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 테스트 질문들
    test_questions = [
        "OLED 효율 향상 방법",  # 단순 질문 (normal)
        "TADF 재료와 OLED 효율의 관계",  # 복잡 질문 (complex - 관계 키워드)
        "발광 효율 측정 방법은 무엇인가요?",  # 단순 질문 (normal)
        "OLED와 QLED의 차이점은 무엇인가?",  # 복잡 질문 (complex - 비교 키워드)
    ]
    
    print("\n[4단계] 기능별 테스트")
    
    # 4-1. HyDE 테스트
    print("\n[4-1] HyDE 테스트")
    test_question = test_questions[0]
    try:
        hyde_doc = rag_chain._generate_hypothetical_document(test_question)
        if hyde_doc:
            print(f"  ✓ HyDE 가상 문서 생성 성공")
            print(f"    질문: {test_question}")
            print(f"    생성된 문서 길이: {len(hyde_doc)}자")
            print(f"    문서 미리보기: {hyde_doc[:100]}...")
        else:
            print(f"  ⚠ HyDE 가상 문서 생성 실패 (빈 응답)")
    except Exception as e:
        print(f"  ✗ HyDE 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 4-2. 복잡 질문 감지 테스트
    print("\n[4-2] 복잡 질문 감지 테스트")
    print("  [4-2-1] 휴리스틱 기반 감지")
    for q in test_questions:
        is_complex = rag_chain._is_complex_question(q)
        print(f"    질문: {q[:50]}...")
        print(f"      복잡 질문 여부: {is_complex}")
    
    # 4-2-2. Question Classifier 분류 테스트
    print("\n  [4-2-2] Question Classifier 분류 테스트")
    if hasattr(rag_chain, 'question_classifier') and rag_chain.question_classifier:
        for q in test_questions:
            try:
                classification = rag_chain.question_classifier.classify(q)
                print(f"    질문: {q[:50]}...")
                print(f"      분류: {classification.get('type')} (confidence: {classification.get('confidence', 0):.1%})")
                print(f"      이유: {classification.get('reasoning', 'N/A')[:100]}...")
            except Exception as e:
                print(f"    질문: {q[:50]}...")
                print(f"      분류 실패: {e}")
    else:
        print("    Question Classifier가 없습니다.")
    
    # 4-3. Query Decomposition 테스트
    print("\n[4-3] Query Decomposition 테스트")
    complex_question = test_questions[1]  # "TADF 재료와 OLED 효율의 관계"
    try:
        sub_questions = rag_chain._decompose_question(complex_question)
        if len(sub_questions) > 1:
            print(f"  ✓ 질문 분해 성공")
            print(f"    원본 질문: {complex_question}")
            print(f"    하위 질문 수: {len(sub_questions)}")
            for i, sq in enumerate(sub_questions, 1):
                print(f"      {i}. {sq}")
        else:
            print(f"  ⚠ 질문 분해 결과: 단일 질문 (분해 불필요)")
    except Exception as e:
        print(f"  ✗ Query Decomposition 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 4-4. 통합 검색 테스트 (최적화 검증)
    print("\n[4-4] 통합 검색 테스트 (최적화 검증)")
    
    # 4-4-1. 단순 질문 테스트 (Query Decomposition 생략 확인)
    print("\n[4-4-1] 단순 질문 테스트 (Query Decomposition 생략 확인)")
    simple_question = test_questions[0]  # "OLED 효율 향상 방법"
    try:
        import time
        start_time = time.perf_counter()
        print(f"  질문: {simple_question}")
        context = rag_chain._get_context_standard(simple_question, search_mode="integrated")
        elapsed = time.perf_counter() - start_time
        if context:
            print(f"  ✓ 검색 성공")
            print(f"    처리 시간: {elapsed:.2f}초")
            print(f"    컨텍스트 길이: {len(context)}자")
            print(f"    컨텍스트 미리보기: {context[:200]}...")
        else:
            print(f"  ⚠ 검색 결과 없음 (DB에 관련 문서가 없을 수 있음)")
    except Exception as e:
        print(f"  ✗ 단순 질문 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 4-4-2. 복잡 질문 테스트 (원본 HyDE + 하위 질문 직접 검색 확인)
    print("\n[4-4-2] 복잡 질문 테스트 (원본 HyDE + 하위 질문 직접 검색)")
    complex_question = test_questions[1]  # "TADF 재료와 OLED 효율의 관계"
    try:
        import time
        start_time = time.perf_counter()
        print(f"  질문: {complex_question}")
        context = rag_chain._get_context_standard(complex_question, search_mode="integrated")
        elapsed = time.perf_counter() - start_time
        if context:
            print(f"  ✓ 검색 성공")
            print(f"    처리 시간: {elapsed:.2f}초")
            print(f"    컨텍스트 길이: {len(context)}자")
            print(f"    컨텍스트 미리보기: {context[:200]}...")
        else:
            print(f"  ⚠ 검색 결과 없음 (DB에 관련 문서가 없을 수 있음)")
    except Exception as e:
        print(f"  ✗ 복잡 질문 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("테스트 완료")
    print("=" * 80)
    return True

if __name__ == "__main__":
    try:
        test_hyde_decomposition()
    except KeyboardInterrupt:
        print("\n\n테스트 중단됨")
    except Exception as e:
        print(f"\n\n테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

