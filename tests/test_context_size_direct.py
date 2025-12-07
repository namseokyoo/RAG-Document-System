"""
Small-to-Large Context Size 직접 테스트
small_to_large_search를 직접 호출하여 context_size의 실제 영향을 측정
"""

import json
import os
import sys
from pathlib import Path

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

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
from utils.small_to_large_search import SmallToLargeSearch

print("=" * 80)
print("Small-to-Large Context Size 직접 테스트")
print("=" * 80)

# Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

# VectorStore 초기화
print("\n[1단계] VectorStore 초기화")
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    embedding_api_key=config.get("embedding_api_key", ""),
)
print(f"  - VectorStore 초기화 완료")

# Small-to-Large 검색 초기화
print(f"\n[2단계] Small-to-Large 검색 초기화")
stl_search = SmallToLargeSearch(vector_manager)
print(f"  - Small-to-Large 검색 초기화 완료")

# 테스트 질문 - 구체적이고 짧은 질문 사용
test_questions = [
    "MIPS란 무엇인가?",
    "화학주성 Péclet 수는?",
    "OLED 효율은?",
    "TADF 메커니즘은?",
    "reranker 모델은?",
]

print(f"\n[3단계] 테스트 질문: {len(test_questions)}개")
for i, q in enumerate(test_questions, 1):
    print(f"  {i}. {q}")

# Context Size 설정
context_sizes = [200, 400, 600, 800]

print(f"\n[4단계] Context Size 변형: {context_sizes}")

# 테스트 실행
print("\n" + "=" * 80)
print("테스트 실행")
print("=" * 80)

all_results = {}

for context_size in context_sizes:
    print(f"\n{'=' * 80}")
    print(f"Context Size = {context_size}")
    print(f"{'=' * 80}")

    results = []

    for i, question in enumerate(test_questions, 1):
        print(f"\n[질문 {i}/{len(test_questions)}] {question}")
        print("-" * 80)

        try:
            # Small-to-Large 검색 직접 호출
            docs = stl_search.search_with_context_expansion(
                query=question,
                top_k=5,
                max_parents=3,
                partial_context_size=context_size
            )

            # 결과 분석
            if docs:
                total_length = sum(len(doc.page_content) for doc in docs)
                avg_length = total_length / len(docs)
                max_length = max(len(doc.page_content) for doc in docs)
                min_length = min(len(doc.page_content) for doc in docs)

                print(f"  검색된 문서: {len(docs)}개")
                print(f"  총 길이: {total_length:,}자")
                print(f"  평균 길이: {avg_length:.0f}자")
                print(f"  최대 길이: {max_length:,}자")
                print(f"  최소 길이: {min_length:,}자")

                # 첫 번째 문서 미리보기
                first_doc = docs[0]
                preview = first_doc.page_content[:200].replace('\n', ' ')
                print(f"  첫 문서 미리보기: {preview}...")

                results.append({
                    "question": question,
                    "num_docs": len(docs),
                    "total_length": total_length,
                    "avg_length": avg_length,
                    "max_length": max_length,
                    "min_length": min_length,
                    "first_doc_length": len(first_doc.page_content),
                    "success": True
                })
            else:
                print(f"  [경고] 검색된 문서 없음")
                results.append({
                    "question": question,
                    "success": False
                })

        except Exception as e:
            print(f"  [오류] {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "question": question,
                "error": str(e),
                "success": False
            })

    all_results[str(context_size)] = results

# 비교 분석
print("\n" + "=" * 80)
print("비교 분석")
print("=" * 80)

print(f"\n{'Context Size':<15} {'평균 문서 길이':<18} {'평균 총 길이':<18} {'성공률':<10}")
print("-" * 65)

for size in context_sizes:
    size_str = str(size)
    success_results = [r for r in all_results[size_str] if r.get("success", False)]

    if success_results:
        avg_doc_len = sum(r["avg_length"] for r in success_results) / len(success_results)
        avg_total_len = sum(r["total_length"] for r in success_results) / len(success_results)
        success_rate = len(success_results) / len(all_results[size_str]) * 100

        print(f"{size_str + '자':<15} {avg_doc_len:>16.0f}자 {avg_total_len:>16.0f}자 {success_rate:>8.0f}%")
    else:
        print(f"{size_str + '자':<15} {'N/A':<18} {'N/A':<18} {'0%':<10}")

# 질문별 비교
print("\n" + "=" * 80)
print("질문별 평균 문서 길이 비교")
print("=" * 80)

for i, question in enumerate(test_questions):
    print(f"\n[질문 {i+1}] {question}")
    print(f"  {'Context Size':<15} {'평균 문서 길이':<20}")
    print(f"  {'-' * 40}")

    for size in context_sizes:
        size_str = str(size)
        result = all_results[size_str][i]

        if result.get("success", False):
            print(f"  {size_str + '자':<15} {result['avg_length']:>18.0f}자")
        else:
            print(f"  {size_str + '자':<15} {'실패':<20}")

# 결과 저장
output = {
    "test_config": {
        "context_sizes": context_sizes,
        "num_questions": len(test_questions),
        "test_type": "direct_small_to_large",
        "questions": test_questions
    },
    "results": all_results
}

output_file = "test_context_size_direct_result.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n[결과 저장] {output_file}")

# 권장사항
print("\n" + "=" * 80)
print("분석 및 권장사항")
print("=" * 80)

# Context Size 증가에 따른 문서 길이 증가율 계산
baseline = context_sizes[0]
baseline_results = [r for r in all_results[str(baseline)] if r.get("success", False)]
baseline_avg = sum(r["avg_length"] for r in baseline_results) / len(baseline_results) if baseline_results else 0

print(f"\n기준선 (context_size={baseline}): 평균 {baseline_avg:.0f}자")
print(f"\nContext Size 증가에 따른 효과:")
print(f"  {'Context Size':<15} {'평균 길이':<15} {'증가율':<15} {'권장 사유'}")
print(f"  {'-' * 70}")

for size in context_sizes:
    size_str = str(size)
    success_results = [r for r in all_results[size_str] if r.get("success", False)]

    if success_results:
        avg_len = sum(r["avg_length"] for r in success_results) / len(success_results)
        increase = ((avg_len - baseline_avg) / baseline_avg * 100) if baseline_avg > 0 else 0

        # 권장 사유
        if size == 200:
            reason = "현재 기본값"
        elif size == 400:
            reason = "표 헤더 포함 가능"
        elif size == 600:
            reason = "중간 크기 표/수식 커버"
        elif size == 800:
            reason = "큰 표/복잡한 수식 완전 포함"
        else:
            reason = ""

        print(f"  {size_str + '자':<15} {avg_len:>13.0f}자 {increase:>13.1f}% {reason}")

print(f"\n최종 권장:")
print(f"  - 기본 문서용: 600자 (표와 수식을 안정적으로 커버)")
print(f"  - 복잡한 기술 문서용: 800자 (큰 표와 복잡한 수식 완전 포함)")
print(f"  - 사용자 요청: \"향후 사용하는 문서에 따라 차이가 있을 수 있으니 좀 여유있게 설정\"")
print(f"  => **권장값: 600자** (안정성과 성능의 균형)")

print("\n" + "=" * 80)
print("테스트 완료!")
print("=" * 80)
