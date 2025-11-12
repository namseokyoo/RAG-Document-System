"""
Cross-Encoder Re-ranker
Vector Search로 추출된 후보를 정확하게 재순위화
로컬 모델 캐시 지원으로 외부 네트워크 의존성 제거
"""

from typing import List, Dict, Any, Optional
from sentence_transformers import CrossEncoder
from pathlib import Path
import logging
import os
import sys

# 폐쇄망 환경에서의 안전한 실행을 위한 환경변수 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Cross-Encoder 기반 재순위화 (로컬 캐시 지원)"""
    
    # 로컬 모델 경로 매핑
    LOCAL_MODELS = {
        "multilingual-mini": "models/reranker-mini",
    }

    # HuggingFace 모델 ID (다운로드용)
    HF_MODELS = {
        "multilingual-mini": "cross-encoder/ms-marco-MiniLM-L-6-v2",  # 22MB, 빠름
    }
    
    def __init__(self, model_name: str = "multilingual-mini", device: str = "cpu"):
        """
        Args:
            model_name: 사용할 모델 ("multilingual-mini")
            device: 실행 디바이스 ("cpu" 또는 "cuda")
        """
        self.model_name = model_name
        self.device = device
        
        # 로컬 모델 경로 확인
        local_path = self.LOCAL_MODELS.get(model_name)
        hf_model_id = self.HF_MODELS.get(model_name)
        
        if not local_path or not hf_model_id:
            raise ValueError(f"지원하지 않는 모델: {model_name}")
        
        # PyInstaller 환경에서 올바른 경로 찾기
        if getattr(sys, 'frozen', False):
            # PyInstaller로 빌드된 실행 파일
            base_path = Path(sys._MEIPASS)
            # 모델 이름을 실제 디렉토리 이름으로 매핑
            model_dir_map = {
                "multilingual-mini": "reranker-mini",
            }
            actual_dir_name = model_dir_map.get(model_name, model_name)
            local_model_path = base_path / "models" / actual_dir_name
        else:
            # 일반 Python 실행
            local_model_path = Path(local_path)
        
        try:
            # 모델 파일 존재 여부 확인 (config.json만 있어도 폴더는 존재할 수 있음)
            model_files = ["model.safetensors", "pytorch_model.bin", "tf_model.h5", "model.ckpt.index", "flax_model.msgpack"]
            has_model_file = False
            
            if local_model_path.exists():
                # 모델 파일이 실제로 있는지 확인
                for model_file in model_files:
                    if (local_model_path / model_file).exists():
                        has_model_file = True
                        break
            
            if local_model_path.exists() and has_model_file:
                # 로컬 모델 사용
                logger.info(f"로컬 Re-ranker 모델 로딩 중: {local_model_path}")
                self.model = CrossEncoder(str(local_model_path), device=device)
                logger.info(f"로컬 Re-ranker 모델 로딩 완료")
            else:
                # 로컬 모델이 없으면 HuggingFace에서 다운로드 시도
                # 오프라인 모드 확인
                if os.environ.get("TRANSFORMERS_OFFLINE") == "1":
                    error_msg = (
                        f"오프라인 모드에서 Re-ranker 모델 파일을 찾을 수 없습니다.\n"
                        f"모델: {model_name}\n"
                        f"모델 경로: {local_model_path}\n"
                        f"필요한 파일 중 하나: {', '.join(model_files)}\n\n"
                        f"외부망에서 다음 명령으로 모델을 다운로드하세요:\n"
                        f"python download_models.py --model {model_name}\n\n"
                        f"또는 config.json에서 use_reranker를 false로 설정하여 Re-ranker를 비활성화할 수 있습니다."
                    )
                    raise RuntimeError(error_msg)
                
                logger.info(f"HuggingFace에서 다운로드 중: {hf_model_id}")
                self.model = CrossEncoder(hf_model_id, device=device)
                logger.info(f"HuggingFace 모델 로딩 완료")
                
        except Exception as e:
            # 이미 친절한 에러 메시지가 있는 경우 그대로 사용
            if isinstance(e, RuntimeError) and "오프라인 모드에서" in str(e):
                raise  # 이미 포맷된 에러 메시지이므로 그대로 전달
            # 그 외의 경우 에러 메시지 생성
            error_msg = f"Re-ranker 모델 로딩 실패: {str(e)}"
            # 중복 메시지 방지 (이미 로그에 출력된 경우)
            if "no file named" in str(e).lower() or "not found" in str(e).lower():
                error_msg = (
                    f"모델 파일을 찾을 수 없습니다.\n"
                    f"모델: {model_name}\n"
                    f"경로: {local_model_path}\n\n"
                    f"외부망에서 모델을 다운로드하거나 config.json에서 use_reranker를 false로 설정하세요."
                )
            raise RuntimeError(error_msg)
    
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        diversity_penalty: float = 0.0,
        diversity_source_key: str = "source"
    ) -> List[Dict[str, Any]]:
        """
        문서들을 재순위화 (diversity penalty 지원)

        Args:
            query: 검색 쿼리
            documents: 재순위화할 문서 리스트 (page_content 필드 필요)
            top_k: 반환할 상위 문서 수 (None이면 전체 반환)
            diversity_penalty: 동일 출처 문서에 대한 penalty (0.0~1.0)
                              0.0 = 패널티 없음 (기본값, 기존 동작)
                              0.3 = 2번째부터 30% 감소 (권장값)
                              1.0 = 2번째부터 완전히 제거
            diversity_source_key: metadata에서 출처를 식별할 키 (기본: "source")

        Returns:
            재순위화된 문서 리스트 (rerank_score, adjusted_score 필드 추가됨)
        """
        if not documents:
            return []

        # 쿼리-문서 쌍 생성
        pairs = []
        for doc in documents:
            content = doc.get("page_content", "")
            if isinstance(content, str):
                pairs.append([query, content])
            else:
                # Document 객체인 경우
                pairs.append([query, getattr(content, "page_content", str(content))])

        # Cross-Encoder로 점수 계산
        try:
            scores = self.model.predict(pairs)
        except Exception as e:
            logger.error(f"Re-ranking 실패: {str(e)}")
            return documents  # 실패 시 원본 반환

        # 문서에 재순위화 점수 추가
        reranked_docs = []
        for doc, score in zip(documents, scores):
            doc_copy = doc.copy() if isinstance(doc, dict) else doc
            if isinstance(doc_copy, dict):
                doc_copy["rerank_score"] = float(score)
                doc_copy["adjusted_score"] = float(score)  # 초기에는 동일
            else:
                # Document 객체인 경우
                if not hasattr(doc_copy, "metadata"):
                    doc_copy.metadata = {}
                doc_copy.metadata["rerank_score"] = float(score)
                doc_copy.metadata["adjusted_score"] = float(score)
            reranked_docs.append(doc_copy)

        # Diversity penalty 적용 (0보다 큰 경우에만)
        if diversity_penalty > 0.0:
            reranked_docs = self._apply_diversity_penalty(
                reranked_docs,
                diversity_penalty,
                diversity_source_key
            )

        # 점수 기준 정렬 (adjusted_score 사용)
        reranked_docs.sort(
            key=lambda x: (
                x.get("adjusted_score", 0) if isinstance(x, dict)
                else x.metadata.get("adjusted_score", 0)
            ),
            reverse=True
        )

        # top_k 개수만 반환
        if top_k is not None:
            reranked_docs = reranked_docs[:top_k]

        return reranked_docs

    def _apply_diversity_penalty(
        self,
        documents: List[Dict[str, Any]],
        penalty_strength: float,
        source_key: str = "source"
    ) -> List[Dict[str, Any]]:
        """
        동일 출처 문서에 diversity penalty 적용

        Args:
            documents: 문서 리스트 (rerank_score 필요)
            penalty_strength: penalty 강도 (0.0~1.0)
            source_key: metadata에서 출처 식별 키

        Returns:
            adjusted_score가 추가된 문서 리스트

        Algorithm:
            - 1번째 출처 문서: 100% 점수 유지 (penalty = 0%)
            - 2번째 출처 문서: penalty_strength만큼 감소
            - 3번째: penalty_strength * 2 만큼 감소
            - ...
            예: penalty_strength=0.3일 때
                1번째: score * 1.0  (100%)
                2번째: score * 0.7  (70%)
                3번째: score * 0.4  (40%)
                4번째: score * 0.1  (10%, min)
        """
        from collections import Counter

        source_counter = Counter()

        for doc in documents:
            # 원래 점수 가져오기
            original_score = (
                doc.get("rerank_score", 0) if isinstance(doc, dict)
                else doc.metadata.get("rerank_score", 0)
            )

            # 출처 식별
            if isinstance(doc, dict):
                metadata = doc.get("metadata", {})
            else:
                metadata = getattr(doc, "metadata", {})

            source = metadata.get(source_key, "unknown")

            # Penalty 계산 (같은 출처의 N번째 문서)
            repeat_count = source_counter[source]
            penalty = 1.0 - (repeat_count * penalty_strength)
            penalty = max(penalty, 0.1)  # 최소 10% 점수는 유지

            # Adjusted score 계산
            adjusted_score = original_score * penalty

            # 점수 업데이트
            if isinstance(doc, dict):
                doc["adjusted_score"] = float(adjusted_score)
                doc["diversity_penalty"] = float(penalty)
                doc["source_repeat_count"] = repeat_count
            else:
                doc.metadata["adjusted_score"] = float(adjusted_score)
                doc.metadata["diversity_penalty"] = float(penalty)
                doc.metadata["source_repeat_count"] = repeat_count

            # 출처 카운터 증가
            source_counter[source] += 1

        return documents
    
    def rerank_with_details(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        재순위화 + 상세 정보 반환
        
        Returns:
            {
                "documents": 재순위화된 문서 리스트,
                "scores": 점수 리스트,
                "original_ranks": 원래 순위 리스트,
                "rank_changes": 순위 변화 리스트
            }
        """
        if not documents:
            return {
                "documents": [],
                "scores": [],
                "original_ranks": [],
                "rank_changes": []
            }
        
        # 원본 순위 기록
        for idx, doc in enumerate(documents):
            if isinstance(doc, dict):
                doc["original_rank"] = idx + 1
            else:
                if not hasattr(doc, "metadata"):
                    doc.metadata = {}
                doc.metadata["original_rank"] = idx + 1
        
        # 재순위화
        reranked = self.rerank(query, documents, top_k)
        
        # 상세 정보 추출
        scores = []
        original_ranks = []
        rank_changes = []
        
        for new_rank, doc in enumerate(reranked, 1):
            score = (
                doc.get("rerank_score", 0) if isinstance(doc, dict)
                else doc.metadata.get("rerank_score", 0)
            )
            orig_rank = (
                doc.get("original_rank", 0) if isinstance(doc, dict)
                else doc.metadata.get("original_rank", 0)
            )
            
            scores.append(score)
            original_ranks.append(orig_rank)
            rank_changes.append(orig_rank - new_rank)  # 양수면 순위 상승
        
        return {
            "documents": reranked,
            "scores": scores,
            "original_ranks": original_ranks,
            "rank_changes": rank_changes
        }


# 전역 인스턴스 (싱글톤)
_reranker_instance: Optional[CrossEncoderReranker] = None


def get_reranker(
    model_name: str = "multilingual-mini",
    device: str = "cpu",
    force_reload: bool = False
) -> CrossEncoderReranker:
    """
    Re-ranker 싱글톤 인스턴스 반환
    
    Args:
        model_name: 모델 이름
        device: 실행 디바이스
        force_reload: 강제 재로드 여부
    
    Returns:
        CrossEncoderReranker 인스턴스
    """
    global _reranker_instance
    
    if _reranker_instance is None or force_reload:
        _reranker_instance = CrossEncoderReranker(model_name, device)
    
    return _reranker_instance

