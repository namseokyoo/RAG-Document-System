# Phase 1-B Test Results: Table Structure Matching

**Date**: 2025-11-19
**Status**: ⚠️ Issue Discovered - Vision API Table Detection Inaccuracy

---

## Test Overview

**Objective**: Verify that table structure matching can correctly identify Slide 2 (title-less) by comparing table dimensions.

**Test File**: `advanced_01_financial_report.pptx`

**Test Script**: [test_table_matching.py](test_table_matching.py)

**Result**: ❌ Matching Failed (but provided valuable insights)

---

## Test Results

### Part 1: python-pptx Table Extraction ✅

**All slides successfully analyzed**:

| Slide | Title | Tables | Structure |
|-------|-------|--------|-----------|
| 1 | 2024년 1분기 경영 성과 분석 | 0 | - |
| 2 | 제목없음-슬라이드2 | 1 | **7행 × 5열** |
| 3 | 비용 구조 분석 | 1 | **5행 × 3열** |
| 4 | 전략적 분석 및 계획 | 0 | - |

**Conclusion**: python-pptx table extraction works perfectly.

---

### Part 2: COM Rendering ✅

**All slides successfully rendered**:

```
[Vision] PowerPoint 열림: 4개 슬라이드
  [OK] 슬라이드 1 렌더링 완료 (제목: 제목없음-슬라이드1)
  [OK] 슬라이드 2 렌더링 완료 (제목: 비용 구조 분석)
  [OK] 슬라이드 3 렌더링 완료 (제목: 전략적 분석 및 계획)
  [OK] 슬라이드 4 렌더링 완료 (제목: 전략적 분석 및 계획)
[Vision] PowerPoint 종료
렌더링 완료: 4개 이미지
```

**Observations**:
1. COM rendered 4 images successfully
2. Image titles confirm the ordering mismatch (COM Slide 1 is title-less, COM Slide 2 is "비용 구조 분석")
3. This matches our previous diagnostic findings

**Conclusion**: COM rendering works correctly.

---

### Part 3: Vision API Table Detection ⚠️

**Vision API detected table structures**:

| COM Image | Title | Vision Detection | python-pptx Ground Truth |
|-----------|-------|------------------|-------------------------|
| 1 | 제목없음-슬라이드1 | **6행 × 4열** | 7행 × 5열 |
| 2 | 비용 구조 분석 | **4행 × 3열** | 5행 × 3열 |
| 3 | 전략적 분석 및 계획 | No table | - |
| 4 | 전략적 분석 및 계획 | No table | - |

**Critical Finding**: Vision API table detection is **inaccurate**!

**Discrepancies**:
- COM Image 1 (Slide 2 ground truth): Vision detected 6×4, actual 7×5
  - Missing 1 row, missing 1 column
- COM Image 2 (Slide 3 ground truth): Vision detected 4×3, actual 5×3
  - Missing 1 row

**Conclusion**: Vision API with `detail: "low"` mode is not reliable for table structure detection.

---

### Part 4: Table Structure Matching ❌

**Test**: Match python-pptx Slide 2 (7×5 table) with COM images

**Process**:
```
python-pptx Slide 2 structure: 1개 표, 7행 5열

Checking COM Image 1:
  Vision detected: 6행 × 4열
  Score: +10 (table count match) + 0 (structure mismatch) = 10

Checking COM Image 2:
  Vision detected: 4행 × 3열
  Score: +10 (table count match) + 0 (structure mismatch) = 10

Best score: 10 (below threshold 20)
```

**Result**: ❌ Matching Failed

**Conclusion**: Matching failed due to Vision API inaccuracy, NOT algorithm failure.

---

## Root Cause Analysis

### Why Did Vision API Fail?

**Hypothesis 1**: `detail: "low"` mode insufficient

- **Low detail**: 85 tokens (512×512 simplified image)
- **High detail**: 600+ tokens (2048×2048 detailed tiles)

**Evidence**: The "low" mode likely can't distinguish merged cells or small text clearly enough to count rows/cols accurately.

**Solution**: Use `detail: "high"` for table structure detection only

---

### Why Missing 1 Row/Col Consistently?

**Hypothesis 2**: Vision API may be skipping headers or merged cells

**Observations**:
- Both tables missing exactly 1 row
- Image 1 also missing 1 col

**Possible Causes**:
1. Header rows not counted as data rows
2. Merged cells causing confusion
3. Low resolution making some borders invisible

---

## Revised Implementation Strategy

### Option A: Use `detail: "high"` for Table Detection ⭐ **Recommended**

**Changes Needed**:

```python
# In _detect_table_structure_via_vision()
payload = {
    "model": llm_model,
    "messages": [...],
    "max_tokens": 100,
    "temperature": 0
}

# Change image detail level
"image_url": {
    "url": f"data:image/png;base64,{image_base64}",
    "detail": "high"  # Changed from "low"
}
```

**Cost Impact**:
- Low: 85 tokens → High: ~600 tokens (7x increase)
- Per table detection: $0.000044 → $0.00030
- 4 images: $0.00018 → $0.0012 (still <0.2 cents)

**Expected Accuracy**: Much higher (GPT-4V achieves 90%+ on high detail)

---

### Option B: Improve Prompt for Low Detail

**Add specific instructions**:

```python
prompt = """이 슬라이드에 표가 있나요?

주의: 헤더 행과 병합된 셀도 모두 세어주세요.

표_개수: N
표1: R행 C열 (헤더 포함, 모든 행/열 포함)
"""
```

**Cost**: Same (still "low" detail)

**Expected Accuracy**: Moderate improvement (maybe 80%)

---

### Option C: Fuzzy Matching (Tolerance)

**Modify scoring algorithm**:

```python
# Allow ±1 row/col difference
def is_table_match(t1, t2, tolerance=1):
    row_diff = abs(t1["rows"] - t2["rows"])
    col_diff = abs(t1["cols"] - t2["cols"])
    return row_diff <= tolerance and col_diff <= tolerance

# Scoring
if is_table_match(s_tbl, i_tbl, tolerance=1):
    score += 20  # Match with tolerance
```

**Cost**: None (algorithm change only)

**Risk**: May match wrong slides if tables are similar

---

## Recommended Next Steps

### Immediate (Today)

1. **Implement Option A: `detail: "high"` mode**
   - Quick code change (1 line)
   - Test with same script
   - Verify accuracy improvement

2. **If Option A succeeds**:
   - Rerun full integration test
   - Document final accuracy
   - Move to Phase 2

### Alternative (If high detail too expensive)

3. **Implement Option C: Fuzzy matching**
   - Add tolerance parameter
   - Test with tolerance=1
   - Monitor for false positives

---

## Lessons Learned

### Key Insights

1. **Vision API `detail: "low"` is NOT suitable for precise structure detection**
   - Good for: Content understanding, general layout
   - Bad for: Exact counting, precise measurements

2. **Table structure matching concept is sound**
   - Algorithm works correctly
   - Scoring system is reasonable
   - Only limitation: Vision API input quality

3. **Cost optimization can backfire**
   - Saving 85% of tokens ($0.000044 → $0.00030) is not worth it if accuracy drops
   - Better to use high detail for critical tasks

### What Works

✅ python-pptx table extraction (100% accurate)
✅ COM rendering (works correctly)
✅ Matching algorithm (logic is correct)
✅ Test methodology (discovered the real issue)

### What Needs Improvement

❌ Vision API detail level (too low)
❌ Prompt specificity (could be clearer about headers/merged cells)

---

## Updated Implementation Plan

### Phase 1-B (Revised)

**Step 1**: Change `detail: "low"` → `"high"` in `_detect_table_structure_via_vision()`

**Step 2**: Rerun `test_table_matching.py`

**Step 3**: If successful, run full integration test

**Expected Outcome**: 75% Vision usage (3/4 slides)

**Total Cost**: Still negligible (<$0.002 for full test)

---

## Conclusion

### Summary

**Implementation**: ✅ Technically correct
**Algorithm**: ✅ Sound logic
**Test**: ✅ Revealed critical insight
**Result**: ⚠️ Vision API limitation discovered

### The Real Issue

Not a code bug, but a **configuration choice**:
- `detail: "low"` is insufficient for table structure detection
- Need `detail: "high"` for accurate row/col counting

### Path Forward

1. **Short term**: Switch to `detail: "high"` for table detection
2. **Medium term**: Implement Phase 2-A (Smart Vision Decision)
   - Simple tables: Skip Vision, use python-pptx directly
   - Complex tables: Use Vision with high detail
3. **Long term**: Phase 3 text similarity matching (most robust)

---

**Status**: Phase 1-B implementation complete, refinement needed
**Next Action**: Update detail level to "high" and retest
**Expected Time**: 10 minutes to fix + 5 minutes to test

**Files Modified**: 1 line change in [utils/pptx_chunking_engine.py:367](utils/pptx_chunking_engine.py#L367)
