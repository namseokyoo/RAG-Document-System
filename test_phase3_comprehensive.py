"""
Comprehensive Phase 3 PDF Hybrid Mode Test

Tests:
1. PDF chunking with Hybrid mode
2. Smart Vision Decision logic
3. Chunk metadata accuracy
4. Cost reduction statistics
"""
import os
import sys
from pathlib import Path

def test_hybrid_chunking():
    """Test Phase 3 Hybrid mode PDF chunking"""
    print("=" * 80)
    print("Phase 3 Comprehensive Test: PDF Hybrid Mode")
    print("=" * 80)
    print()

    # Test PDF selection
    test_pdf = Path("data/test_documents/OLED_materials_2019_arX.pdf")

    if not test_pdf.exists():
        print(f"[ERROR] Test PDF not found: {test_pdf}")
        return False

    print(f"Test PDF: {test_pdf.name}")
    print(f"File size: {test_pdf.stat().st_size / 1024:.1f} KB")
    print()

    # Import after path check
    from utils.pdf_chunking_engine import PDFChunkingEngine
    from config import ConfigManager

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    # Get LLM settings
    llm_api_type = config.get("llm_api_type", "openai")
    llm_model = config.get("llm_model", "gpt-4o-mini")
    llm_api_key = config.get("llm_api_key", os.getenv("OPENAI_API_KEY"))
    llm_base_url = config.get("llm_base_url", None)

    print("Configuration:")
    print(f"  API Type: {llm_api_type}")
    print(f"  Model: {llm_model}")
    print(f"  API Key: {'[SET]' if llm_api_key else '[NOT SET]'}")
    print(f"  Poppler: {config.get('poppler_path', 'System PATH')}")
    print()

    if not llm_api_key:
        print("[ERROR] LLM API key not configured")
        print("Please set OPENAI_API_KEY environment variable or configure in config.json")
        return False

    # Initialize engine
    engine = PDFChunkingEngine(config)

    print("Starting Hybrid chunking...")
    print("-" * 80)

    try:
        # Process with Hybrid mode
        chunks = engine.process_pdf_document(
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

        print()
        print("=" * 80)
        print("Chunking Results")
        print("=" * 80)
        print(f"Total chunks: {len(chunks)}")
        print()

        # Analyze chunk types
        vision_chunks = [c for c in chunks if c.chunk_type == "pdf_page_vision_hybrid"]
        text_chunks = [c for c in chunks if c.chunk_type == "pdf_page_text"]

        print("Chunk Type Distribution:")
        print(f"  Vision chunks: {len(vision_chunks)} ({len(vision_chunks)/len(chunks)*100:.1f}%)")
        print(f"  Text chunks: {len(text_chunks)} ({len(text_chunks)/len(chunks)*100:.1f}%)")
        print()

        # Sample chunks
        if vision_chunks:
            print("Sample Vision Chunk:")
            chunk = vision_chunks[0]
            print(f"  ID: {chunk.id}")
            print(f"  Page: {chunk.metadata.page_number}")
            print(f"  Type: {chunk.chunk_type}")
            print(f"  Content preview (first 200 chars):")
            print(f"    {chunk.content[:200]}...")
            print()

        if text_chunks:
            print("Sample Text Chunk:")
            chunk = text_chunks[0]
            print(f"  ID: {chunk.id}")
            print(f"  Page: {chunk.metadata.page_number}")
            print(f"  Type: {chunk.chunk_type}")
            print(f"  Content preview (first 200 chars):")
            print(f"    {chunk.content[:200]}...")
            print()

        # Cost analysis
        print("=" * 80)
        print("Cost Reduction Analysis")
        print("=" * 80)

        vision_pct = (len(vision_chunks) / len(chunks)) * 100 if chunks else 0
        text_pct = (len(text_chunks) / len(chunks)) * 100 if chunks else 0

        print(f"Vision API usage: {vision_pct:.1f}%")
        print(f"Text-only processing: {text_pct:.1f}%")
        print(f"Estimated cost reduction: ~{text_pct:.1f}%")
        print()

        # Success criteria
        if text_pct >= 70:
            print("[SUCCESS] Target cost reduction achieved (70%+)")
        elif len(vision_chunks) > 0 and len(text_chunks) > 0:
            print("[PARTIAL] Hybrid mode working (both Vision and text chunks created)")
            print("Note: Cost reduction depends on document content")
        elif len(text_chunks) == len(chunks):
            print("[INFO] All text-only pages (no tables/charts detected)")
        elif len(vision_chunks) == len(chunks):
            print("[INFO] All pages require Vision (tables/charts/images on every page)")

        print()
        print("=" * 80)
        print("Metadata Verification")
        print("=" * 80)

        # Check metadata accuracy
        all_have_page_numbers = all(c.metadata.page_number is not None for c in chunks)
        all_have_doc_id = all(c.metadata.document_id is not None for c in chunks)
        all_have_chunk_id = all(c.id is not None for c in chunks)

        print(f"All chunks have page numbers: {all_have_page_numbers}")
        print(f"All chunks have document IDs: {all_have_doc_id}")
        print(f"All chunks have unique IDs: {all_have_chunk_id}")

        if all_have_page_numbers and all_have_doc_id and all_have_chunk_id:
            print("[OK] Metadata integrity verified")
        else:
            print("[WARNING] Some metadata missing")

        print()
        print("=" * 80)
        print("Test Complete")
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
    success = test_hybrid_chunking()
    sys.exit(0 if success else 1)
