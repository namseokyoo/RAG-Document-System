"""
Phase 4: Hybrid Search - BM25 + Vector 결합 검색기
BM25 (키워드 기반) + Vector (의미 기반) 하이브리드 검색

VectorStoreManager의 정교한 BM25 인덱스를 재사용하여:
- 중복 인덱스 구축 방지 (성능 향상)
- Stopwords 제거 및 한국어 조사 처리로 검색 품질 향상
"""
from typing import List, Dict, Any, Tuple
import numpy as np


class HybridRetriever:
    """BM25와 Vector Search를 결합한 하이브리드 검색기 (VectorStoreManager의 BM25 재사용)"""

    def __init__(self, vector_manager, bm25_weight: float = 0.5):
        """
        Args:
            vector_manager: VectorStoreManager 인스턴스
            bm25_weight: BM25 점수 가중치 (0.0~1.0), Vector 가중치 = 1 - bm25_weight
        """
        self.vector_manager = vector_manager
        self.bm25_weight = bm25_weight
        self.vector_weight = 1.0 - bm25_weight

        print(f"[HybridRetriever] 초기화 완료 (BM25:{bm25_weight:.1f} / Vector:{self.vector_weight:.1f})")
        print(f"[HybridRetriever] VectorStoreManager의 정교한 BM25 재사용 (Stopwords 제거, 한국어 조사 처리)")

    def search(self, query: str, top_k: int = 20, domain_filter: str = None) -> List[Tuple[Any, float]]:
        """
        하이브리드 검색 수행

        Args:
            query: 검색 쿼리
            top_k: 반환할 상위 결과 개수
            domain_filter: 도메인 필터 (선택)

        Returns:
            List[(document, score)]: 검색 결과와 점수
        """
        print(f"[HybridRetriever] 하이브리드 검색 시작 (top_k={top_k})")

        # BM25가 준비되지 않았으면 Vector 검색만 수행
        if not self.vector_manager.bm25_ready:
            print("[HybridRetriever] ⚠ BM25 로딩 중... Vector 검색만 수행")
            return self._vector_search_only(query, top_k, domain_filter)

        # 1. BM25 검색
        print(f"[HybridRetriever] 1단계: BM25 키워드 검색 중... (가중치: {self.bm25_weight:.1f})")
        bm25_results = self._bm25_search(query, top_k * 2)  # 2배로 검색 (융합용)

        # 2. Vector 검색
        print(f"[HybridRetriever] 2단계: Vector 의미 검색 중... (가중치: {self.vector_weight:.1f})")
        vector_results = self._vector_search(query, top_k * 2, domain_filter)

        # 3. 결과 융합 (Reciprocal Rank Fusion)
        print(f"[HybridRetriever] 3단계: 검색 결과 융합 중... (RRF)")
        fused_results = self._fuse_results(bm25_results, vector_results, top_k)

        print(f"[HybridRetriever] ✓ 하이브리드 검색 완료: {len(fused_results)}개 결과")
        return fused_results

    def _bm25_search(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        """BM25 검색 수행 (VectorStoreManager의 BM25 사용)"""
        try:
            # VectorStoreManager의 BM25 락 획득
            with self.vector_manager.bm25_lock:
                # 준비 상태 재확인
                if not self.vector_manager.bm25_ready or self.vector_manager.bm25 is None:
                    print("[HybridRetriever] BM25가 아직 준비되지 않았습니다")
                    return []

                # VectorStoreManager의 정교한 토큰화 사용
                tokenized_query = self.vector_manager._tokenize(query)
                
                # 빈 토큰 리스트 처리
                if not tokenized_query:
                    print("[HybridRetriever] BM25 토큰 없음, 빈 결과 반환")
                    return []

                # VectorStoreManager의 BM25로 점수 계산
                scores = self.vector_manager.bm25.get_scores(tokenized_query)
                
                # NumPy 배열 크기 확인
                if isinstance(scores, np.ndarray) and scores.size == 0:
                    print("[HybridRetriever] BM25 점수 없음, 빈 결과 반환")
                    return []

                # 상위 k개 선택
                top_indices = np.argsort(scores)[::-1][:top_k]
                
                # 빈 인덱스 처리
                if len(top_indices) == 0:
                    return []

                # (document_id, score) 반환
                results = [(self.vector_manager.doc_ids[i], float(scores[i])) for i in top_indices if i < len(scores) and scores[i] > 0]

                print(f"[HybridRetriever] BM25 검색: {len(results)}개 결과")
                return results

        except Exception as e:
            print(f"[HybridRetriever] BM25 검색 실패: {e}")
            return []

    def _vector_search(self, query: str, top_k: int, domain_filter: str = None) -> List[Tuple[str, float]]:
        """Vector 검색 수행"""
        try:
            # VectorStoreManager에서 Chroma collection 가져오기
            collection = self.vector_manager.vectorstore._collection

            # 쿼리 임베딩 생성
            query_embedding = self.vector_manager.embeddings.embed_query(query)

            # Chroma 검색
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where={"file_name": domain_filter} if domain_filter else None
            )

            # (document_id, similarity_score) 반환
            # Chroma는 거리를 반환하므로, 유사도로 변환 (1 - distance)
            if results and results['ids'] and len(results['ids'][0]) > 0:
                ids = results['ids'][0]
                distances = results['distances'][0] if 'distances' in results else [0] * len(ids)

                # 거리를 유사도로 변환 (작은 거리 = 높은 유사도)
                # 코사인 유사도 범위 [0, 1]로 정규화
                similarities = [max(0, 1 - dist) for dist in distances]

                vector_results = list(zip(ids, similarities))
                print(f"[HybridRetriever] Vector 검색: {len(vector_results)}개 결과")
                return vector_results
            else:
                return []

        except Exception as e:
            print(f"[HybridRetriever] Vector 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _vector_search_only(self, query: str, top_k: int, domain_filter: str = None) -> List[Tuple[Any, float]]:
        """Vector 검색만 수행 (폴백용)"""
        try:
            # Vector 검색
            vector_results = self._vector_search(query, top_k, domain_filter)

            # 문서 객체와 점수 반환
            documents_with_scores = []
            collection = self.vector_manager.vectorstore._collection

            for doc_id, score in vector_results:
                # ID로 문서 가져오기
                doc_data = collection.get(ids=[doc_id])
                if doc_data and doc_data['documents']:
                    # 문서 객체 생성 (간단히 딕셔너리로)
                    doc = {
                        'id': doc_id,
                        'content': doc_data['documents'][0],
                        'metadata': doc_data['metadatas'][0] if 'metadatas' in doc_data else {}
                    }
                    documents_with_scores.append((doc, score))

            return documents_with_scores

        except Exception as e:
            print(f"[HybridRetriever] Vector 전용 검색 실패: {e}")
            return []

    def _fuse_results(self, bm25_results: List[Tuple[str, float]],
                     vector_results: List[Tuple[str, float]],
                     top_k: int) -> List[Tuple[Any, float]]:
        """
        Reciprocal Rank Fusion (RRF)으로 결과 융합

        RRF 공식: score(d) = Σ 1 / (k + rank(d))
        k = 60 (일반적인 상수)
        """
        k = 60  # RRF 상수

        # 문서별 RRF 점수 계산
        doc_scores = {}

        # BM25 결과 추가
        for rank, (doc_id, score) in enumerate(bm25_results, start=1):
            rrf_score = 1.0 / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + self.bm25_weight * rrf_score

        # Vector 결과 추가
        for rank, (doc_id, score) in enumerate(vector_results, start=1):
            rrf_score = 1.0 / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + self.vector_weight * rrf_score

        # 점수 기준 정렬
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # 문서 객체와 점수 반환
        documents_with_scores = []
        collection = self.vector_manager.vectorstore._collection

        for doc_id, score in sorted_docs:
            try:
                # Chroma에서 문서 가져오기
                doc_data = collection.get(ids=[doc_id])

                if doc_data and doc_data['documents']:
                    # 문서 객체 생성
                    doc = {
                        'id': doc_id,
                        'content': doc_data['documents'][0],
                        'metadata': doc_data['metadatas'][0] if 'metadatas' in doc_data else {}
                    }
                    documents_with_scores.append((doc, score))
            except Exception as e:
                print(f"[HybridRetriever] 문서 {doc_id} 가져오기 실패: {e}")
                continue

        print(f"[HybridRetriever] 융합 완료: {len(documents_with_scores)}개 결과 (BM25:{len(bm25_results)}, Vector:{len(vector_results)})")
        return documents_with_scores


# 하이브리드 검색 사용 예시
if __name__ == "__main__":
    print("HybridRetriever 모듈 로드 완료")
    print("사용법:")
    print("  retriever = HybridRetriever(vector_manager, bm25_weight=0.5)")
    print("  # VectorStoreManager의 BM25가 백그라운드에서 자동 로딩됨")
    print("  results = retriever.search('검색 쿼리', top_k=10)")
