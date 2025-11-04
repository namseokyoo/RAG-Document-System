"""
 3, 5  
-     ( 3)
- Re-ranker Gap   ( 5)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from langchain.schema import Document
import numpy as np


def create_mock_rag_chain():
    """RAGChain     Mock """
    from utils.rag_chain import RAGChain

    # Mock vectorstore ( )
    class MockVectorstore:
        def __init__(self):
            self.vectorstore = self

        def as_retriever(self, **kwargs):
            return self

    # RAGChain   (vectorstore )
    mock_vectorstore = MockVectorstore()

    #   RAGChain 
    # LLM       
    try:
        rag = RAGChain(
            vectorstore=mock_vectorstore,
            llm_api_type="ollama",
            llm_base_url="http://localhost:11434",
            llm_model="test",
            top_k=5
        )
    except Exception as e:
        # LLM    (  )
        print(f" LLM   (): {e}")
        #   
        rag = object.__new__(RAGChain)
        rag.top_k = 5

    return rag


def test_statistical_outlier_removal():
    """ 3:     """
    print("\n" + "="*80)
    print("[TEST 1]     ( 3)")
    print("="*80)

    rag = create_mock_rag_chain()

    #   1:   
    print("\n[ 1]   -  ")
    candidates = [
        (Document(page_content=f"Doc {i}"), 0.9 - i*0.05)
        for i in range(10)
    ]
    print(f": {len(candidates)} ,  : {candidates[-1][1]:.2f} ~ {candidates[0][1]:.2f}")

    filtered = rag._statistical_outlier_removal(candidates, method='mad')
    print(f": {len(filtered)} ")
    print(f": {' ' if len(filtered) >= 8 else ' '} (    )")

    #   2:   (  )
    print("\n[ 2]   -  ")
    candidates = [
        (Document(page_content="OLED  1"), 0.95),
        (Document(page_content="OLED  2"), 0.92),
        (Document(page_content="OLED  3"), 0.90),
        (Document(page_content="OLED  4"), 0.88),
        (Document(page_content="OLED  5"), 0.85),
        (Document(page_content="  1"), 0.45),  # !
        (Document(page_content="  2"), 0.42),  # !
        (Document(page_content="  3"), 0.40),  # !
    ]
    print(f": {len(candidates)} ")
    print(f"  -   (0.85~0.95): 5")
    print(f"  -  (0.40~0.45): 3")

    filtered = rag._statistical_outlier_removal(candidates, method='mad')
    print(f": {len(filtered)} ")
    print(f" : {len(candidates) - len(filtered)}")

    #   
    filtered_scores = [score for _, score in filtered]
    min_filtered_score = min(filtered_scores)
    print(f"   : {min_filtered_score:.2f}")
    print(f": {' ' if min_filtered_score > 0.7 else ' '} (  )")

    #   3: MAD vs IQR vs Z-score 
    print("\n[ 3]   ")
    for method in ['mad', 'iqr', 'zscore']:
        filtered = rag._statistical_outlier_removal(candidates, method=method)
        print(f"  - {method.upper()}: {len(candidates) - len(filtered)} ")

    return True


def test_reranker_gap_based_cutoff():
    """ 5: Re-ranker Gap   """
    print("\n" + "="*80)
    print("  2: Re-ranker Gap   ( 5)")
    print("="*80)

    rag = create_mock_rag_chain()

    #   1: Gap   ( )
    print("\n[ 1] Gap  -  ")
    candidates = [
        (Document(page_content=f"Doc {i}"), 0.9 - i*0.02)
        for i in range(10)
    ]
    print(f": {len(candidates)} ,  : {candidates[-1][1]:.2f} ~ {candidates[0][1]:.2f}")

    filtered = rag._reranker_gap_based_cutoff(candidates, min_docs=3)
    print(f": {len(filtered)} ")
    print(f": {' ' if len(filtered) == len(candidates) else ' '} (Gap    )")

    #   2:  Gap  (  )
    print("\n[ 2]  Gap  -  ")
    candidates = [
        (Document(page_content="  1"), 0.95),
        (Document(page_content="  2"), 0.92),
        (Document(page_content="  3"), 0.90),
        (Document(page_content="  4"), 0.88),
        (Document(page_content="  5"), 0.87),
        #   Gap (0.87 -> 0.65 = 0.22 )
        (Document(page_content="  1"), 0.65),
        (Document(page_content="  2"), 0.63),
        (Document(page_content="  3"), 0.61),
        (Document(page_content="  4"), 0.60),
    ]

    # Gap 
    scores = [score for _, score in candidates]
    gaps = [scores[i] - scores[i+1] for i in range(len(scores)-1)]
    max_gap = max(gaps)
    max_gap_idx = gaps.index(max_gap)

    print(f": {len(candidates)} ")
    print(f"  -  Gap: {max_gap:.2f} (: {max_gap_idx+1} )")
    print(f"  -  Gap: {np.mean(gaps):.2f}")

    filtered = rag._reranker_gap_based_cutoff(candidates, min_docs=3)
    print(f": {len(filtered)} ")
    print(f" : {len(candidates) - len(filtered)}")
    print(f": {' ' if len(filtered) <= 6 else ' '} ( Gap   )")

    #   3: min_docs  
    print("\n[ 3]    ")
    candidates_small = [
        (Document(page_content=f"Doc {i}"), 0.9 - i*0.3)
        for i in range(5)
    ]

    filtered = rag._reranker_gap_based_cutoff(candidates_small, min_docs=3)
    print(f": {len(candidates_small)} ")
    print(f": {len(filtered)} ")
    print(f": {' ' if len(filtered) >= 3 else ' '} ( 3  )")

    return True


def test_integrated_scenario():
    """ :    """
    print("\n" + "="*80)
    print("  3:   ( 3 + 5)")
    print("="*80)

    rag = create_mock_rag_chain()

    #    
    print("\n[] 3    ")
    candidates = [
        # /  ( )
        (Document(page_content="OLED efficiency paper 1", metadata={"topic": "physics"}), 0.95),
        (Document(page_content="OLED efficiency paper 2", metadata={"topic": "physics"}), 0.92),
        (Document(page_content="OLED efficiency paper 3", metadata={"topic": "physics"}), 0.90),
        (Document(page_content="OLED efficiency paper 4", metadata={"topic": "physics"}), 0.88),
        (Document(page_content="OLED efficiency paper 5", metadata={"topic": "physics"}), 0.85),

        #   (  - Gap )
        (Document(page_content="Business efficiency doc 1", metadata={"topic": "business"}), 0.68),
        (Document(page_content="Business efficiency doc 2", metadata={"topic": "business"}), 0.66),
        (Document(page_content="Business efficiency doc 3", metadata={"topic": "business"}), 0.64),

        #   (  - )
        (Document(page_content="Biology fluorescence doc 1", metadata={"topic": "biology"}), 0.42),
        (Document(page_content="Biology fluorescence doc 2", metadata={"topic": "biology"}), 0.40),
    ]

    print(f": {len(candidates)} ")
    print(f"  - / (0.85~0.95): 5 ")
    print(f"  -  (0.64~0.68): 3 ")
    print(f"  -  (0.40~0.42): 2 ")

    # 1:    
    print("\n[1]    ")
    step1 = rag._statistical_outlier_removal(candidates, method='mad')
    print(f": {len(candidates)}  {len(step1)} ({len(candidates) - len(step1)} )")

    # 2: Re-ranker Gap  
    print("\n[2] Re-ranker Gap  ")
    step2 = rag._reranker_gap_based_cutoff(step1, min_docs=3)
    print(f": {len(step1)}  {len(step2)} ({len(step1) - len(step2)} )")

    #   
    print("\n[ ]")
    print(f" {len(candidates)}  {len(step2)} (: {(1 - len(step2)/len(candidates))*100:.1f}%)")

    #   
    final_topics = {}
    for doc, score in step2:
        topic = doc.metadata.get("topic", "unknown")
        final_topics[topic] = final_topics.get(topic, 0) + 1

    print(f" :")
    for topic, count in final_topics.items():
        print(f"  - {topic}: {count}")

    #  : /   
    physics_count = final_topics.get("physics", 0)
    success = physics_count >= len(step2) * 0.7  # 70%  /
    print(f"\n: {' ' if success else ' '} (/  {physics_count}/{len(step2)} = {physics_count/len(step2)*100:.1f}%)")

    return success


def test_edge_cases():
    """  """
    print("\n" + "="*80)
    print("  4:  ")
    print("="*80)

    rag = create_mock_rag_chain()

    #  1:  
    print("\n[ 1]  ")
    result = rag._statistical_outlier_removal([], method='mad')
    print(f": {' ' if result == [] else ' '}")

    #  2:  1
    print("\n[ 2]  1")
    candidates = [(Document(page_content="Doc 1"), 0.9)]
    result = rag._statistical_outlier_removal(candidates, method='mad')
    print(f": {' ' if len(result) == 1 else ' '}")

    #  3:   
    print("\n[ 3]   ")
    candidates = [(Document(page_content=f"Doc {i}"), 0.9) for i in range(5)]
    result = rag._statistical_outlier_removal(candidates, method='mad')
    print(f": {' ' if len(result) == 5 else ' '}")

    #  4: Gap  -  min_docs 
    print("\n[ 4] min_docs  ")
    candidates = [(Document(page_content=f"Doc {i}"), 0.9 - i*0.1) for i in range(2)]
    result = rag._reranker_gap_based_cutoff(candidates, min_docs=5)
    print(f": {' ' if len(result) == 2 else ' '}")

    return True


def run_all_tests():
    """  """
    print("\n" + "="*80)
    print("RAG Smart Filtering Test Start")
    print("="*80)

    tests = [
        ("   ", test_statistical_outlier_removal),
        ("Re-ranker Gap  ", test_reranker_gap_based_cutoff),
        (" ", test_integrated_scenario),
        (" ", test_edge_cases),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"\n  : {e}")
            import traceback
            traceback.print_exc()

    #  
    print("\n" + "="*80)
    print("   ")
    print("="*80)

    passed = sum(1 for _, result, _ in results if result)
    total = len(results)

    for test_name, result, error in results:
        status = " " if result else " "
        print(f"{status} - {test_name}")
        if error:
            print(f"     : {error}")

    print(f"\n {total}   {passed}  ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n[SUCCESS]   !")
    else:
        print(f"\n[FAILED] {total - passed}  ")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
