"""카테고리 시스템 적용 후 성능 테스트"""
import sys
import os

# UTF-8 출력 설정 (Windows 콘솔 호환)
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
import json
from datetime import datetime

def main():
    print("=" * 80)
    print("카테고리 시스템 성능 테스트")
    print("=" * 80)

    # 설정 로드
    config = ConfigManager().get_all()

    # VectorStore 초기화
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    # RAGChain 초기화 (VectorStoreManager 객체 전달)
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
        enable_synonym_expansion=config.get("enable_synonym_expansion", True),
        enable_multi_query=config.get("enable_multi_query", True),
        multi_query_num=config.get("multi_query_num", 3),
        enable_hybrid_search=config.get("enable_hybrid_search", True),
        hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5),
    )

    # 테스트 쿼리 (OLED 기술 관련)
    test_queries = [
        "TADF 재료의 양자 효율은 얼마인가?",
        "FRET 에너지 전달 효율은?",
        "kFRET 값은 얼마인가?",
        "OLED의 외부 양자 효율(EQE)은?",
        "분자 구조와 성능의 관계는?",
        "Hyperfluorescence 기술의 핵심은?",
        "TADF sensitizer의 역할은?",
    ]

    # 비즈니스 관련 쿼리
    business_queries = [
        "LG디스플레이의 OLED 시장 동향은?",
        "8.6세대 IT OLED 생산라인은?",
    ]

    # HR 관련 쿼리
    hr_queries = [
        "HRD-Net 출결 관리 방법은?",
        "출결관리 앱 설치 방법은?",
    ]

    # 모든 쿼리 통합
    all_queries = test_queries + business_queries + hr_queries

    results = []

    print(f"\n총 {len(all_queries)}개 쿼리 테스트 시작\n")

    for i, query in enumerate(all_queries, 1):
        print(f"\n[Query {i}/{len(all_queries)}] {query}")
        print("-" * 80)

        try:
            # RAG 체인 실행
            result = rag_chain.query(query)
            answer = result.get("answer", "")

            # 출처 분석
            sources = result.get("sources", [])
            source_info = []
            categories_found = set()

            # _last_retrieved_docs에서 카테고리 정보 가져오기
            for i, source_dict in enumerate(sources):
                file_name = source_dict.get("file_name", "unknown")
                score = source_dict.get("similarity_score", 0.0)

                # VectorStore에서 카테고리 정보 가져오기 (원본 문서에서)
                # rag_chain._last_retrieved_docs에 (doc, score) 형태로 저장됨
                category = "unknown"
                if hasattr(rag_chain, '_last_retrieved_docs') and i < len(rag_chain._last_retrieved_docs):
                    doc, _ = rag_chain._last_retrieved_docs[i]
                    category = doc.metadata.get("category", "unknown")

                categories_found.add(category)
                source_info.append({
                    "file_name": file_name,
                    "category": category,
                    "score": float(score)
                })

            # 결과 요약
            print(f"\n답변: {answer[:200]}...")
            print(f"\n출처 ({len(sources)}개):")
            for src in source_info:
                print(f"  - {src['file_name']} (카테고리: {src['category']}, 점수: {src['score']:.4f})")

            print(f"\n감지된 카테고리: {', '.join(categories_found)}")

            # 결과 저장
            results.append({
                "query": query,
                "answer": answer,
                "sources": source_info,
                "categories": list(categories_found),
                "num_sources": len(sources),
                "avg_score": sum(s["score"] for s in source_info) / len(source_info) if source_info else 0
            })

        except Exception as e:
            print(f"❌ 에러 발생: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "query": query,
                "error": str(e),
                "sources": [],
                "categories": [],
                "num_sources": 0,
                "avg_score": 0
            })

    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"test_results/category_system_test_{timestamp}.json"

    os.makedirs("test_results", exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "total_queries": len(all_queries),
            "results": results
        }, f, ensure_ascii=False, indent=2)

    # 통계 출력
    print("\n" + "=" * 80)
    print("테스트 결과 통계")
    print("=" * 80)

    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    print(f"\n성공: {len(successful)}/{len(all_queries)}개")
    print(f"실패: {len(failed)}/{len(all_queries)}개")

    if successful:
        avg_sources = sum(r["num_sources"] for r in successful) / len(successful)
        avg_score = sum(r["avg_score"] for r in successful) / len(successful)
        print(f"\n평균 출처 개수: {avg_sources:.2f}개")
        print(f"평균 신뢰도 점수: {avg_score:.4f}")

        # 카테고리별 통계
        print(f"\n[카테고리별 결과]")
        category_stats = {}
        for r in successful:
            for cat in r["categories"]:
                if cat not in category_stats:
                    category_stats[cat] = 0
                category_stats[cat] += 1

        for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {cat}: {count}회")

        # OLED 쿼리 정확도 체크
        print(f"\n[OLED 쿼리 카테고리 정확도]")
        oled_correct = 0
        for i, r in enumerate(successful[:len(test_queries)]):
            if "technical" in r["categories"]:
                oled_correct += 1
                print(f"  ✓ Query {i+1}: technical 카테고리 포함")
            else:
                print(f"  ✗ Query {i+1}: {r['categories']} (technical 없음)")

        print(f"\nOLED 쿼리 정확도: {oled_correct}/{len(test_queries)} ({100*oled_correct/len(test_queries):.1f}%)")

    print(f"\n결과 저장: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    main()
