"""
Cross-Encoder Re-ranker
Vector Search로 추출된 후보를 정확하게 재순위화
"""

from typing import List, Dict, Any, Optional
from sentence_transformers import CrossEncoder
import logging

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Cross-Encoder 기반 재순위화"""
    
    # 사용 가능한 모델들
    AVAILABLE_MODELS = {
        "multilingual-mini": "cross-encoder/ms-marco-MiniLM-L-6-v2",  # 22MB, 빠름
        "multilingual-base": "cross-encoder/ms-marco-MiniLM-L-12-v2",  # 133MB, 더 정확
        "korean": "Dongjin-kr/ko-reranker",  # 100MB, 한국어 최적화
    }
    
    def __init__(self, model_name: str = "multilingual-mini", device: str = "cpu"):
        """
        Args:
            model_name: 사용할 모델 ("multilingual-mini", "multilingual-base", "korean")
            device: 실행 디바이스 ("cpu" 또는 "cuda")
        """
        self.model_name = model_name
        self.device = device
        
        # 모델 로드
        model_path = self.AVAILABLE_MODELS.get(
            model_name,
            self.AVAILABLE_MODELS["multilingual-mini"]
        )
        
        try:
            logger.info(f"Re-ranker 모델 로딩 중: {model_path}")
            self.model = CrossEncoder(model_path, device=device)
            logger.info(f"Re-ranker 모델 로딩 완료")
        except Exception as e:
            logger.error(f"Re-ranker 모델 로딩 실패: {str(e)}")
            raise
    
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        문서들을 재순위화
        
        Args:
            query: 검색 쿼리
            documents: 재순위화할 문서 리스트 (page_content 필드 필요)
            top_k: 반환할 상위 문서 수 (None이면 전체 반환)
        
        Returns:
            재순위화된 문서 리스트 (rerank_score 필드 추가됨)
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
            else:
                # Document 객체인 경우
                if not hasattr(doc_copy, "metadata"):
                    doc_copy.metadata = {}
                doc_copy.metadata["rerank_score"] = float(score)
            reranked_docs.append(doc_copy)
        
        # 점수 기준 정렬 (높은 순)
        reranked_docs.sort(
            key=lambda x: (
                x.get("rerank_score", 0) if isinstance(x, dict)
                else x.metadata.get("rerank_score", 0)
            ),
            reverse=True
        )
        
        # top_k 개수만 반환
        if top_k is not None:
            reranked_docs = reranked_docs[:top_k]
        
        return reranked_docs
    
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

