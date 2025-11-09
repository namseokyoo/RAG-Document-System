import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from langchain.schema import Document
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from utils.request_embeddings import RequestEmbeddings
import os
from utils.reranker import get_reranker
import re

# BM25 임포트 (선택적)
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("[VectorStore][WARN] rank-bm25 미설치: 하이브리드 검색에서 키워드 검색 미사용")
    print("[VectorStore] 설치: pip install rank-bm25")


class VectorStoreManager:
    def __init__(self, persist_directory: str = "data/chroma_db",
                 embedding_api_type: str = "ollama",
                 embedding_base_url: str = "http://localhost:11434",
                 embedding_model: str = "mxbai-embed-large",
                 embedding_api_key: str = "",
                 shared_db_path: str = None,
                 shared_db_enabled: bool = False):
        # 개인 DB 설정
        self.persist_directory = persist_directory
        self.embedding_api_type = embedding_api_type
        self.embedding_base_url = embedding_base_url
        self.embedding_model = embedding_model
        self.embedding_api_key = embedding_api_key
        self._embedding_dimension = None  # 캐시된 임베딩 차원

        # 공유 DB 설정
        self.shared_db_path = shared_db_path
        self.shared_db_enabled = shared_db_enabled and shared_db_path is not None

        # 임베딩 초기화 - API 타입에 따라 다른 클라이언트 사용
        self.embeddings = self._create_embeddings()

        # 개인 DB 초기화
        os.makedirs(persist_directory, exist_ok=True)
        self.vectorstore = None  # 개인 DB
        self._init_vectorstore()

        # 공유 DB 초기화 (활성화된 경우)
        self.shared_vectorstore = None
        if self.shared_db_enabled:
            try:
                os.makedirs(shared_db_path, exist_ok=True)
                self._init_shared_vectorstore()
                print(f"[VectorStore] 공유 DB 초기화 완료: {shared_db_path}")
            except Exception as e:
                print(f"[VectorStore][ERROR] 공유 DB 초기화 실패: {e}")
                self.shared_db_enabled = False

        # BM25 초기화 (개인 DB)
        if BM25_AVAILABLE:
            self.bm25_corpus = []
            self.bm25_tokenized_corpus = []
            self.bm25 = None
            self.doc_ids = []
            self._load_bm25_corpus()

            # 공유 DB용 BM25 초기화
            self.shared_bm25_corpus = []
            self.shared_bm25_tokenized_corpus = []
            self.shared_bm25 = None
            self.shared_doc_ids = []
            if self.shared_db_enabled:
                self._load_shared_bm25_corpus()
        else:
            self.bm25 = None
            self.shared_bm25 = None

        # Phase 3: 엔티티 인덱스 초기화
        self.entity_index: Dict[str, Dict[str, List[str]]] = {}
        self.entity_index_file = os.path.join(os.path.dirname(persist_directory), "entity_index.json")
        self._load_entity_index()
    
    def _create_embeddings(self):
        """API 타입에 따라 적절한 임베딩 클라이언트 생성"""
        if self.embedding_api_type == "ollama":
            # Ollama 로컬 서버
            return OllamaEmbeddings(
                base_url=self.embedding_base_url,
                model=self.embedding_model
            )
        elif self.embedding_api_type == "request":
            # Request 방식 (메모리 효율적)
            # 내부 API 타입을 명시적으로 지정하지 않으면 RequestEmbeddings에서 자동 감지
            # 초기 검증을 건너뛰고 실제 임베딩 호출 시 타입 결정
            embeddings = RequestEmbeddings(
                base_url=self.embedding_base_url,
                model=self.embedding_model,
                timeout=60,
                skip_validation=True  # 초기 검증 건너뛰기
            )
            
            # API 키가 있는 경우 설정
            if self.embedding_api_key:
                embeddings.set_api_key(self.embedding_api_key)
            
            return embeddings
        elif self.embedding_api_type in ["openai", "openai-compatible"]:
            # 폐쇄망 환경에서는 OpenAI 임베딩 사용 시 tiktoken 오류 발생 가능
            # 안전을 위해 Ollama로 폴백
            print("[VectorStore][WARN] 폐쇄망: OpenAI 임베딩 대신 Ollama 임베딩 사용")
            print(f"[VectorStore] 설정 변경: {self.embedding_api_type} -> ollama")
            
            return OllamaEmbeddings(
                base_url=self.embedding_base_url,
                model=self.embedding_model
            )
        else:
            raise ValueError(f"지원하지 않는 임베딩 API 타입: {self.embedding_api_type}")
    
    def _init_vectorstore(self):
        """개인 DB 벡터스토어 초기화 또는 로드"""
        try:
            # 먼저 현재 임베딩 차원 확인
            current_dimension = self._get_embedding_dimension()
            print(f"[VectorStore] 임베딩 모델 차원: {current_dimension}")

            # 기존 벡터 스토어가 있는지 확인
            if os.path.exists(self.persist_directory):
                existing_dimension = self._check_existing_dimension(self.persist_directory)
                if existing_dimension is not None and existing_dimension != current_dimension:
                    error_msg = (
                        f"❌ 임베딩 차원 불일치 오류!\n\n"
                        f"기존 벡터 스토어의 임베딩 차원: {existing_dimension}\n"
                        f"현재 설정된 임베딩 모델의 차원: {current_dimension}\n\n"
                        f"해결 방법:\n"
                        f"1. 기존 벡터 스토어 삭제 후 재생성:\n"
                        f"   - {self.persist_directory} 폴더 삭제\n"
                        f"2. 임베딩 모델을 기존과 동일한 모델로 변경:\n"
                        f"   - 설정에서 임베딩 모델 확인\n"
                    )
                    print(error_msg)
                    raise ValueError(error_msg)

            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_name="documents"
            )
        except ValueError:
            # 차원 불일치 오류는 그대로 전달
            raise
        except Exception as e:
            print(f"[VectorStore][ERROR] 초기화 실패: {e}")
            raise

    def _init_shared_vectorstore(self):
        """공유 DB 벡터스토어 초기화 또는 로드"""
        try:
            # 공유 DB 경로가 유효한지 확인
            if not self.shared_db_path or not os.path.exists(self.shared_db_path):
                raise ValueError(f"공유 DB 경로가 유효하지 않습니다: {self.shared_db_path}")

            # 기존 벡터 스토어가 있는지 확인 (공유 DB는 "shared_documents" 컬렉션 사용)
            existing_dimension = self._check_existing_dimension(self.shared_db_path, collection_name="shared_documents")
            current_dimension = self._get_embedding_dimension()

            if existing_dimension is not None and existing_dimension != current_dimension:
                error_msg = (
                    f"❌ 공유 DB 임베딩 차원 불일치!\n\n"
                    f"공유 DB의 임베딩 차원: {existing_dimension}\n"
                    f"현재 설정된 임베딩 모델의 차원: {current_dimension}\n\n"
                    f"관리자에게 문의하여 임베딩 모델을 통일해주세요.\n"
                )
                print(error_msg)
                raise ValueError(error_msg)

            self.shared_vectorstore = Chroma(
                persist_directory=self.shared_db_path,
                embedding_function=self.embeddings,
                collection_name="shared_documents"
            )
            print(f"[VectorStore] 공유 DB 연결 성공: {self.shared_db_path}")

        except Exception as e:
            print(f"[VectorStore][ERROR] 공유 DB 초기화 실패: {e}")
            raise
    
    def _get_embedding_dimension(self) -> int:
        """현재 임베딩 모델의 차원 확인"""
        # 캐시된 차원이 있으면 반환
        if self._embedding_dimension is not None:
            return self._embedding_dimension
        
        try:
            # 테스트 텍스트로 임베딩 생성하여 차원 확인
            test_text = "test"
            embedding = self.embeddings.embed_query(test_text)
            dimension = len(embedding)
            self._embedding_dimension = dimension
            return dimension
        except Exception as e:
            print(f"[VectorStore][WARN] 임베딩 차원 확인 실패: {e}")
            # 기본값 반환 (일반적인 차원)
            self._embedding_dimension = 768
            return 768
    
    def _check_existing_dimension(self, persist_directory: str, collection_name: str = "documents") -> Optional[int]:
        """기존 벡터 스토어의 임베딩 차원 확인"""
        try:
            # chromadb는 이미 상단에서 import됨
            client = chromadb.PersistentClient(path=persist_directory)
            collection = client.get_or_create_collection(name=collection_name)
            
            # 기존 데이터가 있는지 확인
            count = collection.count()
            if count == 0:
                return None
            
            # 샘플 하나 가져와서 차원 확인
            sample = collection.peek(limit=1)
            embeddings = sample.get("embeddings")
            
            if not embeddings:
                return None
                
            # embeddings가 리스트이고 비어있지 않은지 확인
            if not isinstance(embeddings, list) or len(embeddings) == 0:
                return None
            
            # 첫 번째 임베딩 벡터 가져오기
            first_embedding = embeddings[0]
            
            # numpy 배열인 경우 - 안전하게 처리
            import numpy as np
            if isinstance(first_embedding, np.ndarray):
                try:
                    shape = first_embedding.shape
                    if len(shape) > 0:
                        return int(shape[0])
                    return None
                except Exception:
                    pass
            
            # numpy 배열인지 확인 (hasattr 사용하되 boolean 비교 피하기)
            if hasattr(first_embedding, 'shape'):
                try:
                    shape = first_embedding.shape
                    # shape가 tuple인지 확인하여 안전하게 처리
                    if isinstance(shape, tuple) and len(shape) > 0:
                        return int(shape[0])
                except Exception:
                    pass
            
            # 리스트나 튜플인 경우
            if isinstance(first_embedding, (list, tuple)):
                return len(first_embedding)
            
            # 기타 시퀀스 타입
            try:
                return len(first_embedding)
            except:
                return None
        except Exception as e:
            # 조용히 실패 처리 (기존 데이터가 없거나 비어있을 수 있음)
            # 경고 메시지는 출력하지 않음
            return None
    
    def _load_bm25_corpus(self):
        """개인 DB의 저장된 문서를 로드하여 BM25 인덱스 구축"""
        try:
            collection = self.vectorstore._collection
            # get()은 파라미터 없이 호출하면 모든 데이터 반환
            data = collection.get()

            if data and data.get("documents"):
                documents = data.get("documents", [])
                self.doc_ids = data.get("ids", [])

                # 문서를 토큰화하여 BM25 인덱스 구축
                self.bm25_corpus = documents
                self.bm25_tokenized_corpus = [self._tokenize(doc) for doc in documents]

                if self.bm25_tokenized_corpus:
                    self.bm25 = BM25Okapi(self.bm25_tokenized_corpus)
                    print(f"[VectorStore] BM25 인덱스 구축 완료: {len(documents)}개 문서")
        except Exception as e:
            print(f"[VectorStore][WARN] BM25 로드 실패: {e}")
            self.bm25 = None

    def _load_shared_bm25_corpus(self):
        """공유 DB의 저장된 문서를 로드하여 BM25 인덱스 구축"""
        try:
            if not self.shared_vectorstore:
                return

            collection = self.shared_vectorstore._collection
            data = collection.get()

            if data and data.get("documents"):
                documents = data.get("documents", [])
                self.shared_doc_ids = data.get("ids", [])

                # 문서를 토큰화하여 BM25 인덱스 구축
                self.shared_bm25_corpus = documents
                self.shared_bm25_tokenized_corpus = [self._tokenize(doc) for doc in documents]

                if self.shared_bm25_tokenized_corpus:
                    self.shared_bm25 = BM25Okapi(self.shared_bm25_tokenized_corpus)
                    print(f"[VectorStore] 공유 DB BM25 인덱스 구축 완료: {len(documents)}개 문서")
        except Exception as e:
            print(f"[VectorStore][WARN] 공유 DB BM25 로드 실패: {e}")
            self.shared_bm25 = None
    
    def add_documents(self, documents: List[Document], extract_entities: bool = False, llm=None, target_db: str = "personal") -> bool:
        """
        문서를 벡터스토어에 추가하고 BM25 및 엔티티 인덱스 업데이트

        Args:
            documents: 추가할 문서 리스트
            extract_entities: 엔티티 추출 여부
            llm: LLM 객체 (엔티티 추출 시 필요)
            target_db: 대상 DB ("personal" | "shared")

        Returns:
            성공 여부
        """
        try:
            # 차원 확인 (실패 시 명확한 에러 메시지 제공)
            if not documents:
                print("[VectorStore][WARN] 추가할 문서가 없습니다.")
                return False

            # 공유 DB 선택 시 활성화 여부 확인
            if target_db == "shared" and not self.shared_db_enabled:
                raise ValueError("공유 DB가 비활성화되어 있습니다. 개인 DB만 사용 가능합니다.")

            # 임베딩 차원 검증
            try:
                test_dim = self._get_embedding_dimension()
            except Exception as e:
                error_msg = f"임베딩 차원 확인 실패: {e}\n임베딩 모델 설정을 확인해주세요."
                print(f"[VectorStore][ERROR] 문서 추가 실패: {error_msg}")
                raise ValueError(error_msg)

            # 대상 DB 선택
            if target_db == "shared":
                self.shared_vectorstore.add_documents(documents)
                db_name = "공유 DB"
            else:
                self.vectorstore.add_documents(documents)
                db_name = "개인 DB"

            # BM25 인덱스 업데이트
            if BM25_AVAILABLE:
                if target_db == "shared" and self.shared_bm25 is not None:
                    for doc in documents:
                        self.shared_bm25_corpus.append(doc.page_content)
                        self.shared_bm25_tokenized_corpus.append(self._tokenize(doc.page_content))
                        self.shared_doc_ids.append(doc.metadata.get("source", ""))

                    # BM25 모델 재구축
                    if self.shared_bm25_tokenized_corpus:
                        self.shared_bm25 = BM25Okapi(self.shared_bm25_tokenized_corpus)
                        print(f"[VectorStore] 공유 DB BM25 인덱스 업데이트: 총 {len(self.shared_bm25_corpus)}개 문서")

                elif target_db == "personal" and self.bm25 is not None:
                    for doc in documents:
                        self.bm25_corpus.append(doc.page_content)
                        self.bm25_tokenized_corpus.append(self._tokenize(doc.page_content))
                        self.doc_ids.append(doc.metadata.get("source", ""))

                    # BM25 모델 재구축
                    if self.bm25_tokenized_corpus:
                        self.bm25 = BM25Okapi(self.bm25_tokenized_corpus)
                        print(f"[VectorStore] 개인 DB BM25 인덱스 업데이트: 총 {len(self.bm25_corpus)}개 문서")

            # Phase 3: 엔티티 인덱스 업데이트 (선택적, 개인 DB만)
            if extract_entities and llm is not None and target_db == "personal":
                self._update_entity_index(documents, llm)

            print(f"[VectorStore] {db_name}에 문서 추가 완료: {len(documents)}개")
            return True

        except ValueError as e:
            # 차원 관련 오류는 그대로 전달
            raise
        except Exception as e:
            error_msg = str(e)
            if "Inconsistent dimensions" in error_msg or "dimension" in error_msg.lower():
                error_msg = (
                    f"임베딩 차원 불일치 오류!\n\n"
                    f"기존 벡터 스토어와 현재 임베딩 모델의 차원이 일치하지 않습니다.\n\n"
                    f"해결 방법:\n"
                    f"1. 벡터 스토어 초기화: {self.persist_directory} 폴더 삭제\n"
                    f"2. 임베딩 모델을 기존과 동일하게 설정\n\n"
                    f"원본 오류: {e}"
                )
            print(f"[VectorStore][ERROR] 문서 추가 실패: {error_msg}")
            raise ValueError(error_msg)

    def delete_documents_by_file_name(self, file_name: str, target_db: str = "personal") -> bool:
        """
        특정 파일명의 모든 청크를 ChromaDB에서 삭제

        Args:
            file_name: 삭제할 파일명
            target_db: 대상 DB ("personal" | "shared")

        Returns:
            성공 여부
        """
        try:
            # 대상 DB 선택
            if target_db == "shared":
                if not self.shared_db_enabled:
                    print(f"[VectorStore] 공유 DB가 비활성화되어 있습니다")
                    return False
                collection = self.shared_vectorstore._collection
                db_name = "공유 DB"
            else:
                collection = self.vectorstore._collection
                db_name = "개인 DB"

            # file_name으로 필터링하여 해당 청크 ID 가져오기
            results = collection.get(
                where={"file_name": file_name}
            )

            if not results or not results['ids']:
                print(f"[VectorStore] {db_name}에 파일 '{file_name}'의 청크가 없습니다")
                return False

            chunk_ids = results['ids']
            chunk_count = len(chunk_ids)

            # Chroma에서 청크 삭제
            collection.delete(ids=chunk_ids)

            # BM25 인덱스 재구축 (전체)
            if BM25_AVAILABLE:
                if target_db == "shared" and self.shared_bm25 is not None:
                    self._load_shared_bm25_corpus()
                elif target_db == "personal" and self.bm25 is not None:
                    self._load_bm25_corpus()

            print(f"[VectorStore] {db_name}에서 파일 '{file_name}' 삭제 완료: {chunk_count}개 청크")
            return True

        except Exception as e:
            print(f"[VectorStore][ERROR] 파일 삭제 실패 ({file_name}): {e}")
            import traceback
            traceback.print_exc()
            return False

    def similarity_search(self, query: str, k: int = 3) -> List[Document]:
        """유사도 검색"""
        try:
            results = self.vectorstore.similarity_search(query, k=k)
            return results
        except Exception as e:
            print(f"[VectorStore][ERROR] 검색 실패: {e}")
            return []
    
    def similarity_search_with_score(self, query: str, k: int = 3) -> List[tuple]:
        """유사도 검색 (점수 포함)"""
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            return results
        except Exception as e:
            print(f"[VectorStore][ERROR] 검색 실패: {e}")
            return []

    # ----------------- 하이브리드 검색 -----------------
    def _tokenize(self, text: str, preserve_numbers: bool = True) -> List[str]:
        """텍스트 토큰화 (정확도 향상 v2: stopwords 제거, 숫자/단위 보존)"""
        if not text:
            return []
        
        # 한국어 stopwords (조사 및 불용어)
        korean_stopwords = [
            '을', '를', '이', '가', '은', '는', '에', '에서', '로', '으로', 
            '와', '과', '의', '도', '만', '부터', '까지', '처럼', '같이',
            '한테', '에게', '께', '보다', '마다', '조차', '마저', '까지',
            '이라', '라', '이야', '야', '이다', '다', '어요', '아요', '해요',
            '습니다', '습니다', '어', '아', '지', '네', '어서', '아서',
            '그', '것', '수', '있는', '있', '없는', '없', '로', '및', '그리고'
        ]
        
        # 영어 stopwords
        english_stopwords = [
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their'
        ]
        
        all_stopwords = set(korean_stopwords + english_stopwords)
        
        # 숫자 및 단위 패턴 (보존 필요)
        number_pattern = r'\d+\.?\d*'  # 숫자 (소수점 포함)
        unit_pattern = r'[%°C℃℉kmhmgdlnmlμΩVAmWkg]+\b'  # 단위 기호
        
        # 토큰화: 영문, 한글, 숫자 모두 포함
        tokens = re.findall(r'[\w가-힣]+|\d+\.?\d*[%°C℃℉kmhmgdlnmlμΩVAmWkg]*', text.lower())
        
        cleaned_tokens = []
        for token in tokens:
            # 숫자 포함 토큰은 보존 (preserve_numbers=True인 경우)
            if preserve_numbers and re.search(number_pattern, token):
                cleaned_tokens.append(token)
                continue
            
            # 단위만 있는 경우도 보존
            if any(unit in token for unit in ['%', '°', '℃', '℉']):
                cleaned_tokens.append(token)
                continue
            
            # stopwords 제거
            if token in all_stopwords:
                continue
            
            # 너무 짧은 토큰 제거
            if len(token) <= 1:
                continue
            
            # 조사로 끝나는 토큰에서 조사 제거 (한국어 처리)
            cleaned_token = token
            for stopword in korean_stopwords:
                if cleaned_token.endswith(stopword) and len(cleaned_token) > len(stopword):
                    cleaned_token = cleaned_token[:-len(stopword)]
                    break
            
            if len(cleaned_token) > 1:
                cleaned_tokens.append(cleaned_token)
        
        return cleaned_tokens

    def similarity_search_hybrid(self, query: str, initial_k: int = 40,
                                 vector_weight: float = 0.6, keyword_weight: float = 0.4,
                                 top_k: int = 10) -> List[tuple]:
        """하이브리드 검색: 벡터 + BM25"""
        try:
            # 1단계: 벡터 검색으로 후보 확보
            vector_candidates = self.vectorstore.similarity_search_with_score(query, k=initial_k)
            neg_raw_count = 0
            
            if not vector_candidates:
                # 벡터 검색 실패 시 BM25 단독 검색 폴백
                return self._bm25_only_search(query, top_k)
            
            # 2단계: BM25 검색
            if BM25_AVAILABLE and self.bm25 is not None:
                # BM25 점수 계산
                query_tokens = self._tokenize(query)
                bm25_scores = self.bm25.get_scores(query_tokens)
                
                # 3단계: 문서 ID 매핑 생성
                doc_id_to_idx = {}
                for idx, doc_id in enumerate(self.doc_ids):
                    doc_id_to_idx[doc_id] = idx
                
                # 4단계: RRF(Reciprocal Rank Fusion)로 결합 (스케일 불변, 견고)
                # 벡터 순위 (거리 오름차순으로 이미 정렬되어 있다고 가정)
                vector_rank: Dict[str, int] = {}
                for r, (doc, _score) in enumerate(vector_candidates, start=1):
                    doc_id = doc.metadata.get("source", "")
                    if doc_id and doc_id not in vector_rank:
                        vector_rank[doc_id] = r

                # BM25 순위
                bm25_rank: Dict[str, int] = {}
                bm25_sorted = sorted(list(enumerate(bm25_scores)), key=lambda x: x[1], reverse=True)
                for r, (idx, _s) in enumerate(bm25_sorted, start=1):
                    if 0 <= idx < len(self.doc_ids):
                        bm25_doc_id = self.doc_ids[idx]
                        if bm25_doc_id and bm25_doc_id not in bm25_rank:
                            bm25_rank[bm25_doc_id] = r

                # RRF 계산
                from collections import defaultdict
                rrf_scores: Dict[str, float] = defaultdict(float)
                C = 60.0

                all_ids = set(vector_rank.keys()) | set(bm25_rank.keys())
                for did in all_ids:
                    if did in vector_rank:
                        rrf_scores[did] += 1.0 / (C + vector_rank[did])
                    if did in bm25_rank:
                        rrf_scores[did] += 1.0 / (C + bm25_rank[did])

                # 상위 top_k 문서로 Document 구성
                ranked_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

                # 컬렉션 데이터 로드(문서 재구성용)
                coll = self.vectorstore._collection
                data = coll.get()
                docs_raw = data.get("documents", [])
                metas_raw = data.get("metadatas", [])
                id_to_index = {idv: i for i, idv in enumerate(data.get("ids", []) or [])}

                results_rrf: List[tuple] = []
                for did, score in ranked_ids:
                    # 우선 벡터 후보에서 Document를 찾고, 없으면 컬렉션에서 재구성
                    doc_obj: Optional[Document] = None
                    for d, _ in vector_candidates:
                        if d.metadata.get("source", "") == did:
                            doc_obj = d
                            break
                    if doc_obj is None and did in id_to_index:
                        idx = id_to_index[did]
                        if 0 <= idx < len(docs_raw):
                            from langchain.schema import Document as LC_Document
                            meta = metas_raw[idx] if idx < len(metas_raw) else {}
                            doc_obj = LC_Document(page_content=docs_raw[idx], metadata=meta or {})
                    if doc_obj is not None:
                        results_rrf.append((doc_obj, float(score)))

                # 관측 로그 (디버그)
                try:
                    print(f"[Hybrid-RRF] query='{query[:64]}...' candidates={{'vector': {len(vector_candidates)}, 'bm25': {len(bm25_scores)}}}, top_k={top_k}")
                except Exception:
                    pass
                return results_rrf
            else:
                # BM25 사용 불가 시 개선된 정규화로 폴백
                combined = []
                all_scores = [float(score) for _, score in vector_candidates]
                
                if all_scores:
                    min_score = min(all_scores)
                    max_score = max(all_scores)
                    score_range = max_score - min_score if max_score > min_score else 1.0
                    
                    for doc, score in vector_candidates:
                        raw_score = float(score)
                        
                        # 하이퍼볼릭 변환
                        if raw_score >= 0:
                            sim = 1.0 / (1.0 + raw_score)
                        else:
                            sim = 0.0
                            neg_raw_count += 1
                        
                        # Min-Max 정규화 보정
                        if score_range > 0:
                            normalized = (max_score - raw_score) / score_range
                            sim = 0.7 * sim + 0.3 * normalized
                        
                        sim = max(0.0, min(1.0, sim))
                        combined.append((doc, sim))
                else:
                    # 점수가 없는 경우 기본값
                    for doc, score in vector_candidates:
                        combined.append((doc, 0.5))
                
                combined.sort(key=lambda x: x[1], reverse=True)
                try:
                    print(f"[Hybrid-VectorOnly] query='{query[:64]}...' neg_raw_clamped={neg_raw_count}, top_k={top_k}")
                except Exception:
                    pass
                return combined[:top_k]
            
        except Exception as e:
            print(f"[VectorStore][ERROR] 하이브리드 검색 실패: {e}")
            # 폴백: BM25 단독 검색 우선, 실패 시 벡터 검색
            try:
                return self._bm25_only_search(query, top_k)
            except Exception:
                results = self.vectorstore.similarity_search_with_score(query, k=top_k)
                # 개선된 정규화 적용
                normalized_results = []
                all_scores = [float(score) for _, score in results]
                
                if all_scores:
                    min_score = min(all_scores)
                    max_score = max(all_scores)
                    score_range = max_score - min_score if max_score > min_score else 1.0
                    
                    for doc, score in results:
                        raw_score = float(score)
                        if raw_score >= 0:
                            sim = 1.0 / (1.0 + raw_score)
                        else:
                            sim = 0.0
                        
                        if score_range > 0:
                            normalized = (max_score - raw_score) / score_range
                            sim = 0.7 * sim + 0.3 * normalized
                        
                        sim = max(0.0, min(1.0, sim))
                        normalized_results.append((doc, sim))
                else:
                    normalized_results = [(doc, 0.5) for doc, _ in results]
                
                return normalized_results

    def _bm25_only_search(self, query: str, top_k: int = 10) -> List[tuple]:
        """BM25 단독 검색 (임베딩 실패 시 폴백)"""
        if not (BM25_AVAILABLE and self.bm25 is not None):
            return []
        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        if not scores:
            return []
        # 상위 인덱스 선택
        ranked = sorted(list(enumerate(scores)), key=lambda x: x[1], reverse=True)[:max(top_k, 1)]
        # 컬렉션에서 문서 로드
        coll = self.vectorstore._collection
        data = coll.get()
        docs = data.get("documents", [])
        metas = data.get("metadatas", [])
        results = []
        max_score = max(scores) if scores else 1.0
        for idx, s in ranked:
            if idx < len(docs):
                from langchain.schema import Document
                meta = metas[idx] if idx < len(metas) else {}
                doc = Document(page_content=docs[idx], metadata=meta or {})
                # 0~1 정규화 점수
                norm = float(s) / max_score if max_score > 0 else 0.0
                results.append((doc, norm))
        return results

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
            # 1단계: Hybrid Search (Vector + BM25)로 초기 후보 추출
            # 하이브리드 검색이 가능하면 사용, 아니면 벡터 검색으로 폴백
            if hasattr(self, 'similarity_search_hybrid') and self.bm25 is not None:
                candidates = self.similarity_search_hybrid(
                    query,
                    initial_k=initial_k * 2,  # 하이브리드는 더 많은 후보 필요
                    top_k=initial_k
                )
            else:
                # BM25 없으면 순수 벡터 검색으로 폴백
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
            print(f"[VectorStore][ERROR] Re-ranking 검색 실패: {e}")
            # 실패 시 일반 검색으로 폴백
            return self.vectorstore.similarity_search_with_score(query, k=top_k)
    
    def get_documents_list(self, db_type: str = "both") -> List[Dict[str, Any]]:
        """
        저장된 문서 목록 조회 (메타데이터 기반, 임베딩 불필요)

        Args:
            db_type: DB 타입 ("personal" | "shared" | "both")

        Returns:
            문서 목록 리스트 (각 항목에 db_type 포함)
        """
        try:
            file_dict: Dict[str, Dict[str, Any]] = {}

            # 개인 DB 조회
            if db_type in ["personal", "both"]:
                collection = self.vectorstore._collection
                data = collection.get(include=["metadatas"])
                metadatas = data.get("metadatas", []) or []

                for meta in metadatas:
                    if not isinstance(meta, dict):
                        continue
                    file_name = meta.get("file_name", "Unknown")
                    key = f"personal_{file_name}"

                    if key not in file_dict:
                        enable_vision = meta.get("enable_vision_chunking", False)
                        file_dict[key] = {
                            "file_name": file_name,
                            "file_type": meta.get("file_type", "Unknown"),
                            "upload_time": meta.get("upload_time", "Unknown"),
                            "chunk_count": 0,
                            "enable_vision_chunking": enable_vision,
                            "db_type": "개인 DB",
                        }
                    file_dict[key]["chunk_count"] += 1

            # 공유 DB 조회
            if db_type in ["shared", "both"] and self.shared_db_enabled:
                collection = self.shared_vectorstore._collection
                data = collection.get(include=["metadatas"])
                metadatas = data.get("metadatas", []) or []

                for meta in metadatas:
                    if not isinstance(meta, dict):
                        continue
                    file_name = meta.get("file_name", "Unknown")
                    key = f"shared_{file_name}"

                    if key not in file_dict:
                        enable_vision = meta.get("enable_vision_chunking", False)
                        file_dict[key] = {
                            "file_name": file_name,
                            "file_type": meta.get("file_type", "Unknown"),
                            "upload_time": meta.get("upload_time", "Unknown"),
                            "chunk_count": 0,
                            "enable_vision_chunking": enable_vision,
                            "db_type": "공유 DB",
                        }
                    file_dict[key]["chunk_count"] += 1

            return list(file_dict.values())

        except Exception as e:
            print(f"[VectorStore][ERROR] 문서 목록 조회 실패: {e}")
            return []
    
    def delete_document(self, file_name: str) -> bool:
        """특정 파일의 모든 청크 삭제"""
        try:
            collection = self.vectorstore._collection
            data = collection.get()
            
            # 삭제할 문서의 인덱스 찾기
            indices_to_remove = []
            for idx, metadata in enumerate(data.get("metadatas", [])):
                if metadata and metadata.get("file_name") == file_name:
                    indices_to_remove.append(idx)
            
            # BM25 인덱스에서 제거
            if BM25_AVAILABLE and self.bm25 is not None:
                for idx in reversed(indices_to_remove):
                    if idx < len(self.bm25_corpus):
                        self.bm25_corpus.pop(idx)
                    if idx < len(self.bm25_tokenized_corpus):
                        self.bm25_tokenized_corpus.pop(idx)
                    if idx < len(self.doc_ids):
                        self.doc_ids.pop(idx)
                
                # BM25 재구축
                if self.bm25_tokenized_corpus:
                    self.bm25 = BM25Okapi(self.bm25_tokenized_corpus)
            
            # 벡터스토어에서 삭제
            collection.delete(where={"file_name": file_name})
            return True
        except Exception as e:
            print(f"[VectorStore][ERROR] 문서 삭제 실패: {e}")
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
    
    def _load_entity_index(self):
        """엔티티 인덱스를 파일에서 로드"""
        import json
        try:
            if os.path.exists(self.entity_index_file):
                with open(self.entity_index_file, 'r', encoding='utf-8') as f:
                    self.entity_index = json.load(f)
                print(f"[VectorStore] 엔티티 인덱스 로드: {len(self.entity_index)}개 청크")
            else:
                self.entity_index = {}
        except Exception as e:
            print(f"[VectorStore][WARN] 엔티티 인덱스 로드 실패: {e}")
            self.entity_index = {}
    
    def _save_entity_index(self):
        """엔티티 인덱스를 파일에 저장"""
        import json
        try:
            with open(self.entity_index_file, 'w', encoding='utf-8') as f:
                json.dump(self.entity_index, f, ensure_ascii=False, indent=2)
            print(f"[VectorStore] 엔티티 인덱스 저장 완료: {len(self.entity_index)}개 청크")
        except Exception as e:
            print(f"[VectorStore][WARN] 엔티티 인덱스 저장 실패: {e}")
    
    def _update_entity_index(self, documents: List[Document], llm):
        """새로 추가된 문서들에 대해 엔티티 인덱스 업데이트"""
        from utils.entity_extractor import LLMEntityExtractor
        
        try:
            extractor = LLMEntityExtractor(llm)
            
            # 배치 단위로 엔티티 추출
            new_entities = extractor.batch_extract_entities(documents, batch_size=10)
            
            # 기존 인덱스에 병합
            self.entity_index.update(new_entities)
            
            # 파일에 저장
            self._save_entity_index()
            
            print(f"[VectorStore] 엔티티 인덱스 업데이트 완료: {len(new_entities)}개 청크 추가")
        except Exception as e:
            print(f"[VectorStore][WARN] 엔티티 인덱스 업데이트 실패: {e}")
    
    def get_entities_for_chunk(self, chunk_id: str) -> Optional[Dict[str, List[str]]]:
        """특정 청크의 엔티티 정보 조회"""
        return self.entity_index.get(chunk_id)
    
    def search_by_entity(self, entity: str, entity_type: str = None) -> List[str]:
        """엔티티로 청크 ID 검색"""
        matching_chunk_ids = []
        
        entity_lower = entity.lower()
        
        for chunk_id, entities_dict in self.entity_index.items():
            # entity_type이 지정된 경우 해당 타입만 검색
            if entity_type:
                if entity_type in entities_dict:
                    for ent in entities_dict[entity_type]:
                        if entity_lower in ent.lower():
                            matching_chunk_ids.append(chunk_id)
                            break
            else:
                # 모든 타입 검색
                for ent_list in entities_dict.values():
                    for ent in ent_list:
                        if entity_lower in ent.lower():
                            matching_chunk_ids.append(chunk_id)
                            break
                    if chunk_id in matching_chunk_ids:
                        break
        
        return matching_chunk_ids

    # ==================== 듀얼 DB 검색 메서드 ====================

    def search_with_mode(
        self,
        query: str,
        search_mode: str = "integrated",
        initial_k: int = 40,
        top_k: int = 10,
        use_reranker: bool = True,
        reranker_model: str = "multilingual-mini"
    ) -> List[tuple]:
        """
        검색 모드에 따라 개인 DB, 공유 DB, 또는 통합 검색 수행

        Args:
            query: 검색 쿼리
            search_mode: 검색 모드 ("integrated" | "personal" | "shared")
            initial_k: 초기 후보 문서 수
            top_k: 최종 반환 문서 수
            use_reranker: Re-ranker 사용 여부
            reranker_model: Re-ranker 모델명

        Returns:
            (Document, score) 튜플 리스트
        """
        try:
            # 개인 DB만 검색
            if search_mode == "personal":
                if use_reranker:
                    return self.similarity_search_with_rerank(
                        query=query,
                        top_k=top_k,
                        initial_k=initial_k,
                        reranker_model=reranker_model
                    )
                else:
                    return self.similarity_search_hybrid(
                        query=query,
                        initial_k=initial_k,
                        top_k=top_k
                    )

            # 공유 DB만 검색
            elif search_mode == "shared":
                if not self.shared_db_enabled:
                    print("[VectorStore] 공유 DB가 비활성화되어 있습니다")
                    return []

                # 공유 DB 단독 검색
                return self._search_shared_db_only(
                    query=query,
                    initial_k=initial_k,
                    top_k=top_k,
                    use_reranker=use_reranker,
                    reranker_model=reranker_model
                )

            # 통합 검색 (개인 + 공유)
            elif search_mode == "integrated":
                if not self.shared_db_enabled:
                    # 공유 DB 비활성화 시 개인 DB만 검색
                    print("[VectorStore] 공유 DB 비활성화 - 개인 DB만 검색")
                    if use_reranker:
                        return self.similarity_search_with_rerank(
                            query=query,
                            top_k=top_k,
                            initial_k=initial_k,
                            reranker_model=reranker_model
                        )
                    else:
                        return self.similarity_search_hybrid(
                            query=query,
                            initial_k=initial_k,
                            top_k=top_k
                        )

                # 통합 검색 수행
                return self._integrated_search(
                    query=query,
                    initial_k=initial_k,
                    top_k=top_k,
                    use_reranker=use_reranker,
                    reranker_model=reranker_model
                )

            else:
                raise ValueError(f"지원하지 않는 검색 모드: {search_mode}")

        except Exception as e:
            print(f"[VectorStore][ERROR] 검색 실패 ({search_mode}): {e}")
            return []

    def _search_shared_db_only(
        self,
        query: str,
        initial_k: int,
        top_k: int,
        use_reranker: bool,
        reranker_model: str
    ) -> List[tuple]:
        """공유 DB 단독 검색"""
        try:
            if use_reranker:
                # Re-ranker 사용
                candidates = self.shared_vectorstore.similarity_search_with_score(query, k=initial_k)
                if not candidates:
                    return []

                reranker = get_reranker(model_name=reranker_model)

                docs_for_rerank = []
                for doc, vector_score in candidates:
                    doc_dict = {
                        "page_content": doc.page_content,
                        "metadata": doc.metadata,
                        "vector_score": vector_score,
                        "document": doc
                    }
                    docs_for_rerank.append(doc_dict)

                reranked = reranker.rerank(query, docs_for_rerank, top_k=top_k)

                results = []
                for doc_dict in reranked:
                    results.append((
                        doc_dict["document"],
                        doc_dict.get("rerank_score", 0)
                    ))

                return results
            else:
                # 일반 벡터 검색
                return self.shared_vectorstore.similarity_search_with_score(query, k=top_k)

        except Exception as e:
            print(f"[VectorStore][ERROR] 공유 DB 검색 실패: {e}")
            return []

    def _integrated_search(
        self,
        query: str,
        initial_k: int,
        top_k: int,
        use_reranker: bool,
        reranker_model: str
    ) -> List[tuple]:
        """개인 DB + 공유 DB 통합 검색"""
        try:
            # 각 DB에서 initial_k개씩 검색
            personal_results = []
            shared_results = []

            # 개인 DB 검색
            if use_reranker:
                personal_results = self.similarity_search_with_rerank(
                    query=query,
                    top_k=initial_k,
                    initial_k=initial_k * 2,
                    reranker_model=reranker_model
                )
            else:
                personal_results = self.similarity_search_hybrid(
                    query=query,
                    initial_k=initial_k,
                    top_k=initial_k
                )

            # 공유 DB 검색
            shared_results = self._search_shared_db_only(
                query=query,
                initial_k=initial_k * 2,
                top_k=initial_k,
                use_reranker=use_reranker,
                reranker_model=reranker_model
            )

            # 결과 병합 및 정렬
            all_results = personal_results + shared_results

            # 점수 기준으로 정렬
            all_results.sort(key=lambda x: x[1], reverse=True)

            # 상위 top_k개 반환
            return all_results[:top_k]

        except Exception as e:
            print(f"[VectorStore][ERROR] 통합 검색 실패: {e}")
            return []

    def reconnect_shared_db(self) -> bool:
        """공유 DB 재접속 시도"""
        try:
            from utils.drive_scanner import DriveScanner

            # 드라이브 스캔
            result = DriveScanner.find_shared_db_drive()

            if result:
                drive_letter, db_path = result

                # 경로 검증
                if DriveScanner.verify_db_path(db_path):
                    self.shared_db_path = db_path
                    self.shared_db_enabled = True

                    # 공유 DB 재초기화
                    self._init_shared_vectorstore()

                    # BM25 인덱스 로드
                    if BM25_AVAILABLE:
                        self._load_shared_bm25_corpus()

                    print(f"[VectorStore] 공유 DB 재접속 성공: {db_path}")
                    return True
                else:
                    print(f"[VectorStore] 공유 DB 경로 접근 불가: {db_path}")
                    return False
            else:
                print(f"[VectorStore] 공유 DB를 찾을 수 없습니다")
                return False

        except Exception as e:
            print(f"[VectorStore][ERROR] 공유 DB 재접속 실패: {e}")
            self.shared_db_enabled = False
            return False

