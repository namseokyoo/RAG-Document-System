# Phase D: 답변 자연화 구현 계획

**작성일**: 2025-11-07
**버전**: v3.3.0 (Phase D)
**예상 소요**: 0.5일 (4-5시간)
**우선순위**: ★★★★★ (즉시 착수)

---

## 🎯 목표

**사용자 제기 문제 해결**:
1. ❌ 섹션 구조 강제 (답변:, 상세설명:, 참조 정보: 등)
2. ❌ 내용 중복 (섹션 채우기 위한 억지 분리)
3. ❌ 부자연스러운 답변
4. ⚠️ 토큰 부족 (복잡한 질문/번역 시)

**Phase D 목표**:
1. ✅ 섹션 제목 제거 → 자연스러운 문단
2. ✅ max_tokens 증가 → 복잡한 답변 가능 (2048 → 4096)
3. ✅ Inline Citation → NotebookLM 스타일
4. ✅ 금지 조항 완화 → 긍정적 가이드

---

## 📋 현재 문제점

### 문제 1: 섹션 강제 구조

**현재 프롬프트** (utils/rag_chain.py:189-194):
```
답변 형식 (다음 구조를 반드시 따르세요):

## 답변
[질문에 대한 직접적인 답변을 1-2문장으로 요약]

## 상세 설명
...
```

**문제**:
- 짧은 질문에도 무리하게 여러 섹션 생성
- 내용 중복 (답변 ↔ 상세설명)
- NotebookLM과 다른 형식

### 문제 2: 과도한 금지 조항

**현재 프롬프트** (utils/rag_chain.py:133-138):
```python
2. **금지 표현** (절대 사용 금지):
   [ERROR] "정보를 찾을 수 없습니다"
   [ERROR] "문서에 없습니다"
   [ERROR] "확인할 수 없습니다"
   [ERROR] "제공된 문서에서는 해당 정보를 찾을 수 없습니다"
   [ERROR] "문서에 명시되어 있지 않습니다"
```

**문제**:
- LLM이 금지어를 더 의식하게 만듦 (역효과)
- 정보가 실제로 없을 때 대응 방법 모호
- 프롬프트가 부정적

### 문제 3: max_tokens 설정 없음

**현재 코드**:
```python
# __init__에 max_tokens 파라미터 없음
# LLM 생성 시 max_tokens 설정 없음
# → Ollama 기본값 (2048) 사용
```

**문제**:
- 복잡한 질문/번역 시 토큰 부족
- 답변이 중간에 잘림

---

## ✅ 개선 방안

### 1. 프롬프트 개선 (1-2시간)

#### 제거할 것
- ❌ 섹션 강제 구조 (## 답변, ## 상세 설명 등)
- ❌ 5개 금지 표현 목록
- ❌ 5단계 답변 절차

#### 추가할 것
- ✅ 자연스러운 문단 형식 가이드
- ✅ 4개 다양한 예시 (간단/설명/번역/정보부족)
- ✅ Inline Citation 가이드
- ✅ 부드러운 원칙 1개

#### 개선된 프롬프트

```python
self.base_prompt_template = """당신은 문서 기반 AI 어시스턴트입니다. 제공된 문서를 바탕으로 정확하고 유용한 답변을 제공하세요.

제공된 문서:
{context}

이전 대화:
{chat_history}

질문:
{question}

---

답변 가이드:

1. **자연스러운 형식**:
   - 섹션 제목 없이 자연스러운 문단으로 작성
   - 질문이 간단하면 짧게 (1-2문장), 복잡하면 여러 문단으로
   - 사용자 의도에 맞게 답변 (번역/요약/설명 등)

2. **Inline Citation** (필수):
   - 모든 사실에 [번호] 표시
   - 예시: "kFRET 값은 87.8%입니다[1]."
   - 여러 출처: "TADF를 활용하며[1], 높은 효율을 보입니다[2]."

3. **예시**:

질문: "kFRET 값은?"
답변: 제공된 문서에 따르면, kFRET 값은 약 87.8%입니다[1]. 이는 형광 도펀트와 호스트 간의 에너지 전달 효율을 나타냅니다[1].

질문: "TADF란 무엇인가?"
답변: TADF(Thermally Activated Delayed Fluorescence)는 삼중항 여기자를 열적으로 활성화하여 일중항으로 재변환하는 발광 메커니즘입니다[1]. 이를 통해 OLED에서 이론적으로 100%의 내부 양자 효율을 달성할 수 있습니다[1][2].

질문: "서론 번역해줘"
답변: 하이브리드 형광 OLED는 TADF 보조 호스트와 형광 도펀트를 결합한 새로운 아키텍처입니다[1]. 이 접근법은 TADF의 높은 효율과 형광 도펀트의 우수한 색순도를 동시에 달성합니다[1][2].

질문: "합성 온도는?"
답변: 문서에서는 유기 합성 과정을 설명하고 있지만[1], 구체적인 합성 온도는 명시되어 있지 않습니다.

4. **중요**:
   문서에 근거하지 않은 추측은 하지 마세요. 문서의 내용만을 바탕으로 답변하세요.

답변:
"""
```

---

### 2. max_tokens 증가 (30분)

**파일**: utils/rag_chain.py

#### __init__ 메서드 수정

```python
def __init__(self,
             vectorstore,
             llm_api_type: str = "ollama",
             llm_base_url: str = "http://localhost:11434",
             llm_model: str = "gemma2:2b",
             llm_api_key: str = None,
             temperature: float = 0.3,
             max_tokens: int = 4096,  # 추가: 기본값 4096
             top_k: int = 5,
             ...):

    self.llm_api_type = llm_api_type
    self.llm_base_url = llm_base_url
    self.llm_model = llm_model
    self.llm_api_key = llm_api_key
    self.temperature = temperature
    self.max_tokens = max_tokens  # 추가
    self.top_k = top_k
    ...
```

#### _create_llm 메서드 수정

```python
def _create_llm(self):
    """API 타입에 따라 적절한 LLM 클라이언트 생성"""
    if self.llm_api_type == "request":
        return RequestLLM(
            base_url=self.llm_base_url,
            model=self.llm_model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,  # 추가
            timeout=60
        )
    elif self.llm_api_type == "ollama":
        return OllamaLLM(
            base_url=self.llm_base_url,
            model=self.llm_model,
            temperature=self.temperature,
            num_predict=self.max_tokens  # 추가 (Ollama는 num_predict 사용)
        )
    elif self.llm_api_type == "openai":
        kwargs = {
            "model": self.llm_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,  # 추가
            "api_key": self.llm_api_key if self.llm_api_key else "not-needed"
        }
        ...
```

---

### 3. 테스트 (2시간)

#### 테스트 케이스

**test_phase_d.py**:
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase D 테스트: 답변 자연화 검증"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_phase_d():
    print("=" * 80)
    print("Phase D 테스트: 답변 자연화")
    print("=" * 80)
    print()

    # VectorStore 초기화
    vectorstore = VectorStoreManager(
        embedding_api_type="ollama",
        embedding_base_url="http://localhost:11434",
        embedding_model="mxbai-embed-large:latest"
    )

    # RAGChain 초기화 (max_tokens=4096)
    rag = RAGChain(
        vectorstore=vectorstore,
        llm_api_type="ollama",
        llm_base_url="http://localhost:11434",
        llm_model="gemma3:latest",
        temperature=0.3,
        max_tokens=4096,  # Phase D: 증가
        top_k=5,
        use_reranker=True,
        enable_hybrid_search=True
    )

    # 테스트 질문
    test_cases = [
        {
            "question": "kFRET 값은?",
            "expected": "간단한 답변 (1-2문장)",
            "check_section": False  # 섹션 제목 없어야 함
        },
        {
            "question": "TADF의 원리를 설명해줘",
            "expected": "여러 문단 답변",
            "check_section": False
        },
        {
            "question": "HF-OLED 논문의 서론 부분 번역해줘",
            "expected": "전체 번역 (토큰 충분)",
            "check_section": False
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n[{i}] 질문: {case['question']}")
        print("-" * 80)

        result = rag.query(case["question"])

        if result["success"]:
            answer = result["answer"]
            print(answer)
            print()

            # 검증
            has_section_title = any(
                title in answer
                for title in ["## 답변", "## 상세 설명", "답변:", "상세설명:"]
            )

            if has_section_title:
                print("[WARN] 섹션 제목 발견 (제거되지 않음)")
            else:
                print("[OK] 섹션 제목 없음 (자연스러운 문단)")

            # Citation 확인
            citation_count = answer.count("[")
            print(f"[INFO] Citation 개수: {citation_count}")

            # 답변 길이
            print(f"[INFO] 답변 길이: {len(answer)} chars")
        else:
            print(f"[ERROR] 쿼리 실패: {result['answer']}")

        print()

    print("=" * 80)
    print("Phase D 테스트 완료")
    print("=" * 80)

if __name__ == "__main__":
    test_phase_d()
```

---

## 📊 예상 효과

| 항목 | Before (v3.2.0) | After (Phase D) | 개선 |
|------|----------------|-----------------|------|
| **섹션 강제** | 있음 (5개) | 없음 (자유) | ✅ 제거 |
| **답변 자연스러움** | 낮음 | 높음 | ✅ +40% |
| **max_tokens** | 2048 | 4096 | ✅ +100% |
| **금지 조항** | 5개 | 1개 | ✅ -80% |
| **중복 내용** | 많음 | 거의 없음 | ✅ -60% |
| **번역 요청 대응** | 부족 | 충분 | ✅ +100% |

---

## 📅 구현 일정

### 0.5일 (4-5시간)

**오전** (2-3시간):
1. 프롬프트 개선 (1-2시간)
   - 섹션 강제 제거
   - 금지 조항 완화
   - 4개 예시 추가
2. max_tokens 증가 (30분)
   - __init__ 수정
   - _create_llm 수정

**오후** (2시간):
3. 테스트 스크립트 작성 (30분)
4. 테스트 실행 및 검증 (1시간)
5. 문서화 (30분)

---

## 🎯 체크리스트

### 구현
- [ ] utils/rag_chain.py - base_prompt_template 수정
- [ ] utils/rag_chain.py - __init__ max_tokens 파라미터 추가
- [ ] utils/rag_chain.py - _create_llm max_tokens 전달

### 테스트
- [ ] test_phase_d.py 작성
- [ ] 간단한 질문 테스트 (섹션 없는지 확인)
- [ ] 복잡한 질문 테스트 (여러 문단 확인)
- [ ] 번역 요청 테스트 (토큰 충분한지 확인)

### 검증
- [ ] 섹션 제목 제거 확인
- [ ] Inline Citation 확인
- [ ] 답변 자연스러움 확인
- [ ] max_tokens 4096 적용 확인

---

## 📝 다음 단계

Phase D 완료 후:
```
✅ Phase A-3 (완료)
✅ Phase D (답변 자연화) - 0.5일
    ↓
➡️ Phase B-1 (Qwen3) - 3-4일
    ↓
➡️ Phase C (Citation 95%) - 3일
    ↓
✅ v4.0 완성
```

**총 예상 기간**: 6.5-7.5일

---

## 🔗 참고

- **NotebookLM**: 자연스러운 문단 형식, Inline Citation
- **Perplexity AI**: "Cite every claim with a URL, or respond with 'I don't know.'"
- **OpenAI GPT-4**: Few-shot learning, Clear Instructions
- **RAG 연구**: Extractive answering, Document-grounded generation
