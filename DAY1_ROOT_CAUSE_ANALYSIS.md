# Day 1: Root Cause Analysis - Single-Document Dependency

**Date**: 2025-11-11
**Status**: ✅ Root Cause Identified
**Next Step**: Implement Diversity Penalty

---

## Executive Summary

**Problem**: 90%+ of test cases retrieve **ALL** citations from a **single document**, despite having 8,177 documents in the database covering diverse topics.

**Impact**:
- Document Relevance Score: **50.9/100** (FAIL)
- Multi-document synthesis: **FAILED**
- RAG core value: **NOT ACHIEVED**

**Root Cause Confirmed**: **Small-to-Large context expansion** amplifies single-document bias from reranking.

---

## Analysis Results

### Test Data Evidence

From `benchmark_001` (MicroLED 디스플레이의 장점은?):
```json
{
  "citation_sources": 5,
  "unique_documents": 1,  // ⚠️ ALL from SAME file!
  "document": "lgd_display_news_2025_oct_20251019133222.pptx",
  "pages": [2, 6, 5, 7, 2]  // Different pages, SAME document
}
```

### Diversity Statistics (47 Tests)

```
Average Unique Docs:  1.0  // ALL tests = 1 unique document
Average Total Chunks: 4.6  // ~5 chunks retrieved
Diversity Ratio:      0.23 // 23% (should be >70%)
```

**Finding**: **100% of successful tests** used only ONE unique document.

---

## Root Cause: Three-Stage Amplification

### Stage 1: Reranking Bias (Initial Clustering)

**Code**: [`utils/vector_store.py:732-796`](utils/vector_store.py#L732-L796)

```python
def similarity_search_with_rerank(self, query, top_k=3, initial_k=20):
    # 1. Hybrid search retrieves initial_k * 2 candidates
    candidates = self.similarity_search_hybrid(query, initial_k=initial_k * 2, top_k=initial_k)

    # 2. Reranker scores all candidates
    reranked = reranker.rerank(query, docs_for_rerank, top_k=top_k)

    # ⚠️ NO DIVERSITY MECHANISM HERE
```

**Issue**: Reranker optimizes for **query-document relevance** only, with **no penalty** for same-document chunks. If Document A has multiple highly-relevant chunks, they ALL get high reranking scores.

**Example**:
```
Initial candidates (20):
- 8 chunks from Document A (OLED paper)
- 6 chunks from Document B (MicroLED paper)
- 4 chunks from Document C (QLED paper)
- 2 chunks from Document D (LCD paper)

After reranking (top 5):
- 5 chunks from Document A  // ⚠️ All from same doc!
```

**Why**: Document A has 8 candidates (highest count), so even with equal per-chunk relevance, it dominates by sheer volume.

---

### Stage 2: Small-to-Large Expansion (Amplification)

**Code**: [`utils/small_to_large_search.py:17-89`](utils/small_to_large_search.py#L17-L89)

```python
def search_with_context_expansion(self, query, top_k=5, max_parents=3):
    # 1. Small chunk search
    small_results = self.vectorstore.similarity_search_with_score(query, k=top_k * 2)

    # 2. For EACH small chunk, add parent chunk
    for doc, score in small_results:
        expanded_results.append((doc, score))  # Small chunk

        parent_id = doc.metadata.get("parent_chunk_id")
        if parent_id:
            parent_doc = self._get_parent_chunk(parent_id)
            if parent_doc:
                # ⚠️ ADDS PARENT FROM SAME DOCUMENT
                expanded_results.append((partial_parent_doc, score * 0.8))
```

**Issue**: If top 3 small chunks come from Document A, then up to 3 parent chunks ALSO come from Document A, resulting in 6 chunks from the same document.

**Amplification Factor**:
```
Input:  3 chunks from Doc A, 1 from Doc B, 1 from Doc C

After Small-to-Large:
- 3 small chunks from Doc A
- 3 parent chunks from Doc A  // ⚠️ DOUBLES Doc A presence
- 1 small chunk from Doc B
- 1 parent chunk from Doc B
- 1 small chunk from Doc C
- 1 parent chunk from Doc C

Result: 6 chunks from Doc A (60%), 2 from Doc B (20%), 2 from Doc C (20%)
        → Single document dominates
```

---

### Stage 3: Deduplication (Insufficient Filtering)

**Code**: [`utils/small_to_large_search.py:128-150`](utils/small_to_large_search.py#L128-L150)

```python
def _deduplicate_by_similarity(self, results, threshold=0.85):
    # Only removes IDENTICAL or near-identical chunks
    for doc, score in results:
        is_duplicate = False
        for seen_content in seen_contents:
            if self._is_similar_content(content, seen_content, threshold):
                is_duplicate = True  # ⚠️ Only removes duplicates, NOT diversity
```

**Issue**: Deduplication removes **identical chunks** but does **NOT** enforce **document diversity**. Multiple chunks from the same document with **different content** pass through.

**Example**:
```
Before dedup (Doc A):
- Chunk 1: "OLED has high contrast..."
- Chunk 2: "OLED efficiency is..."
- Chunk 3: "OLED cost analysis..."
- Chunk 4: "OLED market share..."

After dedup (85% similarity threshold):
→ ALL 4 chunks KEPT (different content, same document)
```

---

## Why This Matters

### 1. RAG Core Value Failure

**Expected Behavior**:
```
Question: "MicroLED 디스플레이의 장점은?"

Expected sources:
- MicroLED paper 1
- MicroLED paper 2
- Comparative study (MicroLED vs OLED)
- Industry report
- Review paper

→ Multi-document synthesis
```

**Actual Behavior**:
```
Actual sources:
- lgd_display_news.pptx page 2
- lgd_display_news.pptx page 6
- lgd_display_news.pptx page 5
- lgd_display_news.pptx page 7
- lgd_display_news.pptx page 2 (duplicate)

→ Single-document limitation
```

### 2. Knowledge Recall Limitation

**Impact**:
- ❌ Cannot synthesize across multiple papers
- ❌ Misses alternative perspectives
- ❌ Limited to one author's viewpoint
- ❌ Cannot compare/contrast approaches

**Example (Real Test)**:
```
Question: "OLED와 QLED의 차이점은?"

Expected: Compare OLED paper + QLED paper + Comparison study
Actual:   Only uses 1 OLED paper

Result: Partial answer, missing QLED perspective
Score:  60/100 (PARTIAL)
```

---

## Solution Design

### Primary Solution: **Diversity Penalty in Reranking**

**Location**: [`utils/reranker.py`](utils/reranker.py)

**Strategy**:
```python
def rerank_with_diversity_penalty(self, query, docs, top_k=10):
    # 1. Standard reranking scores
    scores = self.model.rank(query, docs)

    # 2. Apply diversity penalty
    source_counter = Counter()
    adjusted_scores = []

    for doc, score in sorted_docs:
        source = doc['metadata']['source']

        # Penalty increases with each chunk from same document
        penalty = 1.0 - (source_counter[source] * 0.3)
        penalty = max(penalty, 0.1)  # Minimum 10% of original score

        adjusted_score = score * penalty
        source_counter[source] += 1

        adjusted_scores.append((doc, adjusted_score))

    # 3. Re-sort by adjusted scores
    return sorted(adjusted_scores, key=lambda x: x[1], reverse=True)[:top_k]
```

**Expected Effect**:
```
Before (no penalty):
- Doc A chunk 1: 0.95 → rank 1
- Doc A chunk 2: 0.93 → rank 2
- Doc B chunk 1: 0.91 → rank 3
- Doc A chunk 3: 0.90 → rank 4
- Doc A chunk 4: 0.88 → rank 5

After (30% penalty per repeat):
- Doc A chunk 1: 0.95 * 1.0 = 0.95 → rank 1
- Doc B chunk 1: 0.91 * 1.0 = 0.91 → rank 2 ⬆️
- Doc A chunk 2: 0.93 * 0.7 = 0.65 → rank 3 ⬇️
- Doc C chunk 1: 0.85 * 1.0 = 0.85 → rank 4 ⬆️
- Doc A chunk 3: 0.90 * 0.4 = 0.36 → rank 5 ⬇️

Result: 1 from Doc A, 1 from Doc B, 1 from Doc C
        → Multi-document diversity achieved!
```

---

## Expected Improvements

### Quantitative Targets (Week 1)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Document Relevance | 50.9/100 | 75.0/100 | +24.1 points |
| Unique Docs per Query | 1.0 avg | 3.5 avg | +250% |
| Multi-doc Tests (>1 doc) | 0% | 85% | +85pp |
| Overall Score | 73.1/100 | 85.0/100 | +11.9 points |

### Qualitative Benefits

1. ✅ **True RAG**: Multi-document synthesis working as intended
2. ✅ **Better Coverage**: Multiple perspectives from different sources
3. ✅ **Reduced Bias**: Not limited to single author/viewpoint
4. ✅ **Improved Comparison**: Can compare across papers

---

## Implementation Plan (Day 1-2)

### Task 1: Implement Diversity Penalty (4 hours)

**File**: [`utils/reranker.py`](utils/reranker.py)

1. Add `apply_diversity_penalty()` method
2. Integrate into `rerank()` method
3. Add configurable penalty strength (0.2-0.5)
4. Add option to disable for backward compatibility

### Task 2: Test & Tune (2 hours)

1. Create test script with known multi-document queries
2. Test penalty strengths: 0.2, 0.3, 0.4, 0.5
3. Measure diversity ratio for each
4. Select optimal penalty (target: 0.3)

### Task 3: Integration (2 hours)

1. Update `config.py` to add diversity settings
2. Update `rag_chain.py` to pass penalty parameter
3. Add logging for diversity metrics
4. Document in code comments

---

## Validation Criteria

### Success Metrics

1. ✅ **Unique Docs**: Average ≥ 3.0 per query (currently 1.0)
2. ✅ **Diversity Ratio**: ≥ 0.60 (currently 0.23)
3. ✅ **Multi-doc Tests**: ≥ 80% with >1 unique doc (currently 0%)
4. ✅ **No Regression**: Answer completeness maintains ≥ 75/100

### Test Cases

**High Priority (Multi-document Expected)**:
- `benchmark_002`: "OLED와 QLED의 차이점은?"
- `benchmark_004`: "Display 분야 최신 트렌드는?"
- `performance_001`: "OLED, QLED, MicroLED, Mini-LED, LCD, Flexible Display의 차이점..."

**Edge Cases (Should NOT Over-Diversify)**:
- `doc_format_001`: "LG디스플레이의 2025년 계획은? (PPTX 문서)"
  - Expected: Single document OK (specific document query)

---

## Risk Assessment

### Low Risk ✅

- **Backward Compatible**: Can disable penalty via config
- **Incremental**: Only affects reranking, not search/indexing
- **Reversible**: Easy to roll back if issues arise

### Potential Issues

1. **Over-Diversification**: Too strong penalty → irrelevant docs
   - Mitigation: Tunable penalty (0.2-0.5), testing with multiple values

2. **Performance Impact**: Additional computation in reranking
   - Mitigation: O(n) overhead, negligible for n<100

3. **Document-Specific Queries**: User asks about specific document
   - Mitigation: Penalty only applies after 2+ chunks, first chunk unpenalized

---

## Next Steps

### Immediate (Today)

1. ✅ Root cause confirmed
2. 🔄 Create diagnostic report (this document)
3. ⏭️ Implement diversity penalty in `utils/reranker.py`
4. ⏭️ Test with sample queries
5. ⏭️ Integrate into RAG chain

### Tomorrow (Day 2)

6. Run comprehensive test suite (47 tests)
7. Analyze diversity improvements
8. Tune penalty strength if needed
9. Document results in Day 2 report

### Week 1 Completion

- Day 3: Multi-query optimization
- Day 4: Combined testing
- Day 5: Week 1 summary report

---

## References

- Test Results: `INTERIM_STATUS_REPORT.md`
- Week 1 Plan: `WEEK1_ACTION_PLAN.md`
- Deep Quality Report: `deep_quality_report_comprehensive.json`
- Diversity Analysis: `retrieval_diversity_report.json`

---

**Report Generated**: 2025-11-11
**Analyst**: Claude Code (Week 1, Day 1)
**Status**: Ready for Implementation ✅
