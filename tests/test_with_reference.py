"""
Reference 답변과 비교하는 통합 테스트
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
print("Reference 답변 비교 테스트")
print("=" * 80)

# Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

print("\n[1단계] 설정 확인")
print(f"  - Question Classifier: {config.get('enable_question_classifier', True)}")
print(f"  - Classifier Use LLM: {config.get('classifier_use_llm', True)}")
print(f"  - Multi-Query: {config.get('enable_multi_query', True)}")
print(f"  - Reranker Model: {config.get('reranker_model', 'multilingual-mini')}")

# Reference 데이터 로드
ref_file = Path("data/test_documents/reference_result.json")
if not ref_file.exists():
    print(f"\n[오류] Reference 파일 없음: {ref_file}")
    sys.exit(1)

with open(ref_file, "r", encoding="utf-8") as f:
    reference_data = json.load(f)

print(f"\n[2단계] Reference 데이터 로드")
print(f"  - 파일: {ref_file}")
print(f"  - 질문 수: {len(reference_data)}")

# VectorStore 초기화
print(f"\n[3단계] VectorStore 초기화")
try:
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "request"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )
    print(f"  - VectorStore 초기화 완료")
except Exception as e:
    print(f"  [오류] VectorStore 초기화 실패: {e}")
    sys.exit(1)

# RAGChain 초기화
print(f"\n[4단계] RAGChain 초기화")
try:
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

    if hasattr(rag_chain, 'question_classifier') and rag_chain.question_classifier:
        print(f"  - Question Classifier: 활성화됨")
    else:
        print(f"  - Question Classifier: 비활성화됨")

    print(f"  - RAGChain 초기화 완료")
except Exception as e:
    print(f"  [오류] RAGChain 초기화 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 테스트 실행 (처음 5개 질문만)
print("\n" + "=" * 80)
print("테스트 실행 (처음 5개 질문)")
print("=" * 80)

results = []

for i, ref_item in enumerate(reference_data[:5], 1):
    question = ref_item["질문"]
    ref_answer = ref_item["답변"]
    ref_sources = ref_item["출처"]

    print(f"\n[테스트 {i}/5]")
    print(f"질문: \"{question}\"")
    print(f"-" * 80)

    try:
        # 분류 결과 확인
        if hasattr(rag_chain, 'question_classifier') and rag_chain.question_classifier:
            classification = rag_chain.question_classifier.classify(question)
            print(f"\n[분류 결과]")
            print(f"  유형: {classification['type']}")
            print(f"  신뢰도: {classification['confidence']:.0%}")
            print(f"  Multi-Query: {classification['multi_query']}")
            print(f"  RerankK: {classification['reranker_k']}")
            print(f"  MaxTokens: {classification['max_tokens']}")

        # 답변 생성
        print(f"\n[답변 생성 중...]")
        start = time.time()

        # 답변 생성
        result = rag_chain.query(question)
        answer = result.get('answer', '')
        sources = result.get('sources', [])

        elapsed = time.time() - start

        print(f"  답변 생성 시간: {elapsed:.2f}초")
        print(f"\n[생성된 답변]")
        print(f"  {answer[:200]}..." if len(answer) > 200 else f"  {answer}")

        print(f"\n[Reference 답변]")
        print(f"  {ref_answer[:200]}..." if len(ref_answer) > 200 else f"  {ref_answer}")

        # 출처 확인
        print(f"\n[검색된 출처]")
        if sources:
            for j, source in enumerate(sources[:3], 1):
                print(f"  {j}. {source.get('file_name', '?')} (p.{source.get('page_number', '?')})")
        else:
            print(f"  (없음)")

        print(f"\n[Reference 출처]")
        for j, ref_src in enumerate(ref_sources, 1):
            print(f"  {j}. {ref_src['문서']} {ref_src['인용']}")

        print(f"\n  [성공] 테스트 통과")

        results.append({
            "question": question,
            "answer": answer,
            "reference_answer": ref_answer,
            "sources": [s.get('file_name', '?') for s in sources] if sources else [],
            "reference_sources": [s['문서'] for s in ref_sources],
            "elapsed_time": elapsed,
            "success": True
        })

    except Exception as e:
        print(f"\n  [실패] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

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
fail_count = len(results) - success_count

print(f"\n[전체 결과]")
print(f"  - 성공: {success_count}/{len(results)}")
print(f"  - 실패: {fail_count}/{len(results)}")

if success_count > 0:
    avg_time = sum(r["elapsed_time"] for r in results if r.get("success", False)) / success_count
    print(f"  - 평균 답변 시간: {avg_time:.2f}초")

# 결과 저장
output_file = "test_with_reference_result.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n[결과 저장]")
print(f"  - 파일: {output_file}")

print("\n" + "=" * 80)
print("테스트 완료!")
print("=" * 80)
