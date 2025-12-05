"""
질문 분류기 (Question Classifier)

규칙 기반 + LLM 하이브리드 방식으로 질문 유형을 분류하고
최적화 파라미터를 반환합니다.

질문 유형:
- simple: 단순 사실 질문 (예: "값은?", "얼마?")
- normal: 일반 질문 (예: "효율은?", "어떻게?")
- complex: 복잡한 질문 (예: 비교, 분석)
- exhaustive: 포괄적 질문 (예: "모든", "전체")
"""

import re
import json
from typing import Dict, Optional, Tuple
from langchain_core.language_models import BaseChatModel


class QuestionClassifier:
    """하이브리드 질문 분류기 (규칙 + LLM)"""

    # 신뢰도 임계값
    HIGH_CONFIDENCE_THRESHOLD = 0.8   # 이상이면 LLM 불필요
    LOW_CONFIDENCE_THRESHOLD = 0.5    # 미만이면 LLM 필수

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        use_llm_fallback: bool = True,
        verbose: bool = False,
        llm_timeout: float = 5.0  # LLM 호출 타임아웃 (초)
    ):
        """
        Args:
            llm: LLM 모델 (None이면 규칙만 사용)
            use_llm_fallback: LLM 사용 여부 (LLM 우선 방식)
            verbose: 상세 로그 출력
            llm_timeout: LLM 호출 타임아웃 (초)
        """
        self.llm = llm
        self.use_llm_fallback = use_llm_fallback and (llm is not None)
        self.verbose = verbose
        self.llm_timeout = llm_timeout

        # 통계 (성능 모니터링용)
        self.stats = {
            "total": 0,
            "llm_success": 0,      # LLM 성공
            "llm_failed": 0,        # LLM 실패 (폴백)
            "rule_only": 0,         # 규칙만 사용 (LLM 비활성화)
        }

    def classify(self, question: str) -> Dict:
        """
        질문을 분류하고 최적화 파라미터 반환
        
        LLM 우선 방식: 먼저 LLM으로 분류 시도, 오류 발생 시 규칙 기반으로 폴백

        Args:
            question: 사용자 질문

        Returns:
            dict: {
                "type": "simple|normal|complex|exhaustive",
                "confidence": 0.0-1.0,
                "method": "llm|rule",
                "multi_query": bool,
                "max_results": int,
                "reranker_k": int,
                "max_tokens": int,
                "reasoning": str
            }
        """
        self.stats["total"] += 1

        # Stage 1: LLM 우선 시도
        if self.llm and self.use_llm_fallback:
            try:
                print(f"[QuestionClassifier] LLM 우선 분류 시도: \"{question[:50]}...\"")
                
                # LLM으로 분류 시도
                llm_result = self._classify_by_llm(question, timeout=self.llm_timeout)
                
                # LLM 결과가 유효한지 검증
                if llm_result and llm_result.get("type") in ["simple", "normal", "complex", "exhaustive"]:
                    self.stats["llm_success"] += 1
                    final_result = self._finalize_result(llm_result, method="llm")
                    
                    # LLM 결과 상세 출력
                    print(f"[QuestionClassifier] ✓ LLM 분류 성공")
                    print(f"  → 유형: {final_result['type']}")
                    print(f"  → 신뢰도: {final_result.get('confidence', 0.8):.1%}")
                    print(f"  → 이유: {final_result.get('reasoning', 'N/A')}")
                    print(f"  → Multi-Query: {final_result.get('multi_query', False)}")
                    print(f"  → Max Results: {final_result.get('max_results', 0)}")
                    print(f"  → Max Tokens: {final_result.get('max_tokens', 0)}")
                    
                    return final_result
                else:
                    # LLM 결과가 유효하지 않음 → 규칙으로 폴백
                    print(f"[QuestionClassifier] ✗ LLM 결과 무효, 규칙으로 폴백")
                    raise ValueError("Invalid LLM result")
                    
            except (TimeoutError, json.JSONDecodeError, ValueError, Exception) as e:
                # 타임아웃, JSON 파싱 실패, 기타 오류 → 규칙 기반으로 폴백
                self.stats["llm_failed"] += 1
                error_type = type(e).__name__
                print(f"[QuestionClassifier] ✗ LLM 오류 ({error_type}): {str(e)[:100]}")
                print(f"[QuestionClassifier] → 규칙 기반으로 폴백")
                # 폴백: 규칙 기반 분류 계속 진행
        
        # Stage 2: 규칙 기반 분류 (LLM 실패 또는 LLM 비활성화)
        rule_result = self._classify_by_rules(question)
        final_result = self._finalize_result(rule_result, method="rule")
        
        # 규칙 기반 결과 출력
        print(f"[QuestionClassifier] 규칙 기반 분류")
        print(f"  → 유형: {final_result['type']}")
        print(f"  → 신뢰도: {final_result.get('confidence', 0.6):.1%}")
        print(f"  → 이유: {final_result.get('reasoning', 'N/A')}")
        print(f"  → Multi-Query: {final_result.get('multi_query', False)}")
        print(f"  → Max Results: {final_result.get('max_results', 0)}")
        
        self.stats["rule_only"] += 1
        return final_result

    def _classify_by_rules(self, question: str) -> Dict:
        """규칙 기반 분류"""

        # Priority 1: Exhaustive (가장 명확)
        exhaustive_result = self._check_exhaustive(question)
        if exhaustive_result:
            return exhaustive_result

        # Priority 2: Complex (가장 명확하게 구분 가능)
        complex_score, complex_reasons = self._calculate_complex_score(question)
        if complex_score >= 0.5:  # 0.6 → 0.5로 완화 (Option 3)
            return {
                "type": "complex",
                "confidence": complex_score,
                "reasoning": f"Complex indicators: {', '.join(complex_reasons)}"
            }

        # Priority 2.5: 정의 질문 패턴 체크 (Normal 우선)
        # "OLED는 무엇인가?", "TADF는 무엇이?" 같은 정의 질문
        definition_patterns = [
            r"[은는이가]\s*무엇[인가이]",  # ~는 무엇인가?, ~는 무엇이?
            r"[이란는]\s*무엇",            # ~란 무엇, ~는 무엇
            r"[은는]\s*뭐",                # ~는 뭐야?, ~는 뭔가?
        ]
        for pattern in definition_patterns:
            if re.search(pattern, question):
                return {
                    "type": "normal",
                    "confidence": 0.8,
                    "reasoning": "Definition question pattern (정의 질문)"
                }

        # Priority 3: Normal 체크 (Simple과 구분)
        normal_keywords = [
            "원리", "메커니즘", "과정", "방법", "이유", "의미",
            "정의", "개념", "특성", "특징", "구조", "작동",
            "측정", "제작", "합성", "공정", "설명", "어떻게",
            "왜", "어떤", "장점", "단점", "한계", "목적"
        ]

        has_normal_keyword = any(kw in question for kw in normal_keywords)

        # Priority 4: Simple (단순 값/수치 질문)
        simple_score, simple_reasons = self._calculate_simple_score(question)

        # Simple과 Normal 구분
        if simple_score >= 0.7:
            # Simple 패턴이지만 Normal 키워드가 있으면 Normal
            if has_normal_keyword:
                return {
                    "type": "normal",
                    "confidence": 0.7,
                    "reasoning": f"Normal keywords detected: {[kw for kw in normal_keywords if kw in question]}"
                }
            else:
                return {
                    "type": "simple",
                    "confidence": simple_score,
                    "reasoning": f"Simple indicators: {', '.join(simple_reasons)}"
                }

        # Priority 5: Normal (기본값)
        # Normal 키워드가 있거나, Simple/Complex 모두 아님
        if has_normal_keyword:
            return {
                "type": "normal",
                "confidence": 0.6,
                "reasoning": f"Normal keywords: {[kw for kw in normal_keywords if kw in question]}"
            }
        else:
            # 애매한 경우 (LLM 후보)
            confidence = 0.4  # 낮은 신뢰도 → LLM 호출 유도
            return {
                "type": "normal",
                "confidence": confidence,
                "reasoning": "No strong indicators (default to normal, consider LLM)"
            }

    def _check_exhaustive(self, question: str) -> Optional[Dict]:
        """Exhaustive 질문 감지 (명확한 키워드 기반)"""

        # 고신뢰도 키워드 (완전 일치)
        high_confidence_keywords = [
            "모든", "전체", "모두", "각각",
            "전부", "모든페이지", "모든슬라이드",
            "전체페이지", "전체슬라이드"
        ]

        for keyword in high_confidence_keywords:
            if keyword in question:
                return {
                    "type": "exhaustive",
                    "confidence": 1.0,
                    "reasoning": f"Exhaustive keyword detected: '{keyword}'"
                }

        # 중신뢰도 패턴
        medium_patterns = [
            (r"나열\s*(해|하)", "나열 요청"),
            (r"리스트\s*(업|로|화)", "리스트 요청"),
            (r"목록\s*(을|으로|화)", "목록 요청"),
        ]

        for pattern, description in medium_patterns:
            if re.search(pattern, question):
                return {
                    "type": "exhaustive",
                    "confidence": 0.85,
                    "reasoning": f"Exhaustive pattern: {description}"
                }

        return None

    def _calculate_simple_score(self, question: str) -> Tuple[float, list]:
        """Simple 점수 계산"""
        score = 0.0
        reasons = []

        # Indicator 1: 짧은 길이 (+0.3)
        if len(question) < 20:
            score += 0.3
            reasons.append("short length (<20 chars)")

        # Indicator 2: 단순 패턴들 (각 +0.3, 가중치 증가)
        simple_patterns = [
            (r"값[은는이가]", "value query (값은/는/이/가)"),
            (r"얼마[인가나는]", "how much (얼마)"),
            # (r"무엇[인가이]", "what is (무엇)"),  # 제거: 정의 질문은 Normal (Priority 2.5에서 처리)
            (r"\d+\s*(페이지|슬라이드|장)", "specific page/slide number"),

            # 추가: 명사 + 은/는 패턴 (Simple의 핵심 패턴!)
            (r"^[가-힣A-Za-z0-9]+[은는]\?$", "noun + 은/는?"),
            (r"^[가-힣A-Za-z0-9\s]{2,15}[은는]\?$", "simple noun question"),
        ]

        for pattern, description in simple_patterns:
            if re.search(pattern, question):
                score += 0.3
                reasons.append(description)

        # Indicator 3: 특정 용어 직접 언급 (+0.2)
        specific_terms = ["kFRET", "EQE", "IQE", "수명", "PLQY", "CRI", "cd/A", "V", "mA"]
        if any(term in question for term in specific_terms):
            # 단, "비교"나 "분석"과 함께 나오면 제외
            if not any(kw in question for kw in ["비교", "분석", "차이", "관계", "영향"]):
                score += 0.2
                reasons.append("specific technical term")

        # Indicator 4: 물음표 하나만 (+0.15)
        if question.count("?") == 1:
            score += 0.15
            reasons.append("single question mark")

        # Indicator 5: 단순 용어 질문 패턴 (+0.25)
        # "효율은?", "파장은?", "농도는?" 등
        simple_noun_patterns = [
            "효율", "파장", "전압", "전류", "온도", "농도", "두께",
            "밀도", "굴절률", "투과율", "반사율", "흡광도", "양자효율",
            "색좌표", "발광", "피크", "반치폭"
        ]

        # 단순 명사 + 조사 형태 확인
        for noun in simple_noun_patterns:
            if re.search(rf"{noun}[은는이가]?\?$", question):
                if len(question) < 25:  # 짧은 질문일 때만
                    score += 0.25
                    reasons.append(f"simple noun question ({noun})")
                    break

        return min(1.0, score), reasons

    def _calculate_complex_score(self, question: str) -> Tuple[float, list]:
        """Complex 점수 계산"""
        score = 0.0
        reasons = []

        # Indicator 1: 복잡 키워드들 (각 +0.3)
        complex_keywords = {
            "비교": "comparison",
            "차이": "difference",
            "분석": "analysis",
            "평가": "evaluation",  # Option 3: 이미 있음
            "관계": "relationship",
            "영향": "influence",
            "원인": "cause",
            "이유": "reason",
            # Option 3: 추가 키워드
            "상관관계": "correlation",
            "상관성": "correlation",
            "트레이드오프": "tradeoff",
            "장단점": "pros and cons",
            "상호작용": "interaction",
            "종합": "synthesis",
            "검토": "review",
            "고찰": "discussion",
        }

        for keyword, description in complex_keywords.items():
            if keyword in question:
                score += 0.3
                reasons.append(f"{description} ({keyword})")

        # Indicator 2: 다중 항목 패턴 (+0.4)
        multi_item_patterns = [
            (r"[와과]\s*[^\s]{2,10}\s*[를을]?\s*(비교|차이)", "A와 B 비교"),
            (r"[,]\s*[^\s]{2,10}\s*[를을]?\s*(비교|분석)", "A, B 분석"),
            (r"(\w+)[와과]\s*(\w+)[의]?\s*(공통|차이)", "A와 B의 공통/차이"),
            # Option 3: 추가 패턴
            (r"[와과]\s*[^\s]{2,10}\s*.*(관계|영향|상관)", "A와 B 관계/영향"),
            (r"[에]?\s*미치는\s*영향", "~에 미치는 영향"),
            (r"[과와]\s*[^\s]{2,10}\s*.*(장단점|트레이드오프)", "A와 B 장단점"),
        ]

        for pattern, description in multi_item_patterns:
            if re.search(pattern, question):
                score += 0.4
                reasons.append(description)
                break  # 하나만 카운트

        # Indicator 3: 긴 질문 (+0.2)
        if len(question) > 50:
            score += 0.2
            reasons.append("long question (>50 chars)")

        # Indicator 4: 다중 질문 부호 (+0.25)
        if question.count("?") > 1:
            score += 0.25
            reasons.append("multiple questions")

        # Indicator 5: 연결어 (+0.15)
        connectors = ["그리고", "또한", "또", "및", "그리고나서"]
        if any(conn in question for conn in connectors):
            score += 0.15
            reasons.append("connectors found")

        return min(1.0, score), reasons

    def _classify_by_llm(
        self,
        question: str,
        rule_hint: Optional[Dict] = None,
        timeout: float = 5.0
    ) -> Dict:
        """LLM 기반 분류 (타임아웃 지원)"""

        if self.llm is None:
            raise ValueError("LLM이 설정되지 않았습니다")

        # 프롬프트 구성
        hint_text = ""
        if rule_hint:
            hint_text = f"""
참고: 규칙 기반 분석 결과
- 예상 유형: {rule_hint['type']}
- 신뢰도: {rule_hint['confidence']:.0%}
- 이유: {rule_hint['reasoning']}

위 결과를 참고하되, 더 정확하게 재분류하세요.
"""

        prompt = f"""다음 질문을 정확하게 분류하세요:

질문: "{question}"
{hint_text}

분류 기준:
1. **simple** (단순 사실 질문)
   - 특정 값, 숫자, 이름을 묻는 질문
   - 저자, 작성자, author 등의 키워드가 있으면 simple로 분류
   - 1-2 문장으로 답변 가능
   - 예: "kFRET 값은?", "3페이지 요약", "얼마인가?", "duan lian 저자 찾아줘"

2. **normal** (일반 질문)
   - 설명이 필요한 질문
   - 2-3 문단 답변 필요
   - 약간의 모호함 포함 가능
   - 예: "OLED 효율은?", "작동 원리는?"

3. **complex** (복잡한 질문)
   - 비교, 분석, 평가 요청
   - 다중 항목 또는 다중 관점
   - 긴 답변 필요 (4+ 문단)
   - 예: "A와 B를 비교", "영향 분석"

4. **exhaustive** (포괄적 질문)
   - "모든", "전체", "각각" 등의 전수 조사
   - 리스트/목록 형태 답변
   - 예: "모든 슬라이드 제목", "전체 논문 찾아줘"

추가 분석:
- ambiguity: 질문의 모호함 정도 (0.0=명확, 1.0=매우 모호)
- multi_query_helpful: Multi-Query 생성이 도움될까? (true/false)

**JSON 형식으로만 출력** (다른 텍스트 없이):
{{
    "type": "simple",
    "confidence": 0.95,
    "reasoning": "특정 값을 묻는 단순 질문",
    "ambiguity": 0.1,
    "multi_query_helpful": false
}}"""

        try:
            import threading
            
            # 타임아웃 처리를 위한 래퍼
            result_container = {"result": None, "error": None}
            
            def llm_call():
                try:
                    response = self.llm.invoke(prompt)
                    result_container["result"] = response
                except Exception as e:
                    result_container["error"] = e
            
            # 별도 스레드에서 LLM 호출
            thread = threading.Thread(target=llm_call)
            thread.daemon = True
            thread.start()
            thread.join(timeout=timeout)
            
            if thread.is_alive():
                # 타임아웃 발생
                raise TimeoutError(f"LLM 호출이 {timeout}초를 초과했습니다")
            
            if result_container["error"]:
                raise result_container["error"]
            
            if result_container["result"] is None:
                raise ValueError("LLM 응답이 없습니다")
            
            # 응답에서 JSON 추출
            response = result_container["result"]
            content = response.content if hasattr(response, 'content') else str(response)

            # JSON 파싱 (여러 형식 시도)
            result = self._parse_llm_response(content)

            if self.verbose:
                print(f"[LLM 응답] {result}")

            return result

        except TimeoutError as e:
            if self.verbose:
                print(f"[LLM 타임아웃] {e}")
            raise  # 타임아웃은 상위로 전파
        
        except (json.JSONDecodeError, ValueError) as e:
            if self.verbose:
                print(f"[LLM 파싱 오류] {e}")
            raise  # 파싱 오류는 상위로 전파
        
        except Exception as e:
            if self.verbose:
                print(f"[LLM 오류] {e}")
            raise  # 기타 오류는 상위로 전파

    def _parse_llm_response(self, content: str) -> Dict:
        """LLM 응답 파싱 (여러 형식 지원)"""

        # 1. 순수 JSON 시도
        try:
            return json.loads(content)
        except:
            pass

        # 2. JSON 코드 블록 추출 시도
        json_pattern = r'```json\s*(\{.*?\})\s*```'
        match = re.search(json_pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass

        # 3. 중괄호 부분만 추출 시도
        brace_pattern = r'\{[^}]+\}'
        match = re.search(brace_pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass

        # 4. 파싱 실패
        raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {content[:200]}")

    def _combine_results(self, rule_result: Dict, llm_result: Dict) -> Dict:
        """규칙과 LLM 결과 조합 (가중 평균)"""

        rule_weight = rule_result['confidence']
        llm_weight = llm_result.get('confidence', 0.8)

        # LLM 신뢰도가 높으면 LLM 우선
        if llm_weight > 0.8:
            return {
                **llm_result,
                "reasoning": f"LLM (confident): {llm_result.get('reasoning', '')}"
            }

        # 규칙 신뢰도가 높으면 규칙 우선
        if rule_weight > 0.8:
            return {
                **rule_result,
                "reasoning": f"Rule (confident): {rule_result['reasoning']}"
            }

        # 둘 다 애매하면 LLM 우선 (더 정교함)
        return {
            **llm_result,
            "reasoning": f"LLM+Rule hybrid: {llm_result.get('reasoning', '')}"
        }

    def _finalize_result(self, result: Dict, method: str) -> Dict:
        """최종 결과 구성 (최적화 파라미터 추가)"""

        question_type = result["type"]

        # 유형별 최적화 파라미터 (llama4-scout 기준 토큰 대폭 상향 조정 + 문서 수 최적화)
        params = {
            "simple": {
                "multi_query": False,
                "max_results": 8,  # 10 → 8 (Lost-in-the-Middle 완화)
                "reranker_k": 30,
                "max_tokens": 20480,  # 4096 × 5 (llama4-scout 128K context: 단순 질문)
            },
            "normal": {
                "multi_query": False,
                "max_results": 12,  # 20 → 12 (업계 표준)
                "reranker_k": 60,
                "max_tokens": 40960,  # 8192 × 5 (llama4-scout 128K context: 일반 질문)
            },
            "complex": {
                "multi_query": True,
                "max_results": 15,  # 30 → 15 (품질 우선)
                "reranker_k": 80,
                "max_tokens": 61440,  # 12288 × 5 (llama4-scout 128K context: 복잡한 질문)
            },
            "exhaustive": {
                "multi_query": False,
                "max_results": 30,  # 100 → 30 (대폭 감소, 실용성 중심)
                "reranker_k": 150,
                "max_tokens": 81920,  # 16384 × 5 (llama4-scout 128K context: 전체 조회, 최대한 긴 답변)
            }
        }

        # LLM의 추가 판단 반영
        if "multi_query_helpful" in result:
            params[question_type]["multi_query"] = result["multi_query_helpful"]

        return {
            **result,
            **params[question_type],
            "method": method,
        }

    def print_stats(self):
        """통계 출력 (성능 모니터링)"""
        total = self.stats["total"]
        if total == 0:
            print("아직 분류 기록이 없습니다.")
            return

        llm_success = self.stats.get("llm_success", 0)
        llm_failed = self.stats.get("llm_failed", 0)
        rule_only = self.stats.get("rule_only", 0)
        
        llm_success_pct = (llm_success / total * 100) if total > 0 else 0
        llm_failed_pct = (llm_failed / total * 100) if total > 0 else 0
        rule_only_pct = (rule_only / total * 100) if total > 0 else 0

        print(f"\n=== 질문 분류기 통계 (LLM 우선 방식) ===")
        print(f"총 질문 수: {total}")
        print(f"LLM 성공: {llm_success} ({llm_success_pct:.1f}%)")
        print(f"LLM 실패 (폴백): {llm_failed} ({llm_failed_pct:.1f}%)")
        print(f"규칙만 사용: {rule_only} ({rule_only_pct:.1f}%)")
        print(f"LLM 성공률: {llm_success_pct:.1f}%")


# ============ 편의 함수 ============

def create_classifier(llm=None, use_llm: bool = True, verbose: bool = False, llm_timeout: float = 5.0):
    """
    분류기 생성 편의 함수

    Args:
        llm: LLM 모델 (None이면 규칙만 사용)
        use_llm: LLM 사용 여부 (LLM 우선 방식)
        verbose: 상세 로그
        llm_timeout: LLM 호출 타임아웃 (초)

    Returns:
        QuestionClassifier 인스턴스
    """
    return QuestionClassifier(
        llm=llm,
        use_llm_fallback=use_llm,
        verbose=verbose,
        llm_timeout=llm_timeout
    )


# ============ 테스트 코드 ============

if __name__ == "__main__":
    # 테스트 (규칙만 사용)
    print("=" * 60)
    print("규칙 기반 분류기 테스트")
    print("=" * 60)

    classifier = QuestionClassifier(llm=None, use_llm_fallback=False, verbose=True)

    test_cases = [
        "kFRET 값은?",
        "3페이지 내용 요약해줘",
        "OLED 효율은?",
        "OLED의 발광 원리를 설명해줘",
        "OLED와 QLED의 효율과 수명을 비교 분석해줘",
        "모든 슬라이드의 제목을 나열해줘",
        "제품의 장단점은?",
    ]

    for question in test_cases:
        print(f"\n질문: {question}")
        result = classifier.classify(question)
        print(f"  → 유형: {result['type']} (신뢰도: {result['confidence']:.0%})")
        print(f"  → Multi-Query: {result['multi_query']}")
        print(f"  → Max Results: {result['max_results']}")
        print(f"  → Max Tokens: {result['max_tokens']}")
        print(f"  → 이유: {result['reasoning']}")

    classifier.print_stats()
