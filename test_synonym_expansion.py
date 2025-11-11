"""
동의어 확장 효과 비교 테스트
- Synonym ON vs OFF 비교
- 속도와 검색 품질 측정
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
print("동의어 확장 효과 비교 테스트")
print("=" * 80)

# 테스트 질문 (다양한 타입)
test_questions = [
    "OLED 효율은 얼마인가?",  # Simple - 동의어 확장 거의 사용 안 됨 (Multi-Query OFF)
    "TADF 재료는 무엇인가?",  # Normal - 동의어 확장 거의 사용 안 됨 (Multi-Query OFF)
    "유기발광다이오드와 양자점 발광다이오드를 비교해줘",  # Complex - Multi-Query ON이므로 동의어 사용 안 됨
]

# Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

print("\n[설정 확인]")
print(f"  - Multi-Query: {config.get('enable_multi_query', True)}")
print(f"  - Synonym Expansion: {config.get('enable_synonym_expansion', True)}")
print(f"  - Hybrid Search: {config.get('enable_hybrid_search', True)}")

# VectorStore 초기화
print(f"\n[VectorStore 초기화]")
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    embedding_api_key=config.get("embedding_api_key", ""),
)

def run_test(synonym_enabled: bool, test_name: str):
    """특정 설정으로 테스트 실행"""
    print(f"\n{'=' * 80}")
    print(f"{test_name}: Synonym Expansion = {synonym_enabled}")
    print(f"{'=' * 80}")

    # RAGChain 초기화
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
        enable_synonym_expansion=synonym_enabled,  # 동의어 확장 토글
        enable_multi_query=config.get("enable_multi_query", True),
        multi_query_num=config.get("multi_query_num", 3),
        enable_hybrid_search=config.get("enable_hybrid_search", True),
        hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5)
    )

    results = []

    for i, question in enumerate(test_questions, 1):
        print(f"\n[테스트 {i}/{len(test_questions)}]")
        print(f"질문: \"{question}\"")
        print(f"-" * 80)

        try:
            # 분류 결과 확인
            if hasattr(rag_chain, 'question_classifier') and rag_chain.question_classifier:
                classification = rag_chain.question_classifier.classify(question)
                print(f"  분류: {classification['type']}, Multi-Query: {classification['multi_query']}")

            # 답변 생성
            start = time.time()
            result = rag_chain.query(question)
            elapsed = time.time() - start

            answer = result.get('answer', '')
            sources = result.get('sources', [])

            print(f"  시간: {elapsed:.2f}초")
            print(f"  답변: {answer[:100]}..." if len(answer) > 100 else f"  답변: {answer}")
            print(f"  출처 수: {len(sources)}개")

            results.append({
                "question": question,
                "answer": answer,
                "sources": [s.get('file_name', '?') for s in sources] if sources else [],
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
        print(f"\n[통계]")
        print(f"  - 성공: {success_count}/{len(results)}")
        print(f"  - 평균 시간: {avg_time:.2f}초")

    return results

# 테스트 1: Synonym ON
results_with_synonym = run_test(synonym_enabled=True, test_name="테스트 1")

# 테스트 2: Synonym OFF
results_without_synonym = run_test(synonym_enabled=False, test_name="테스트 2")

# 비교 결과
print("\n" + "=" * 80)
print("비교 결과")
print("=" * 80)

for i, question in enumerate(test_questions, 1):
    print(f"\n[질문 {i}] {question}")
    print(f"-" * 80)

    r1 = results_with_synonym[i-1]
    r2 = results_without_synonym[i-1]

    if r1.get("success") and r2.get("success"):
        time_diff = r2["elapsed_time"] - r1["elapsed_time"]
        time_change = f"{'+' if time_diff > 0 else ''}{time_diff:.2f}초"

        print(f"  [Synonym ON]  시간: {r1['elapsed_time']:.2f}초, 출처: {len(r1['sources'])}개")
        print(f"  [Synonym OFF] 시간: {r2['elapsed_time']:.2f}초, 출처: {len(r2['sources'])}개")
        print(f"  [차이] 시간: {time_change}")

        # 답변 비교 (처음 100자)
        if r1['answer'][:100] != r2['answer'][:100]:
            print(f"  [주의] 답변 차이 발견")

# 결과 저장
output = {
    "with_synonym": results_with_synonym,
    "without_synonym": results_without_synonym,
    "test_questions": test_questions
}

output_file = "test_synonym_expansion_result.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n[결과 저장] {output_file}")

print("\n" + "=" * 80)
print("테스트 완료!")
print("=" * 80)
