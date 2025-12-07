"""
Phase A Baseline 테스트
Phase A 구현 전 현재 성능 측정 (v3.1)

목적: Phase A 적용 전후 비교를 위한 Baseline 데이터 수집
"""
import sys
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any

# UTF-8 출력 설정 (Windows 콘솔 호환)
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


# 확장된 테스트 쿼리 세트 (50개)
TEST_QUERIES = {
    "easy": {
        "technical": [
            "TADF란 무엇인가?",
            "OLED란?",
            "FRET란 무엇인가?",
            "EQE란?",
            "Hyperfluorescence란?",
            "ACRSA란 무엇인가?",
            "DABNA1이란?",
            "kFRET는 무엇을 의미하나?",
        ],
        "business": [
            "LG디스플레이는 어떤 회사인가?",
            "OLED 시장 규모는?",
            "8.6세대 OLED란?",
            "OLEDoS란?",
        ],
        "hr": [
            "HRD-Net이란?",
            "출결관리 시스템이란?",
            "훈련생 출결 관리란?",
        ],
    },
    "medium": [
        # Technical + 수치/성능 관련
        "TADF 재료의 양자 효율은 얼마인가?",
        "FRET 에너지 전달 효율은?",
        "kFRET 값은 얼마인가?",
        "OLED의 외부 양자 효율(EQE)은?",
        "Hyperfluorescence 기술의 핵심은?",
        "TADF sensitizer의 역할은?",
        "ACRSA의 특징은?",
        "DABNA1과 ACRSA의 차이는?",
        "CT 에너지 분산이 FRET에 미치는 영향은?",
        "spiro-linkage의 역할은?",

        # Business + 기술 연결
        "LG디스플레이의 OLED 시장 동향은?",
        "8.6세대 IT OLED 생산라인은?",
        "LG디스플레이의 OLED 기술 경쟁력은?",
        "LTPO 기술이란?",
        "OLEDoS 기술의 장점은?",

        # HR 시스템
        "HRD-Net 출결 관리 방법은?",
        "출결관리 앱 설치 방법은?",
        "HRD-Net 앱 사용법은?",
        "출결 QR 코드 스캔 방법은?",
        "자동시간 설정이 필요한 이유는?",
    ],
    "hard": [
        # 복합 도메인 질문
        "TADF 재료와 OLED 효율의 관계를 설명해줘",
        "분자 구조와 성능의 관계는?",
        "FRET 효율과 CT 에너지의 상관관계는?",
        "Hyperfluorescence가 OLED 성능을 향상시키는 메커니즘은?",

        # 비교/분석 질문
        "ACRSA와 DABNA1의 성능을 비교해줘",
        "BM25와 Vector 검색의 차이는?",
        "Small-to-Large 검색과 Standard 검색의 장단점은?",

        # 기술+비즈니스 통합
        "TADF 기술 발전이 LG디스플레이 비즈니스에 미치는 영향은?",
        "8.6세대 IT OLED 생산라인의 특징과 LG디스플레이 전략을 연결해서 설명해줘",
        "OLED 기술 발전이 디스플레이 시장에 미치는 영향은?",
    ],
}


def calculate_category_purity(query: str, categories: List[str]) -> float:
    """질문에 맞는 카테고리 순도 계산

    Args:
        query: 사용자 질문
        categories: 검색된 문서들의 카테고리 리스트

    Returns:
        순도 점수 (0-1)
    """
    if not categories:
        return 0.0

    # 질문 타입 추정
    query_lower = query.lower()

    if any(kw in query_lower for kw in ['tadf', 'oled', 'fret', 'quantum', '양자', '효율', 'eqe',
                                          'hyperfluorescence', 'acrsa', 'dabna', 'sensitizer',
                                          '분자', '구조', 'ct', '에너지']):
        expected = ['technical', 'business']  # 기술은 비즈니스와 연결 가능

    elif any(kw in query_lower for kw in ['lg디스플레이', '시장', '뉴스', '생산', '라인',
                                            '투자', '전략', 'oledo', 'ltpo']):
        expected = ['business', 'technical']  # 비즈니스는 기술과 연결 가능

    elif any(kw in query_lower for kw in ['hrd', '출결', '교육', '훈련', '앱', '관리',
                                            'qr', '스캔']):
        expected = ['hr']

    elif any(kw in query_lower for kw in ['안전', '규정', '위험', '보건']):
        expected = ['safety']

    else:
        # 판단 불가능 - 중립적 평가
        return 0.7

    # 순도 계산
    match_count = sum(1 for c in categories if c in expected)
    purity = match_count / len(categories)

    return purity


def analyze_sources(sources: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """출처 분석

    Args:
        sources: RAG 체인이 반환한 출처 리스트
        query: 원본 질문

    Returns:
        분석 결과 딕셔너리
    """
    categories = []
    scores = []
    file_names = set()

    for source in sources:
        category = source.get('category', 'unknown')
        score = source.get('score', 0)
        file_name = source.get('file_name', 'unknown')

        categories.append(category)
        scores.append(score)
        file_names.add(file_name)

    # 카테고리 분포
    category_dist = {}
    for cat in set(categories):
        count = categories.count(cat)
        category_dist[cat] = {
            'count': count,
            'percentage': count / len(categories) if categories else 0
        }

    # 카테고리 순도
    purity = calculate_category_purity(query, categories)

    return {
        'num_sources': len(sources),
        'unique_files': len(file_names),
        'categories': categories,
        'category_distribution': category_dist,
        'category_purity': purity,
        'avg_score': sum(scores) / len(scores) if scores else 0,
        'min_score': min(scores) if scores else 0,
        'max_score': max(scores) if scores else 0,
    }


def check_answer_quality(answer: str) -> Dict[str, Any]:
    """답변 품질 체크

    Args:
        answer: 생성된 답변

    Returns:
        품질 지표 딕셔너리
    """
    # 인라인 출처 확인
    has_inline_citation = '[' in answer and ']' in answer
    citation_count = answer.count('[')

    # 금지 구문 체크
    forbidden_phrases = [
        "정보를 찾을 수 없습니다",
        "문서에 없습니다",
        "확인할 수 없습니다",
        "제공된 문서에서는 해당 정보를 찾을 수 없습니다"
    ]
    has_forbidden_phrase = any(phrase in answer for phrase in forbidden_phrases)
    found_forbidden = [phrase for phrase in forbidden_phrases if phrase in answer]

    # 답변 구조 확인
    has_sections = '##' in answer  # Markdown 섹션 헤더
    has_list = any(marker in answer for marker in ['- ', '* ', '1.', '2.'])

    # 참조 정보 섹션 확인
    has_reference_section = '## 참조 정보' in answer or '참조 정보' in answer

    return {
        'answer_length': len(answer),
        'has_inline_citation': has_inline_citation,
        'citation_count': citation_count,
        'has_forbidden_phrase': has_forbidden_phrase,
        'forbidden_phrases_found': found_forbidden,
        'has_sections': has_sections,
        'has_list': has_list,
        'has_reference_section': has_reference_section,
    }


def run_baseline_test():
    """Baseline 성능 측정 실행"""

    print("=" * 80)
    print("Phase A Baseline 테스트 (v3.1)")
    print("=" * 80)
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 설정 로드
    config = ConfigManager().get_all()

    # VectorStore 초기화
    print("VectorStore 초기화 중...")
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    # RAGChain 초기화
    print("RAGChain 초기화 중...")
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "ollama"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:latest"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.3),
        top_k=config.get("top_k", 3),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=config.get("reranker_initial_k", 20),
        enable_hybrid_search=config.get("enable_hybrid_search", True),
        hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5),
    )
    print()

    # 결과 저장 구조
    results = {
        "timestamp": datetime.now().isoformat(),
        "version": "v3.1 (before Phase A)",
        "config": {
            "llm_model": config.get("llm_model"),
            "embedding_model": config.get("embedding_model"),
            "top_k": config.get("top_k"),
            "use_reranker": config.get("use_reranker"),
            "enable_hybrid_search": config.get("enable_hybrid_search"),
        },
        "queries": {},
        "summary": {}
    }

    # 난이도별 집계
    difficulty_stats = {
        "easy": {"times": [], "purities": [], "citation_rates": [], "forbidden_rates": []},
        "medium": {"times": [], "purities": [], "citation_rates": [], "forbidden_rates": []},
        "hard": {"times": [], "purities": [], "citation_rates": [], "forbidden_rates": []},
    }

    # 전체 쿼리 리스트 생성
    all_queries_list = []

    # Easy 쿼리
    for category, queries in TEST_QUERIES["easy"].items():
        for query in queries:
            all_queries_list.append((query, "easy", category))

    # Medium 쿼리
    for query in TEST_QUERIES["medium"]:
        all_queries_list.append((query, "medium", "mixed"))

    # Hard 쿼리
    for query in TEST_QUERIES["hard"]:
        all_queries_list.append((query, "hard", "complex"))

    total_queries = len(all_queries_list)
    print(f"총 {total_queries}개 쿼리 테스트 시작\n")

    # 각 쿼리 테스트
    for idx, (query, difficulty, category_hint) in enumerate(all_queries_list, 1):
        print(f"\n{'='*80}")
        print(f"[{idx}/{total_queries}] 난이도: {difficulty.upper()}, 카테고리: {category_hint}")
        print(f"질문: {query}")
        print(f"{'='*80}")

        try:
            # 성능 측정
            start_time = time.time()
            result = rag_chain.query(query)
            elapsed_time = time.time() - start_time

            # 결과 추출
            answer = result.get("answer", "")
            sources = result.get("sources", [])

            # 분석
            source_analysis = analyze_sources(sources, query)
            answer_quality = check_answer_quality(answer)

            # 출력
            print(f"\n⏱️  응답 시간: {elapsed_time:.2f}초")
            print(f"📊 출처: {source_analysis['num_sources']}개 (파일 {source_analysis['unique_files']}개)")
            print(f"📁 카테고리 분포: {source_analysis['category_distribution']}")
            print(f"🎯 카테고리 순도: {source_analysis['category_purity']:.1%}")
            print(f"⭐ 평균 신뢰도: {source_analysis['avg_score']:.1f}")
            print(f"📝 답변 길이: {answer_quality['answer_length']}자")
            print(f"🔗 인라인 출처: {'✓' if answer_quality['has_inline_citation'] else '✗'} ({answer_quality['citation_count']}개)")
            print(f"⚠️  금지 구문: {'✗ 발견!' if answer_quality['has_forbidden_phrase'] else '✓'}")

            if answer_quality['has_forbidden_phrase']:
                print(f"   발견된 구문: {answer_quality['forbidden_phrases_found']}")

            # 결과 저장
            query_result = {
                "query": query,
                "difficulty": difficulty,
                "category_hint": category_hint,
                "elapsed_time": elapsed_time,
                "source_analysis": source_analysis,
                "answer_quality": answer_quality,
                "answer_preview": answer[:200] + "..." if len(answer) > 200 else answer
            }

            results["queries"][f"query_{idx}"] = query_result

            # 난이도별 집계
            stats = difficulty_stats[difficulty]
            stats["times"].append(elapsed_time)
            stats["purities"].append(source_analysis['category_purity'])
            stats["citation_rates"].append(1 if answer_quality['has_inline_citation'] else 0)
            stats["forbidden_rates"].append(1 if answer_quality['has_forbidden_phrase'] else 0)

        except Exception as e:
            print(f"\n❌ 에러 발생: {e}")
            import traceback
            traceback.print_exc()

            results["queries"][f"query_{idx}"] = {
                "query": query,
                "difficulty": difficulty,
                "error": str(e)
            }

    # 요약 통계 계산
    print(f"\n\n{'='*80}")
    print("📊 요약 통계")
    print(f"{'='*80}\n")

    for difficulty, stats in difficulty_stats.items():
        if not stats["times"]:
            continue

        avg_time = sum(stats["times"]) / len(stats["times"])
        avg_purity = sum(stats["purities"]) / len(stats["purities"])
        citation_rate = sum(stats["citation_rates"]) / len(stats["citation_rates"])
        forbidden_rate = sum(stats["forbidden_rates"]) / len(stats["forbidden_rates"])

        print(f"[{difficulty.upper()}] (n={len(stats['times'])})")
        print(f"  평균 응답 시간: {avg_time:.2f}초")
        print(f"  평균 카테고리 순도: {avg_purity:.1%}")
        print(f"  인라인 출처 비율: {citation_rate:.1%}")
        print(f"  금지 구문 사용 비율: {forbidden_rate:.1%}")
        print()

        results["summary"][difficulty] = {
            "count": len(stats["times"]),
            "avg_response_time": avg_time,
            "avg_category_purity": avg_purity,
            "inline_citation_rate": citation_rate,
            "forbidden_phrase_rate": forbidden_rate,
        }

    # 전체 통계
    all_times = []
    all_purities = []
    all_citation_rates = []
    all_forbidden_rates = []

    for stats in difficulty_stats.values():
        all_times.extend(stats["times"])
        all_purities.extend(stats["purities"])
        all_citation_rates.extend(stats["citation_rates"])
        all_forbidden_rates.extend(stats["forbidden_rates"])

    if all_times:
        results["summary"]["overall"] = {
            "total_queries": len(all_times),
            "avg_response_time": sum(all_times) / len(all_times),
            "avg_category_purity": sum(all_purities) / len(all_purities),
            "inline_citation_rate": sum(all_citation_rates) / len(all_citation_rates),
            "forbidden_phrase_rate": sum(all_forbidden_rates) / len(all_forbidden_rates),
        }

        print(f"[OVERALL] (n={len(all_times)})")
        print(f"  평균 응답 시간: {results['summary']['overall']['avg_response_time']:.2f}초")
        print(f"  평균 카테고리 순도: {results['summary']['overall']['avg_category_purity']:.1%}")
        print(f"  인라인 출처 비율: {results['summary']['overall']['inline_citation_rate']:.1%}")
        print(f"  금지 구문 사용 비율: {results['summary']['overall']['forbidden_phrase_rate']:.1%}")

    # 결과 저장
    os.makedirs("test_results", exist_ok=True)
    output_file = f"test_results/phase_a_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*80}")
    print(f"✅ Baseline 테스트 완료!")
    print(f"📁 결과 저장: {output_file}")
    print(f"⏰ 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    return results


if __name__ == "__main__":
    try:
        results = run_baseline_test()
        print("\n테스트 성공적으로 완료되었습니다.")
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n\n❌ 치명적 에러 발생: {e}")
        import traceback
        traceback.print_exc()
