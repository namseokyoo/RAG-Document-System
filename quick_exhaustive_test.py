#!/usr/bin/env python3
"""
빠른 Exhaustive Query 검증 테스트
config_test.json 적용 확인
"""

import sys
import os
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 오프라인 모드 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
import time

def load_config(config_file="config_test.json"):
    """config_test.json 로드"""
    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_exhaustive_query():
    """Exhaustive Query 테스트"""
    print("="*80)
    print("빠른 Exhaustive Query 검증")
    print("="*80)

    # Config 로드
    print(f"\n[1/5] Config 로드 중...")
    config = load_config("config_test.json")

    print(f"\n[Config 확인]")
    print(f"  diversity_penalty: {config.get('diversity_penalty', 0.0)}")
    print(f"  enable_file_aggregation: {config.get('enable_file_aggregation', False)}")
    print(f"  file_aggregation_strategy: {config.get('file_aggregation_strategy', 'N/A')}")
    print(f"  file_aggregation_top_n: {config.get('file_aggregation_top_n', 'N/A')}")

    # VectorStore 초기화
    print(f"\n[2/5] VectorStore 초기화 중...")
    start = time.time()
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "request"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
        distance_function=config.get("chroma_distance_function", "cosine")
    )
    print(f"  초기화 완료: {time.time()-start:.1f}초")

    # RAG Chain 초기화
    print(f"\n[3/5] RAG Chain 초기화 중...")
    start = time.time()

    multi_query_num = int(config.get("multi_query_num", 3))
    enable_multi_query = config.get("enable_multi_query", True) and multi_query_num > 0

    rag = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "openai"),
        llm_base_url=config.get("llm_base_url", "https://api.openai.com/v1"),
        llm_model=config.get("llm_model", "gpt-4o-mini"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.3),
        top_k=config.get("top_k", 5),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=config.get("reranker_initial_k", 30),
        enable_synonym_expansion=config.get("enable_synonym_expansion", False),
        enable_multi_query=enable_multi_query,
        multi_query_num=multi_query_num,
        diversity_penalty=config.get("diversity_penalty", 0.0),
        diversity_source_key=config.get("diversity_source_key", "source"),
        enable_file_aggregation=config.get("enable_file_aggregation", False),
        file_aggregation_strategy=config.get("file_aggregation_strategy", "weighted"),
        file_aggregation_top_n=config.get("file_aggregation_top_n", 20),
        file_aggregation_min_chunks=config.get("file_aggregation_min_chunks", 1),
        enable_hybrid_search=config.get("enable_hybrid_search", True),
        hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5)
    )
    print(f"  초기화 완료: {time.time()-start:.1f}초")

    # Test 1: Exhaustive Query
    print(f"\n[4/5] Test 1: Exhaustive Query - 파일 리스트 요청")
    print("="*80)

    question = "모든 OLED 논문을 찾아줘"
    print(f"\n질문: {question}")

    start = time.time()
    result = rag.query(question)
    elapsed = time.time() - start

    print(f"\n[결과]")
    print(f"  성공: {result.get('success', False)}")
    print(f"  소요시간: {elapsed:.1f}초")
    print(f"  분류: {result.get('classification', {}).get('type', 'N/A')}")
    print(f"  출처 개수: {len(result.get('sources', []))}")

    # 답변 출력
    answer = result.get('answer', '')
    print(f"\n[답변 미리보기] (처음 500자)")
    print("-"*80)
    print(answer[:500])
    print("-"*80)

    # 파일 리스트 형식 확인
    is_file_list = False
    if '|' in answer and ('순위' in answer or '파일명' in answer or 'Rank' in answer.lower() or '관련도' in answer):
        print(f"\n✅ 파일 리스트 형식 감지됨!")
        is_file_list = True
    elif 'OLED' in answer and ('논문' in answer or '문서' in answer):
        print(f"\n⚠️  일반 답변 형식 (파일 리스트 아님)")
    else:
        print(f"\n❓ 형식 불확실")

    # Test 2: Normal Query (비교용)
    print(f"\n[5/5] Test 2: Normal Query - 일반 질문 (비교용)")
    print("="*80)

    question2 = "OLED란 무엇인가?"
    print(f"\n질문: {question2}")

    start = time.time()
    result2 = rag.query(question2)
    elapsed2 = time.time() - start

    print(f"\n[결과]")
    print(f"  성공: {result2.get('success', False)}")
    print(f"  소요시간: {elapsed2:.1f}초")
    print(f"  분류: {result2.get('classification', {}).get('type', 'N/A')}")
    print(f"  출처 개수: {len(result2.get('sources', []))}")

    # 답변 출력
    answer2 = result2.get('answer', '')
    print(f"\n[답변 미리보기] (처음 300자)")
    print("-"*80)
    print(answer2[:300])
    print("-"*80)

    # Diversity 확인
    print(f"\n" + "="*80)
    print("[Diversity 검증]")
    print("="*80)

    sources1 = result.get('sources', [])
    sources2 = result2.get('sources', [])

    # Test 1 Diversity
    if sources1:
        files1 = [s.get('file_name', '') for s in sources1]
        unique1 = len(set(files1))
        diversity1 = unique1 / len(files1) if files1 else 0
        print(f"\n[Test 1 - Exhaustive Query]")
        print(f"  총 출처: {len(files1)}개")
        print(f"  고유 파일: {unique1}개")
        print(f"  Diversity Ratio: {diversity1:.1%}")

    # Test 2 Diversity
    diversity2 = 0
    if sources2:
        files2 = [s.get('file_name', '') for s in sources2]
        unique2 = len(set(files2))
        diversity2 = unique2 / len(files2) if files2 else 0
        print(f"\n[Test 2 - Normal Query]")
        print(f"  총 출처: {len(files2)}개")
        print(f"  고유 파일: {unique2}개")
        print(f"  Diversity Ratio: {diversity2:.1%}")

    # 최종 판정
    print(f"\n" + "="*80)
    print("[최종 판정]")
    print("="*80)

    # 1. File Aggregation 작동 여부
    if is_file_list:
        print(f"\n✅ 1. File Aggregation 작동: YES")
        print(f"     → Exhaustive Query가 파일 리스트로 응답")
    else:
        print(f"\n❌ 1. File Aggregation 작동: NO")
        print(f"     → 일반 답변으로 처리됨")

    # 2. Diversity Penalty 효과
    if sources2:
        if diversity2 >= 0.5:
            print(f"\n✅ 2. Diversity Penalty (0.35) 효과: GOOD")
            print(f"     → Diversity Ratio {diversity2:.1%} >= 50%")
        else:
            print(f"\n⚠️  2. Diversity Penalty (0.35) 효과: PARTIAL")
            print(f"     → Diversity Ratio {diversity2:.1%} < 50%")

    print(f"\n" + "="*80)
    print("빠른 검증 완료")
    print("="*80)

if __name__ == "__main__":
    test_exhaustive_query()
