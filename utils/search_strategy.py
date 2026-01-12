"""
검색 전략 매핑 테이블

질문 유형별로 최적화된 검색 파라미터를 정의합니다.
10개 분류 체계에 따라 HyDE, Multi-Query, BM25/Vector 가중치 등을 동적으로 조정합니다.
"""

from typing import Dict, Optional

# 10개 분류별 검색 전략 정의
SEARCH_STRATEGIES = {
    "simple_fact": {
        "enable_hyde": False,        # ❌ 단순 질문에는 불필요
        "enable_multi_query": False,  # ❌ 단순 질문에는 불필요
        "bm25_weight": 0.8,           # 키워드 정확도 중요
        "vector_weight": 0.2,
        "initial_k": 30,             # 적은 후보
        "max_results": 5,            # 적은 결과
        "adaptive_threshold_percentile": 0.7,  # 엄격한 필터링
        "skip_search": False,
    },
    "simple_keyword": {
        "enable_hyde": False,        # ❌ 키워드 검색에는 HyDE 부적합
        "enable_multi_query": False, # ❌ 키워드 검색에는 Multi-Query 불필요
        "bm25_weight": 0.9,           # 키워드 매칭 최우선
        "vector_weight": 0.1,
        "initial_k": 150,             # 넓은 검색 범위
        "max_results": 20,            # 많은 결과
        "adaptive_threshold_percentile": 0.4,  # 완화된 필터링
        "skip_search": False,
    },
    "normal_definition": {
        "enable_hyde": True,         # ✅ 정의 질문에는 HyDE 유용
        "enable_multi_query": False,
        "bm25_weight": 0.4,
        "vector_weight": 0.6,        # 의미론적 유사도 중요
        "initial_k": 60,
        "max_results": 8,
        "adaptive_threshold_percentile": 0.6,
        "skip_search": False,
    },
    "normal_explanation": {
        "enable_hyde": True,         # ✅ 설명 질문에는 HyDE 유용
        "enable_multi_query": True,  # ✅ 다양한 관점 유용
        "bm25_weight": 0.5,
        "vector_weight": 0.5,
        "initial_k": 80,
        "max_results": 12,
        "adaptive_threshold_percentile": 0.6,
        "skip_search": False,
    },
    "normal_translation_direct": {
        "enable_hyde": False,        # ❌ 직접 번역에는 불필요
        "enable_multi_query": False, # ❌ 직접 번역에는 불필요
        "bm25_weight": 0.0,           # 검색 스킵
        "vector_weight": 0.0,        # 검색 스킵
        "initial_k": 0,              # 검색 스킵
        "max_results": 0,            # 검색 스킵
        "adaptive_threshold_percentile": 0.0,
        "skip_search": True,         # 검색 완전 스킵
    },
    "normal_translation_search": {
        "enable_hyde": False,        # ❌ 검색 후 번역에는 HyDE 불필요
        "enable_multi_query": False, # ❌ 검색 후 번역에는 Multi-Query 불필요
        "bm25_weight": 0.6,           # 키워드 매칭 중요 (검색 필요)
        "vector_weight": 0.4,
        "initial_k": 80,             # 검색 필요
        "max_results": 10,           # 검색 결과 번역
        "adaptive_threshold_percentile": 0.6,
        "skip_search": False,        # 검색 수행
    },
    "complex_comparison": {
        "enable_hyde": True,
        "enable_multi_query": True,  # ✅ 비교 질문에는 Multi-Query 필수
        "bm25_weight": 0.3,
        "vector_weight": 0.7,        # 의미론적 유사도 중요
        "initial_k": 100,
        "max_results": 15,
        "adaptive_threshold_percentile": 0.5,
        "skip_search": False,
    },
    "complex_relationship": {
        "enable_hyde": True,
        "enable_multi_query": True,  # ✅ 관계 질문에는 Multi-Query 필수
        "bm25_weight": 0.3,
        "vector_weight": 0.7,
        "initial_k": 120,
        "max_results": 15,
        "adaptive_threshold_percentile": 0.5,
        "skip_search": False,
    },
    "exhaustive_keyword": {
        "enable_hyde": False,        # ❌ 키워드 기반 전체 검색에는 HyDE 부적합
        "enable_multi_query": False, # ❌ 키워드 검색에는 Multi-Query 불필요
        "bm25_weight": 0.8,          # 키워드 매칭 최우선
        "vector_weight": 0.2,
        "initial_k": 200,             # 매우 넓은 검색 범위
        "max_results": 50,            # 많은 결과
        "adaptive_threshold_percentile": 0.4,  # 최대한 많은 문서
        "skip_search": False,
    },
    "exhaustive_list": {
        "enable_hyde": False,        # ❌ 목록 질문에는 HyDE 부적합
        "enable_multi_query": False, # ❌ 목록 질문에는 Multi-Query 불필요
        "bm25_weight": 0.6,          # 키워드 매칭 중요
        "vector_weight": 0.4,
        "initial_k": 200,
        "max_results": 50,
        "adaptive_threshold_percentile": 0.4,
        "skip_search": False,
    }
}

# 기본 전략 (알 수 없는 유형에 대한 폴백)
DEFAULT_STRATEGY = {
    "enable_hyde": True,             # 안전한 기본값
    "enable_multi_query": True,
    "bm25_weight": 0.5,
    "vector_weight": 0.5,
    "initial_k": 80,
    "max_results": 12,
    "adaptive_threshold_percentile": 0.6,
    "skip_search": False,
}


def get_search_strategy(question_type: str, detailed_type: Optional[str] = None) -> Dict:
    """
    질문 유형에 따른 검색 전략 반환
    
    Args:
        question_type: 기본 질문 유형 (simple, normal, complex, exhaustive)
        detailed_type: 세분화된 질문 유형 (simple_fact, normal_definition 등)
    
    Returns:
        검색 전략 딕셔너리
    """
    # 세분화된 유형이 있으면 우선 사용
    strategy_key = detailed_type if detailed_type else question_type
    
    # 검색 전략 매핑 테이블에서 조회
    strategy = SEARCH_STRATEGIES.get(strategy_key)
    
    # 매핑 테이블에 없으면 기본 전략 사용
    if strategy is None:
        print(f"[SearchStrategy] 알 수 없는 질문 유형: {strategy_key}, 기본 전략 사용")
        strategy = DEFAULT_STRATEGY.copy()
    
    return strategy.copy()  # 복사본 반환 (원본 보호)



