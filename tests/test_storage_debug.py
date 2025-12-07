"""
Vector Storage 디버깅 테스트
왜 저장된 청크를 찾을 수 없는지 확인
"""
import os
from pathlib import Path

def test_storage_debug():
    from utils.pdf_chunking_engine import PDFChunkingEngine
    from utils.vector_store import VectorStoreManager
    from config import ConfigManager
    from langchain_core.documents import Document

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    test_pdf = Path("data/test_documents/OLED_materials_2019_arX.pdf")

    # Initialize
    pdf_engine = PDFChunkingEngine(config)
    vector_store = VectorStoreManager(
        persist_directory=config.get("chroma_db_path", "data/chroma_db"),
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large"),
        embedding_api_key=config.get("embedding_api_key", ""),
        shared_db_path=config.get("shared_db_path"),
        shared_db_enabled=config.get("shared_db_enabled", False),
        distance_function=config.get("distance_function", "l2")
    )

    # Get LLM settings
    llm_api_type = config.get("llm_api_type", "openai")
    llm_model = config.get("llm_model", "gpt-4o-mini")
    llm_api_key = config.get("llm_api_key", os.getenv("OPENAI_API_KEY"))
    llm_base_url = config.get("llm_base_url", None)

    print("=" * 80)
    print("Storage Debug Test")
    print("=" * 80)
    print()

    # Chunk PDF (just first 3 pages for speed)
    print("Step 1: Chunk first 3 pages...")
    chunks = pdf_engine.process_pdf_document(
        pdf_path=str(test_pdf.absolute()),
        enable_vision=False,  # Use text mode for speed
        llm_api_type=llm_api_type,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_api_key=llm_api_key
    )

    if not chunks:
        print("[ERROR] No chunks generated")
        return

    # Limit to 3 chunks for testing
    chunks = chunks[:3]
    document_id = chunks[0].metadata.document_id

    print(f"Generated {len(chunks)} chunks")
    print(f"Document ID: {document_id}")
    print()

    # Convert to Documents
    print("Step 2: Convert to LangChain Documents...")
    documents = []
    for i, chunk in enumerate(chunks):
        doc = Document(
            page_content=chunk.content,
            metadata={
                "source": str(test_pdf.absolute()),
                "chunk_id": chunk.id,
                "page_number": chunk.metadata.page_number,
                "document_id": chunk.metadata.document_id,
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.metadata.section_title,
                "test_marker": "DEBUG_TEST"  # Special marker for testing
            }
        )
        documents.append(doc)
        print(f"  Doc {i+1}: page={chunk.metadata.page_number}, chunk_id={chunk.id}")

    print()

    # Store
    print("Step 3: Store documents...")
    print(f"Before storage: Vector store has {len(vector_store.vectorstore.get()['ids'])} documents")

    vector_store.add_documents(documents=documents)

    print(f"After storage: Vector store has {len(vector_store.vectorstore.get()['ids'])} documents")
    print()

    # Verify storage immediately
    print("Step 4: Immediate verification...")
    all_docs = vector_store.vectorstore.get()

    # Check by document_id
    print(f"\nSearch by document_id '{document_id}':")
    found_by_doc_id = [doc_id for doc_id in all_docs['ids'] if document_id in doc_id]
    print(f"  Found: {len(found_by_doc_id)} chunks")

    # Check by chunk_id
    print(f"\nSearch by chunk_id pattern:")
    for chunk in chunks:
        found = [doc_id for doc_id in all_docs['ids'] if chunk.id in doc_id]
        print(f"  chunk_id={chunk.id}: Found={len(found)}")

    # Check by test marker
    print(f"\nSearch by test_marker 'DEBUG_TEST':")
    if all_docs.get('metadatas'):
        found_by_marker = [m for m in all_docs['metadatas'] if m.get('test_marker') == 'DEBUG_TEST']
        print(f"  Found: {len(found_by_marker)} chunks")

        if found_by_marker:
            print("\n  Sample metadata:")
            sample = found_by_marker[0]
            for key, value in sample.items():
                print(f"    {key}: {value}")

    # Check by source file path
    print(f"\nSearch by source file (OLED_materials):")
    if all_docs.get('metadatas'):
        found_by_source = [m for m in all_docs['metadatas'] if 'OLED_materials' in str(m.get('source', ''))]
        print(f"  Found: {len(found_by_source)} chunks")

    print()
    print("=" * 80)
    print("Debug Analysis")
    print("=" * 80)

    if found_by_marker:
        print("[OK] Documents were stored successfully!")
        print("Issue: Search logic in test was incorrect")
    else:
        print("[ERROR] Documents were NOT stored!")
        print("Issue: Vector store add_documents() failed silently")

    print()


if __name__ == "__main__":
    test_storage_debug()
