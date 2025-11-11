"""
프롬프트 개선 효과 테스트 - 수식 추출 능력 확인
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
print("프롬프트 개선 효과 테스트 (수식 추출)")
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

# RAGChain 초기화
print(f"\n[2단계] RAGChain 초기화")
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
    enable_synonym_expansion=config.get("enable_synonym_expansion", True),
    enable_multi_query=config.get("enable_multi_query", True),
    multi_query_num=config.get("multi_query_num", 3),
    enable_hybrid_search=config.get("enable_hybrid_search", True),
    hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5)
)
print(f"  - RAGChain 초기화 완료")

# 테스트 질문 (수식이 중요한 3개)
test_questions = [
    "화학주성이 MIPS를 억제(suppress)할 수 있는 두 가지 기준(criteria)은 무엇입니까?",
    "MIPS 모델에서 화학주성(chemotaxis)은 입자 플럭스(J)에 어떻게 반영되며, 화학주성 Péclet 수($Pe_C$)는 무엇을 나타냅니까?",
    "비-화학주성 MIPS($Pe_C=0$)에서 도메인 크기 R(t)의 거칠어짐(coarsening)은 시간에 따라 어떤 법칙을 따르며, 화학주성이 강해지면 어떻게 변합니까?"
]

print("\n" + "=" * 80)
print("테스트 실행 (3개 질문)")
print("=" * 80)

results = []

for i, question in enumerate(test_questions, 1):
    print(f"\n[테스트 {i}/3]")
    print(f"질문: \"{question}\"")
    print(f"-" * 80)

    try:
        start = time.time()
        result = rag_chain.query(question)
        answer = result.get('answer', '')
        elapsed = time.time() - start

        print(f"\n답변 생성 시간: {elapsed:.2f}초")
        print(f"\n[생성된 답변]")
        print(answer)

        results.append({
            "question": question,
            "answer": answer,
            "elapsed_time": elapsed,
            "success": True
        })

        print(f"\n  [성공] 답변 생성 완료")

    except Exception as e:
        print(f"\n  [실패] 오류 발생: {e}")
        results.append({
            "question": question,
            "error": str(e),
            "success": False
        })

# 결과 요약
print("\n" + "=" * 80)
print("테스트 결과 요약")
print("=" * 80)

success_count = sum(1 for r in results if r.get("success", False))
print(f"\n성공: {success_count}/3")

if success_count > 0:
    avg_time = sum(r["elapsed_time"] for r in results if r.get("success", False)) / success_count
    print(f"평균 답변 시간: {avg_time:.2f}초")

# 결과 저장
output_file = "test_prompt_improvement_result.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n결과 저장: {output_file}")
print("\n" + "=" * 80)
print("테스트 완료!")
print("=" * 80)
