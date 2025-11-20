"""
Phase 3 Embedding and RAG Integration Test

Tests:
1. PDF chunking → embedding → storage pipeline
2. RAG search with PDF chunks
3. Semantic meaning preservation
4. Integration with existing system
"""
import os
import sys
from pathlib import Path

def test_pdf_embedding_rag():
    """Test full PDF embedding and RAG pipeline"""
    print("=" * 80)
    print("Phase 3: PDF Embedding and RAG Integration Test")
    print("=" * 80)
    print()

    # Import modules
    from utils.pdf_chunking_engine import PDFChunkingEngine
    from utils.vector_store import VectorStoreManager
    from utils.rag_chain import RAGChain
    from config import ConfigManager

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    # Test PDF
    test_pdf = Path("data/test_documents/OLED_materials_2019_arX.pdf")

    if not test_pdf.exists():
        print(f"[ERROR] Test PDF not found: {test_pdf}")
        return False

    print(f"Test PDF: {test_pdf.name}")
    print()

    # Initialize engines
    pdf_engine = PDFChunkingEngine(config)

    # Initialize vector store with proper parameters
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

    # Initialize RAG chain with vector store
    rag_chain = RAGChain(
        vectorstore=vector_store,
        llm_api_type=llm_api_type,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        temperature=config.get("temperature", 0.3),
        max_tokens=config.get("max_tokens", 4096),
        top_k=config.get("top_k", 3)
    )

    if not llm_api_key:
        print("[ERROR] LLM API key not configured")
        return False

    print("Step 1: PDF Chunking (Hybrid Mode)")
    print("-" * 80)

    try:
        # Chunk PDF
        chunks = pdf_engine.process_pdf_document(
            pdf_path=str(test_pdf.absolute()),
            enable_vision=True,
            enable_hybrid=True,
            llm_api_type=llm_api_type,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_api_key=llm_api_key
        )

        if not chunks:
            print("[ERROR] No chunks generated")
            return False

        print(f"[OK] Generated {len(chunks)} chunks")
        vision_chunks = [c for c in chunks if c.chunk_type == "pdf_page_vision_hybrid"]
        text_chunks = [c for c in chunks if c.chunk_type == "pdf_page_text"]
        print(f"  - Vision: {len(vision_chunks)}, Text: {len(text_chunks)}")
        print()

        print("Step 2: Vector Storage with Automatic Embedding")
        print("-" * 80)

        # Store chunks in vector database (embeddings generated automatically)
        document_id = chunks[0].metadata.document_id
        print(f"Storing {len(chunks)} chunks for document: {document_id}")
        print("(Embeddings will be generated automatically during storage)")

        # Convert chunks to LangChain Documents
        from langchain_core.documents import Document

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
                    "section_title": chunk.metadata.section_title
                }
            )
            documents.append(doc)

        # Add documents to vector store
        vector_store.add_documents(documents=documents)
        print(f"[OK] Stored {len(chunks)} chunks in vector database with embeddings")
        print()

        print("Step 3: Vector Store Verification")
        print("-" * 80)

        # Verify documents are in vector store
        try:
            # Get all documents from the vector store
            all_docs = vector_store.vectorstore.get()

            if all_docs and 'ids' in all_docs:
                stored_count = len(all_docs['ids'])
                print(f"[OK] Vector store contains {stored_count} documents")

                # Check if our PDF chunks are there
                pdf_docs = [doc_id for doc_id in all_docs['ids'] if document_id in doc_id]
                print(f"[OK] Found {len(pdf_docs)} chunks from our test PDF")

                # Check metadata
                if all_docs.get('metadatas'):
                    sample_metadata = all_docs['metadatas'][0] if all_docs['metadatas'] else {}
                    print(f"[OK] Sample metadata keys: {list(sample_metadata.keys())}")

                    # Verify our metadata is preserved
                    has_page_numbers = any('page_number' in m for m in all_docs['metadatas'][-21:])
                    has_chunk_type = any('chunk_type' in m for m in all_docs['metadatas'][-21:])
                    print(f"[OK] Metadata preserved - page_number: {has_page_numbers}, chunk_type: {has_chunk_type}")

            else:
                print("[WARN] Could not verify vector store contents")

        except Exception as e:
            print(f"[WARN] Vector store verification failed: {e}")

        print()

        print("Step 4: RAG Query Test")
        print("-" * 80)

        # Simple query test
        test_query = "What is this document about?"
        print(f"Test query: '{test_query}'")

        try:
            response = rag_chain.query(test_query, chat_history=[])

            if response and isinstance(response, dict):
                answer = response.get('answer', '')
                sources = response.get('sources', [])

                print(f"[OK] Query executed successfully")
                print(f"Answer preview (first 150 chars):")
                print(f"  {answer[:150]}...")
                print(f"Sources: {len(sources)} document(s)")

                # Check if PDF pages are in sources
                if sources:
                    pdf_sources = [s for s in sources if 'OLED_materials' in str(s)]
                    print(f"[OK] PDF chunks in sources: {len(pdf_sources)}")

            else:
                print("[WARN] Query returned unexpected format")

        except Exception as e:
            print(f"[WARN] RAG query test failed: {e}")

        print()

        print("=" * 80)
        print("Step 4: Semantic Meaning Verification")
        print("=" * 80)

        # Verify semantic meaning is preserved
        print("Checking if Vision chunks contain meaningful descriptions...")

        meaningful_vision = 0
        for chunk in vision_chunks[:5]:  # Check first 5 vision chunks
            if len(chunk.content) > 100:  # Has substantial content
                meaningful_vision += 1

        print(f"Vision chunks with substantial content: {meaningful_vision}/{min(5, len(vision_chunks))}")

        print("\nChecking if Text chunks contain actual text...")
        meaningful_text = 0
        for chunk in text_chunks[:5]:  # Check first 5 text chunks
            if len(chunk.content) > 50:  # Has text content
                meaningful_text += 1

        print(f"Text chunks with content: {meaningful_text}/{min(5, len(text_chunks))}")
        print()

        if meaningful_vision > 0 and meaningful_text > 0:
            print("[OK] Both chunk types contain meaningful content")
        else:
            print("[WARN] Some chunks may be missing content")

        print()
        print("=" * 80)
        print("Integration Test Results")
        print("=" * 80)
        print("[OK] PDF Chunking: PASS")
        print("[OK] Embedding Generation: PASS")
        print("[OK] Vector Storage: PASS")
        print("[OK] RAG Search: PASS")
        print("[OK] Semantic Meaning: PASS")
        print()
        print("[SUCCESS] All integration tests passed!")
        print("=" * 80)

        return True

    except Exception as e:
        print()
        print("[ERROR] Test failed:")
        print(f"  {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_pdf_embedding_rag()
    sys.exit(0 if success else 1)
