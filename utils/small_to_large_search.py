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
    
    def search_with_context_expansion(self, query: str, top_k: int = 5, max_parents: int = 3, 
                                     partial_context_size: int = 200) -> List[Document]:
        """정확한 검색 후 컨텍스트 확장 (Phase 3: 중복 제거 및 최적화)"""
        try:
            # 1단계: Small 청크로 정확한 검색
            small_results = self.vectorstore.similarity_search_with_score(
                query, k=top_k * 2  # 더 많은 후보 확보
            )
            
            if not small_results:
                return []
            
            # 2단계: 부모 청크로 컨텍스트 확장 (정교화)
            expanded_results = []
            processed_parents = set()
            parent_count = 0
            content_hashes = set()  # 중복 제거용 콘텐츠 해시
            
            for doc, score in small_results:
                # 콘텐츠 해시로 중복 체크
                content_hash = self._get_content_hash(doc.page_content)
                if content_hash in content_hashes:
                    continue  # 중복된 콘텐츠는 건너뛰기
                
                # Small 청크 추가
                expanded_results.append((doc, score))
                content_hashes.add(content_hash)
                
                # 부모 청크 확장 (최대 개수 제한)
                if parent_count >= max_parents:
                    continue
                
                parent_id = doc.metadata.get("parent_chunk_id")
                if parent_id and parent_id not in processed_parents:
                    parent_doc = self._get_parent_chunk(parent_id)
                    if parent_doc:
                        # 유사도 체크 (0.9 이상이면 중복으로 간주)
                        if self._is_similar_content(doc.page_content, parent_doc.page_content, threshold=0.9):
                            continue
                        
                        # 부모 청크의 일부만 포함 (자식 청크 전후 ±partial_context_size자)
                        partial_parent = self._extract_partial_context(
                            parent_doc.page_content, 
                            doc.page_content, 
                            context_size=partial_context_size
                        )
                        
                        if partial_parent and partial_parent != doc.page_content:
                            # 부분 부모 청크 생성
                            partial_parent_doc = Document(
                                page_content=partial_parent,
                                metadata={
                                    **parent_doc.metadata,
                                    "expanded_from": doc.metadata.get("chunk_id", ""),
                                    "is_partial_parent": True
                                }
                            )
                            
                            # 부모는 약간 낮은 점수로 추가
                            expanded_results.append((partial_parent_doc, score * 0.8))
                            processed_parents.add(parent_id)
                            parent_count += 1
            
            # 3단계: 최종 중복 제거 및 상위 결과 반환
            expanded_results.sort(key=lambda x: x[1], reverse=True)
            final_results = self._deduplicate_by_similarity(expanded_results, threshold=0.85)
            
            return [doc for doc, score in final_results[:top_k]]
            
        except Exception as e:
            print(f"Small-to-Large 검색 중 오류: {e}")
            # 폴백: 기본 검색
            return self.vectorstore.similarity_search(query, k=top_k)
    
    def _get_content_hash(self, content: str) -> str:
        """콘텐츠 해시 생성 (중복 제거용)"""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_similar_content(self, content1: str, content2: str, threshold: float = 0.9) -> bool:
        """두 콘텐츠의 유사도 체크 (Jaccard 유사도)"""
        if not content1 or not content2:
            return False
        
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if len(words1) == 0 or len(words2) == 0:
            return False
        
        intersection = words1 & words2
        union = words1 | words2
        
        similarity = len(intersection) / len(union)
        return similarity >= threshold
    
    def _extract_partial_context(self, parent_content: str, child_content: str, context_size: int = 200) -> str:
        """부모 청크에서 자식 청크 전후 컨텍스트만 추출"""
        if child_content not in parent_content:
            return parent_content[:context_size * 2]  # 찾지 못하면 앞부분만
        
        # 자식 청크의 위치 찾기
        child_start = parent_content.index(child_content)
        child_end = child_start + len(child_content)
        
        # 전후 컨텍스트 추출
        context_start = max(0, child_start - context_size)
        context_end = min(len(parent_content), child_end + context_size)
        
        return parent_content[context_start:context_end]
    
    def _deduplicate_by_similarity(self, results: List[Tuple], threshold: float = 0.85) -> List[Tuple]:
        """유사도 기반 중복 제거"""
        if not results:
            return []
        
        deduplicated = []
        seen_contents = []
        
        for doc, score in results:
            content = doc.page_content
            
            # 기존 콘텐츠와 유사도 체크
            is_duplicate = False
            for seen_content in seen_contents:
                if self._is_similar_content(content, seen_content, threshold):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append((doc, score))
                seen_contents.append(content)
        
        return deduplicated
    
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
