#!/usr/bin/env python3
"""
RAG 시스템 종합 테스트 실행 스크립트
모든 테스트 케이스를 실행하고 상세 로그를 수집
"""

import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# 프로젝트 경로 추가
sys.path.append(str(Path(__file__).parent))

from utils.detailed_logger import DetailedLogger, DetailedLog
from config import ConfigManager


def load_test_cases(file_path: str = "test_cases_comprehensive.json") -> Dict:
    """테스트 케이스 JSON 로드"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def initialize_rag_system(config_manager: ConfigManager):
    """RAG 시스템 초기화 (상세 로깅 모드)"""
    # 이 부분은 실제 RAGChain 초기화로 대체
    # 현재는 시뮬레이션
    print("[INFO] RAG 시스템 초기화 중...")
    print("[INFO] 상세 로깅 모드 활성화")

    # TODO: 실제 RAGChain 초기화
    # from utils.rag_chain import RAGChain
    # rag_chain = RAGChain(
    #     config=config_manager.config,
    #     detailed_logging=True
    # )

    return None  # 시뮬레이션


def run_single_test(
    test_case: Dict,
    rag_chain,
    logger: DetailedLogger
) -> DetailedLog:
    """단일 테스트 실행"""

    test_id = test_case['test_id']
    question = test_case['question']
    category = test_case['category']

    print(f"\n{'='*60}")
    print(f"[TEST] {test_id}: {category}")
    print(f"[QUESTION] {question}")
    print(f"{'='*60}")

    # 로그 시작
    log = logger.start_test(test_id, question)

    try:
        # === 시뮬레이션: 실제 RAG 실행으로 대체 필요 ===
        # 여기서는 테스트 구조를 보여주기 위한 더미 데이터
        import random

        # 1. Classification
        start_time = time.time()
        classification = {
            "type": test_case['expected_classification'],
            "confidence": random.uniform(0.7, 0.95),
            "method": "rule-based",
            "multi_query": category in ['normal', 'complex'],
            "max_results": 20,
            "max_tokens": 2048
        }
        logger.log_classification(
            q_type=classification['type'],
            confidence=classification['confidence'],
            method=classification['method'],
            multi_query=classification['multi_query'],
            max_results=classification['max_results'],
            max_tokens=classification['max_tokens'],
            elapsed_time=time.time() - start_time
        )
        print(f"  [1/7] Classification: {classification['type']} ({classification['confidence']:.2f})")

        # 2. Query Expansion
        start_time = time.time()
        expanded_queries = [question]
        if classification['multi_query']:
            expanded_queries = [
                question,
                f"{question} (확장1)",
                f"{question} (확장2)"
            ]
        logger.log_query_expansion(
            enabled=classification['multi_query'],
            original_query=question,
            expanded_queries=expanded_queries,
            elapsed_time=time.time() - start_time,
            llm_calls=1 if classification['multi_query'] else 0,
            tokens_used=150 if classification['multi_query'] else 0
        )
        print(f"  [2/7] Query Expansion: {len(expanded_queries)} queries")

        # 3. Search
        start_time = time.time()
        doc_count = random.randint(
            test_case['expected_doc_count'][0],
            test_case['expected_doc_count'][1]
        )
        logger.log_search(
            vector_search={
                "query": question,
                "k": 60,
                "results": doc_count,
                "elapsed_time": 1.2,
                "embedding_time": 0.3,
                "embedding_dimension": 1024,
                "top_scores": [0.9, 0.85, 0.8]
            },
            bm25_search={
                "query": question,
                "k": 60,
                "results": doc_count - 5,
                "elapsed_time": 0.5,
                "top_scores": [0.95, 0.88, 0.82]
            },
            fusion={
                "alpha": 0.5,
                "vector_results": doc_count,
                "bm25_results": doc_count - 5,
                "combined_results": doc_count,
                "elapsed_time": 0.1
            },
            total_elapsed_time=time.time() - start_time
        )
        print(f"  [3/7] Search: {doc_count} documents")

        # 4. Reranking
        start_time = time.time()
        reranked_count = min(doc_count, 20)
        scores = [random.uniform(0.5, 0.95) for _ in range(reranked_count)]
        scores.sort(reverse=True)
        logger.log_reranking(
            enabled=True,
            input_docs=doc_count,
            reranker_model="multilingual-mini",
            output_docs=reranked_count,
            score_threshold=0.5,
            adaptive_threshold=scores[0] * 0.6 if scores else None,
            scores=scores,
            elapsed_time=time.time() - start_time,
            filtered_by_score=doc_count - reranked_count,
            filtered_by_max=0
        )
        print(f"  [4/7] Reranking: {doc_count} → {reranked_count} documents")

        # 5. Context Expansion
        start_time = time.time()
        expanded_chunks = reranked_count * 2
        context_size = expanded_chunks * 800
        logger.log_context_expansion(
            enabled=True,
            initial_chunks=reranked_count,
            expanded_chunks=expanded_chunks,
            context_size_chars=context_size,
            context_size_tokens_estimate=int(context_size * 0.75),
            expansion_strategy="small-to-large",
            elapsed_time=time.time() - start_time
        )
        print(f"  [5/7] Context Expansion: {reranked_count} → {expanded_chunks} chunks")

        # 6. Generation
        start_time = time.time()
        time.sleep(2)  # LLM 호출 시뮬레이션
        answer = f"[시뮬레이션 답변] {question}에 대한 답변입니다..."
        output_tokens = random.randint(200, 500)
        logger.log_generation(
            llm_model="gemma3:4b",
            temperature=0.3,
            max_tokens=classification['max_tokens'],
            context_tokens_estimate=int(context_size * 0.75),
            output_tokens_estimate=output_tokens,
            elapsed_time=time.time() - start_time,
            streaming=True,
            prompt_template="System: You are a helpful assistant..."
        )
        print(f"  [6/7] Generation: {output_tokens} tokens")

        # 7. Citation
        start_time = time.time()
        sources = [
            {"source": "document_1.pdf", "page": 5},
            {"source": "document_2.pdf", "page": 12},
            {"source": "document_3.pdf", "page": 8}
        ]
        logger.log_citation(
            sources=sources,
            deduplication=True,
            accuracy_check=True,
            elapsed_time=time.time() - start_time
        )
        print(f"  [7/7] Citation: {len(sources)} sources")

        # 로그 완료
        log = logger.finalize(answer)

        print(f"  [RESULT] Total time: {log.total.elapsed_time:.2f}s")
        print(f"  [RESULT] LLM calls: {log.total.llm_calls}")
        print(f"  [RESULT] Tokens: {log.total.total_tokens_estimate}")

        return log

    except Exception as e:
        print(f"  [ERROR] {e}")
        logger.log_error(str(e), "unknown")
        log = logger.finalize("ERROR")
        return log


def run_comprehensive_test(
    test_cases_file: str = "test_cases_comprehensive.json",
    output_dir: str = "test_logs",
    summary_file: str = "test_summary.json"
):
    """종합 테스트 실행"""

    print("=" * 60)
    print("RAG 시스템 종합 테스트 시작")
    print("=" * 60)

    # 1. 테스트 케이스 로드
    print("\n[1/5] 테스트 케이스 로드 중...")
    test_data = load_test_cases(test_cases_file)
    total_tests = test_data['metadata']['total_tests']
    print(f"  - 총 테스트: {total_tests}개")
    print(f"  - 예상 소요 시간: {test_data['metadata']['expected_duration_minutes']}분")

    # 2. RAG 시스템 초기화
    print("\n[2/5] RAG 시스템 초기화 중...")
    config_manager = ConfigManager()
    rag_chain = initialize_rag_system(config_manager)

    # 3. 로거 초기화
    print("\n[3/5] 로거 초기화 중...")
    logger = DetailedLogger(output_dir)

    # 4. 테스트 실행
    print("\n[4/5] 테스트 실행 중...")
    all_logs: List[DetailedLog] = []
    test_count = 0

    for suite in test_data['test_suites']:
        suite_name = suite['suite_name']
        print(f"\n{'='*60}")
        print(f"[SUITE] {suite_name}")
        print(f"{'='*60}")

        for test_case in suite['tests']:
            test_count += 1
            print(f"\n[Progress] {test_count}/{total_tests}")

            # 테스트 실행
            log = run_single_test(test_case, rag_chain, logger)
            all_logs.append(log)

            # 간단한 대기 (시스템 부하 방지)
            time.sleep(1)

    # 5. 요약 저장
    print("\n[5/5] 요약 저장 중...")
    logger.save_summary(all_logs, summary_file)

    # 결과 출력
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)
    print(f"  - 총 테스트: {len(all_logs)}개")
    print(f"  - 성공: {len([l for l in all_logs if l.error is None])}개")
    print(f"  - 실패: {len([l for l in all_logs if l.error is not None])}개")

    # 통계 출력
    if all_logs:
        times = [l.total.elapsed_time for l in all_logs]
        print(f"\n[통계]")
        print(f"  - 평균 응답 시간: {sum(times)/len(times):.2f}s")
        print(f"  - 최소 응답 시간: {min(times):.2f}s")
        print(f"  - 최대 응답 시간: {max(times):.2f}s")

        llm_calls = [l.total.llm_calls for l in all_logs]
        print(f"  - 평균 LLM 호출: {sum(llm_calls)/len(llm_calls):.1f}회")

        tokens = [l.total.total_tokens_estimate for l in all_logs]
        print(f"  - 평균 토큰 사용: {sum(tokens)/len(tokens):.0f}개")

        costs = [l.total.estimated_cost for l in all_logs]
        print(f"  - 총 예상 비용: ${sum(costs):.4f}")

    print(f"\n[출력 파일]")
    print(f"  - 로그 디렉토리: {output_dir}/")
    print(f"  - 요약 파일: {output_dir}/{summary_file}")

    print("\n다음 단계:")
    print("  python analyze_test_results.py --input test_logs/test_summary.json")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG 시스템 종합 테스트")
    parser.add_argument(
        "--test-cases",
        default="test_cases_comprehensive.json",
        help="테스트 케이스 JSON 파일"
    )
    parser.add_argument(
        "--output-dir",
        default="test_logs",
        help="로그 출력 디렉토리"
    )
    parser.add_argument(
        "--summary",
        default="test_summary.json",
        help="요약 파일명"
    )

    args = parser.parse_args()

    try:
        run_comprehensive_test(
            test_cases_file=args.test_cases,
            output_dir=args.output_dir,
            summary_file=args.summary
        )
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자가 테스트를 중단했습니다.")
    except Exception as e:
        print(f"\n[오류] {e}")
        import traceback
        traceback.print_exc()
