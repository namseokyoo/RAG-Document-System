# RAG 시스템 성능 테스트 계획

## 📋 테스트 목적

### Phase 1 파라미터 최적화 후 성능 개선도 측정
- `chunk_size`: 1000 → 1500 (+50%)
- `chunk_overlap`: 200 → 400 (+100%)
- `top_k`: 3 → 5 (+67%)
- `reranker_initial_k`: 20 → 40 (+100%)
- `reranker_top_k`: 3 → 5 (+67%)

**예상 개선**: +30-50%

### 📚 기준 답변 세트 (Ground Truth)
**파일**: `data/reference_result.json`

이 파일은 **test_documents** 폴더의 실제 PDF 문서들을 바탕으로 생성된 정답 세트입니다:
- **총 56개 질문** (단일 문서 + 합성 질문 포함)
- **카테고리**:
  - MIPS 이론 관련 질문 (5개)
  - 스핀파 동역학 (5개)
  - 3D OPA 기술 (6개)
  - X-ray 단층촬영 (5개)
  - 그래프 이론 (7개)
  - 헤테로틱 플럭스 (6개)
  - 초저온 왜성 (6개)
  - f(T) 중력 (5개)
  - 합성 질문 (8개)

**테스트 방식**:
1. 각 질문을 RAG 시스템에 입력
2. 생성된 답변과 정답 답변 비교
3. 자동/수동 평가 수행

## 🎯 테스트 시나리오

### 실제 테스트 질문 목록 (총 56개)

**reference_result.json**에서 추출된 실제 질문 목록:

#### 1. MIPS 이론 (5개)
```
1. MIPS(운동성 유도 상분리)란 무엇이며, 수동적 시스템의 상분리와의 주요 차이점은 무엇입니까?
2. MIPS 모델에서 화학주성(chemotaxis)은 입자 플럭스(J)에 어떻게 반영되며, 화학주성 Péclet 수($Pe_C$)는 무엇을 나타냅니까?
3. 화학주성이 MIPS를 억제(suppress)할 수 있는 두 가지 기준(criteria)은 무엇입니까?
4. MIPS의 불안정성(instability)을 '유한 파장(Finite-wavelength, F)'과 '무한 파장(Unbounded, U)'으로 분류하는 기준은 무엇입니까?
5. 비-화학주성 MIPS($Pe_C=0$)에서 도메인 크기 R(t)의 거칠어짐(coarsening)은 시간에 따라 어떤 법칙을 따르며, 화학주성이 강해지면 어떻게 변합니까?
```

#### 2. 스핀파 동역학 (5개)
```
6. DC(직류) 마그노닉 결정(magnonic crystal)이 스핀파 스펙트럼에 미치는 영향은 무엇이며, 밴드 갭의 크기는 무엇에 비례합니까?
7. AC(교류) 마그노닉 결정의 공명 조건은 DC의 경우와 어떻게 다르며, 동일 진폭에서 밴드 갭 크기는 어떻게 비교됩니까?
8. 스핀파 동역학을 블로흐 구(Bloch sphere)로 표현할 때, $|k\rangle$ 상태와 $|k-q\rangle$ 상태는 각각 구의 어느 위치에 해당합니까?
9. AC 마그노닉 결정을 사용하여 스핀파 '큐비트'를 조작할 때, $\\pi/2$ 펄스와 $\\pi$ 펄스는 각각 어떤 연산을 수행합니까?
10. 제안된 AC 마그노닉 결정의 '조절 가능성(tunability)'이 스핀파 컴퓨팅의 확장성(scalability) 문제를 어떻게 해결할 수 있습니까?
```

#### 3. 3D OPA 기술 (6개)
```
11. 기존의 단일 도파관 레이어 OPA가 격자 커플러(grating couplers)를 사용할 때 발생하는 주요 문제점은 무엇입니까?
12. 단일 도파관 레이어 OPA에 에지 커플러(end-fire emitters)를 사용할 때 발생하는 '팬빔(fan-beam)' 문제는 무엇입니까?
13. 이 연구에서 제안한 3D OPA의 '$\Omega$-형태' 지연 라인(delay line)은 어떤 원리로 수평 빔 조향(horizontal beam steering)을 가능하게 합니까?
14. 3D OPA 장치에서 1-레이어 샘플과 4-레이어 샘플의 수직 FWHM(반치전폭) 테스트 결과는 각각 몇 도입니까?
15. 3D OPA의 $\Omega$-형태 지연 라인 길이(DL)와 빔 조향 감도($\Delta\delta / \Delta\lambda$) 사이의 관계는 어떻습니까? 60µm 지연 라인 샘플의 측정된 감도는 얼마입니까?
16. 이상적인 다중 레이어 OPA(그림 9)는 어떤 기능을 가지며, 입력 광섬유 요구 사항에 어떤 변화를 가져옵니까?
```

#### 4. X-ray 단층촬영 (5개)
```
17. X-ray 단층 촬영 재구성을 위한 베이지안(Bayesian) 방법에서 '프라이어(prior)'의 역할은 무엇입니까?
18. X-ray 단층 촬영 재구성에서 가우시안(Gaussian) 프라이어와 non-Gaussian 프라이어(TV, Besov, Cauchy)의 주요 차이점은 무엇입니까?
19. X-ray 단층 촬영에서 TV(Total Variation) 프라이어를 사용할 때의 주요 단점은 무엇입니까?
20. Besov 프라이어를 X-ray 단층 촬영에 사용할 때의 단점은 무엇입니까?
21. 이 연구에서 사용된 두 가지 MCMC(Markov chain Monte Carlo) 방법론은 무엇입니까?
22. HMC-NUTS(Hamiltonian Monte Carlo with no-U-turn sampling) 알고리즘은 어떻게 작동합니까?
23. X-ray 단층 촬영 연구에서 통나무(log)와 시추 코어(drill-core) 샘플은 각각 어떤 특성을 대표하기 위해 사용되었습니까?
```

#### 5. 그래프 이론 (7개)
```
24. 그래프의 '색채 대칭 함수(chromatic symmetric function)'란 무엇입니까?
25. 'e-양성(e-positive)'과 '슈어-양성(Schur-positive)'의 관계는 무엇입니까?
26. 그래프 G가 'e-양성(e-positive)'이 아니라는 것을 증명하기 위한 조건 중 하나인 '연결 파티션(connected partition)'과 관련된 정리는 무엇입니까?
27. n-정점 그래프 G가 e-양성이 아님을 증명하는 '매칭(matching)'과 관련된 정리는 무엇입니까?
28. 스파이더(spider) 그래프가 완벽한 매칭(perfect matching)을 가질 필요충분조건은 무엇입니까?
29. n-정점 이분 그래프(bipartite graph)가 슈어-양성(Schur-positive)이 아니기 위한 정점 차수(vertex degree) 조건은 무엇입니까?
30. 그래프의 '안정 파티션(stable partition)'이란 무엇이며, 슈어-양성(Schur-positivity)과 어떤 관계가 있습니까?
```

#### 6. 헤테로틱 플럭스 (6개)
```
31. 헤테로틱 플럭스 진공(Heterotic flux vacua)과 고전적인 $X_0 = M \times T^2$ 컴팩트화의 주요 차이점은 무엇입니까?
32. 8개의 초대칭을 보존하는 헤테로틱 플럭스 진공(heterotic flux vacua)은 모두 $K3 \times T^2$ 컴팩트화와 T-이중성(T-duality) 관계에 있습니까?
33. 헤테로틱 플럭스 진공에서 H-플럭스(H-flux)의 기하학적 의미는 무엇입니까?
34. 이 논문에서 5차원 플럭스 진공($X_{v_0}$)을 토폴로지적으로 자명한 $M \times S^1$ 공간($X_{v_1}$)으로 변환하기 위해 사용된 T-이중성(T-duality) 변환은 구체적으로 무엇입니까?
35. 8개의 초대칭(supercharges)을 보존하는 배경에서 플럭스 양자화(flux quantization) 조건 $\tilde{\pi}_I \cdot v = 0$은 $T^2$ CFT의 합리성(rationality)과 어떤 관련이 있습니까?
36. $N=1$ (4개 초대칭) 헤테로틱 플럭스 진공은 왜 $M \times T^2$ 기하학으로 T-이중화(T-dualized)될 수 없습니까?
```

#### 7. 초저온 왜성 (6개)
```
37. 초저온 왜성(ultracool dwarfs)의 대기 특성을 분석하기 위해 '순방향 모델링(forward-modeling)'을 사용하는 것이 '대기 검색(atmospheric retrieval)' 기술과 비교하여 가지는 장단점은 무엇입니까?
38. 후기 T형 왜성 분석에 사용된 'Starfish' 프레임워크는 전통적인 $\chi^2$ 기반 피팅 방법과 비교하여 불확실성을 어떻게 다루나요?
39. 55개의 후기 T형 왜성을 Sonora-Bobcat 모델로 분석한 결과, 도출된 대기 매개변수들에서 어떤 체계적인 문제점들이 발견되었습니까?
40. 후기 T형 왜성의 분광 분석에서 표면 중력($\log g$)과 금속성($Z$) 사이에 어떤 축퇴(degeneracy)가 발견되었으며, 그 정량적 관계는 무엇입니까?
41. 후기 T형 왜성 분석에서 스펙트럼의 S/N(신호 대 잡음비)이 50 이상일 때, 매개변수 정밀도(parameter precision)가 더 이상 향상되지 않는 이유는 무엇입니까?
42. Sonora-Bobcat 모델이 후기 T형 왜성의 J-밴드($\approx 1.18-1.35 \mu m$) 스펙트럼을 과대예측(over-predict)하는 현상은 어떤 물리적 과정이 모델에서 누락되었음을 시사합니까?
```

#### 8. f(T) 중력 (5개)
```
43. f(T) 중력의 파워-로(power-law) 모델 $f(T) = T + \alpha(-T)^{\beta}$에서, 정규화된 허블 파라미터 $E^2(z)$는 어떻게 표현됩니까?
44. f(T) 중력은 중력파(GW) 전파 방정식에 어떤 수정을 가하며, 이는 GR(일반 상대성 이론)과 어떻게 다릅니까?
45. f(T) 중력 하에서 중력파 광도 거리($d_L^{gw}$)와 전자기파 광도 거리($d_L^{em}$) 사이의 관계식은 무엇입니까?
46. 3세대 중력파 검출기(ET, 2CE)를 이용한 BNS 및 NSBH 시뮬레이션에서, $d_L^{gw}$의 추정 정확도를 높이기 위해 경사각($\iota$)에 어떤 특별한 선택 기준을 적용했습니까?
47. BNS(쌍중성자성) 병합과 NSBH(중성자성-블랙홀) 병합 시뮬레이션에서, EM(전자기파) 대응체의 존재 여부를 판단하는 기준은 각각 무엇입니까?
48. f(T) 중력의 파워-로 모델에서 파라미터 $\beta$는 $d_L^{gw} / d_L^{em}$ 비율에 어떤 영향을 줍니까?
```

#### 9. 합성 질문 (8개) - 다중 문서
```
49. (합성 질문) X-ray 단층 촬영(Sony_OLED_white_paper.pdf)과 초저온 왜성(Organic_LEDs_2021_arX.pdf) 연구에서 사용된 베이지안(Bayesian) 방법론의 공통점과 차이점은 무엇입니까?
50. (합성 질문) 스핀파 동역학(Flexible_OLED_2023_arX.pdf)과 MIPS(OLED_efficiency_2023_arX.pdf) 현상을 설명하는 두 모델에서, 시스템의 안정성(stability) 또는 공명(resonance)을 결정하는 핵심적인 '경쟁(competition)' 관계는 각각 무엇입니까?
51. (합성 질문) 3D OPA(TADF_mechanism_2022_arX.pdf)와 f(T) 중력(OLED_device_2024_arX.pdf)에 관한 두 논문은 각각 기존 기술/이론(단일 레이어 OPA, 일반 상대성 이론)의 한계를 극복하기 위해 어떤 새로운 '수정(modification)'을 제안하고 있습니까?
52. (합성 질문) X-ray 단층 촬영(Sony_OLED_white_paper.pdf)에서 non-Gaussian 프라이어(예: Cauchy)를 사용하는 이유와, 그래프 이론(OLED_materials_2019_arX.pdf)에서 e-양성이 아닌(not e-positive) 그래프를 찾는 기준(예: 완벽한 매칭 부재) 사이의 공통적인 목표는 무엇입니까?
53. (합성 질문) 헤테로틱 플럭스 진공(OLED_modeling_2023_arX.pdf)과 MIPS(OLED_efficiency_2023_arX.pdf) 모델에서, 시스템의 핵심 특성을 정의하는 두 가지 상반되는(competing) 요소를 각각 설명하십시오.
54. (합성 질문) X-ray 단층 촬영(Sony_OLED_white_paper.pdf), 초저온 왜성(Organic_LEDs_2021_arX.pdf), MIPS(OLED_efficiency_2023_arX.pdf) 연구에서, 모델의 한계나 특정 조건으로 인해 발생한 '비물리적이거나(unphysical)' '비현실적인(implausible)' 결과 또는 현상은 각각 무엇입니까?
55. (합성 질문) f(T) 중력(OLED_device_2024_arX.pdf)과 MIPS(OLED_efficiency_2023_arX.pdf) 모델은 기존 이론(GR, 표준 MIPS)에 어떤 새로운 '항(term)'을 추가하여 현상을 설명합니까?
56. (합성 질문) 3D OPA(TADF_mechanism_2022_arX.pdf)의 빔 조향 감도와 헤테로틱 플럭스 진공(OLED_modeling_2023_arX.pdf)의 초대칭 보존은 각각 어떤 핵심 파라미터에 의해 결정됩니까?
```

**평가 기준**:
- ✅ 정확한 답변 제공
- ✅ 문서 출처 명시
- ✅ 관련 정보 누락 없음
- ✅ 여러 청크에서 정보 통합 (합성 질문)
- ✅ 논리적 일관성
- ✅ 완전한 맥락 제공

## 📊 평가 지표

### 1. 정확도 (Accuracy)
```python
# 정답 사전 정의
ground_truth = {
    "질문1": "정답1",
    "질문2": "정답2",
    ...
}

# 자동 평가 또는 수동 평가
accuracy = correct_answers / total_questions
```

**측정 방법**:
- 자동 평가: 키워드 매칭
- 수동 평가: 5점 척도 (0=완전 오답, 5=완벽)

### 2. 응답 시간 (Response Time)
```python
import time

start = time.time()
answer = rag_chain.invoke({"question": query})
elapsed = time.time() - start

print(f"응답 시간: {elapsed:.2f}초")
```

**측정 지표**:
- 평균 응답 시간
- 최대 응답 시간
- P95 응답 시간

### 3. 검색 품질 (Retrieval Quality)
```python
# 검색된 문서의 관련성 평가
retrieval_metrics = {
    "precision@k": ...,
    "recall@k": ...,
    "mrr": ...,  # Mean Reciprocal Rank
    "ndcg": ...  # Normalized Discounted Cumulative Gain
}
```

### 4. 답변 완전성 (Answer Completeness)
- 필수 정보 포함 여부
- 맥락의 충분성
- 관련 정보 누락률

### 5. 출처 명확성 (Source Clarity)
- 문서 출처 제공 여부
- 인용 정확도
- 메타데이터 활용

## 🧪 테스트 구현

### 테스트 스크립트 생성

```python
# tests/performance_test.py
import time
import json
from typing import List, Dict
from config import ConfigManager
from utils.rag_chain import RAGChain
from utils.vector_store import VectorStoreManager

class RAGPerformanceTester:
    def __init__(self):
        config = ConfigManager().get_all()
        vector_manager = VectorStoreManager(
            persist_directory="data/chroma_db",
            embedding_api_type=config.get("embedding_api_type", "ollama"),
            embedding_base_url=config.get("embedding_base_url"),
            embedding_model=config.get("embedding_model"),
        )
        
        self.rag_chain = RAGChain(
            vectorstore=vector_manager.get_vectorstore(),
            llm_api_type=config.get("llm_api_type", "ollama"),
            llm_base_url=config.get("llm_base_url"),
            llm_model=config.get("llm_model"),
            temperature=config.get("temperature", 0.7),
            top_k=config.get("top_k", 3),
            use_reranker=config.get("use_reranker", True),
            reranker_model=config.get("reranker_model"),
            reranker_initial_k=config.get("reranker_initial_k", 20),
            enable_synonym_expansion=config.get("enable_synonym_expansion", True),
            enable_multi_query=config.get("enable_multi_query", True)
        )
    
    def run_single_test(self, question: str) -> Dict:
        """단일 질문 테스트"""
        start_time = time.time()
        
        # 응답 생성
        answer = self.rag_chain.invoke({"question": question})
        
        elapsed_time = time.time() - start_time
        
        return {
            "question": question,
            "answer": answer,
            "response_time": elapsed_time,
            "tokens": self._estimate_tokens(answer),
            "documents_retrieved": len(self.rag_chain._last_retrieved_docs)
        }
    
    def run_batch_test(self, questions: List[str]) -> List[Dict]:
        """배치 테스트"""
        results = []
        for i, question in enumerate(questions, 1):
            print(f"\n테스트 {i}/{len(questions)}: {question}")
            result = self.run_single_test(question)
            results.append(result)
            
            # 통계 출력
            print(f"  응답 시간: {result['response_time']:.2f}초")
            print(f"  검색 문서 수: {result['documents_retrieved']}")
        
        return results
    
    def generate_report(self, results: List[Dict]) -> str:
        """테스트 보고서 생성"""
        avg_time = sum(r['response_time'] for r in results) / len(results)
        max_time = max(r['response_time'] for r in results)
        min_time = min(r['response_time'] for r in results)
        avg_docs = sum(r['documents_retrieved'] for r in results) / len(results)
        
        report = f"""
=== RAG 성능 테스트 보고서 ===

테스트 기간: {time.strftime('%Y-%m-%d %H:%M:%S')}
총 질문 수: {len(results)}

=== 응답 시간 ===
평균: {avg_time:.2f}초
최소: {min_time:.2f}초
최대: {max_time:.2f}초

=== 검색 품질 ===
평균 검색 문서 수: {avg_docs:.1f}개

=== 상세 결과 ===
"""
        for i, result in enumerate(results, 1):
            report += f"""
질문 {i}: {result['question']}
응답 시간: {result['response_time']:.2f}초
검색 문서 수: {result['documents_retrieved']}개
"""
        
        return report
    
    def _estimate_tokens(self, text: str) -> int:
        """토큰 수 추정 (대략적)"""
        return len(text.split()) * 1.3  # 단어 수 * 1.3
    
    def save_results(self, results: List[Dict], filename: str = "test_results.json"):
        """결과를 JSON으로 저장"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {filename}")

# 테스트 실행
if __name__ == "__main__":
    # 기준 답변 세트에서 질문 로드
    from test_with_reference import load_reference_answers
    
    reference_data = load_reference_answers()
    test_questions = [qa['질문'] for qa in reference_data]
    
    print(f"테스트 질문 수: {len(test_questions)}개")
    
    # 테스트 실행
    tester = RAGPerformanceTester()
    results = tester.run_batch_test(test_questions)
    
    # 보고서 생성
    report = tester.generate_report(results)
    print(report)
    
    # 결과 저장
    tester.save_results(results)
```

### 간단한 테스트 스크립트

```python
# quick_test.py
#!/usr/bin/env python
"""빠른 성능 테스트"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
import time

def quick_test():
    print("=" * 60)
    print("RAG 시스템 빠른 성능 테스트")
    print("=" * 60)
    
    # 설정 로드
    config = ConfigManager().get_all()
    print(f"\n[설정 확인]")
    print(f"  LLM: {config['llm_model']}")
    print(f"  임베딩: {config['embedding_model']}")
    print(f"  청크 크기: {config['chunk_size']}")
    print(f"  Top K: {config['top_k']}")
    print(f"  Reranker: {config['use_reranker']} ({config.get('reranker_model', 'N/A')})")
    
    # 초기화
    print(f"\n[시스템 초기화 중...]")
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url"),
        embedding_model=config.get("embedding_model"),
    )
    
    rag_chain = RAGChain(
        vectorstore=vector_manager.get_vectorstore(),
        llm_api_type=config.get("llm_api_type", "ollama"),
        llm_base_url=config.get("llm_base_url"),
        llm_model=config.get("llm_model"),
        temperature=config.get("temperature", 0.7),
        top_k=config.get("top_k", 3),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model"),
        reranker_initial_k=config.get("reranker_initial_k", 20),
        enable_synonym_expansion=config.get("enable_synonym_expansion", True),
        enable_multi_query=config.get("enable_multi_query", True)
    )
    print("  ✓ 초기화 완료")
    
    # 테스트 질문 (간단한 검증용)
    test_questions = [
        "MIPS(운동성 유도 상분리)란 무엇이며, 수동적 시스템의 상분리와의 주요 차이점은 무엇입니까?",
        "DC(직류) 마그노닉 결정(magnonic crystal)이 스핀파 스펙트럼에 미치는 영향은 무엇이며, 밴드 갭의 크기는 무엇에 비례합니까?",
        "X-ray 단층 촬영 재구성을 위한 베이지안(Bayesian) 방법에서 '프라이어(prior)'의 역할은 무엇입니까?",
    ]
    
    # 전체 테스트를 위해서는 test_with_reference.py 사용 권장
    
    print(f"\n[테스트 시작 ({len(test_questions)}개 질문)]")
    print("=" * 60)
    
    results = []
    for i, question in enumerate(test_questions, 1):
        print(f"\n질문 {i}: {question}")
        print("-" * 60)
        
        start = time.time()
        try:
            answer = rag_chain.invoke({"question": question})
            elapsed = time.time() - start
            
            print(f"응답 시간: {elapsed:.2f}초")
            print(f"검색 문서 수: {len(rag_chain._last_retrieved_docs)}개")
            print(f"\n답변:\n{answer[:200]}...")
            
            results.append({
                "question": question,
                "time": elapsed,
                "docs": len(rag_chain._last_retrieved_docs)
            })
        except Exception as e:
            print(f"오류 발생: {e}")
            results.append({
                "question": question,
                "error": str(e)
            })
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("[테스트 결과 요약]")
    print("=" * 60)
    
    if results:
        avg_time = sum(r.get('time', 0) for r in results) / len(results)
        print(f"평균 응답 시간: {avg_time:.2f}초")
        print(f"성공한 질문: {sum(1 for r in results if 'time' in r)}/{len(results)}")

if __name__ == "__main__":
    quick_test()
```

## 📈 베이스라인 비교

### Before (기존 설정)
```json
{
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "top_k": 3,
  "reranker_initial_k": 20,
  "reranker_top_k": 3
}
```

### After (개선 설정)
```json
{
  "chunk_size": 1500,
  "chunk_overlap": 400,
  "top_k": 5,
  "reranker_initial_k": 40,
  "reranker_top_k": 5
}
```

### 예상 차이
- **평균 응답 시간**: 2-3초 → 3-5초 (+1-2초)
- **검색 정확도**: 77% → 85% (+8%)
- **답변 완전성**: 70% → 90% (+20%)
- **복잡 질문 처리**: 60% → 75% (+15%)

## 🎯 테스트 실행 가이드

### 1단계: 환경 준비
```bash
# 가상환경 활성화
.\venv\Scripts\activate

# 필요한 라이브러리 확인
python test_app.py
```

### 2단계: 빠른 테스트
```bash
# 빠른 성능 확인 (3개 샘플 질문)
python quick_test.py
```

### 3단계: 전체 테스트 (56개 질문)
```bash
# reference_result.json 기반 전체 성능 테스트
.\venv\Scripts\python.exe test_with_reference.py
```

또는
```bash
# 상세 성능 테스트 스크립트
python tests/performance_test.py
```

### 4단계: 결과 분석
- `test_results.json` 확인
- 개선도 계산
- 병목 지점 확인

## 📋 체크리스트

### Before 테스트
- [ ] Ollama 실행 중
- [ ] 벡터 DB에 문서 로드됨
- [ ] Reranker 모델 다운로드됨
- [ ] 네트워크 연결 확인

### After 테스트
- [ ] 결과 JSON 저장
- [ ] 응답 시간 측정
- [ ] 정확도 평가
- [ ] 리포트 생성
- [ ] 개발 로그 업데이트

## 🔍 평가 기준

### 정답 판정
1. **완벽한 답변** (5점): 모든 정보 포함, 정확한 출처
2. **매우 좋은 답변** (4점): 핵심 정보 포함, 일부 세부사항 누락
3. **좋은 답변** (3점): 부분적 정보, 맥락 부족
4. **보통 답변** (2점): 관련 있으나 불완전
5. **나쁜 답변** (1점): 부정확하거나 관련 없음
6. **완전 오답** (0점): 전혀 관련 없음

### 성공 기준
- **평균 점수**: 3.5점 이상
- **응답 시간**: 5초 이내 (평균)
- **성공률**: 80% 이상
- **개선도**: 최소 10% 향상

## 📊 결과 보고서 템플릿

```
=== RAG 성능 테스트 보고서 ===

날짜: 2025-01-14
설정: Phase 1 최적화 적용

=== 설정 ===
- 청크 크기: 1500 (기존 1000)
- 오버랩: 400 (기존 200)
- Top K: 5 (기존 3)
- Reranker Initial K: 40 (기존 20)

=== 성능 지표 ===
응답 시간:
  - 평균: X.XX초 (기존 Y.YY초)
  - 개선: +/-X%

검색 정확도:
  - 현재: XX% (기존 YY%)
  - 개선: +ZZ%

답변 품질:
  - 평균 점수: X.X/5.0 (기존 Y.Y/5.0)
  - 개선: +AA%

=== 주요 발견 ===
1. [발견 1]
2. [발견 2]
3. [발견 3]

=== 결론 ===
[요약 및 다음 단계]
```

---

**작성일**: 2025-01-14  
**상태**: 준비 완료  
**다음 단계**: `quick_test.py` 실행으로 성능 확인 시작

