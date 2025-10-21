"""
Small-to-Large 검색 시스템
정확한 Small 청크 검색 후 부모 청크로 컨텍스트 확장
"""
from typing import List, Dict, Any, Optional, Tuple
from langchain.schema import Document
import uuid


class SmallToLargeSearch:
    """Small-to-Large 아키텍처 검색 시스템"""
    
    def __init__(self, vectorstore):
        self.vectorstore = vectorstore
        self.parent_cache = {}  # 부모 청크 캐시
    
    def search_with_context_expansion(self, query: str, top_k: int = 5) -> List[Document]:
        """정확한 검색 후 컨텍스트 확장"""
        try:
            # 1단계: Small 청크로 정확한 검색
            small_results = self.vectorstore.similarity_search_with_score(
                query, k=top_k * 2  # 더 많은 후보 확보
            )
            
            if not small_results:
                return []
            
            # 2단계: 부모 청크로 컨텍스트 확장
            expanded_results = []
            processed_parents = set()
            
            for doc, score in small_results:
                # Small 청크 추가
                expanded_results.append((doc, score))
                
                # 부모 청크 확장
                parent_id = doc.metadata.get("parent_chunk_id")
                if parent_id and parent_id not in processed_parents:
                    parent_doc = self._get_parent_chunk(parent_id)
                    if parent_doc:
                        # 부모는 약간 낮은 점수로 추가
                        expanded_results.append((parent_doc, score * 0.8))
                        processed_parents.add(parent_id)
            
            # 3단계: 상위 결과 반환
            expanded_results.sort(key=lambda x: x[1], reverse=True)
            return [doc for doc, score in expanded_results[:top_k]]
            
        except Exception as e:
            print(f"Small-to-Large 검색 중 오류: {e}")
            # 폴백: 기본 검색
            return self.vectorstore.similarity_search(query, k=top_k)
    
    def search_small_only(self, query: str, top_k: int = 5) -> List[Document]:
        """Small 청크만 검색 (정확성 우선)"""
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=top_k)
            return [doc for doc, score in results]
        except Exception as e:
            print(f"Small 청크 검색 중 오류: {e}")
            return []
    
    def search_large_only(self, query: str, top_k: int = 5) -> List[Document]:
        """Large 청크만 검색 (컨텍스트 우선)"""
        try:
            # page_summary 타입만 검색
            results = self.vectorstore.similarity_search_with_score(query, k=top_k * 2)
            
            # page_summary 타입만 필터링
            large_results = []
            for doc, score in results:
                if doc.metadata.get("chunk_type") == "page_summary":
                    large_results.append((doc, score))
                    if len(large_results) >= top_k:
                        break
            
            return [doc for doc, score in large_results]
        except Exception as e:
            print(f"Large 청크 검색 중 오류: {e}")
            return []
    
    def search_by_chunk_type(self, query: str, chunk_type: str, top_k: int = 5) -> List[Document]:
        """특정 청크 타입으로 검색"""
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=top_k * 2)
            
            # 특정 타입만 필터링
            filtered_results = []
            for doc, score in results:
                if doc.metadata.get("chunk_type") == chunk_type:
                    filtered_results.append((doc, score))
                    if len(filtered_results) >= top_k:
                        break
            
            return [doc for doc, score in filtered_results]
        except Exception as e:
            print(f"청크 타입별 검색 중 오류: {e}")
            return []
    
    def search_with_weighted_scoring(self, query: str, top_k: int = 5) -> List[Document]:
        """가중치를 적용한 검색"""
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=top_k * 3)
            
            # 가중치 적용
            weighted_results = []
            for doc, score in results:
                chunk_type_weight = doc.metadata.get("chunk_type_weight", 1.0)
                weighted_score = score * chunk_type_weight
                weighted_results.append((doc, weighted_score))
            
            # 가중치 점수로 정렬
            weighted_results.sort(key=lambda x: x[1], reverse=True)
            return [doc for doc, score in weighted_results[:top_k]]
            
        except Exception as e:
            print(f"가중치 검색 중 오류: {e}")
            return []
    
    def search_by_section(self, query: str, section_title: str, top_k: int = 5) -> List[Document]:
        """특정 섹션에서 검색"""
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=top_k * 2)
            
            # 섹션 필터링
            section_results = []
            for doc, score in results:
                if doc.metadata.get("section_title") == section_title:
                    section_results.append((doc, score))
                    if len(section_results) >= top_k:
                        break
            
            return [doc for doc, score in section_results]
        except Exception as e:
            print(f"섹션별 검색 중 오류: {e}")
            return []
    
    def _get_parent_chunk(self, parent_id: str) -> Optional[Document]:
        """부모 청크 조회"""
        # 캐시 확인
        if parent_id in self.parent_cache:
            return self.parent_cache[parent_id]
        
        try:
            # 벡터스토어에서 parent_id로 검색
            # 실제 구현에서는 벡터스토어의 특정 필드 검색 기능 사용
            results = self.vectorstore.similarity_search(
                f"parent_chunk_id:{parent_id}", k=1
            )
            
            if results:
                parent_doc = results[0]
                # 캐시에 저장
                self.parent_cache[parent_id] = parent_doc
                return parent_doc
            
        except Exception as e:
            print(f"부모 청크 조회 중 오류: {e}")
        
        return None
    
    def get_search_statistics(self, query: str) -> Dict[str, Any]:
        """검색 통계 정보 반환"""
        try:
            # 기본 검색으로 통계 수집
            results = self.vectorstore.similarity_search_with_score(query, k=20)
            
            stats = {
                "total_results": len(results),
                "chunk_types": {},
                "sections": set(),
                "pages": set(),
                "avg_score": 0,
                "score_range": (0, 0)
            }
            
            if not results:
                return stats
            
            scores = []
            for doc, score in results:
                # 청크 타입별 카운트
                chunk_type = doc.metadata.get("chunk_type", "unknown")
                stats["chunk_types"][chunk_type] = stats["chunk_types"].get(chunk_type, 0) + 1
                
                # 섹션 및 페이지 정보
                section = doc.metadata.get("section_title")
                if section:
                    stats["sections"].add(section)
                
                page = doc.metadata.get("page_number")
                if page:
                    stats["pages"].add(page)
                
                scores.append(score)
            
            # 점수 통계
            stats["avg_score"] = sum(scores) / len(scores)
            stats["score_range"] = (min(scores), max(scores))
            stats["sections"] = len(stats["sections"])
            stats["pages"] = len(stats["pages"])
            
            return stats
            
        except Exception as e:
            print(f"검색 통계 수집 중 오류: {e}")
            return {}
    
    def clear_cache(self):
        """캐시 초기화"""
        self.parent_cache.clear()
