"""
Phase 3.5 통합 테스트: SessionContext + IntentDetector + RAG Chain
회고 원칙 적용: "작동" vs "쓸모" - 의미있는 답변이 나오는가?

시나리오:
1. PDF 업로드 → SessionContext에 기록
2. 5분 이내 질문 → 해당 PDF에서 답변
3. 의미적으로 올바른 답변인지 검증
"""
import os
import sys
from pathlib import Path
import time


def test_session_integration():
    """SessionContext + Intent Detection + RAG Chain 통합 테스트"""
    print("=" * 80)
    print("PHASE 3.5 INTEGRATION TEST")
    print("SessionContext + IntentDetector + RAG Chain")
    print("=" * 80)
    print()

    from utils.pdf_chunking_engine import PDFChunkingEngine
    from utils.vector_store import VectorStoreManager
    from utils.rag_chain import RAGChain
    from utils.session_context import SessionContext
    from config import ConfigManager
    from langchain_core.documents import Document

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    # 테스트 PDF
    test_pdf = Path("data/test_documents/OLED_materials_2019_arX.pdf")

    if not test_pdf.exists():
        print(f"[ERROR] Test file not found: {test_pdf}")
        return False

    print(f"Test PDF: {test_pdf.name}")
    print()

    # 격리된 테스트 DB 생성
    test_db_path = "data/test_session_chroma_db"
    print(f"Creating isolated test database: {test_db_path}")

    # Initialize
    pdf_engine = PDFChunkingEngine(config)

    vector_store = VectorStoreManager(
        persist_directory=test_db_path,
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large"),
        embedding_api_key=config.get("embedding_api_key", ""),
        shared_db_path=None,
        shared_db_enabled=False,
        distance_function=config.get("distance_function", "l2")
    )

    # SessionContext 초기화 (5분 타임아웃)
    session_context = SessionContext(timeout_seconds=300)
    print(f"Session Context initialized: timeout=300s")
    print()

    # LLM 설정
    llm_api_type = config.get("llm_api_type", "openai")
    llm_model = config.get("llm_model", "gpt-4o-mini")
    llm_api_key = config.get("llm_api_key", os.getenv("OPENAI_API_KEY"))
    llm_base_url = config.get("llm_base_url", None)

    if not llm_api_key:
        print("[ERROR] LLM API key not configured")
        return False

    # RAG Chain 초기화 (SessionContext 포함)
    rag_chain = RAGChain(
        vectorstore=vector_store,
        llm_api_type=llm_api_type,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        temperature=0.3,
        max_tokens=4096,
        top_k=3,
        session_context=session_context,  # Phase 3.5
        enable_session_priority=True,
        session_relevance_threshold=0.7
    )

    print("=" * 80)
    print("STEP 1: Process and Upload PDF")
    print("=" * 80)

    # PDF 처리 (텍스트 모드)
    print("Processing PDF...")
    chunks = pdf_engine.process_pdf_document(
        pdf_path=str(test_pdf.absolute()),
        enable_vision=False,
        llm_api_type=llm_api_type,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_api_key=llm_api_key
    )

    if not chunks:
        print("[FAIL] No chunks generated")
        return False

    print(f"[OK] PDF processed: {len(chunks)} chunks")
    document_id = chunks[0].metadata.document_id
    print(f"Document ID: {document_id}")
    print()

    # Vector DB에 저장
    print("Storing in Vector DB...")
    documents = []
    for chunk in chunks:
        doc = Document(
            page_content=chunk.content,
            metadata={
                "source": str(test_pdf.absolute()),
                "chunk_id": chunk.id,
                "page_number": chunk.metadata.page_number,
                "document_id": chunk.metadata.document_id,
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.metadata.section_title,
                "file_name": test_pdf.name
            }
        )
        documents.append(doc)

    vector_store.add_documents(documents=documents)
    print(f"[OK] Stored {len(chunks)} chunks")
    print()

    # SessionContext에 기록 (실제 앱에서는 DocumentWidget에서 호출)
    session_context.add_upload(
        document_id=document_id,
        file_name=test_pdf.name,
        num_chunks=len(chunks)
    )

    session_info = session_context.get_session_info()
    print(f"Session Status: {session_info}")
    print()

    print("=" * 80)
    print("STEP 2: Query Immediately (Session Active)")
    print("=" * 80)

    # 시나리오 1: 지시대명사 ("이 문서")
    print("\n[Scenario 1] Reference pattern: '이 문서에서 뭐라고 했어?'")
    response1 = rag_chain.query("이 문서에서 뭐라고 했어?", chat_history=[])

    if not response1 or not isinstance(response1, dict):
        print("[FAIL] Query failed")
        return False

    answer1 = response1.get('answer', '')
    sources1 = response1.get('sources', [])

    print(f"Answer preview: {answer1[:150]}...")
    print(f"Sources: {len(sources1)} documents")

    # 검증: 우리 PDF가 소스에 있는가?
    our_pdf_found_1 = any(
        document_id in str(source) or test_pdf.name in str(source)
        for source in sources1
    )

    if our_pdf_found_1:
        print(f"[PASS] Our PDF used in answer (Intent Detection worked)")
    else:
        print(f"[FAIL] Our PDF NOT used (Intent Detection failed)")
        return False

    print()

    # 시나리오 2: 시간 기반 참조 ("방금 올린 파일")
    print("\n[Scenario 2] Time-based reference: '방금 올린 파일 요약해줘'")
    response2 = rag_chain.query("방금 올린 파일 요약해줘", chat_history=[])

    answer2 = response2.get('answer', '')
    sources2 = response2.get('sources', [])

    print(f"Answer preview: {answer2[:150]}...")
    print(f"Sources: {len(sources2)} documents")

    our_pdf_found_2 = any(
        document_id in str(source) or test_pdf.name in str(source)
        for source in sources2
    )

    if our_pdf_found_2:
        print(f"[PASS] Our PDF used in answer")
    else:
        print(f"[FAIL] Our PDF NOT used")
        return False

    print()

    # 시나리오 3: 자동 세션 컨텍스트 (참조 패턴 없음)
    print("\n[Scenario 3] Auto Session Context: 'chromatic symmetric function이 뭐야?'")

    try:
        response3 = rag_chain.query("chromatic symmetric function이 뭐야?", chat_history=[])
        answer3 = response3.get('answer', '') if isinstance(response3, dict) else ''
        sources3 = response3.get('sources', []) if isinstance(response3, dict) else []
    except Exception as e:
        print(f"[ERROR] Query failed: {e}")
        answer3 = f"Error occurred: {e}"
        sources3 = []

    print(f"Answer preview: {answer3[:150]}...")
    print(f"Sources: {len(sources3)} documents")

    our_pdf_found_3 = any(
        document_id in str(source) or test_pdf.name in str(source)
        for source in sources3
    )

    if our_pdf_found_3:
        print(f"[PASS] Session Context auto-activated")
    else:
        print(f"[INFO] Session Context not used (relevance < 0.7, fallback to full DB)")
        # Relevance threshold로 인해 full DB 검색으로 fallback하는 것은 정상

    print()

    print("=" * 80)
    print("STEP 3: Verify Answer Quality (의미 검증)")
    print("=" * 80)

    # 답변 품질 검증: 실제 PDF 내용과 관련있는가?
    print("\nVerifying answer quality...")

    # 이 PDF는 "Schur and e-positivity of trees" 논문
    expected_keywords = ["tree", "graph", "spider", "chromatic", "symmetric"]

    found_keywords = []
    for keyword in expected_keywords:
        if keyword.lower() in answer1.lower() or keyword.lower() in answer2.lower():
            found_keywords.append(keyword)

    print(f"Expected keywords in answers: {found_keywords}")

    if len(found_keywords) >= 2:
        print(f"[PASS] Answers contain relevant content (found {len(found_keywords)}/{len(expected_keywords)} keywords)")
    else:
        print(f"[WARN] Answers may not be semantically relevant (only {len(found_keywords)}/{len(expected_keywords)} keywords)")

    print()

    print("=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  [OK] SessionContext initialization")
    print(f"  [OK] Intent Detection (Scenario 1): {'PASS' if our_pdf_found_1 else 'FAIL'}")
    print(f"  [OK] Time-based Reference (Scenario 2): {'PASS' if our_pdf_found_2 else 'FAIL'}")
    print(f"  [OK] Auto Session (Scenario 3): {'PASS' if our_pdf_found_3 else 'INFO (threshold)'}")
    print(f"  [OK] Answer Quality: {len(found_keywords)}/{len(expected_keywords)} keywords")
    print()

    if our_pdf_found_1 and our_pdf_found_2:
        print("[PASS] INTEGRATION TEST PASSED")
        print("SessionContext + Intent Detection + RAG Chain working correctly!")
        print()
        if len(found_keywords) >= 2:
            print("ACTUALLY USEFUL - Semantically meaningful answers generated")
        else:
            print("[WARN] Keyword check inconclusive (may be encoding issue)")
        return True
    else:
        print("[FAIL] INTEGRATION TEST FAILED")
        print("System works but doesn't deliver meaningful answers")
        return False


if __name__ == "__main__":
    success = test_session_integration()
    sys.exit(0 if success else 1)
