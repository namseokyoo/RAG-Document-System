#!/usr/bin/env python3
"""
Test Diversity Penalty Implementation
Verifies that diversity penalty correctly promotes multi-document retrieval
"""

from utils.encoding_helper import setup_utf8_encoding
setup_utf8_encoding()  # Windows 터미널 한글 출력 설정

import json
from utils.vector_store import VectorStoreManager
from collections import Counter


def test_diversity_penalty(query: str, penalty_values=[0.0, 0.2, 0.3, 0.4, 0.5]):
    """Test different diversity penalty strengths"""

    print("="*80)
    print(f"TEST QUERY: {query}")
    print("="*80)

    # Initialize vector store
    vm = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type="ollama",
        embedding_base_url="http://localhost:11434",
        embedding_model="mxbai-embed-large:latest"
    )

    results = {}

    for penalty in penalty_values:
        print(f"\n{'─'*80}")
        print(f"Testing with diversity_penalty = {penalty}")
        print(f"{'─'*80}")

        try:
            # Search with diversity penalty
            docs_with_scores = vm.similarity_search_with_rerank(
                query=query,
                top_k=5,
                initial_k=20,
                reranker_model="multilingual-mini",
                diversity_penalty=penalty,
                diversity_source_key="source"
            )

            # Extract sources
            sources = []
            for doc, score in docs_with_scores:
                source = doc.metadata.get("source", "unknown")
                page = doc.metadata.get("page", "?")
                rerank_score = doc.metadata.get("rerank_score", 0)
                adjusted_score = doc.metadata.get("adjusted_score", 0)
                penalty_applied = doc.metadata.get("diversity_penalty", 1.0)

                sources.append(source)

                print(f"\n  [{len(sources)}] {source} (p.{page})")
                print(f"      Original Score: {rerank_score:.4f}")
                if penalty > 0:
                    print(f"      Adjusted Score: {adjusted_score:.4f} (penalty: {penalty_applied:.2f}x)")
                print(f"      Content: {doc.page_content[:100]}...")

            # Calculate diversity metrics
            unique_sources = len(set(sources))
            total_sources = len(sources)
            diversity_ratio = unique_sources / total_sources if total_sources > 0 else 0

            source_distribution = Counter(sources)

            print(f"\n  {'─'*76}")
            print(f"  DIVERSITY METRICS:")
            print(f"    Total Sources: {total_sources}")
            print(f"    Unique Sources: {unique_sources}")
            print(f"    Diversity Ratio: {diversity_ratio:.2f} ({diversity_ratio*100:.0f}%)")
            print(f"\n  SOURCE DISTRIBUTION:")
            for source, count in source_distribution.most_common():
                percentage = (count / total_sources) * 100
                bar = "#" * int(percentage / 5)
                print(f"    {source[:50]:<50} | {count} ({percentage:.0f}%) {bar}")

            results[penalty] = {
                "unique_sources": unique_sources,
                "total_sources": total_sources,
                "diversity_ratio": diversity_ratio,
                "source_distribution": dict(source_distribution),
                "sources": sources
            }

        except Exception as e:
            print(f"\n  [ERROR] Test failed: {e}")
            import traceback
            traceback.print_exc()
            results[penalty] = {"error": str(e)}

    # Summary comparison
    print(f"\n\n{'='*80}")
    print("SUMMARY COMPARISON")
    print(f"{'='*80}")

    print(f"\n{'Penalty':<10} | {'Unique':<8} | {'Ratio':<8} | {'Top Source':<40}")
    print(f"{'-'*10}-+-{'-'*8}-+-{'-'*8}-+-{'-'*40}")

    for penalty in penalty_values:
        if penalty in results and "error" not in results[penalty]:
            data = results[penalty]
            if "source_distribution" in data and data["source_distribution"]:
                top_source = max(data["source_distribution"], key=data["source_distribution"].get)
                top_source_short = top_source[:37] + "..." if len(top_source) > 40 else top_source

                print(f"{penalty:<10.1f} | {data['unique_sources']:<8} | "
                      f"{data['diversity_ratio']:<8.2f} | {top_source_short:<40}")

    # Recommendations
    print(f"\n\n{'='*80}")
    print("RECOMMENDATIONS")
    print(f"{'='*80}")

    best_penalty = None
    best_diversity = 0

    for penalty, data in results.items():
        if "error" not in data and "diversity_ratio" in data and data["diversity_ratio"] >= 0.6:
            if data["diversity_ratio"] > best_diversity:
                best_diversity = data["diversity_ratio"]
                best_penalty = penalty

    if best_penalty is not None:
        print(f"\n  [OK] Recommended diversity_penalty: {best_penalty}")
        print(f"     Achieves {best_diversity:.1%} diversity ratio")
        print(f"     {results[best_penalty]['unique_sources']} unique sources from 5 total")
    elif 0.3 in results and "diversity_ratio" in results[0.3] and 0.0 in results and "diversity_ratio" in results[0.0]:
        if results[0.3]["diversity_ratio"] > results[0.0]["diversity_ratio"]:
            print(f"\n  [WARN] Recommended diversity_penalty: 0.3 (default)")
            print(f"     Improves diversity from {results[0.0]['diversity_ratio']:.1%} -> {results[0.3]['diversity_ratio']:.1%}")
        else:
            print(f"\n  [WARN] This query may benefit from single-document focus")
            print(f"     Consider penalty = 0.0 for specific-document queries")
    else:
        print(f"\n  [INFO] Insufficient data for recommendation")

    return results


def main():
    """Run diversity penalty tests"""

    # Test Case 1: Multi-document query (should benefit from diversity)
    print("\n" + "="*80)
    print("TEST CASE 1: Multi-Document Query")
    print("="*80)
    test_diversity_penalty(
        query="OLED와 QLED의 차이점은?",
        penalty_values=[0.0, 0.3, 0.5]
    )

    # Test Case 2: Specific query (may prefer single document)
    print("\n\n" + "="*80)
    print("TEST CASE 2: Specific Query")
    print("="*80)
    test_diversity_penalty(
        query="MicroLED 디스플레이의 장점은?",
        penalty_values=[0.0, 0.3, 0.5]
    )

    # Test Case 3: Broad query (should strongly benefit)
    print("\n\n" + "="*80)
    print("TEST CASE 3: Broad Query")
    print("="*80)
    test_diversity_penalty(
        query="Display 분야 최신 트렌드는?",
        penalty_values=[0.0, 0.3, 0.5]
    )

    print("\n\n" + "="*80)
    print("TESTING COMPLETE")
    print("="*80)
    print("\nNext Steps:")
    print("  1. Review diversity ratios above")
    print("  2. Select optimal penalty value (recommended: 0.3)")
    print("  3. Integrate into RAG chain via config")
    print("  4. Run full test suite to validate")


if __name__ == "__main__":
    main()
