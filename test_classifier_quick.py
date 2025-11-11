"""
빠른 분류기 테스트 - 3개 질문만
"""

from utils.question_classifier import create_classifier

print("=" * 80)
print("Question Classifier 빠른 테스트")
print("=" * 80)

# 분류기 초기화
classifier = create_classifier(llm=None, use_llm=False, verbose=False)

# 테스트 질문
tests = [
    ("OLED는 무엇인가?", "normal"),
    ("효율 값은?", "simple"),
    ("OLED와 QLED를 비교해줘", "complex"),
]

print("\n[테스트 실행]\n")

for i, (question, expected) in enumerate(tests, 1):
    result = classifier.classify(question)

    actual = result['type']
    match = "[OK]" if actual == expected else "[FAIL]"

    print(f"{i}. \"{question}\"")
    print(f"   Expected: {expected}, Actual: {actual} {match}")
    print(f"   Confidence: {result['confidence']:.0%}, Method: {result['method']}")
    print(f"   Multi-Query: {result['multi_query']}, RerankK: {result['reranker_k']}, MaxTokens: {result['max_tokens']}")
    print()

# 통계
print("=" * 80)
print("테스트 완료")
print("=" * 80)
