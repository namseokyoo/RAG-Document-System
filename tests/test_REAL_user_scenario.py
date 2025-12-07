"""
진짜 사용자 시나리오 테스트
회고 교훈 적용: "작동"이 아닌 "쓸모" 검증

시나리오:
1. 사용자가 PDF 업로드
2. 그 PDF의 고유한 내용에 대해 질문
3. 답변이 그 PDF에서 나오는가?
"""
import os
import sys
from pathlib import Path

def test_real_user_scenario():
    """실제 사용자 시나리오대로 테스트"""
    print("=" * 80)
    print("REAL USER SCENARIO TEST")
    print("Test Philosophy: Does it actually work for users?")
    print("=" * 80)
    print()

    from utils.pdf_chunking_engine import PDFChunkingEngine
    from utils.vector_store import VectorStoreManager
    from config import ConfigManager
    from langchain_core.documents import Document

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    # 사용자가 업로드할 PDF (실제 파일 사용)
    test_pdf = Path("data/test_documents/OLED_materials_2019_arX.pdf")

    if not test_pdf.exists():
        print(f"[ERROR] Test file not found: {test_pdf}")
        return False

    print(f"USER ACTION: Upload PDF '{test_pdf.name}'")
    print()

    # Initialize
    pdf_engine = PDFChunkingEngine(config)

    # 새로운 Vector Store 생성 (기존 DB와 분리)
    test_db_path = "data/test_chroma_db"
    print(f"Creating isolated test database: {test_db_path}")

    vector_store = VectorStoreManager(
        persist_directory=test_db_path,
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large"),
        embedding_api_key=config.get("embedding_api_key", ""),
        shared_db_path=None,  # 공유 DB 비활성화
        shared_db_enabled=False,
        distance_function=config.get("distance_function", "l2")
    )

    llm_api_type = config.get("llm_api_type", "openai")
    llm_model = config.get("llm_model", "gpt-4o-mini")
    llm_api_key = config.get("llm_api_key", os.getenv("OPENAI_API_KEY"))
    llm_base_url = config.get("llm_base_url", None)

    if not llm_api_key:
        print("[ERROR] LLM API key not configured")
        return False

    print()
    print("=" * 80)
    print("STEP 1: Process PDF (User uploads document)")
    print("=" * 80)

    # Chunk PDF (텍스트 모드로 빠르게 - 이미 Phase 2/3 테스트했으므로)
    print("Processing PDF in text mode (for speed)...")
    chunks = pdf_engine.process_pdf_document(
        pdf_path=str(test_pdf.absolute()),
        enable_vision=False,  # 빠른 테스트를 위해 텍스트 모드
        llm_api_type=llm_api_type,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_api_key=llm_api_key
    )

    if not chunks:
        print("[FAIL] No chunks generated")
        return False

    print(f"[OK] PDF processed: {len(chunks)} chunks created")
    document_id = chunks[0].metadata.document_id
    print(f"Document ID: {document_id}")

    # 첫 번째 청크의 내용 확인 (검색 가능한 내용 파악)
    first_chunk_preview = chunks[0].content[:200]
    print(f"\nFirst chunk preview:")
    print(f"  {first_chunk_preview}...")
    print()

    print("=" * 80)
    print("STEP 2: Store in Vector Database")
    print("=" * 80)

    # Convert to Documents
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

    # Store
    before = len(vector_store.vectorstore.get()['ids'])
    vector_store.add_documents(documents=documents)
    after = len(vector_store.vectorstore.get()['ids'])

    print(f"Vector DB size: {before} → {after} ({after - before} added)")

    if after - before != len(chunks):
        print(f"[FAIL] Expected {len(chunks)} chunks, but only {after - before} were added")
        return False

    print(f"[OK] All {len(chunks)} chunks stored")
    print()

    print("=" * 80)
    print("STEP 3: CRITICAL TEST - Can we actually search this PDF?")
    print("=" * 80)

    # 직접 벡터 검색 테스트 (RAG chain 없이)
    print("\nDirect vector similarity search test...")

    # 첫 번째 청크의 내용으로 검색 (자기 자신을 찾아야 함)
    test_query_1 = chunks[0].content[:50]  # 첫 50자로 검색
    print(f"Query 1 (from PDF content): '{test_query_1}'")

    # ChromaDB 직접 쿼리
    search_results = vector_store.vectorstore.similarity_search(
        test_query_1,
        k=3
    )

    if not search_results:
        print("[FAIL] No results from similarity search!")
        return False

    print(f"Found {len(search_results)} results")

    # 우리 문서가 결과에 있는지 확인
    our_doc_found = False
    for i, result in enumerate(search_results, 1):
        result_doc_id = result.metadata.get('document_id', '')
        result_filename = result.metadata.get('file_name', '')

        print(f"  Result {i}:")
        print(f"    doc_id: {result_doc_id}")
        print(f"    file: {result_filename}")
        print(f"    content preview: {result.page_content[:80]}...")

        if result_doc_id == document_id:
            our_doc_found = True
            print(f"    [MATCH] This is our PDF! [OK]")

    print()

    if not our_doc_found:
        print("[FAIL] Our PDF not found in search results!")
        print("This means the PDF is stored but NOT searchable")
        return False

    print("[PASS] Our PDF found in similarity search!")
    print()

    # 더 일반적인 쿼리 테스트
    print("\nGeneral topic search test...")
    general_query = "chromatic symmetric function"
    print(f"Query 2 (general topic): '{general_query}'")

    general_results = vector_store.vectorstore.similarity_search(
        general_query,
        k=5
    )

    our_doc_in_general = any(
        r.metadata.get('document_id') == document_id
        for r in general_results
    )

    print(f"Found {len(general_results)} results")
    if our_doc_in_general:
        print("[PASS] Our PDF found in general topic search!")
        for i, r in enumerate(general_results, 1):
            if r.metadata.get('document_id') == document_id:
                print(f"  Result {i}: OUR PDF (page {r.metadata.get('page_number')})")
    else:
        print("[WARN] Our PDF not in top 5 for general topic")
        print("(This may be OK if other docs are more relevant)")

    print()

    print("=" * 80)
    print("STEP 4: Real RAG Query Test")
    print("=" * 80)

    # RAG Chain 초기화
    from utils.rag_chain import RAGChain

    rag_chain = RAGChain(
        vectorstore=vector_store,
        llm_api_type=llm_api_type,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        temperature=0.3,
        max_tokens=4096,
        top_k=3
    )

    # 사용자의 질문
    user_query = "What is this document about?"
    print(f"\nUSER QUESTION: '{user_query}'")
    print()

    response = rag_chain.query(user_query, chat_history=[])

    if not response or not isinstance(response, dict):
        print("[FAIL] RAG query failed")
        return False

    answer = response.get('answer', '')
    sources = response.get('sources', [])

    print("SYSTEM ANSWER:")
    print(f"  {answer[:300]}...")
    print()
    print(f"SOURCES: {len(sources)} documents used")

    # 중요: 우리 PDF가 소스에 있는가?
    our_pdf_in_sources = False
    for source in sources:
        source_str = str(source)
        if document_id in source_str or test_pdf.name in source_str:
            our_pdf_in_sources = True
            # Extract safe metadata to print
            if isinstance(source, dict):
                file_name = source.get('file_name', '')
                page_num = source.get('page_number', '')
                print(f"  [FOUND] Our PDF: {file_name}, page {page_num}")
            else:
                print(f"  [FOUND] Our PDF in sources")

    print()

    if our_pdf_in_sources:
        print("[SUCCESS] Our PDF was used to answer the question!")
        print("=" * 80)
        print("FINAL VERDICT: ACTUALLY USEFUL [PASS]")
        print("=" * 80)
        return True
    else:
        print("[FAIL] Our PDF was NOT used to answer the question")
        print("The system answered from OTHER documents")
        print()
        print("=" * 80)
        print("FINAL VERDICT: NOT USEFUL (Works but doesn't do what users need)")
        print("=" * 80)
        return False


if __name__ == "__main__":
    success = test_real_user_scenario()
    sys.exit(0 if success else 1)
