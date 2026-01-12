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
import os
import pickle
import hashlib
import numpy as np
from typing import Dict, Optional, Tuple
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings


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
        llm_timeout: float = 10.0,  # LLM 호출 타임아웃 (초)
        embeddings: Optional[Embeddings] = None  # Semantic Router용 임베딩 모델
    ):
        """
        Args:
            llm: LLM 모델 (None이면 규칙만 사용)
            use_llm_fallback: LLM 사용 여부 (LLM 우선 방식)
            verbose: 상세 로그 출력
            llm_timeout: LLM 호출 타임아웃 (초)
            embeddings: 임베딩 모델 (None이면 Semantic Router 비활성화)
        """
        self.llm = llm
        self.use_llm_fallback = use_llm_fallback and (llm is not None)
        self.verbose = verbose
        self.llm_timeout = llm_timeout
        self.embeddings = embeddings

        # 통계 (성능 모니터링용)
        self.stats = {
            "total": 0,
            "llm_success": 0,      # LLM 성공
            "llm_failed": 0,        # LLM 실패 (폴백)
            "rule_only": 0,         # 규칙만 사용 (LLM 비활성화)
            "semantic_router": 0,   # Semantic Router 사용
            "translation_fasttrack": 0,  # 번역 Fast-Track 사용
        }

        # Semantic Router 초기화
        self.category_embeddings = None
        self.category_examples = None
        if self.embeddings:
            try:
                self._init_semantic_router()
            except Exception as e:
                print(f"[QuestionClassifier] Semantic Router 초기화 실패: {e}, LLM 폴백 사용")
                self.embeddings = None

    def classify(self, question: str) -> Dict:
        """
        질문을 분류하고 최적화 파라미터 반환
        
        하이브리드 분류: Regex Fast-Track → Semantic Router → LLM Fallback

        Args:
            question: 사용자 질문

        Returns:
            dict: {
                "type": "simple|normal|complex|exhaustive",
                "detailed_type": "simple_fact|normal_definition|...",  # 10개 세분화 유형
                "confidence": 0.0-1.0,
                "method": "regex_fast_track|semantic_router|llm|rule",
                "multi_query": bool,
                "max_results": int,
                "reranker_k": int,
                "max_tokens": int,
                "reasoning": str
            }
        """
        self.stats["total"] += 1

        # Step 1: 번역 Fast-Track (Regex 기반, 가장 빠름)
        translation_type = self._check_translation_regex(question)
        if translation_type:
            self.stats["translation_fasttrack"] += 1
            result = {
                "type": "normal",
                "detailed_type": translation_type,
                "confidence": 1.0,
                "method": "regex_fast_track",
                "reasoning": "번역 질문 감지 (Regex)"
            }
            return self._finalize_result(result, method="regex_fast_track")

        # Step 2: Semantic Router (임베딩 기반, 빠름)
        if self.category_embeddings:
            try:
                semantic_result = self._classify_by_semantic_router(question)
                if semantic_result and semantic_result.get('confidence', 0) >= 0.75:
                    self.stats["semantic_router"] += 1
                    return self._finalize_result(semantic_result, method="semantic_router")
            except Exception as e:
                print(f"[QuestionClassifier] Semantic Router 실패: {e}, LLM 폴백")

        # Step 3: LLM Fallback (계층적 라우팅)
        if self.llm and self.use_llm_fallback:
            try:
                hierarchical_result = self._classify_hierarchical(question)
                if hierarchical_result:
                    return self._finalize_result(hierarchical_result, method="hierarchical")
            except Exception as e:
                print(f"[QuestionClassifier] 계층적 라우팅 실패: {e}, 기존 LLM 방식으로 폴백")
        
        # Step 4: 기존 LLM 방식 (폴백)
        if self.llm and self.use_llm_fallback:
            try:
                print(f"[QuestionClassifier] LLM 우선 분류 시도: \"{question[:50]}...\"")
                
                # LLM으로 분류 시도
                llm_result = self._classify_by_llm(question, timeout=self.llm_timeout)
                
                # LLM 결과가 유효한지 검증
                if llm_result and llm_result.get("type") in ["simple", "normal", "complex", "exhaustive"]:
                    self.stats["llm_success"] += 1
                    
                    # Phase 2: 하이브리드 검증 - LLM이 normal로 분류했지만 규칙 기반 점수가 높은 경우 재검증
                    if llm_result.get('type') == 'normal':
                        complex_score, complex_reasons = self._calculate_complex_score(question)
                        if complex_score >= 0.5:  # 규칙 기반 점수가 높으면 complex로 재분류
                            llm_result['type'] = 'complex'
                            llm_result['confidence'] = max(llm_result.get('confidence', 0.8), complex_score)
                            original_reasoning = llm_result.get('reasoning', '')
                            llm_result['reasoning'] = f"LLM: {original_reasoning}, Rule-based override: {', '.join(complex_reasons)} (score: {complex_score:.2f})"
                            print(f"[QuestionClassifier] 하이브리드 검증: LLM normal → complex로 재분류 (규칙 기반 점수: {complex_score:.2f})")
                    
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
    
    # ============ Semantic Router ============
    
    def _init_semantic_router(self):
        """Semantic Router 초기화 (임베딩 로드/계산)"""
        try:
            # 카테고리 예시 로드
            self.category_examples = self._load_category_examples()
            
            # 임베딩 로드 또는 계산
            self.category_embeddings = self._load_or_compute_category_embeddings()
            
            print(f"[SemanticRouter] 초기화 완료: {len(self.category_examples)}개 카테고리")
        except Exception as e:
            print(f"[SemanticRouter] 초기화 실패: {e}")
            self.category_embeddings = None
            self.category_examples = None
    
    def _load_category_examples(self) -> Dict[str, list]:
        """카테고리별 대표 질문 예시 로드"""
        examples_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "utils", "data", "router_examples.json"
        )
        
        # 상대 경로로도 시도
        if not os.path.exists(examples_path):
            examples_path = os.path.join("utils", "data", "router_examples.json")
        
        if not os.path.exists(examples_path):
            raise FileNotFoundError(f"카테고리 예시 파일을 찾을 수 없습니다: {examples_path}")
        
        with open(examples_path, 'r', encoding='utf-8') as f:
            examples = json.load(f)
        
        return examples
    
    def _get_model_hash(self) -> str:
        """임베딩 모델 고유 해시 생성"""
        try:
            # 임베딩 모델 정보 추출
            model_info = {
                "type": self.embeddings.__class__.__name__,
                "model": getattr(self.embeddings, 'model', 'unknown'),
                "base_url": getattr(self.embeddings, 'base_url', 'unknown'),
            }
            
            # 해시 생성
            hash_str = json.dumps(model_info, sort_keys=True)
            model_hash = hashlib.md5(hash_str.encode()).hexdigest()[:8]
            return model_hash
        except Exception as e:
            print(f"[SemanticRouter] 모델 해시 생성 실패: {e}")
            return "unknown"
    
    def _get_cache_path(self) -> str:
        """캐시 파일 경로 생성"""
        model_hash = self._get_model_hash()
        cache_dir = os.path.join("utils", "data")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"router_embeddings_{model_hash}.pkl")
    
    def _get_embedding_dimension(self) -> int:
        """현재 임베딩 모델의 차원 확인"""
        try:
            # 테스트 임베딩 생성
            test_text = "test"
            test_embedding = self.embeddings.embed_query(test_text)
            return len(test_embedding)
        except Exception as e:
            print(f"[SemanticRouter] 차원 확인 실패: {e}")
            return 0
    
    def _validate_cache_file(self, cache_path: str, current_dimension: int) -> bool:
        """캐시 파일 검증 (파일 존재, 로드 가능, 차원 일치)"""
        try:
            if not os.path.exists(cache_path):
                return False
            
            with open(cache_path, 'rb') as f:
                cache_data = pickle.load(f)
            
            # 차원 불일치 체크
            cached_dimension = cache_data.get('dimension')
            if cached_dimension != current_dimension:
                print(f"[SemanticRouter] 차원 불일치 감지: 캐시={cached_dimension}, 현재={current_dimension}")
                return False
            
            # 모델 해시 일치 확인
            cached_hash = cache_data.get('model_hash')
            current_hash = self._get_model_hash()
            if cached_hash != current_hash:
                print(f"[SemanticRouter] 모델 해시 불일치: 캐시={cached_hash}, 현재={current_hash}")
                return False
            
            return True
        except Exception as e:
            print(f"[SemanticRouter] 캐시 검증 실패: {e}")
            return False
    
    def _load_or_compute_category_embeddings(self) -> Dict[str, np.ndarray]:
        """캐시 로드 또는 임베딩 계산"""
        cache_path = self._get_cache_path()
        current_dimension = self._get_embedding_dimension()
        
        # 캐시 검증
        if self._validate_cache_file(cache_path, current_dimension):
            print(f"[SemanticRouter] 캐시에서 임베딩 로드 중...")
            try:
                with open(cache_path, 'rb') as f:
                    cache_data = pickle.load(f)
                print(f"[SemanticRouter] 캐시 로드 완료")
                return cache_data.get('embeddings', {})
            except Exception as e:
                print(f"[SemanticRouter] 캐시 로드 실패: {e}, 재계산")
        
        # 캐시 없거나 검증 실패 시 계산
        print(f"[SemanticRouter] 임베딩 계산 중... (최초 1회)")
        embeddings = self._compute_category_embeddings()
        
        # 캐시 저장
        try:
            cache_data = {
                "embeddings": embeddings,
                "dimension": current_dimension,
                "model_hash": self._get_model_hash()
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            print(f"[SemanticRouter] 임베딩 계산 완료 및 캐시 저장")
        except Exception as e:
            print(f"[SemanticRouter] 캐시 저장 실패: {e}")
        
        return embeddings
    
    def _compute_category_embeddings(self) -> Dict[str, np.ndarray]:
        """카테고리별 임베딩 계산"""
        embeddings = {}
        
        for category, examples in self.category_examples.items():
            try:
                # 각 카테고리의 예시들을 임베딩
                example_embeddings = self.embeddings.embed_documents(examples)
                # 카테고리별 평균 임베딩 계산
                category_embedding = np.mean(example_embeddings, axis=0)
                embeddings[category] = category_embedding
            except Exception as e:
                print(f"[SemanticRouter] 카테고리 '{category}' 임베딩 계산 실패: {e}")
                continue
        
        return embeddings
    
    def _classify_by_semantic_router(self, question: str) -> Optional[Dict]:
        """임베딩 유사도 + 키워드 소프트 부스팅 기반 분류"""
        if not self.category_embeddings:
            return None
        
        try:
            # 질문 임베딩 생성
            question_embedding = np.array(self.embeddings.embed_query(question))
            
            # 각 카테고리와의 코사인 유사도 계산
            similarities = {}
            for category, category_embedding in self.category_embeddings.items():
                dot_product = np.dot(question_embedding, category_embedding)
                norm_question = np.linalg.norm(question_embedding)
                norm_category = np.linalg.norm(category_embedding)
                
                if norm_question > 0 and norm_category > 0:
                    similarity = dot_product / (norm_question * norm_category)
                    similarities[category] = float(similarity)
            
            if not similarities:
                return None
            
            # 키워드 소프트 부스팅 적용
            similarities = self._apply_keyword_boosting(question, similarities)
            
            # 가장 유사한 카테고리 선택
            best_category = max(similarities, key=similarities.get)
            confidence = similarities[best_category]
            
            # 기본 유형 추출 (simple, normal, complex, exhaustive)
            base_type = best_category.split('_')[0]
            
            return {
                "type": base_type,
                "detailed_type": best_category,
                "confidence": confidence,
                "reasoning": f"Semantic Router: {best_category} (유사도: {confidence:.3f})"
            }
        except Exception as e:
            print(f"[SemanticRouter] 분류 실패: {e}")
            return None

    def _apply_keyword_boosting(self, question: str, scores: Dict[str, float]) -> Dict[str, float]:
        """
        하이브리드 부스팅(Soft Boosting, 일부 Hyper-Boosting) 적용.
        - 명확한 식별자는 강하게 반영(+0.2)하여 simple_keyword 우선.
        - 전수 조사 단서가 없으면 exhaustive 점수를 강하게 감산.
        - 관계/영향, 팩트, 정의/설명/비교는 중간/높은 가중치로 미세 조정.
        """
        q = question.lower()
        BOOST_HIGH = 0.08
        BOOST_MID = 0.05
        PENALTY = -0.05
        list_triggers = ["목록", "리스트", "모두", "all list", "모든 목록"]
        
        # --- Hyper-Boosting: 명확한 식별자 ---
        identifiers = [" id", "no.", "code", "코드", "번호", "파일명", ".pdf", ".xlsx", ".ppt", "논문번호", "특허번호", "문서번호", "저자", "작성자", "교수", "연구원"]
        if any(k in q for k in identifiers):
            if "simple_keyword" in scores:
                scores["simple_keyword"] += 0.15
            if "exhaustive_keyword" in scores:
                scores["exhaustive_keyword"] -= 0.1
        
        # --- Strong Penalty: 전수 단서 부재 시 exhaustive 감점 ---
        exhaustive_triggers = ["모든", "전체", "전부", "싹 다", "리스트", "목록", "all", "list", "every", "total"]
        has_exhaustive = any(k in q for k in exhaustive_triggers)
        # 번역 의도가 전혀 없으면 translation 점수 억제 (완화)
        if not self._detect_translation(question):
            for cat in ["normal_translation_direct", "normal_translation_search"]:
                if cat in scores:
                    scores[cat] = min(scores[cat], 0.3)

        if not has_exhaustive:
            if "exhaustive_keyword" in scores:
                scores["exhaustive_keyword"] -= 0.25
            if "exhaustive_list" in scores:
                scores["exhaustive_list"] -= 0.25
            if any(k in q for k in ["찾아", "검색", "find", "search"]):
                if "simple_keyword" in scores:
                    scores["simple_keyword"] += 0.05
        else:
            # 전수 단서가 있으면 우선적으로 exhaustive에 가산
            if "exhaustive_keyword" in scores:
                scores["exhaustive_keyword"] += 0.15
            if "exhaustive_list" in scores:
                scores["exhaustive_list"] += 0.1

        # 리스트성 표현 + 식별자 부재 시 list 쪽 가중치 이동
        has_list_word = any(k in q for k in list_triggers)
        has_identifier = any(k in q for k in identifiers)
        if has_list_word and not has_identifier:
            if "exhaustive_list" in scores:
                scores["exhaustive_list"] += 0.08
            if "exhaustive_keyword" in scores:
                scores["exhaustive_keyword"] -= 0.05
        
        # --- 관계 vs 설명 명확화 ---
        rel_keywords = ["영향", "관계", "상관", "미치는", "따라", "변화", "affect", "effect", "relation"]
        if any(k in q for k in rel_keywords):
            if "complex_relationship" in scores:
                scores["complex_relationship"] += 0.15
            if "normal_explanation" in scores:
                scores["normal_explanation"] -= 0.05
        
        # --- 팩트 단서 (수치/값/날짜) ---
        if any(k in q for k in ["값", "수치", "얼마", "몇", "단위", "value", "number", "출원일", "등록일", "날짜", "date", "issued", "filed"]):
            if "simple_fact" in scores:
                scores["simple_fact"] += 0.1
            if "normal_explanation" in scores:
                scores["normal_explanation"] -= 0.05

        # --- simple_keyword vs simple_fact 경계 보정 ---
        search_cues = ["검색", "찾아", "find", "search", "검색어", "keyword"]
        numeric_cues = ["값", "수치", "얼마", "몇", "단위", "value", "number", "%", "percent", "퍼센트"]
        if any(k in q for k in search_cues) and not any(k in q for k in numeric_cues):
            if "simple_keyword" in scores:
                scores["simple_keyword"] += 0.05
            if "simple_fact" in scores:
                scores["simple_fact"] -= 0.05
        
        # --- 기존 Soft Boosting (정의/설명/비교/전수/단일) ---
        rules = [
            {
                "triggers": ["모든", "전체", "전부", "싹 다", "리스트", "목록", "나열", "all", "list", "every", "total"],
                "pos": ["exhaustive_keyword", "exhaustive_list"],
                "neg": ["simple_keyword"],
                "pos_w": BOOST_MID,
                "neg_w": PENALTY,
            },
            {
                "triggers": ["단일", "특정", "하나만", " id", "번호", "코드", "파일명", "문서명", "no.", "code", ".pdf", ".xlsx", "특허번호", "문서번호", "저자", "작성자", "교수", "연구원"],
                "pos": ["simple_keyword"],
                "neg": ["exhaustive_keyword"],
                "pos_w": BOOST_MID,
                "neg_w": PENALTY,
            },
            {
                "triggers": ["값", "수치", "얼마", "몇", "%", "단위", "value", "number", "figure", "table"],
                "pos": ["simple_fact"],
                "neg": ["normal_explanation", "normal_definition"],
                "pos_w": BOOST_HIGH,
                "neg_w": PENALTY,
            },
            {
                "triggers": ["왜", "이유", "원인", "원리", "메커니즘", "작동", "어떻게", "why", "how", "mechanism"],
                "pos": ["normal_explanation"],
                "neg": ["normal_definition", "simple_fact"],
                "pos_w": BOOST_MID,
                "neg_w": PENALTY,
            },
            {
                "triggers": ["정의", " 뜻", "의미", "이란", "란?", "definition", "meaning", "what is"],
                "pos": ["normal_definition"],
                "neg": ["simple_fact", "complex_relationship"],
                "pos_w": BOOST_HIGH,
                "neg_w": PENALTY,
            },
            {
                "triggers": ["비교", "차이", "대비", "vs", "versus", "diff", "compare"],
                "pos": ["complex_comparison"],
                "neg": [],
                "pos_w": BOOST_HIGH,
                "neg_w": 0.0,
            },
            {
                "triggers": ["어떻게 변해", "어떤 영향", "상관관계", "비례", "반비례"],
                "pos": ["complex_relationship"],
                "neg": ["normal_explanation"],
                "pos_w": BOOST_HIGH,
                "neg_w": PENALTY,
            },
        ]

        boosted_categories = set()  # positive 중복 부스팅 방지
        for rule in rules:
            if any(trigger in q for trigger in rule["triggers"]):  # 규칙당 1회 적용
                for cat in rule["pos"]:
                    if cat in scores and cat not in boosted_categories:
                        scores[cat] += rule["pos_w"]
                        boosted_categories.add(cat)
                for cat in rule["neg"]:
                    if cat in scores:
                        scores[cat] += rule["neg_w"]
        
        # 점수 하한선 보정 (코사인 특성상 0~1 범위에서 음수 방지)
        for cat in scores:
            scores[cat] = max(scores[cat], 0.0)
        
        return scores
    
    # ============ 번역 Fast-Track ============
    
    def _detect_translation(self, question: str) -> bool:
        """번역 질문인지 판단"""
        translation_patterns = [
            r'번역', r'translate', r'번역해줘',
            r'영어로', r'한글로', r'한국어로',
            r'영어로\s*번역', r'한글로\s*번역',
            r'영작', r'번역해', r'Translate'
        ]
        return any(re.search(pattern, question, re.IGNORECASE) for pattern in translation_patterns)
    
    def _requires_search_for_translation(self, question: str) -> bool:
        """번역 질문이 검색을 필요로 하는지 판단"""
        
        # 1. [최우선] 검색 의도가 명확하면 무조건 Search
        # "찾아서", "검색해서", "find ... and", "search ... and"
        search_indicators = [
            # 검색 + 번역 의도가 함께 있을 때만 탐지
            r'찾아.*번역', r'검색.*번역',
            r'find.*translate', r'search.*translate', r'search.*to\s+english', r'search.*to\s+korean',
            r'찾아서\s*영작', r'검색해서\s*영작',
            r'find.*and\s+translate', r'search.*and\s+translate', r'검색.*바꿔줘',
        ]
        
        if any(re.search(pattern, question, re.IGNORECASE) for pattern in search_indicators):
            return True
        
        # 2. [차순위] 지시어/대명사가 있으면 Direct
        direct_patterns = [
            # 한국어 지시어
            r'이\s*문단', r'이\s*내용', r'이\s*문장', r'이\s*부분',
            r'위\s*내용', r'위\s*실험', r'위\s*결과', r'위\s*문단',
            r'아래\s*내용', r'아래\s*문단',
            r'다음\s*문단', r'다음\s*텍스트', r'다음\s*내용',
            r'방금\s*복사', r'방금\s*붙여넣기',
            # 영어 지시어
            r'following\s+(abstract|paragraph|text|content|section)',
            r'this\s+(paragraph|text|content|section|abstract)',
            r'the\s+above\s+(content|text|paragraph)',
            r'the\s+following\s+(abstract|paragraph|text)',
            r'Change\s+this\s+paragraph',
            r'Translate\s+the\s+following',
            # 말투/스타일 지시
            r'말투로', r'스타일로', r'어조로', r'말투', r'스타일', r'어조', r'style', r'tone',
            # 목적어 없이 "번역해줘"만 있는 경우도 direct 취급
            r'번역해줘',
            # 추가: change/convert 패턴 (유연 매칭)
            r'change.*to', r'convert.*to', r'translate.*to', r'change.*this', r'convert.*this', r'translate.*this',
        ]
        
        # 직접 번역 패턴이 있으면 직접 번역
        if any(re.search(pattern, question, re.IGNORECASE) for pattern in direct_patterns):
            return False
        
        # 3. 키워드 기반 판단 (개선)
        # 번역 키워드 제거
        question_without_translation = re.sub(
            r'번역|translate|영어로|한글로|한국어로|영작|바꿔|작문',
            '', 
            question, 
            flags=re.IGNORECASE
        ).strip()
        
        # 지시어나 명시적 대상이 있으면 직접 번역
        if re.search(r'이|위|아래|다음|방금|following|this|the\s+(above|following)', 
                     question_without_translation, re.IGNORECASE):
            return False
        
        # 남은 내용이 구체적인 주제/키워드면 검색 필요
        # (예: "OLED 전극", "TADF 정의" 등)
        if len(question_without_translation) > 5:  # 3자 → 5자로 완화
            return True
        
        # 기본값: 직접 번역
        return False
    
    def _check_translation_regex(self, question: str) -> Optional[str]:
        """Regex 기반 번역 감지 (가장 빠름)"""
        if not self._detect_translation(question):
            return None
        
        # 검색 필요 여부 판단
        if self._requires_search_for_translation(question):
            return "normal_translation_search"
        else:
            return "normal_translation_direct"
    
    # ============ 계층적 라우팅 ============
    
    def _classify_hierarchical(self, question: str) -> Optional[Dict]:
        """계층적 라우팅 (2단계 분류)"""
        try:
            # Layer 1: 큰 분류 (simple/normal/complex/exhaustive)
            layer1_category, layer1_confidence = self._classify_layer1(question)
            
            # Layer 2: 세부 분류
            if layer1_category == 'simple':
                detailed_type = self._classify_layer2_simple(question)
            elif layer1_category == 'normal':
                detailed_type = self._classify_layer2_normal(question)
            elif layer1_category == 'complex':
                detailed_type = self._classify_layer2_complex(question)
            else:  # exhaustive
                detailed_type = self._classify_layer2_exhaustive(question)
            
            return {
                "type": layer1_category,
                "detailed_type": detailed_type,
                "confidence": layer1_confidence,
                "reasoning": f"계층적 라우팅: Layer1={layer1_category}, Layer2={detailed_type}"
            }
        except Exception as e:
            print(f"[QuestionClassifier] 계층적 라우팅 실패: {e}")
            return None
    
    def _classify_layer1(self, question: str) -> Tuple[str, float]:
        """Layer 1: 큰 분류 (simple/normal/complex/exhaustive)"""
        # 번역 질문은 규칙 기반으로 먼저 감지 (빠름)
        if self._detect_translation(question):
            return "normal", 1.0  # 번역은 normal의 하위 분류
        
        if self.llm is None:
            # LLM 없으면 규칙 기반으로 추정
            rule_result = self._classify_by_rules(question)
            return rule_result['type'], rule_result.get('confidence', 0.7)
        
        prompt = f"""다음 질문을 다음 4가지 중 하나로 분류하세요:
1. simple: 단순 사실/키워드 검색 질문
2. normal: 일반 질문 (정의, 설명, 번역 등)
3. complex: 복잡한 분석/비교/관계 질문
4. exhaustive: 포괄적 검색 질문 ("모든", "전체" 등)

질문: "{question}"

JSON 형식으로 답하세요:
{{
    "category": "simple|normal|complex|exhaustive",
    "confidence": 0.0-1.0,
    "reasoning": "이유"
}}"""
        
        try:
            response = self.llm.invoke(prompt)
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            # JSON 추출
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                category = result.get('category', 'normal')
                confidence = float(result.get('confidence', 0.8))
                return category, confidence
        except Exception as e:
            print(f"[QuestionClassifier] Layer 1 분류 실패: {e}")
        
        # 폴백: 규칙 기반
        rule_result = self._classify_by_rules(question)
        return rule_result['type'], rule_result.get('confidence', 0.7)
    
    def _classify_layer2_simple(self, question: str) -> str:
        """Layer 2: Simple 세부 분류"""
        if self._is_keyword_search(question):
            return "simple_keyword"
        else:
            return "simple_fact"
    
    def _classify_layer2_normal(self, question: str) -> str:
        """Layer 2: Normal 세부 분류"""
        # 번역 질문 감지 및 세분화
        if self._detect_translation(question):
            if self._requires_search_for_translation(question):
                return "normal_translation_search"
            else:
                return "normal_translation_direct"
        # 정의 질문 감지
        elif self._is_definition_question(question):
            return "normal_definition"
        else:
            return "normal_explanation"
    
    def _classify_layer2_complex(self, question: str) -> str:
        """Layer 2: Complex 세부 분류"""
        if self.llm is None:
            # LLM 없으면 규칙 기반
            if self._is_comparison_question(question):
                return "complex_comparison"
            else:
                return "complex_relationship"
        
        prompt = f"""다음 질문을 다음 2가지 중 하나로 분류하세요:
1. comparison: 비교/분석 질문
2. relationship: 관계/영향 질문

질문: "{question}"

JSON 형식으로 답하세요:
{{
    "category": "comparison|relationship",
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = self.llm.invoke(prompt)
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                category = result.get('category', 'relationship')
                return f"complex_{category}"
        except Exception as e:
            print(f"[QuestionClassifier] Layer 2 Complex 분류 실패: {e}")
        
        # 폴백: 규칙 기반
        if self._is_comparison_question(question):
            return "complex_comparison"
        else:
            return "complex_relationship"
    
    def _classify_layer2_exhaustive(self, question: str) -> str:
        """Layer 2: Exhaustive 세부 분류"""
        if self._is_keyword_search(question):
            return "exhaustive_keyword"
        else:
            return "exhaustive_list"
    
    def _is_keyword_search(self, question: str) -> bool:
        """키워드 검색 질문인지 판단"""
        keyword_patterns = [
            r'찾아줘', r'있는', r'포함', r'나와',
            r'find.*by', r'search.*for', r'contain'
        ]
        return any(re.search(pattern, question, re.IGNORECASE) for pattern in keyword_patterns)
    
    def _is_definition_question(self, question: str) -> bool:
        """정의 질문인지 판단"""
        definition_patterns = [
            r'[은는이가]\s*무엇[인가이]',
            r'[이란는]\s*무엇',
            r'[은는]\s*뭐'
        ]
        return any(re.search(pattern, question) for pattern in definition_patterns)
    
    def _is_comparison_question(self, question: str) -> bool:
        """비교 질문인지 판단"""
        comparison_keywords = ['비교', '차이', 'vs', 'versus', 'compared']
        return any(kw in question.lower() for kw in comparison_keywords)

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

        prompt = f"""Classify the following question and translate it to English if it's not already in English:

Question: "{question}"
{hint_text}

**Pre-processing** (before classification):
1. **Multiple Question Detection**: 
   - If the input contains multiple questions (separated by "?", "and", "또한", etc.), 
     identify each question separately
   - Example: "What is TADF? And how does it work?" → 2 separate questions
   - In this case, classify the first/main question

2. **Keyword Extraction**:
   - Extract core keywords and technical terms
   - Identify entities (names, places, concepts)
   - Note: Keywords will be used for search optimization

Classification criteria:
1. **simple** (simple fact question)
   - Questions asking for specific values, numbers, names
   - Keywords like author, writer, etc. → simple
   - Answerable in 1-2 sentences
   - Examples: "What is kFRET?", "Summarize page 3", "How much?", "Find author duan lian"

2. **normal** (general question)
   - Questions requiring explanation
   - Need 2-3 paragraph answer
   - May contain some ambiguity
   - Examples: "What is OLED efficiency?", "How does it work?"

3. **complex** (complex question)
   - Questions about relationships, connections, interactions between multiple items
   - Comparison, analysis, evaluation requests
   - Multiple items or perspectives (using "와/과", "and", "between")
   - Questions containing keywords: "관계" (relationship), "연결" (connection), "비교" (comparison), "차이" (difference), "영향" (influence), "상호작용" (interaction)
   - Need long answer (4+ paragraphs)
   - Examples: 
     * "A와 B의 관계" (relationship between A and B)
     * "Compare A and B" (comparison)
     * "Analyze the impact of X on Y" (analysis with multiple items)

4. **exhaustive** (exhaustive question)
   - Words like "all", "every", "each" indicating comprehensive search
   - List/listing format answer
   - Examples: "All slide titles", "Find all papers"

Additional analysis:
- ambiguity: Question ambiguity level (0.0=clear, 1.0=very ambiguous)
- multi_query_helpful: Would Multi-Query generation be helpful? (true/false)

**Output ONLY in JSON format** (no other text):
{{
    "type": "simple",
    "confidence": 0.95,
    "reasoning": "Simple question asking for specific value",
    "ambiguity": 0.1,
    "multi_query_helpful": false,
    "translated_question": "English translation of the question (if original is not English, otherwise same as original)"
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
        detailed_type = result.get("detailed_type")  # 10개 세분화 유형

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

def create_classifier(
    llm=None, 
    use_llm: bool = True, 
    verbose: bool = False, 
    llm_timeout: float = 10.0,
    embeddings=None  # Semantic Router용 임베딩 모델
):
    """
    분류기 생성 편의 함수

    Args:
        llm: LLM 모델 (None이면 규칙만 사용)
        use_llm: LLM 사용 여부 (LLM 우선 방식)
        verbose: 상세 로그
        llm_timeout: LLM 호출 타임아웃 (초)
        embeddings: 임베딩 모델 (None이면 Semantic Router 비활성화)

    Returns:
        QuestionClassifier 인스턴스
    """
    return QuestionClassifier(
        llm=llm,
        use_llm_fallback=use_llm,
        verbose=verbose,
        llm_timeout=llm_timeout,
        embeddings=embeddings
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
