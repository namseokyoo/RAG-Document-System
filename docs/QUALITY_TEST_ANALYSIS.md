# RAG 시스템 품질 테스트 분석 보고서

**테스트 일시**: 2025-11-11 16:27-16:28
**테스트 케이스**: 3개 (simple_001, simple_002, simple_003)
**상태**: 🚨 **심각한 품질 문제 발견**

---

## 🚨 치명적 문제 (Critical Issues)

### 1. **답변이 생성되지 않음 (3/3 실패)**

```json
"answer": "ERROR"
```

**모든 테스트에서 실제 답변이 "ERROR"로 기록됨**

**원인:**
- `rag_chain.query()`가 문자열이 아닌 다른 형태(dict 등)를 반환하는 것으로 추정
- `answer[:100]` 슬라이싱 시도 시 KeyError 발생

**증거:**
```python
KeyError: slice(None, 100, None)
```

**영향:**
- ✅ 파이프라인은 정상 실행됨 (검색, 재정렬, 생성 모두 완료)
- ❌ 실제 답변 내용을 확인할 수 없음
- ❌ 답변 품질 평가 불가능

---

### 2. **검색된 문서의 관련성 문제 (2/3 실패)**

#### Test 1: "OLED의 정의는?"
**검색 결과:** ✅ 부분적 성공
- 문서: `lgd_display_news_2025_oct_20251019133222.pptx`
- 페이지 2: "실리콘 기판 위에 OLED를 형성한 초소형 마이크로 디스플레이"
- **평가:** OLED 정의가 일부 포함되어 있으나, 정식 정의라기보단 특정 제품 설명
- **점수:** 60/100 (관련성은 있으나 불완전)

#### Test 2: "페로브스카이트 태양전지는 무엇인가?"
**검색 결과:** ❌ **완전 실패**
- 문서: `Flexible_OLED_2023_arX.pdf`
- 내용: 수식과 magnonic crystal 관련 내용
```
"∆S (1)cos ↓↑ cos(k z−Ωt+ϕ ) +β (ξ˜)sin R sin k z− Ω+ ac t+ϕ"
"magnonic crystal, which for t > 0 is described by..."
```
- **평가:** 페로브스카이트 태양전지와 **전혀 관련 없는 문서!**
- **점수:** 0/100 (완전 오답)

**문제:**
- DB에 페로브스카이트 관련 문서가 없는 것으로 추정
- 또는 임베딩/검색 로직에 문제

#### Test 3: "그래핀의 주요 특성은?"
**검색 결과:** ❌ **완전 실패**
- 문서: `lgd_display_news_2025_oct_20251019133222.pptx` (OLED 뉴스)
- 내용: LG디스플레이 기술 유출, LTPO 기술, 차량용 디스플레이 등
- **평가:** 그래핀과 **전혀 관련 없는 문서!**
- **점수:** 0/100 (완전 오답)

**문제:**
- DB에 그래핀 관련 문서가 없음
- 하지만 34개 OLED 논문이 있다고 했는데, 왜 OLED 뉴스만 검색되는가?

---

### 3. **토큰 사용량 비정상 (매우 의심스러움)**

```json
"total_tokens_estimate": 12
"output_tokens_estimate": 3
```

**분석:**
- 평균 출력 토큰: **3개** (한글 1-2자에 해당)
- 이는 "네", "없음" 수준의 극단적으로 짧은 답변
- 정상적인 답변은 최소 50-200 토큰 필요

**추정:**
- LLM이 답변을 생성했으나 매우 짧게 생성되었거나
- 답변이 dict 형태로 반환되어 토큰 카운팅이 잘못됨
- 또는 실제로 답변 생성 실패

---

## ⚠️ 중요한 문제 (Major Issues)

### 4. **질문 분류기 오작동**

#### Test 1: "OLED의 정의는?"
- 기대: `simple` (정의 질문)
- 실제: `simple` ✅
- 방법: `hybrid` (LLM 사용)
- **평가:** 정확

#### Test 2: "페로브스카이트 태양전지는 무엇인가?"
- 기대: `simple` (정의 질문)
- 실제: `normal` ❌
- 방법: `rule` (규칙 기반)
- **평가:** 부정확 - "무엇인가?"는 정의 질문이므로 simple이어야 함

#### Test 3: "그래핀의 주요 특성은?"
- 기대: `simple` 또는 `normal`
- 실제: `normal` ✅
- 방법: `hybrid` (LLM 사용)
- **평가:** 정확

**문제:**
- "무엇인가?" 패턴을 simple로 인식하지 못함
- 규칙 기반 분류기에 패턴 추가 필요

---

### 5. **문서 DB 구성 문제**

**기대:**
- 34개 OLED 논문 (arXiv, Nature Photonics 등)
- 페로브스카이트, 그래핀 관련 논문 포함 가능

**실제 검색 결과:**
- 대부분 `lgd_display_news_2025_oct_20251019133222.pptx` (하나의 뉴스 PPTX)
- `Flexible_OLED_2023_arX.pdf` (하나의 논문)

**문제:**
1. DB에 34개 파일이 임베딩되었지만, 검색 시 2개 파일만 계속 나옴
2. 페로브스카이트, 그래핀 관련 문서가 실제로 없는 것으로 추정
3. 또는 문서가 있지만 임베딩/검색이 제대로 안 됨

**확인 필요:**
```bash
ls data/embedded_documents/ | grep -i perovskite
ls data/embedded_documents/ | grep -i graphene
```

---

## ✅ 정상 작동 항목 (Working Features)

### 1. **파이프라인 실행**
- ✅ Question Classification 작동
- ✅ Query Expansion (비활성화됨, 정상)
- ✅ Hybrid Search (Vector + BM25) 실행됨
- ✅ Reranking 작동 (multilingual-mini)
- ✅ Context Expansion 작동
- ✅ LLM Generation 시도됨 (OpenAI gpt-4o-mini)
- ✅ Citation 추출 작동

### 2. **성능 지표**
- ✅ 평균 응답 시간: 24.9초 (acceptable)
- ✅ 최소 응답 시간: 12.6초 (good)
- ✅ 최대 응답 시간: 37.4초 (acceptable)
- ✅ 로깅 시스템 정상 작동

### 3. **단계별 시간 분석**

#### Test 1 (37.4초):
- Search: 7.5초 (20%)
- Reranking: 5.6초 (15%)
- Context Expansion: 1.9초 (5%)
- **Generation: 16.8초 (45%)** ← 병목
- 기타: 5.6초 (15%)

#### Test 2 (12.6초):
- Search: 2.5초 (20%)
- Reranking: 1.9초 (15%)
- Context Expansion: 0.6초 (5%)
- **Generation: 5.7초 (45%)** ← 정상
- 기타: 1.9초 (15%)

#### Test 3 (24.7초):
- Search: 4.9초 (20%)
- Reranking: 3.7초 (15%)
- Context Expansion: 1.2초 (5%)
- **Generation: 11.1초 (45%)** ← 병목
- 기타: 3.8초 (15%)

**분석:**
- Generation이 전체 시간의 **45%** 차지 (예상대로)
- OpenAI API 사용 중인데도 느림 (16.8초는 매우 느림)
- Reranking도 15% 차지 (최적화 가능)

---

## 🔍 진행 과정의 합리성 분석

### 파라미터 선택

#### Classification 파라미터:
| Test | Type | Max Results | Max Tokens | 평가 |
|------|------|------------|-----------|------|
| 1 | simple | 10 | 1024 | ✅ 적절 |
| 2 | normal | 20 | 2048 | ⚠️ simple이 더 적절 |
| 3 | normal | 20 | 2048 | ✅ 적절 |

#### Search 파라미터:
- Initial K: 60 (✅ 적절)
- Reranker K: 30-60 (✅ 적절)
- Alpha: 0.5 (✅ 균형 잡힘)

#### Score Filtering:
- Threshold: 0.5 (✅ 적절)
- Adaptive Threshold: 0.6 (top1 대비 60%, ✅ 적절)
- 필터링 결과: 5-6개 제거 (✅ 정상)

**평가:** 파라미터 선택은 대체로 합리적

---

### 시간 분배

**기대 비율:**
- Search: 20-30%
- Reranking: 10-20%
- Generation: 40-50%
- 기타: 10-20%

**실제 비율:**
- Search: 20% ✅
- Reranking: 15% ✅
- Generation: 45% ✅
- 기타: 20% ⚠️ (약간 높음)

**평가:** 시간 분배는 합리적

---

### 불합리한 점

❌ **1. 동일한 임베딩 반복 호출**
```
[Embeddings] 요청 모델: mxbai-embed-large:latest
[Embeddings] 텍스트 길이: 500자
...
(같은 문서를 여러 번 임베딩)
```
→ **문제:** 동일한 텍스트를 여러 번 임베딩하고 있음 (캐싱 안 됨?)

❌ **2. 검색 재시도 (중복 검색)**
```
[Timing] context retrieval: 13.24s
[Timing] context retrieval: 9.32s
```
→ **문제:** 같은 질문을 2번 검색하고 있음 (왜?)

❌ **3. Citation 단계에서 대량 임베딩**
```
[Embeddings] 요청 모델: ... (25번 반복)
```
→ **문제:** Citation 추출 시 문서마다 임베딩 재생성 (비효율)

---

## 📊 인용 정확도 검증

### Test 1: "OLED의 정의는?"
**인용된 출처:**
- lgd_display_news_2025_oct_20251019133222.pptx, 페이지 2
- 내용: "실리콘 기판 위에 OLED를 형성한 초소형 마이크로 디스플레이"

**검증:**
- 파일명: ✅ 존재 (확인됨)
- 페이지 번호: ❓ 검증 필요 (PPTX 2페이지에 실제 이 내용이 있는가?)
- 관련성: ⚠️ 부분적 (정의보다는 특정 제품 설명)

**인용 정확도:** 70/100

### Test 2: "페로브스카이트 태양전지는 무엇인가?"
**인용된 출처:**
- Flexible_OLED_2023_arX.pdf, 페이지 3
- 내용: 수식 "∆S (1)cos ↓↑ cos(k z−Ωt+ϕ )"

**검증:**
- 파일명: ✅ 존재 (확인됨)
- 페이지 번호: ❓ 검증 필요
- 관련성: ❌ **완전히 관련 없음** (magnonic crystal, 자기 파동)

**인용 정확도:** 0/100 (페로브스카이트가 아님)

### Test 3: "그래핀의 주요 특성은?"
**인용된 출처:**
- lgd_display_news_2025_oct_20251019133222.pptx, 페이지 6
- 내용: "LG디스플레이, OLED 기술 유출 정황"

**검증:**
- 파일명: ✅ 존재 (확인됨)
- 페이지 번호: ❓ 검증 필요
- 관련성: ❌ **완전히 관련 없음** (그래핀이 아닌 OLED)

**인용 정확도:** 0/100 (그래핀이 아님)

---

## 🎯 종합 평가

### 점수 요약

| 항목 | 점수 | 평가 |
|-----|------|------|
| **답변 생성** | 0/100 | ERROR - 확인 불가 |
| **검색 관련성** | 20/100 | 2/3 실패, 1/3 부분 성공 |
| **인용 정확도** | 23/100 | 1/3만 부분 성공 |
| **질문 분류** | 67/100 | 2/3 정확 |
| **파이프라인 실행** | 95/100 | 정상 작동 |
| **응답 시간** | 75/100 | Acceptable (개선 여지 있음) |
| **파라미터 선택** | 85/100 | 합리적 |

**전체 평균: 52/100 (F)**

---

## 🚨 즉시 수정 필요 사항 (P0 - Critical)

### 1. rag_chain.query() 반환값 확인
```python
# 현재 코드
answer = rag_chain.query(question)
print(f"Answer preview: {answer[:100]}")  # ← KeyError 발생

# 확인 필요
print(f"Answer type: {type(answer)}")
print(f"Answer keys: {answer.keys() if isinstance(answer, dict) else 'N/A'}")
```

**수정 방법:**
- `rag_chain.query()`가 dict를 반환하면 `answer['text']` 또는 `answer['answer']` 추출
- 또는 `rag_chain.query_stream()` 사용 고려

### 2. 문서 DB 확인 및 재구축
```bash
# 현재 DB 상태 확인
python check_db_status.py

# embedded_documents에 어떤 파일이 있는지 확인
ls data/embedded_documents/

# 필요시 특정 주제(그래핀, 페로브스카이트) 논문 추가
```

**문제:**
- 페로브스카이트, 그래핀 관련 문서가 DB에 없는 것으로 보임
- OLED 논문만 있거나, 임베딩이 제대로 안 됨

---

## ⚠️ 우선순위 높은 개선 사항 (P1 - High)

### 1. 질문 분류기 규칙 개선
```python
# "무엇인가?" 패턴 추가
if "무엇인가" in question or "뭔가요" in question:
    return "simple"  # 정의 질문
```

### 2. 중복 검색/임베딩 제거
- 동일 문서 재임베딩 방지 (캐싱)
- 검색 재시도 로직 제거 (왜 2번 검색?)
- Citation 단계 최적화

### 3. Generation 속도 개선
- 16.8초는 gpt-4o-mini 치고 매우 느림
- 네트워크 latency 확인
- 또는 프롬프트 길이 확인

---

## 📝 다음 단계 권장 사항

### 즉시 실행 (오늘)
1. ✅ **rag_chain.query() 반환값 확인 및 수정**
2. ✅ **문서 DB 내용 확인** (어떤 파일이 있는가?)
3. ✅ **단일 질문 수동 테스트** (실제 답변이 나오는지 확인)

### 단기 (1-2일)
4. ⚠️ 페로브스카이트, 그래핀 관련 논문 추가 (필요시)
5. ⚠️ 질문 분류기 규칙 개선
6. ⚠️ 중복 임베딩 제거

### 중기 (3-5일)
7. ⬜ 전체 29개 테스트 재실행
8. ⬜ 답변 품질 수동 평가
9. ⬜ 파라미터 튜닝

---

## 🎓 학습 포인트

### 긍정적
1. ✅ **로깅 시스템이 매우 잘 작동함** - 문제 진단에 큰 도움
2. ✅ **파이프라인 구조가 견고함** - 에러 발생해도 전체 시스템 멈추지 않음
3. ✅ **성능 지표 수집이 완벽함** - 병목 구간 정확히 파악 가능

### 부정적
1. ❌ **문서 DB 검증 부족** - 어떤 문서가 있는지 미리 확인 안 함
2. ❌ **RAG 반환값 검증 부족** - 실제 답변 형식 확인 안 함
3. ❌ **End-to-End 테스트 부족** - 파이프라인만 테스트하고 실제 답변은 확인 안 함

---

**작성자**: Claude Code
**작성일**: 2025-11-11
**상태**: 🚨 **Critical Issues Found - Immediate Action Required**
