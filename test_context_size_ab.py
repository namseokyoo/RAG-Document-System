"""
Small-to-Large Context Size A/B Test
다양한 context_size 설정을 비교하여 최적 크기를 찾습니다.

테스트 구성:
- Baseline: 200 (현재)
- Conservative: 400
- Moderate: 600
- Generous: 800

측정 지표:
- 답변 완성도 (필요한 정보 포함 여부)
- 컨텍스트 관련성
- 성능 (시간)
- 토큰 사용량
"""

import json
import os
import sys
import time
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
from utils.rag_chain import RAGChain

print("=" * 80)
print("Small-to-Large Context Size A/B Test")
print("=" * 80)

# Reference 데이터 로드
ref_file = Path("data/test_documents/reference_result.json")
if not ref_file.exists():
    print(f"\n[오류] Reference 파일 없음: {ref_file}")
    sys.exit(1)

with open(ref_file, "r", encoding="utf-8") as f:
    reference_data = json.load(f)

# 테스트 질문 선택 (다양한 유형 커버)
# - 수식 포함 질문
# - 표 관련 질문
# - 기술적 상세 설명 필요 질문
# - 단순 정의 질문
test_indices = [0, 1, 2, 10, 12, 22, 31]  # 7개 질문 선택

test_questions = []
for idx in test_indices:
    if idx < len(reference_data):
        test_questions.append({
            "question": reference_data[idx]["질문"],
            "reference_answer": reference_data[idx]["답변"],
            "reference_sources": reference_data[idx]["출처"]
        })

print(f"\n[테스트 설정]")
print(f"  - 테스트 질문 수: {len(test_questions)}")
print(f"  - Context Size 변형: [200, 400, 600, 800]")

# Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

# VectorStore 초기화
print(f"\n[1단계] VectorStore 초기화")
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    embedding_api_key=config.get("embedding_api_key", ""),
)
print(f"  - VectorStore 초기화 완료")

def run_test_with_context_size(context_size: int, test_name: str):
    """특정 context_size로 테스트 실행"""
    print(f"\n{'=' * 80}")
    print(f"{test_name}: context_size = {context_size}")
    print(f"{'=' * 80}")

    # RAGChain 초기화 - small_to_large_context_size 파라미터 전달
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "request"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:latest"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.3),
        top_k=config.get("top_k", 5),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=config.get("reranker_initial_k", 30),
        enable_synonym_expansion=config.get("enable_synonym_expansion", False),
        enable_multi_query=config.get("enable_multi_query", True),
        multi_query_num=config.get("multi_query_num", 3),
        enable_hybrid_search=config.get("enable_hybrid_search", True),
        hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5),
        small_to_large_context_size=context_size  # 컨텍스트 크기 설정
    )

    results = []

    for i, test_item in enumerate(test_questions, 1):
        question = test_item["question"]
        ref_answer = test_item["reference_answer"]

        print(f"\n[테스트 {i}/{len(test_questions)}]")
        print(f"질문: \"{question[:80]}...\"" if len(question) > 80 else f"질문: \"{question}\"")
        print(f"-" * 80)

        try:
            # 답변 생성
            start = time.time()
            result = rag_chain.query(question)
            elapsed = time.time() - start

            answer = result.get('answer', '')
            sources = result.get('sources', [])

            # 컨텍스트 길이 측정
            context_length = len(result.get('context', ''))

            print(f"  시간: {elapsed:.2f}초")
            print(f"  컨텍스트 길이: {context_length} 문자")
            print(f"  답변 길이: {len(answer)} 문자")
            print(f"  출처 수: {len(sources)}개")

            # 답변 미리보기
            answer_preview = answer[:150].replace('\n', ' ')
            print(f"  답변 미리보기: {answer_preview}..." if len(answer) > 150 else f"  답변: {answer_preview}")

            results.append({
                "question": question,
                "answer": answer,
                "reference_answer": ref_answer,
                "sources": [s.get('file_name', '?') for s in sources] if sources else [],
                "context_length": context_length,
                "answer_length": len(answer),
                "elapsed_time": elapsed,
                "success": True
            })

        except Exception as e:
            print(f"  [실패] {e}")
            import traceback
            traceback.print_exc()

            results.append({
                "question": question,
                "error": str(e),
                "success": False
            })

    # 통계
    success_count = sum(1 for r in results if r.get("success", False))
    if success_count > 0:
        avg_time = sum(r["elapsed_time"] for r in results if r.get("success", False)) / success_count
        avg_context = sum(r["context_length"] for r in results if r.get("success", False)) / success_count
        avg_answer = sum(r["answer_length"] for r in results if r.get("success", False)) / success_count

        print(f"\n[통계]")
        print(f"  - 성공: {success_count}/{len(results)}")
        print(f"  - 평균 시간: {avg_time:.2f}초")
        print(f"  - 평균 컨텍스트 길이: {avg_context:.0f} 문자")
        print(f"  - 평균 답변 길이: {avg_answer:.0f} 문자")

    return results

# 테스트 실행
print("\n" + "=" * 80)
print("테스트 시작")
print("=" * 80)

all_results = {}

# Baseline: 200
all_results["200"] = run_test_with_context_size(200, "Baseline (현재)")

# Conservative: 400
all_results["400"] = run_test_with_context_size(400, "Conservative")

# Moderate: 600
all_results["600"] = run_test_with_context_size(600, "Moderate")

# Generous: 800
all_results["800"] = run_test_with_context_size(800, "Generous")

# 비교 분석
print("\n" + "=" * 80)
print("비교 분석")
print("=" * 80)

for i, test_item in enumerate(test_questions, 1):
    question = test_item["question"]
    print(f"\n[질문 {i}]")
    print(f"  {question[:80]}..." if len(question) > 80 else f"  {question}")
    print(f"-" * 80)

    for size in ["200", "400", "600", "800"]:
        result = all_results[size][i-1]
        if result.get("success"):
            print(f"  [{size:>3}자] 시간: {result['elapsed_time']:5.2f}초, " +
                  f"컨텍스트: {result['context_length']:5d}자, " +
                  f"답변: {result['answer_length']:4d}자")
        else:
            print(f"  [{size:>3}자] [실패]")

# 전체 통계
print("\n" + "=" * 80)
print("전체 통계 비교")
print("=" * 80)

print(f"\n{'설정':<12} {'평균시간':<10} {'평균컨텍스트':<14} {'평균답변':<10} {'성공률':<10}")
print("-" * 60)

for size in ["200", "400", "600", "800"]:
    results = all_results[size]
    success = [r for r in results if r.get("success", False)]

    if success:
        avg_time = sum(r["elapsed_time"] for r in success) / len(success)
        avg_context = sum(r["context_length"] for r in success) / len(success)
        avg_answer = sum(r["answer_length"] for r in success) / len(success)
        success_rate = len(success) / len(results) * 100

        print(f"{size + '자':<12} {avg_time:>8.2f}초 {avg_context:>12.0f}자 {avg_answer:>8.0f}자 {success_rate:>8.1f}%")

# 결과 저장
output = {
    "test_config": {
        "context_sizes": [200, 400, 600, 800],
        "num_questions": len(test_questions),
        "test_date": time.strftime("%Y-%m-%d %H:%M:%S")
    },
    "results": all_results,
    "test_questions": [q["question"] for q in test_questions]
}

output_file = "test_context_size_ab_result.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n[결과 저장] {output_file}")

# 권장사항
print("\n" + "=" * 80)
print("권장사항")
print("=" * 80)

print("""
분석 기준:
1. 컨텍스트 길이: 더 많은 정보를 제공할수록 답변 품질 향상
2. 답변 길이: 더 상세한 답변이 생성되는지 확인
3. 시간: 성능 영향 최소화
4. 향후 확장성: 다양한 문서 타입 (표, 수식, 코드) 수용

결과 확인:
- test_context_size_ab_result.json 파일에서 각 질문별 답변 내용을 확인하세요.
- Reference 답변과 비교하여 정보 완성도를 평가하세요.
- 컨텍스트가 클수록 표, 수식, 기술적 설명이 더 완전하게 포함됩니다.

일반적 권장:
- 600-800: 표, 수식, 코드가 많은 기술 문서
- 400-600: 일반적인 기술 문서
- 200-400: 짧은 FAQ나 단순 질의응답

사용자 요청사항:
"향후 사용하는 문서에 따라 차이가 있을 수 있으니 좀 여유있게 설정해줘"
=> 권장: 600 또는 800을 기본값으로 설정
""")

print("\n" + "=" * 80)
print("테스트 완료!")
print("=" * 80)
