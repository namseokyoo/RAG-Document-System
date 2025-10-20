import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from langchain.schema import Document
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import os
from utils.reranker import get_reranker


class VectorStoreManager:
    def __init__(self, persist_directory: str = "data/chroma_db",
                 embedding_api_type: str = "ollama",
                 embedding_base_url: str = "http://localhost:11434",
                 embedding_model: str = "nomic-embed-text",
                 embedding_api_key: str = ""):
        self.persist_directory = persist_directory
        self.embedding_api_type = embedding_api_type
        self.embedding_base_url = embedding_base_url
        self.embedding_model = embedding_model
        self.embedding_api_key = embedding_api_key
        
        # 임베딩 초기화 - API 타입에 따라 다른 클라이언트 사용
        self.embeddings = self._create_embeddings()
        
        # ChromaDB 클라이언트 초기화 - 간단한 방식 사용
        os.makedirs(persist_directory, exist_ok=True)
        
        # Chroma 벡터스토어 초기화 - 직접 persist_directory 사용
        self.vectorstore = None
        self._init_vectorstore()
    
    def _create_embeddings(self):
        """API 타입에 따라 적절한 임베딩 클라이언트 생성"""
        if self.embedding_api_type == "ollama":
            # Ollama 로컬 서버
            return OllamaEmbeddings(
                base_url=self.embedding_base_url,
                model=self.embedding_model
            )
        elif self.embedding_api_type in ["openai", "openai-compatible"]:
            # OpenAI 또는 OpenAI 호환 API
            kwargs = {
                "model": self.embedding_model
            }
            
            # OpenAI 공식 API가 아닌 경우 base_url 설정
            if self.embedding_api_type == "openai-compatible":
                kwargs["base_url"] = self.embedding_base_url
            
            # API 키가 있는 경우만 설정
            if self.embedding_api_key:
                kwargs["api_key"] = self.embedding_api_key
            else:
                kwargs["api_key"] = "not-needed"  # 일부 로컬 API는 키 불필요
            
            return OpenAIEmbeddings(**kwargs)
        else:
            raise ValueError(f"지원하지 않는 임베딩 API 타입: {self.embedding_api_type}")
    
    def _init_vectorstore(self):
        """벡터스토어 초기화 또는 로드"""
        try:
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_name="documents"
            )
        except Exception as e:
            print(f"벡터스토어 초기화 실패: {e}")
            raise
    
    def add_documents(self, documents: List[Document]) -> bool:
        """문서를 벡터스토어에 추가"""
        try:
            self.vectorstore.add_documents(documents)
            return True
        except Exception as e:
            print(f"문서 추가 실패: {e}")
            return False
    
    def similarity_search(self, query: str, k: int = 3) -> List[Document]:
        """유사도 검색"""
        try:
            results = self.vectorstore.similarity_search(query, k=k)
            return results
        except Exception as e:
            print(f"검색 실패: {e}")
            return []
    
    def similarity_search_with_score(self, query: str, k: int = 3) -> List[tuple]:
        """유사도 검색 (점수 포함)"""
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            return results
        except Exception as e:
            print(f"검색 실패: {e}")
            return []
    
    def similarity_search_with_rerank(
        self,
        query: str,
        top_k: int = 3,
        initial_k: int = 20,
        reranker_model: str = "multilingual-mini"
    ) -> List[tuple]:
        """
        Re-ranker를 사용한 유사도 검색
        
        Args:
            query: 검색 쿼리
            top_k: 최종 반환할 문서 수
            initial_k: Re-ranking할 초기 후보 수
            reranker_model: Re-ranker 모델 이름
        
        Returns:
            (Document, rerank_score) 튜플 리스트
        """
        try:
            # 1단계: Vector Search로 초기 후보 추출
            candidates = self.vectorstore.similarity_search_with_score(query, k=initial_k)
            
            if not candidates:
                return []
            
            # 2단계: Re-ranker 초기화
            reranker = get_reranker(model_name=reranker_model)
            
            # 3단계: 문서 재순위화
            docs_for_rerank = []
            for doc, vector_score in candidates:
                doc_dict = {
                    "page_content": doc.page_content,
                    "metadata": doc.metadata,
                    "vector_score": vector_score,
                    "document": doc  # 원본 Document 객체 보존
                }
                docs_for_rerank.append(doc_dict)
            
            reranked = reranker.rerank(query, docs_for_rerank, top_k=top_k)
            
            # 4단계: (Document, rerank_score) 형식으로 반환
            results = []
            for doc_dict in reranked:
                results.append((
                    doc_dict["document"],
                    doc_dict.get("rerank_score", 0)
                ))
            
            return results
            
        except Exception as e:
            print(f"Re-ranking 검색 실패: {e}")
            # 실패 시 일반 검색으로 폴백
            return self.vectorstore.similarity_search_with_score(query, k=top_k)
    
    def get_documents_list(self) -> List[Dict[str, Any]]:
        """저장된 문서 목록 조회 (메타데이터 기반, 임베딩 불필요)"""
        try:
            collection = self.vectorstore._collection
            data = collection.get(include=["metadatas"])  # ids, metadatas, documents 등 중 메타데이터만 로드
            metadatas = data.get("metadatas", []) or []

            file_dict: Dict[str, Dict[str, Any]] = {}
            for meta in metadatas:
                if not isinstance(meta, dict):
                    continue
                file_name = meta.get("file_name", "Unknown")
                if file_name not in file_dict:
                    file_dict[file_name] = {
                        "file_name": file_name,
                        "file_type": meta.get("file_type", "Unknown"),
                        "upload_time": meta.get("upload_time", "Unknown"),
                        "chunk_count": 0,
                    }
                file_dict[file_name]["chunk_count"] += 1

            return list(file_dict.values())
        except Exception as e:
            print(f"문서 목록 조회 실패: {e}")
            return []
    
    def delete_document(self, file_name: str) -> bool:
        """특정 파일의 모든 청크 삭제"""
        try:
            # 해당 파일의 모든 문서 찾기
            all_docs = self.vectorstore.similarity_search("", k=1000)
            ids_to_delete = []
            
            for i, doc in enumerate(all_docs):
                if doc.metadata.get("file_name") == file_name:
                    # ChromaDB의 ID는 내부적으로 관리되므로 직접 액세스가 필요
                    # 일단은 파일명으로 필터링하여 삭제
                    pass
            
            # ChromaDB에서는 delete 메서드 사용
            # 메타데이터 필터를 사용하여 삭제
            collection = self.vectorstore._collection
            collection.delete(where={"file_name": file_name})
            
            return True
        except Exception as e:
            print(f"문서 삭제 실패: {e}")
            return False
    
    def get_vectorstore(self):
        """벡터스토어 반환 (RAG 체인에서 사용)"""
        return self.vectorstore
    
    def update_embeddings(self, embedding_api_type: str, embedding_base_url: str, 
                          embedding_model: str, embedding_api_key: str = ""):
        """임베딩 설정 업데이트"""
        self.embedding_api_type = embedding_api_type
        self.embedding_base_url = embedding_base_url
        self.embedding_model = embedding_model
        self.embedding_api_key = embedding_api_key
        
        # 임베딩 재생성
        self.embeddings = self._create_embeddings()
        self._init_vectorstore()

