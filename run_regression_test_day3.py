#!/usr/bin/env python3
"""
Phase 3 Day 3 회귀 테스트
Day 2와 동일한 35개 테스트 케이스 재실행
diversity_penalty=0.35 적용 효과 측정
"""

import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json
import time
from datetime import datetime
from pathlib import Path
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def load_test_cases():
    """테스트 케이스 로드"""
    with open('test_cases_comprehensive_v2.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 모든 suite의 테스트 추출
    all_tests = []
    for suite in data['test_suites']:
        all_tests.extend(suite['tests'])

    # conversation 제외 (conversation 필드가 있는 테스트 = 멀티턴 대화 테스트)
    filtered_tests = [t for t in all_tests if 'conversation' not in t]

    return filtered_tests


def load_config():
    """Config 로드"""
    with open('config_test.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def initialize_rag(config):
    """RAG Chain 초기화"""
    print(f"\n[초기화] VectorStore 로드 중...")
    start = time.time()
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "request"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
        distance_function=config.get("chroma_distance_function", "cosine")
    )
    print(f"  ✓ VectorStore 로드 완료: {time.time()-start:.1f}초")

    print(f"[초기화] RAG Chain 로드 중...")
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
    print(f"  ✓ RAG Chain 로드 완료: {time.time()-start:.1f}초")

    return rag


def run_single_test(rag, test_case, test_idx, total_tests):
    """단일 테스트 실행"""
    test_id = test_case['test_id']
    question = test_case['question']
    category = test_case.get('category', test_id.split('_')[0])  # test_id 앞부분을 category로 사용

    print(f"\n{'='*80}")
    print(f"[{test_idx}/{total_tests}] {test_id} ({category})")
    print(f"질문: {question}")
    print(f"{'='*80}")

    start = time.time()
    try:
        result = rag.query(question)
        elapsed = time.time() - start

        success = result.get('success', False)
        answer = result.get('answer', '')
        sources = result.get('sources', [])

        # Diversity 계산
        source_files = [s.get('file_name', '') for s in sources]
        unique_files = len(set(source_files))
        diversity_ratio = unique_files / len(source_files) if source_files else 0

        print(f"✓ 성공")
        print(f"  소요시간: {elapsed:.1f}초")
        print(f"  출처: {len(sources)}개 (고유: {unique_files}개, Diversity: {diversity_ratio:.1%})")
        print(f"  답변 길이: {len(answer)}자")

        return {
            "test_id": test_id,
            "category": category,
            "question": question,
            "success": True,
            "elapsed_time": elapsed,
            "sources_count": len(sources),
            "unique_sources_count": unique_files,
            "diversity_ratio": diversity_ratio,
            "answer_length": len(answer),
            "source_files": source_files[:5]  # 상위 5개만 저장
        }

    except Exception as e:
        elapsed = time.time() - start
        print(f"✗ 실패: {str(e)[:100]}")

        return {
            "test_id": test_id,
            "category": category,
            "question": question,
            "success": False,
            "elapsed_time": elapsed,
            "error": str(e)
        }


def main():
    """메인 함수"""
    print("="*80)
    print("Phase 3 Day 3 회귀 테스트")
    print("="*80)
    print(f"\n실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Config 로드
    config = load_config()
    print(f"\n[Config]")
    print(f"  diversity_penalty: {config.get('diversity_penalty')}")
    print(f"  enable_file_aggregation: {config.get('enable_file_aggregation')}")
    print(f"  LLM: {config.get('llm_model')}")
    print(f"  Reranker: {config.get('reranker_model')}")

    # 테스트 케이스 로드
    test_cases = load_test_cases()
    print(f"\n[테스트]")
    print(f"  총 테스트: {len(test_cases)}개")
    print(f"  제외: conversation 테스트")

    # RAG 초기화
    rag = initialize_rag(config)

    # 테스트 실행
    print("\n" + "="*80)
    print("테스트 실행 시작")
    print("="*80)

    start_time = time.time()
    results = []

    for idx, test_case in enumerate(test_cases, 1):
        result = run_single_test(rag, test_case, idx, len(test_cases))
        results.append(result)

    total_elapsed = time.time() - start_time

    # 결과 분석
    print("\n" + "="*80)
    print("테스트 결과 분석")
    print("="*80)

    success_results = [r for r in results if r['success']]

    print(f"\n[전체]")
    print(f"  총 테스트: {len(results)}개")
    print(f"  성공: {len(success_results)}개 ({len(success_results)/len(results)*100:.1f}%)")
    print(f"  실패: {len(results) - len(success_results)}개")
    print(f"  총 소요시간: {total_elapsed/60:.1f}분")
    print(f"  평균 소요시간: {total_elapsed/len(results):.1f}초/테스트")

    # Diversity 지표
    if success_results:
        avg_unique_docs = sum(r['unique_sources_count'] for r in success_results) / len(success_results)
        avg_diversity_ratio = sum(r['diversity_ratio'] for r in success_results) / len(success_results)
        multi_doc_tests = sum(1 for r in success_results if r['unique_sources_count'] >= 2)
        multi_doc_ratio = multi_doc_tests / len(success_results)

        print(f"\n[Diversity 지표]")
        print(f"  평균 고유 문서: {avg_unique_docs:.2f}개")
        print(f"  Diversity Ratio: {avg_diversity_ratio:.1%}")
        print(f"  Multi-doc 비율: {multi_doc_tests}/{len(success_results)} ({multi_doc_ratio:.1%})")

        # 목표 달성 여부
        goals_met = 0
        if avg_unique_docs >= 2.5:
            print(f"  ✓ 평균 고유 문서 목표 달성 (>= 2.5개)")
            goals_met += 1
        else:
            print(f"  ✗ 평균 고유 문서 목표 미달 (< 2.5개)")

        if avg_diversity_ratio >= 0.50:
            print(f"  ✓ Diversity Ratio 목표 달성 (>= 50%)")
            goals_met += 1
        else:
            print(f"  ✗ Diversity Ratio 목표 미달 (< 50%)")

        if multi_doc_ratio >= 0.60:
            print(f"  ✓ Multi-doc 비율 목표 달성 (>= 60%)")
            goals_met += 1
        else:
            print(f"  ✗ Multi-doc 비율 목표 미달 (< 60%)")

        print(f"\n달성한 보수적 목표: {goals_met}/3")

    # 고유 문서 수 분포
    from collections import Counter
    unique_docs_list = [r['unique_sources_count'] for r in success_results]
    distribution = Counter(unique_docs_list)

    print(f"\n[고유 문서 수 분포]")
    for docs, count in sorted(distribution.items()):
        percentage = (count / len(success_results)) * 100
        bar = "█" * int(percentage / 2)
        print(f"  {docs}개 문서: {count:2d}회 ({percentage:5.1f}%) {bar}")

    # 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "test_config": {
            "diversity_penalty": config.get('diversity_penalty'),
            "enable_file_aggregation": config.get('enable_file_aggregation'),
            "llm_model": config.get('llm_model'),
            "reranker_model": config.get('reranker_model')
        },
        "summary": {
            "total_tests": len(results),
            "success_tests": len(success_results),
            "success_rate": len(success_results) / len(results),
            "total_elapsed_time": total_elapsed,
            "avg_elapsed_time": total_elapsed / len(results),
            "avg_unique_docs": avg_unique_docs if success_results else 0,
            "avg_diversity_ratio": avg_diversity_ratio if success_results else 0,
            "multi_doc_ratio": multi_doc_ratio if success_results else 0,
            "goals_met": goals_met if success_results else 0,
            "unique_docs_distribution": dict(distribution)
        },
        "detailed_results": results
    }

    output_file = f"regression_test_day3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_file}")
    print("\n" + "="*80)
    print("회귀 테스트 완료")
    print("="*80)


if __name__ == "__main__":
    main()
