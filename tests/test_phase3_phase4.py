"""
Phase 3-4 통합 테스트
- Phase 3: 슬라이드 타입 분류
- Phase 4: Hybrid Search (BM25 + Vector)
"""
import sys
import os

# Windows 콘솔 UTF-8 인코딩 설정 (LLM 응답 출력 오류 방지)
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def test_phase3_phase4():
    """Phase 3-4 통합 테스트"""
    print("=" * 80)
    print("Phase 3-4 통합 테스트")
    print("=" * 80)

    # 1. 설정 로드
    print("\n[1단계] 설정 로드...")
    config = ConfigManager().get_all()

    # 2. DocumentProcessor 초기화
    print("\n[2단계] DocumentProcessor 초기화...")
    doc_processor = DocumentProcessor(
        chunk_size=config.get("chunk_size", 1500),
        chunk_overlap=config.get("chunk_overlap", 200),
    )

    # 3. VectorStoreManager 초기화 (임시 DB)
    print("\n[3단계] VectorStoreManager 초기화 (임시 DB)...")
    vector_manager = VectorStoreManager(
        persist_directory="data/test_chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    # 4. RAGChain 초기화 (Phase 4 Hybrid Search 활성화)
    print("\n[4단계] RAGChain 초기화 (Hybrid Search 활성화)...")
    rag_chain = RAGChain(
        vectorstore=vector_manager,
        llm_api_type=config.get("llm_api_type", "ollama"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:4b"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=0.3,
        top_k=3,
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=20,
        # Phase 4: Hybrid Search 활성화
        enable_hybrid_search=True,
        hybrid_bm25_weight=0.5
    )

    # 5. 테스트용 PPT 파일 찾기
    print("\n[5단계] 테스트용 PPT 파일 찾기...")
    test_ppt_dir = "data/test_files"
    if not os.path.exists(test_ppt_dir):
        print(f"[WARN] 테스트 파일 디렉토리가 없습니다: {test_ppt_dir}")
        print("[INFO] data/embedded_documents에서 PPT 파일 찾기...")
        test_ppt_dir = "data/embedded_documents"

    ppt_files = [f for f in os.listdir(test_ppt_dir) if f.endswith('.pptx')]

    if not ppt_files:
        print("[ERROR] PPT 파일을 찾을 수 없습니다.")
        print(f"        {test_ppt_dir} 디렉토리에 .pptx 파일을 넣어주세요.")
        return False

    # 첫 번째 PPT 파일 사용
    test_ppt = os.path.join(test_ppt_dir, ppt_files[0])
    print(f"[OK] 테스트 파일: {ppt_files[0]}")

    # 6. Phase 3 테스트: 슬라이드 타입 분류 확인
    print("\n" + "=" * 80)
    print("[Phase 3 테스트] 슬라이드 타입 분류")
    print("=" * 80)

    print(f"\n[INFO] 처리 중: {ppt_files[0]}")
    chunks = doc_processor.process_document(
        file_path=test_ppt,
        file_name=ppt_files[0],
        file_type="pptx"
    )

    print(f"\n[OK] 총 {len(chunks)}개 청크 생성")

    # 슬라이드 타입 통계
    slide_types = {}
    for chunk in chunks:
        if hasattr(chunk, 'metadata') and hasattr(chunk.metadata, 'slide_type'):
            slide_type = chunk.metadata.slide_type
            if slide_type:
                slide_types[slide_type] = slide_types.get(slide_type, 0) + 1

    if slide_types:
        print("\n[STAT] 슬라이드 타입 분포:")
        for slide_type, count in sorted(slide_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {slide_type}: {count}개 청크")
    else:
        print("[WARN] 슬라이드 타입이 설정되지 않았습니다.")

    # 7. Vector DB에 추가
    print("\n[6단계] Vector DB에 청크 추가...")
    vector_manager.add_documents(chunks)
    print("[OK] 임베딩 완료")

    # 7.5. BM25 인덱스 재구축 (임베딩 후)
    print("\n[6.5단계] BM25 인덱스 재구축...")
    if rag_chain.hybrid_retriever:
        success = rag_chain.hybrid_retriever.rebuild_index()
        if success:
            print("[OK] BM25 인덱스 재구축 완료")
        else:
            print("[WARN] BM25 인덱스 재구축 실패")

    # 8. Phase 4 테스트: Hybrid Search 확인
    print("\n" + "=" * 80)
    print("[Phase 4 테스트] Hybrid Search (BM25 + Vector)")
    print("=" * 80)

    # 테스트 쿼리들
    test_queries = [
        "표가 있는 슬라이드는?",
        "Q2 매출은?",
        "분기별 성과는?",
        "차트 내용은?"
    ]

    print("\n[SEARCH] 검색 테스트:")
    for i, query in enumerate(test_queries, 1):
        print(f"\n[쿼리 {i}] {query}")
        print("-" * 60)

        try:
            result = rag_chain.query(query)

            if result.get("success"):
                # 인코딩 에러 방지를 위한 안전한 출력
                answer_text = result['answer'][:200]
                try:
                    print(f"[OK] 답변: {answer_text}...")
                except:
                    print(f"[OK] 답변: (출력 불가 - 인코딩 문제)")
                print(f"[STAT] 신뢰도: {result['confidence']:.1%}")
                print(f"[INFO] 출처: {len(result['sources'])}개 문서")
            else:
                print(f"[ERROR] 검색 실패: {result.get('answer', 'Unknown error')}")
        except Exception as e:
            print(f"[ERROR] 오류: {str(e)}")

    # 9. 정리
    print("\n" + "=" * 80)
    print("테스트 완료!")
    print("=" * 80)

    # 임시 DB 자동 정리
    print("\n[CLEAN] 임시 DB 자동 삭제 중...")
    import shutil
    try:
        if os.path.exists("data/test_chroma_db"):
            shutil.rmtree("data/test_chroma_db")
            print("[OK] 임시 DB 삭제 완료")
    except Exception as e:
        print(f"[WARN] 임시 DB 삭제 실패: {e}")

    return True


if __name__ == "__main__":
    try:
        success = test_phase3_phase4()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARN] 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
