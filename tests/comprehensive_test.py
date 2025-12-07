"""
종합 RAG 성능 테스트
- 다양한 질문 유형 테스트
- 파일명 기반 검색 테스트
- 답변 품질 및 성능 측정
"""

from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()  # Windows 터미널 한글 출력 설정

import os
import sys
import time
import json
from datetime import datetime

# 환경 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


# 테스트 케이스 정의
TEST_CASES = [
    # 1. 파일명 기반 검색 테스트 (이게 실패하면 문제)
    {
        "category": "파일명 기반",
        "question": "Lennart Balkenhol의 연구는?",
        "expected_file": "OLED_2010.14287v1.pdf",  # 파일명에 저자 이름 있어야 함
        "description": "파일명/저자명 검색"
    },
    {
        "category": "파일명 기반",
        "question": "Hyperfluorescence OLED에 대해 설명해줘",
        "expected_file": "HF_OLED_Nature_Photonics",
        "description": "파일명 약어 검색"
    },
    {
        "category": "파일명 기반",
        "question": "LG디스플레이 최신 뉴스는?",
        "expected_file": "lgd_display_news",
        "description": "파일명 키워드 검색"
    },

    # 2. 기술 용어 검색 테스트
    {
        "category": "기술 용어",
        "question": "TADF의 효율은?",
        "expected_keywords": ["TADF", "효율", "%"],
        "description": "Simple 질문 - 숫자 답변"
    },
    {
        "category": "기술 용어",
        "question": "kFRET 값은?",
        "expected_keywords": ["kFRET", "s-1", "10"],
        "description": "Simple 질문 - 특정 값"
    },
    {
        "category": "기술 용어",
        "question": "OLED의 발광 원리는?",
        "expected_keywords": ["전자", "정공", "재결합", "발광"],
        "description": "Normal 질문 - 원리 설명"
    },

    # 3. 비교/분석 질문
    {
        "category": "비교/분석",
        "question": "OLED와 QLED의 차이는?",
        "expected_keywords": ["OLED", "QLED", "차이", "양자점"],
        "description": "Complex 질문 - 비교"
    },
    {
        "category": "비교/분석",
        "question": "TADF와 형광 재료의 장단점은?",
        "expected_keywords": ["TADF", "형광", "장점", "단점"],
        "description": "Complex 질문 - 장단점"
    },

    # 4. 개념 이해 질문
    {
        "category": "개념 이해",
        "question": "OLED는 무엇인가?",
        "expected_keywords": ["유기", "발광", "다이오드"],
        "description": "Normal 질문 - 정의"
    },
    {
        "category": "개념 이해",
        "question": "Hyperfluorescence 기술이란?",
        "expected_keywords": ["형광", "TADF", "도펀트"],
        "description": "Normal 질문 - 기술 개념"
    },

    # 5. 숫자/데이터 질문
    {
        "category": "숫자/데이터",
        "question": "ACRSA의 EQE는?",
        "expected_keywords": ["EQE", "%", "ACRSA"],
        "description": "Simple 질문 - 성능 수치"
    },
    {
        "category": "숫자/데이터",
        "question": "파장은 몇 nm인가?",
        "expected_keywords": ["nm", "파장"],
        "description": "Simple 질문 - 파장 값"
    },
]


def run_test(test_case, rag_chain, vector_store, test_number, total_tests):
    """단일 테스트 실행"""

    print(f"\n{'='*80}")
    print(f"[테스트 {test_number}/{total_tests}] {test_case['category']}")
    print(f"질문: {test_case['question']}")
    print(f"설명: {test_case['description']}")
    print(f"{'='*80}")

    result = {
        "test_number": test_number,
        "category": test_case['category'],
        "question": test_case['question'],
        "description": test_case['description'],
        "timestamp": datetime.now().isoformat(),
    }

    # 1. 직접 검색 테스트
    print("\n[1단계] 직접 벡터 검색...")
    try:
        start_time = time.time()
        docs_with_scores = vector_store.vectorstore.similarity_search_with_score(
            test_case['question'], k=10
        )
        search_time = time.time() - start_time

        print(f"  검색 시간: {search_time:.2f}초")
        print(f"  검색 결과: {len(docs_with_scores)}개")

        result["direct_search"] = {
            "time": search_time,
            "count": len(docs_with_scores),
            "top_files": []
        }

        # 상위 5개 문서 출력
        if docs_with_scores:
            print(f"\n  상위 5개 문서:")
            for i, (doc, score) in enumerate(docs_with_scores[:5], 1):
                file_name = doc.metadata.get('source', 'N/A')
                page = doc.metadata.get('page_number', 'N/A')
                print(f"    [{i}] 점수: {score:.2f} | {file_name} p.{page}")
                print(f"        내용: {doc.page_content[:80]}...")

                result["direct_search"]["top_files"].append({
                    "rank": i,
                    "score": float(score),
                    "file": file_name,
                    "page": page
                })

            # 파일명 검증
            if "expected_file" in test_case:
                expected = test_case["expected_file"]
                top_file = docs_with_scores[0][0].metadata.get('source', '')
                if expected in top_file:
                    print(f"\n  [OK] 기대 파일 검색 성공: {expected}")
                    result["file_match"] = True
                else:
                    print(f"\n  [WARN] 기대 파일 불일치")
                    print(f"    기대: {expected}")
                    print(f"    실제: {top_file}")
                    result["file_match"] = False

    except Exception as e:
        print(f"  [ERROR] 검색 실패: {e}")
        result["direct_search"] = {"error": str(e)}

    # 2. RAG 체인 실행
    print("\n[2단계] RAG 체인 실행...")
    try:
        start_time = time.time()
        response = rag_chain.query(
            question=test_case['question'],
            chat_history=[]
        )
        rag_time = time.time() - start_time

        answer = response.get('answer', '')
        context_docs = rag_chain._last_retrieved_docs

        print(f"\n  총 소요 시간: {rag_time:.2f}초")
        print(f"  답변 길이: {len(answer)} 글자")
        print(f"  사용 문서: {len(context_docs)}개")

        print(f"\n  답변:\n  {answer[:300]}...")

        result["rag_chain"] = {
            "time": rag_time,
            "answer_length": len(answer),
            "context_count": len(context_docs),
            "answer": answer
        }

        # 키워드 검증
        if "expected_keywords" in test_case:
            found_keywords = []
            missing_keywords = []

            for keyword in test_case["expected_keywords"]:
                if keyword.lower() in answer.lower():
                    found_keywords.append(keyword)
                else:
                    missing_keywords.append(keyword)

            print(f"\n  키워드 검증:")
            print(f"    찾음: {found_keywords}")
            if missing_keywords:
                print(f"    누락: {missing_keywords}")

            result["keyword_check"] = {
                "found": found_keywords,
                "missing": missing_keywords,
                "score": len(found_keywords) / len(test_case["expected_keywords"])
            }

    except Exception as e:
        print(f"  [ERROR] RAG 실행 실패: {e}")
        result["rag_chain"] = {"error": str(e)}

    # 3. 평가
    print(f"\n[3단계] 평가")

    # 성공 여부 판단
    success = True
    issues = []

    # 검색 시간 체크
    if result.get("rag_chain", {}).get("time", 999) > 30:
        success = False
        issues.append(f"응답 시간 초과 ({result['rag_chain']['time']:.1f}초 > 30초)")

    # 답변 길이 체크
    if result.get("rag_chain", {}).get("answer_length", 0) < 50:
        success = False
        issues.append(f"답변 너무 짧음 ({result['rag_chain']['answer_length']}자)")

    # 파일 매칭 체크
    if "file_match" in result and not result["file_match"]:
        success = False
        issues.append("기대 파일 검색 실패")

    # 키워드 체크
    if "keyword_check" in result:
        score = result["keyword_check"]["score"]
        if score < 0.5:
            success = False
            issues.append(f"키워드 부족 ({score:.0%})")

    result["success"] = success
    result["issues"] = issues

    if success:
        print(f"  [SUCCESS] 테스트 통과")
    else:
        print(f"  [FAIL] 테스트 실패")
        for issue in issues:
            print(f"    - {issue}")

    return result


def main():
    """메인 테스트 실행"""

    print("=" * 80)
    print("RAG 시스템 종합 테스트")
    print("=" * 80)
    print(f"시작 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"테스트 케이스: {len(TEST_CASES)}개")

    # 설정 로드
    config = ConfigManager().get_all()
    print(f"\n[설정]")
    print(f"  Chunk Size: {config.get('chunk_size')}")
    print(f"  Reranker: {config.get('use_reranker')}")
    print(f"  Question Classifier: {config.get('enable_question_classifier')}")

    # 초기화
    print(f"\n[초기화]")
    vector_store = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    rag_chain = RAGChain(
        vectorstore=vector_store,
        llm_api_type=config.get("llm_api_type", "request"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:4b"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.3),
        top_k=config.get("top_k", 3),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=config.get("reranker_initial_k", 60),
        enable_synonym_expansion=config.get("enable_synonym_expansion", True),
        enable_multi_query=config.get("enable_multi_query", True),
        multi_query_num=config.get("multi_query_num", 3),
    )
    print(f"  [OK] 초기화 완료")

    # DB 통계
    collection = vector_store.vectorstore._collection
    total_chunks = collection.count()
    print(f"  총 청크 수: {total_chunks:,}개")

    # 테스트 실행
    results = []
    for i, test_case in enumerate(TEST_CASES, 1):
        result = run_test(test_case, rag_chain, vector_store, i, len(TEST_CASES))
        results.append(result)

        # 다음 테스트 전에 잠시 대기
        if i < len(TEST_CASES):
            print("\n다음 테스트까지 2초 대기...")
            time.sleep(2)

    # 결과 요약
    print("\n" + "=" * 80)
    print("테스트 결과 요약")
    print("=" * 80)

    success_count = sum(1 for r in results if r.get("success", False))
    fail_count = len(results) - success_count

    print(f"\n총 테스트: {len(results)}개")
    print(f"성공: {success_count}개 ({success_count/len(results)*100:.1f}%)")
    print(f"실패: {fail_count}개 ({fail_count/len(results)*100:.1f}%)")

    # 카테고리별 통계
    print(f"\n[카테고리별 성공률]")
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "success": 0}
        categories[cat]["total"] += 1
        if r.get("success", False):
            categories[cat]["success"] += 1

    for cat, stats in categories.items():
        rate = stats["success"] / stats["total"] * 100
        print(f"  {cat}: {stats['success']}/{stats['total']} ({rate:.1f}%)")

    # 성능 통계
    print(f"\n[성능 통계]")
    rag_times = [r["rag_chain"]["time"] for r in results if "time" in r.get("rag_chain", {})]
    if rag_times:
        print(f"  평균 응답 시간: {sum(rag_times)/len(rag_times):.2f}초")
        print(f"  최소 응답 시간: {min(rag_times):.2f}초")
        print(f"  최대 응답 시간: {max(rag_times):.2f}초")

    # 실패한 테스트 상세
    if fail_count > 0:
        print(f"\n[실패한 테스트 상세]")
        for r in results:
            if not r.get("success", False):
                print(f"\n  테스트 #{r['test_number']}: {r['question']}")
                for issue in r.get("issues", []):
                    print(f"    - {issue}")

    # 결과 저장
    output_file = f"comprehensive_test_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(results),
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n결과 저장: {output_file}")
    print(f"\n종료 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
