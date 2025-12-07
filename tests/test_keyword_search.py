"""
키워드 검색 개선 기능 테스트 스크립트

실제 문서를 임베딩하고 저자명/키워드 검색을 테스트합니다.
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_keyword_search():
    """키워드 검색 개선 기능 테스트"""
    
    print("=" * 80)
    print("키워드 검색 개선 기능 테스트")
    print("=" * 80)
    
    # 설정 로드
    config_manager = ConfigManager()
    config = config_manager.get_all()
    
    # 테스트용 문서 경로
    test_doc_path = "data/embedded_documents_backup_1762955774/OLED_0805.1948v1.pdf"
    
    if not os.path.exists(test_doc_path):
        print(f"❌ 테스트 문서를 찾을 수 없습니다: {test_doc_path}")
        return
    
    print(f"\n📄 테스트 문서: {test_doc_path}")
    
    try:
        # 1. DocumentProcessor 초기화
        print("\n[1단계] DocumentProcessor 초기화...")
        doc_processor = DocumentProcessor(
            chunk_size=config.get("chunk_size", 1500),
            chunk_overlap=config.get("chunk_overlap", 200),
        )
        
        # 2. VectorStoreManager 초기화
        print("[2단계] VectorStoreManager 초기화...")
        vector_manager = VectorStoreManager(
            persist_directory="data/chroma_db",
            embedding_api_type=config.get("embedding_api_type", "ollama"),
            embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
            embedding_model=config.get("embedding_model", "nomic-embed-text"),
            embedding_api_key=config.get("embedding_api_key", ""),
            distance_function=config.get("chroma_distance_function", "l2"),
        )
        
        # 3. 문서 임베딩 (이미 임베딩되어 있으면 스킵)
        print(f"\n[3단계] 문서 임베딩 중...")
        print(f"       파일: {os.path.basename(test_doc_path)}")
        
        # 문서가 이미 임베딩되어 있는지 확인
        # 간단하게 임베딩 시도 (중복 체크는 내부에서 처리됨)
        try:
            chunks = doc_processor.process_document(
                test_doc_path,
                enable_vision=config.get("enable_vision", True),
                enable_hybrid=config.get("enable_hybrid", True),
                llm_api_type=config.get("llm_api_type", "request"),
                llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
                llm_model=config.get("llm_model", "gemma3:4b"),
                llm_api_key=config.get("llm_api_key", ""),
            )
            
            if chunks:
                print(f"       ✓ 청크 생성 완료: {len(chunks)}개")
                
                # 벡터 스토어에 추가
                vector_manager.add_documents(chunks)
                print(f"       ✓ 벡터 스토어에 추가 완료")
            else:
                print(f"       ⚠ 청크가 생성되지 않았습니다 (이미 임베딩되어 있을 수 있음)")
        except Exception as e:
            print(f"       ⚠ 임베딩 오류 (이미 임베딩되어 있을 수 있음): {e}")
        
        # 4. RAGChain 초기화
        print("\n[4단계] RAGChain 초기화...")
        rag_chain = RAGChain(
            vectorstore=vector_manager,
            llm_api_type=config.get("llm_api_type", "request"),
            llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
            llm_model=config.get("llm_model", "gemma3:4b"),
            llm_api_key=config.get("llm_api_key", ""),
            temperature=config.get("temperature", 0.7),
            top_k=config.get("top_k", 3),
            use_reranker=config.get("use_reranker", True),
            reranker_model=config.get("reranker_model", "multilingual-mini"),
            reranker_initial_k=config.get("reranker_initial_k", 20),
            enable_multi_query=config.get("enable_multi_query", True),
            multi_query_num=config.get("multi_query_num", 3),
            enable_hyde=config.get("enable_hyde", True),
            enable_query_decomposition=config.get("enable_query_decomposition", True),
            enable_hybrid_search=config.get("enable_hybrid_search", True),
            hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5),
        )
        
        # 5. 벡터 스토어에서 실제 저자명 찾기
        print("\n[5단계] 문서에서 실제 저자명 찾기...")
        
        found_authors = []
        
        # 벡터 스토어에서 "author" 키워드로 검색하여 저자명 찾기
        try:
            # 먼저 BM25로 "author" 키워드 검색
            if hasattr(vector_manager, '_bm25_only_search'):
                print("       BM25로 'author' 키워드 검색 중...")
                author_results = vector_manager._bm25_only_search("author", top_k=30)
                
                if author_results:
                    import re
                    # 검색 결과에서 저자명 패턴 찾기 (더 정확한 패턴)
                    author_patterns = [
                        # "Author:" 또는 "Authors:" 뒤의 이름들
                        r'[Aa]uthors?[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)*)',
                        # "by Author Name" 패턴
                        r'\bby\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                        # "Author Name et al" 패턴
                        r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+et\s+al',
                        # 일반적인 이름 패턴 (소문자로 시작하는 단어 제외)
                        r'^([A-Z][a-z]+\s+[A-Z][a-z]+)\s*[,;]',  # 줄 시작의 이름
                    ]
                    
                    # 일반적인 이름이 아닌 단어 필터
                    invalid_first_names = ['Abstract', 'Introduction', 'Figure', 'Table', 'Section', 
                                          'Optical', 'Quantum', 'Physical', 'Chemical', 'Electronic',
                                          'Bose', 'Einstein', 'Condensate', 'Lattice', 'Lattices']
                    
                    for doc, score in author_results[:15]:  # 상위 15개 확인
                        content = doc.page_content
                        file_name = doc.metadata.get('file_name', '')
                        
                        # 테스트 문서와 관련된 결과만 확인
                        if os.path.basename(test_doc_path) in file_name or not file_name:
                            for pattern in author_patterns:
                                matches = re.findall(pattern, content[:5000], re.MULTILINE)  # 처음 5000자, 멀티라인
                                if matches:
                                    for match in matches:
                                        # 쉼표로 구분된 여러 이름 처리
                                        names = [n.strip() for n in match.split(',')]
                                        for name in names:
                                            if len(name.split()) == 2:  # FirstName LastName 형식
                                                first_name = name.split()[0]
                                                # 유효한 이름인지 확인
                                                if (first_name not in invalid_first_names and 
                                                    len(first_name) > 2 and 
                                                    name not in found_authors):
                                                    found_authors.append(name)
                                                    if len(found_authors) >= 3:
                                                        break
                                        
                                        if len(found_authors) >= 3:
                                            break
                                    
                                    if found_authors:
                                        break
                            
                            if found_authors:
                                break
        except Exception as e:
            print(f"       ⚠ 저자명 자동 추출 실패: {e}")
            import traceback
            traceback.print_exc()
        
        # 중복 제거 및 정리
        if found_authors:
            found_authors = list(set(found_authors))[:3]  # 중복 제거, 최대 3개
        
        # 저자명을 찾지 못했으면 벡터 검색으로 시도
        if not found_authors:
            try:
                print("       벡터 검색으로 'author' 키워드 검색 중...")
                vector_results = vector_manager.vectorstore.similarity_search("author", k=15)
                
                import re
                invalid_first_names = ['Abstract', 'Introduction', 'Figure', 'Table', 'Optical', 'Quantum']
                
                for doc in vector_results:
                    content = doc.page_content
                    # 저자명 패턴 찾기
                    author_patterns = [
                        r'[Aa]uthors?[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                        r'\bby\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                    ]
                    
                    for pattern in author_patterns:
                        matches = re.findall(pattern, content[:3000])
                        if matches:
                            for match in matches:
                                if len(match.split()) == 2:
                                    first_name = match.split()[0]
                                    if (first_name not in invalid_first_names and 
                                        len(first_name) > 2 and 
                                        match not in found_authors):
                                        found_authors.append(match)
                                        if len(found_authors) >= 3:
                                            break
                    
                    if found_authors:
                        break
            except Exception as e:
                print(f"       ⚠ 벡터 검색 실패: {e}")
        
        # 저자명을 찾지 못했으면 실제 문서 내용에서 직접 검색
        if not found_authors:
            print("       문서 내용에서 직접 저자명 검색 중...")
            try:
                # 벡터 스토어의 모든 문서에서 첫 페이지 내용 확인
                coll = vector_manager.vectorstore._collection
                data = coll.get()
                docs = data.get("documents", [])
                metas = data.get("metadatas", [])
                
                import re
                for idx, doc_text in enumerate(docs):
                    if idx < len(metas):
                        meta = metas[idx]
                        file_name = meta.get('file_name', '')
                        page_num = meta.get('page_number', 0)
                        
                        # 첫 페이지만 확인 (저자명은 보통 첫 페이지에 있음)
                        if os.path.basename(test_doc_path) in file_name and page_num == 1:
                            # 더 정확한 저자명 패턴
                            author_patterns = [
                                r'[Aa]uthors?[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s*,\s*[A-Z][a-z]+\s+[A-Z][a-z]+)*)',
                                r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+et\s+al',
                            ]
                            
                            for pattern in author_patterns:
                                matches = re.findall(pattern, doc_text[:2000])
                                if matches:
                                    for match in matches:
                                        # 쉼표로 구분된 이름들 처리
                                        names = [n.strip() for n in match.split(',')]
                                        for name in names:
                                            if len(name.split()) == 2:
                                                first_name = name.split()[0]
                                                if (first_name not in ['Abstract', 'Introduction', 'Optical', 'Quantum'] and
                                                    len(first_name) > 2):
                                                    found_authors.append(name)
                                                    if len(found_authors) >= 2:
                                                        break
                                
                                if found_authors:
                                    break
                            
                            if found_authors:
                                break
            except Exception as e:
                print(f"       ⚠ 직접 검색 실패: {e}")
        
        # 저자명을 찾지 못했으면 테스트용 질문 사용
        if not found_authors:
            print("       ⚠ 저자명을 자동으로 찾지 못했습니다.")
            print("       일반적인 키워드 검색으로 테스트합니다.")
            test_questions = [
                "OLED 논문의 저자를 찾아줘",
                "이 논문의 저자는 누구인가?",
                "논문에서 저자 정보를 찾아줘",
            ]
        else:
            # 찾은 저자명으로 질문 생성
            author_name = found_authors[0]
            print(f"       ✓ 저자명 발견: {author_name}")
            test_questions = [
                f"{author_name} 이 사람이 저자인 논문 찾아줘",
                f"Find papers by {author_name}",
                f"{author_name}의 논문",
            ]
        
        # 6. 키워드 검색 테스트
        print("\n" + "=" * 80)
        print("키워드 검색 테스트 시작")
        print("=" * 80)
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n[테스트 {i}] 질문: {question}")
            print("-" * 80)
            
            try:
                # 질문 실행
                response = rag_chain.query(question, chat_history=[])
                
                # 결과 확인
                if response and response.get('answer'):
                    answer = response['answer']
                    sources = response.get('sources', [])
                    
                    print(f"\n✓ 답변 생성 성공")
                    print(f"  답변 길이: {len(answer)}자")
                    print(f"  출처 문서: {len(sources)}개")
                    
                    # 키워드가 답변에 포함되어 있는지 확인
                    if found_authors:
                        author_in_answer = any(author.lower() in answer.lower() for author in found_authors)
                        if author_in_answer:
                            print(f"  ✓ 저자명이 답변에 포함됨")
                        else:
                            print(f"  ⚠ 저자명이 답변에 포함되지 않음")
                    
                    # 출처 정보 출력
                    if sources:
                        print(f"\n  출처 정보:")
                        for idx, source in enumerate(sources[:3], 1):
                            file_name = source.get('file_name', 'Unknown')
                            page = source.get('page_number', 'N/A')
                            score = source.get('similarity_score', 0)
                            print(f"    {idx}. {os.path.basename(file_name)} (페이지: {page}, 점수: {score:.4f})")
                    
                    # 답변 일부 출력
                    print(f"\n  답변 (일부):")
                    print(f"  {answer[:200]}...")
                else:
                    print(f"\n❌ 답변 생성 실패")
                    print(f"  응답: {response}")
                    
            except Exception as e:
                print(f"\n❌ 테스트 실행 오류: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 80)
        print("테스트 완료")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 테스트 초기화 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_keyword_search()

