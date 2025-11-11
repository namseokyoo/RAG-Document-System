# Small-to-Large Context Size 분석 및 권장사항

## 📊 Executive Summary

**결론**: Small-to-Large `partial_context_size` 파라미터는 **정상 동작**하고 있으나, 현재 데이터베이스 구조상 영향이 제한적입니다.

**최종 권장값**: **800자** (향후 확장성을 고려한 여유있는 설정)

---

## 🔍 테스트 수행 내역

### 1차 테스트: 전체 RAG Chain A/B Test
- **파일**: `test_context_size_ab.py`
- **방법**: RAGChain을 통한 전체 파이프라인 테스트
- **결과**: ❌ Small-to-Large가 활성화되지 않음
  - Question Classifier가 질문을 "comparison", "general" 타입으로 분류
  - Small-to-Large는 "specific_info" 타입에만 활성화
  - **학습**: 실제 사용 시에도 Small-to-Large 활성화 빈도가 낮을 수 있음

### 2차 테스트: 직접 Small-to-Large Method 호출
- **파일**: `test_context_size_direct.py`
- **방법**: `SmallToLargeSearch.search_with_context_expansion()` 직접 호출
- **결과**: ⚠️ 모든 context_size에서 동일한 결과 (평균 596자)

| Context Size | 평균 문서 길이 | 증가율 |
|-------------|------------|--------|
| 200자       | 596자      | 0.0%   |
| 400자       | 596자      | 0.0%   |
| 600자       | 596자      | 0.0%   |
| 800자       | 596자      | 0.0%   |

### 3차 분석: 진단 스크립트
- **파일**: `diagnose_small_to_large.py`
- **발견**: ✅ `_extract_partial_context` 메서드는 정상 동작
  - Partial Parent 추출 성공 (context_size=600 → 693자 추출)
  - 하지만 **Partial Parent가 Top-5에 포함되지 않음**
  - 이유: Small 청크 점수 > Partial Parent 점수 (0.8배)

### 4차 분석: 데이터베이스 구조 분석
- **파일**: `analyze_chunk_relationships.py`
- **핵심 발견**: 🎯 **74.3%의 청크가 부모 없음**

```
청크 타입 분포:
- page_summary : 1,177개 (74.3%) → 부모 없음
- paragraph    :   363개 (22.9%) → 일부만 부모 있음
- list         :    30개 ( 1.9%)
- caption      :    10개 ( 0.6%)
- section      :     5개 ( 0.3%)

부모-자식 관계:
- parent_chunk_id 있음: 408개 (25.7%)
- parent_chunk_id 없음: 1,177개 (74.3%)
- 고유한 parent_id 수: 14개
```

---

## 🧩 왜 Context Size가 결과에 영향을 주지 않았나?

### 근본 원인: 데이터베이스 구조

1. **74.3%의 청크가 확장 불가능**
   - `page_summary` 타입은 `parent_chunk_id`가 없음
   - 이미 페이지 전체 요약이므로 부모 개념이 없음
   - 크기: 대부분 600~800자

2. **확장 가능한 25.7% 청크의 제약**
   - `paragraph` 타입 중 일부만 부모 존재
   - 부모는 `page_summary` (600~800자)
   - `context_size=200~800`으로 추출 시 → 부모 전체 반환 (크기가 비슷)

3. **검색 결과 구성의 문제**
   - Top-10 검색 결과 중 대부분이 `page_summary` (부모 없음)
   - `paragraph`는 상대적으로 낮은 점수
   - Partial Parent는 0.8배 점수로 더욱 낮아짐
   - **최종 Top-5는 모두 Small 청크**

### 실제 동작 예시 (진단 결과)

```
정렬된 상위 10개:
1. [small ] Score: 266.2277, 길이: 786자  ← Top-5 선택
2. [small ] Score: 264.7362, 길이: 750자  ← Top-5 선택
3. [small ] Score: 264.5479, 길이: 746자  ← Top-5 선택
4. [small ] Score: 264.1342, 길이: 754자  ← Top-5 선택
5. [small ] Score: 258.1985, 길이: 751자  ← Top-5 선택
6. [small ] Score: 257.6558, 길이: 777자
7. [small ] Score: 250.8211, 길이:  91자
8. [small ] Score: 237.5578, 길이: 693자
9. [small ] Score: 230.0916, 길이:  83자  ← 부모 있음
10. [small] Score: 229.0221, 길이:  50자  ← 부모 있음

(순위 밖)
11. [parent] Score: 184.0733, 길이: 693자  ← 추출됨, 하지만 Top-5 탈락
12. [parent] Score: 183.2177, 길이: 693자  ← 추출됨, 하지만 Top-5 탈락
```

---

## 💡 Small-to-Large가 효과적인 경우

### 현재 데이터베이스에서는 제한적

1. ✅ **작동하는 경우** (25.7% 청크):
   - `paragraph` 타입이 검색되고
   - 해당 paragraph가 높은 점수를 받고
   - Partial Parent가 0.8배 점수로도 Top-K에 진입할 때

2. ❌ **작동하지 않는 경우** (74.3% 청크):
   - `page_summary` 타입 검색 시 (부모 없음)
   - 이미 충분히 긴 컨텍스트 (600~800자)

### 향후 효과적일 수 있는 시나리오

**사용자 요청**: "향후 사용하는 문서에 따라 차이가 있을 수 있으니 좀 여유있게 설정해줘"

Small-to-Large가 큰 효과를 발휘할 문서 타입:

1. **긴 기술 문서** (2,000자+ 부모 청크):
   - 현재: 부모 600~800자 → context_size 영향 적음
   - 향후: 부모 2,000자+ → context_size 800이 필요한 표/수식 커버

2. **계층적 구조가 명확한 문서**:
   - Small: 50~200자 핵심 문장
   - Large: 1,000~2,000자 섹션 전체
   - → context_size로 필요한 만큼만 추출

3. **표와 수식이 많은 문서**:
   - Small: 표 셀 또는 수식 일부
   - Large: 표 전체 + 헤더 (1,000자+)
   - → context_size 800으로 표 완전성 확보

---

## 🎯 최종 권장사항

### 1. Partial Context Size 설정

```python
# config.json 또는 RAGChain 초기화 시
small_to_large_context_size = 800  # 권장값
```

**선택 근거**:

| Context Size | 장점 | 단점 | 적합 상황 |
|-------------|------|------|----------|
| 200자 (현재) | 빠름, 토큰 절약 | 표/수식 불완전 | 짧은 FAQ |
| 400자 | 균형적 | 중간 크기 표 누락 가능 | 일반 문서 |
| **600자** | **안정적 표 커버** | **토큰 증가 미미** | **일반 기술 문서** (차선) |
| **800자** | **큰 표/수식 완전 포함** | **토큰 증가 중간** | **복잡한 기술 문서** (권장) |

**결정**: **800자**
- 사용자 요청대로 "여유있게" 설정
- 현재 데이터에서는 영향 적지만, 향후 확장성 확보
- 부모 청크가 크거나 표/수식이 많은 문서에서 효과적

### 2. 구현 방법

#### Option A: config.json 수정 (권장)
```json
{
  "small_to_large_context_size": 800,
  "enable_question_classifier": true
}
```

#### Option B: RAGChain 초기화 시 직접 전달
```python
rag_chain = RAGChain(
    vectorstore=vector_manager,
    # ... 기타 파라미터 ...
    small_to_large_context_size=800  # 명시적 설정
)
```

### 3. 추가 최적화 제안

#### 현재 시스템 개선 (선택사항)
```python
# utils/small_to_large_search.py 76번 라인
# 현재: parent_score = score * 0.8
# 제안: parent_score = score * 0.9  # Partial Parent 순위 상승

# 이유:
# - 현재는 Partial Parent가 Top-K에 거의 진입하지 못함
# - 0.9로 조정 시 부모 컨텍스트 포함 확률 증가
# - context_size 파라미터의 실제 영향 증가
```

#### 동적 Context Size (미래 개선)
```python
def get_dynamic_context_size(chunk_type: str, parent_size: int) -> int:
    """문서 타입과 부모 크기에 따라 동적 조정"""
    if chunk_type == "table_cell":
        return 1000  # 표 전체 포함
    elif chunk_type == "formula":
        return 600   # 수식 전후 설명
    elif parent_size > 2000:
        return 800   # 큰 부모는 부분만
    else:
        return parent_size  # 작은 부모는 전체
```

---

## 📈 예상 효과

### 현재 데이터베이스
- **즉각적 개선**: ⚠️ 미미함 (74.3% 청크는 확장 불가)
- **25.7% 청크에서만**: 더 완전한 컨텍스트 제공
- **토큰 증가**: 거의 없음 (Partial Parent가 Top-K에 잘 안 들어감)

### 향후 새로운 문서
- **긴 부모 청크 (1,000자+)**: ✅ 800자 추출로 표/수식 완전성 확보
- **계층적 문서**: ✅ 필요한 만큼만 컨텍스트 추가
- **성능 영향**: 미미 (추출은 단순 문자열 슬라이싱)

---

## 🔧 실행 계획

### 즉시 적용 (필수)
1. ✅ `config.json`에 `small_to_large_context_size: 800` 추가
2. ✅ `utils/rag_chain.py`에서 해당 파라미터 읽어서 전달

### 선택적 개선 (추천하지 않음, 현재 시스템 작동 중)
1. ⚠️ Partial Parent 점수 가중치 조정 (0.8 → 0.9)
   - 장점: context_size 파라미터의 실제 영향 증가
   - 단점: 기존 검색 순위 변경, 예상치 못한 영향 가능

### 미래 고려사항
1. 📋 새로운 문서 인제스트 시 chunking 전략 재검토
   - Small 청크: 50~200자 (핵심 문장)
   - Large 청크: 1,000~2,000자 (전체 섹션)
   - parent_chunk_id 비율 증가 목표

---

## 📚 생성된 테스트 파일

| 파일 | 설명 |
|-----|------|
| `test_context_size_ab.py` | 전체 RAG Chain A/B 테스트 (1차 시도) |
| `test_context_size_ab_result.json` | 1차 테스트 결과 |
| `test_context_size_direct.py` | Small-to-Large 직접 호출 테스트 (2차) |
| `test_context_size_direct_result.json` | 2차 테스트 결과 |
| `diagnose_small_to_large.py` | 상세 진단 스크립트 (3차) |
| `analyze_chunk_relationships.py` | DB 구조 분석 (4차) |
| `CONTEXT_SIZE_ANALYSIS_REPORT.md` | 이 보고서 |

---

## ✅ 결론

1. **`partial_context_size` 파라미터는 정상 작동**함
   - `_extract_partial_context` 메서드가 의도대로 동작
   - 테스트에서 동일한 결과가 나온 이유는 데이터베이스 구조 때문

2. **현재 데이터베이스에서는 영향이 제한적**
   - 74.3%의 청크는 확장 불가능 (부모 없음)
   - 확장 가능한 청크도 부모가 작아서 (600~800자) 전체 반환
   - Partial Parent가 Top-K에 거의 진입하지 못함

3. **하지만 800자 설정을 권장**
   - 사용자 요청대로 "여유있게" 설정
   - 향후 다양한 문서 타입에 대한 확장성 확보
   - 성능 영향 미미 (단순 문자열 슬라이싱)
   - 큰 표, 복잡한 수식, 긴 섹션에서 효과적

**사용자 요구사항 충족**: ✅ "향후 사용하는 문서에 따라 차이가 있을 수 있으니 좀 여유있게 설정" → **800자로 설정**

---

*분석 완료 일시: 2025-01-08*
*RAG System Version: v3.5.0*
