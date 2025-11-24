"""
토큰화 방식 품질 비교 테스트
- VectorStoreManager의 정교한 토큰화 vs HybridRetriever의 단순 토큰화
"""
import re
from typing import List
from rank_bm25 import BM25Okapi

# ============= VectorStoreManager 스타일 (정교한 토큰화) =============
def tokenize_advanced(text: str, preserve_numbers: bool = True) -> List[str]:
    """VectorStoreManager._tokenize() 방식 (stopwords 제거, 조사 처리)"""
    if not text:
        return []

    # 한국어 stopwords (조사 및 불용어)
    korean_stopwords = [
        '을', '를', '이', '가', '은', '는', '에', '에서', '로', '으로',
        '와', '과', '의', '도', '만', '부터', '까지', '처럼', '같이',
        '한테', '에게', '께', '보다', '마다', '조차', '마저', '까지',
        '이라', '라', '이야', '야', '이다', '다', '어요', '아요', '해요',
        '습니다', '습니다', '어', '아', '지', '네', '어서', '아서',
        '그', '것', '수', '있는', '있', '없는', '없', '로', '및', '그리고'
    ]

    # 영어 stopwords
    english_stopwords = [
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
        'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their'
    ]

    all_stopwords = set(korean_stopwords + english_stopwords)

    # 숫자 및 단위 패턴 (보존 필요)
    number_pattern = r'\d+\.?\d*'

    # 토큰화: 영문, 한글, 숫자 모두 포함
    tokens = re.findall(r'[\w가-힣]+|\d+\.?\d*[%°C℃℉kmhmgdlnmlμΩVAmWkg]*', text.lower())

    cleaned_tokens = []
    for token in tokens:
        # 숫자 포함 토큰은 보존
        if preserve_numbers and re.search(number_pattern, token):
            cleaned_tokens.append(token)
            continue

        # 단위만 있는 경우도 보존
        if any(unit in token for unit in ['%', '°', '℃', '℉']):
            cleaned_tokens.append(token)
            continue

        # stopwords 제거
        if token in all_stopwords:
            continue

        # 너무 짧은 토큰 제거
        if len(token) <= 1:
            continue

        # 조사로 끝나는 토큰에서 조사 제거 (한국어 처리)
        cleaned_token = token
        for stopword in korean_stopwords:
            if cleaned_token.endswith(stopword) and len(cleaned_token) > len(stopword):
                cleaned_token = cleaned_token[:-len(stopword)]
                break

        if len(cleaned_token) > 1:
            cleaned_tokens.append(cleaned_token)

    return cleaned_tokens


# ============= HybridRetriever 스타일 (단순 토큰화) =============
def tokenize_simple(text: str) -> List[str]:
    """HybridRetriever._tokenize() 방식 (공백 분리만)"""
    if not text:
        return []

    # 1. 소문자 변환
    text = text.lower()

    # 2. 특수문자 제거 (한글, 영문, 숫자, 공백만 유지)
    text = re.sub(r'[^\w\s가-힣]', ' ', text)

    # 3. 공백 기준 분리
    tokens = text.split()

    # 4. 빈 토큰 제거
    tokens = [t for t in tokens if t.strip()]

    return tokens


# ============= 테스트 데이터 =============
test_corpus = [
    "자동차의 엔진은 25℃에서 가장 효율적으로 작동합니다.",
    "배터리 충전은 80%까지 권장됩니다.",
    "The temperature should be maintained at 25 degrees Celsius.",
    "자동차를 운전하는 것은 매우 조심스럽게 해야 합니다.",
    "엔진 오일 교환은 정기적으로 수행해야 합니다.",
]

test_queries = [
    "자동차 엔진 온도",
    "배터리 충전 권장",
    "temperature celsius",
    "자동차 운전",
    "엔진 오일",
]


# ============= 테스트 실행 =============
def main():
    print("=" * 80)
    print("토큰화 품질 비교 테스트")
    print("=" * 80)
    print()

    # 1단계: 토큰화 결과 비교
    print("[1단계] 토큰화 결과 비교")
    print("-" * 80)
    for idx, text in enumerate(test_corpus, 1):
        print(f"\n[문서 {idx}] {text}")

        tokens_advanced = tokenize_advanced(text)
        tokens_simple = tokenize_simple(text)

        print(f"  정교한 토큰화: {tokens_advanced}")
        print(f"  단순 토큰화:   {tokens_simple}")
        print(f"  토큰 수 차이:  {len(tokens_advanced)} vs {len(tokens_simple)}")

    # 2단계: BM25 검색 품질 비교
    print("\n" + "=" * 80)
    print("[2단계] BM25 검색 품질 비교")
    print("-" * 80)

    # 정교한 토큰화로 BM25 인덱스 구축
    tokenized_corpus_advanced = [tokenize_advanced(doc) for doc in test_corpus]
    bm25_advanced = BM25Okapi(tokenized_corpus_advanced)

    # 단순 토큰화로 BM25 인덱스 구축
    tokenized_corpus_simple = [tokenize_simple(doc) for doc in test_corpus]
    bm25_simple = BM25Okapi(tokenized_corpus_simple)

    for query in test_queries:
        print(f"\n[쿼리] {query}")

        # 정교한 토큰화로 검색
        query_tokens_advanced = tokenize_advanced(query)
        scores_advanced = bm25_advanced.get_scores(query_tokens_advanced)

        # 단순 토큰화로 검색
        query_tokens_simple = tokenize_simple(query)
        scores_simple = bm25_simple.get_scores(query_tokens_simple)

        print(f"  쿼리 토큰 (정교): {query_tokens_advanced}")
        print(f"  쿼리 토큰 (단순): {query_tokens_simple}")
        print()

        # Top 3 결과 비교
        top3_advanced = sorted(enumerate(scores_advanced), key=lambda x: x[1], reverse=True)[:3]
        top3_simple = sorted(enumerate(scores_simple), key=lambda x: x[1], reverse=True)[:3]

        print("  [정교한 토큰화] Top 3 결과:")
        for rank, (doc_idx, score) in enumerate(top3_advanced, 1):
            print(f"    {rank}. (점수: {score:.4f}) {test_corpus[doc_idx][:50]}...")

        print()
        print("  [단순 토큰화] Top 3 결과:")
        for rank, (doc_idx, score) in enumerate(top3_simple, 1):
            print(f"    {rank}. (점수: {score:.4f}) {test_corpus[doc_idx][:50]}...")

        # 순위 변화 확인
        if top3_advanced[0][0] != top3_simple[0][0]:
            print(f"  [주의] 1위 문서가 다릅니다!")
            print(f"     정교: 문서 {top3_advanced[0][0]+1} / 단순: 문서 {top3_simple[0][0]+1}")

    # 3단계: 통계 요약
    print("\n" + "=" * 80)
    print("[3단계] 통계 요약")
    print("-" * 80)

    total_tokens_advanced = sum(len(tokenize_advanced(doc)) for doc in test_corpus)
    total_tokens_simple = sum(len(tokenize_simple(doc)) for doc in test_corpus)

    print(f"전체 토큰 수 (정교): {total_tokens_advanced}")
    print(f"전체 토큰 수 (단순): {total_tokens_simple}")
    print(f"토큰 감소율: {(1 - total_tokens_advanced/total_tokens_simple)*100:.1f}%")
    print()
    print("[+] 정교한 토큰화의 장점:")
    print("  - Stopwords 제거로 노이즈 감소")
    print("  - 한국어 조사 처리로 의미 중심 검색")
    print("  - 숫자/단위 보존으로 정확한 정보 검색")
    print()
    print("[-] 단순 토큰화의 단점:")
    print("  - '을', '를', '이', '가' 등 불필요한 토큰 포함")
    print("  - '자동차를' vs '자동차' 다른 토큰으로 인식")
    print("  - 의미 없는 조사가 검색 품질 저하")


if __name__ == "__main__":
    main()
