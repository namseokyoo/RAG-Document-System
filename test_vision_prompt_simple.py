"""
Vision 프롬프트 간소화 테스트
- 기존 프롬프트 vs 간소화된 프롬프트 비교
"""

# 간소화된 프롬프트 (현재 버전)
SIMPLIFIED_PROMPT = """슬라이드를 분석하여 다음 정보를 구조화된 형식으로 추출하세요:

1. 주제: 핵심 메시지 (1문장)
2. 데이터 유형: 표/그래프 형태 (예: "3행 4열 표", "막대 그래프")
3. 주요 수치: 모든 숫자를 "항목명: 값 (단위)" 형식으로
4. 비교/추이: 증감률, 변화 패턴, 기간별 비교

출력 형식:
```
주제: [...]
데이터 유형: [...]
주요 수치:
- [항목1]: [값1]
- [항목2]: [값2]
비교/추이: [...]
```

예시:
주제: 2024 매출 성장 분석
데이터 유형: 4개 분기 비교 표
주요 수치:
- Q1 온라인: 150억원
- Q2 온라인: 180억원
- Q3 온라인: 190억원
- Q4 온라인: 195억원
비교/추이: Q4/Q1 +30% 성장

주의: 불명확한 수치는 [약]/[추정] 표시"""


# 기존 프롬프트 (참고용)
ORIGINAL_PROMPT_INFO = """
기존 프롬프트: 73라인
간소화 프롬프트: 28라인
감소율: 62%

제거된 요소:
- 5단계 분석 프로세스 설명
- 상세한 필수 항목 설명 (하위 항목 포함)
- 긴 예시 (12개 데이터 포인트 → 4개)
- 중복된 출력 형식 설명

유지된 핵심 요소:
- 주제 추출
- 데이터 유형 식별
- 숫자 추출 (가장 중요)
- 비교/추이 분석
- 간단한 예시
- 불명확한 수치 처리 방법
"""


def count_tokens_estimate(text: str) -> int:
    """토큰 수 추정 (대략 4글자 = 1토큰)"""
    return len(text) // 4


def analyze_prompts():
    """프롬프트 분석"""
    print("=" * 60)
    print("Vision 프롬프트 간소화 분석")
    print("=" * 60)

    simple_lines = SIMPLIFIED_PROMPT.strip().split('\n')
    simple_chars = len(SIMPLIFIED_PROMPT)
    simple_tokens = count_tokens_estimate(SIMPLIFIED_PROMPT)

    print(f"\n간소화된 프롬프트:")
    print(f"  - 라인 수: {len(simple_lines)}라인")
    print(f"  - 글자 수: {simple_chars}자")
    print(f"  - 예상 토큰: 약 {simple_tokens} tokens")

    # 기존 프롬프트 추정치 (실제 측정값 기반)
    original_lines = 73
    original_chars = 1900
    original_tokens = count_tokens_estimate("a" * original_chars)

    print(f"\n기존 프롬프트 (추정):")
    print(f"  - 라인 수: {original_lines}라인")
    print(f"  - 글자 수: 약 {original_chars}자")
    print(f"  - 예상 토큰: 약 {original_tokens} tokens")

    print(f"\n개선 효과:")
    print(f"  - 라인 수 감소: {original_lines}라인 → {len(simple_lines)}라인 ({100 - len(simple_lines)/original_lines*100:.1f}% 감소)")
    print(f"  - 글자 수 감소: {original_chars}자 → {simple_chars}자 ({100 - simple_chars/original_chars*100:.1f}% 감소)")
    print(f"  - 토큰 감소: 약 {original_tokens} → {simple_tokens} tokens ({100 - simple_tokens/original_tokens*100:.1f}% 감소)")

    print(f"\n예상 비용/속도 개선:")
    print(f"  - API 호출당 입력 토큰 절감: 약 {original_tokens - simple_tokens} tokens")
    print(f"  - 100장 슬라이드 처리 시: 약 {(original_tokens - simple_tokens) * 100 / 1000:.1f}K tokens 절감")

    if simple_tokens < original_tokens * 0.5:
        print(f"  ✅ 목표 달성: 50% 이상 감소")
    else:
        print(f"  ⚠️  추가 최적화 가능")

    print("\n" + ORIGINAL_PROMPT_INFO)
    print("=" * 60)


if __name__ == "__main__":
    analyze_prompts()

    print("\n테스트 완료!")
    print("\n다음 단계:")
    print("1. 실제 PPT 파일로 Vision 청킹 테스트")
    print("2. llama4-scout 모델로 정확도 확인")
    print("3. 응답 속도 측정 (기존 vs 간소화)")
    print("4. 추출된 정보 품질 비교")
