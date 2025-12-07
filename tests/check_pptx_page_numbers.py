"""
PPTX 파일의 실제 page_number 값 확인
"""
import chromadb
import json

# ChromaDB 클라이언트 초기화
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection(name="documents")

# PPTX 파일 데이터 가져오기
all_data = collection.get(include=["metadatas", "documents"])
all_ids = all_data['ids']
all_metas = all_data['metadatas']
all_docs = all_data['documents']

print("=== PPTX 파일의 page_number vs slide_number 값 비교 ===\n")

# 첫번째 PPTX 파일의 처음 5개 청크 확인
pptx_chunks = []
for i, metadata in enumerate(all_metas):
    if metadata.get('file_name', '').endswith('.pptx'):
        pptx_chunks.append((i, metadata, all_docs[i][:100]))
    if len(pptx_chunks) >= 5:
        break

for idx, metadata, content in pptx_chunks:
    print(f"\n청크 {idx}:")
    print(f"  파일: {metadata.get('file_name')}")
    print(f"  slide_number: {metadata.get('slide_number')}")
    print(f"  page_number: {metadata.get('page_number')}")
    print(f"  chunk_index: {metadata.get('chunk_index')}")
    print(f"  내용: {content}...")

    # page_number가 chunk_index와 같은지 확인
    if metadata.get('page_number') == metadata.get('chunk_index'):
        print(f"  ⚠️ page_number == chunk_index! 잘못된 매핑!")
    elif metadata.get('page_number') == metadata.get('slide_number'):
        print(f"  ✓ page_number == slide_number (올바름)")
