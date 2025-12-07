"""
페이지 번호 버그 검증:
page_number가 chunk_index와 연관되어 있는지 확인
"""
import chromadb

# ChromaDB 클라이언트 초기화
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection(name="documents")

# 전체 데이터 가져오기
all_data = collection.get(include=["metadatas"])
all_metas = all_data['metadatas']

print("=== 버그 검증: page_number vs chunk_index 관계 ===\n")

# PPTX 파일 중 page_number != slide_number인 케이스 찾기
bugs_found = []
for metadata in all_metas:
    if metadata.get('file_name', '').endswith('.pptx'):
        page_num = metadata.get('page_number')
        slide_num = metadata.get('slide_number')
        chunk_idx = metadata.get('chunk_index')

        if page_num is not None and chunk_idx is not None:
            # page_number가 chunk_index + 1과 같은지 확인
            if page_num == chunk_idx + 1:
                # slide_number와 다른지 확인
                if slide_num is not None and page_num != slide_num:
                    bugs_found.append({
                        'file': metadata.get('file_name'),
                        'page_number': page_num,
                        'slide_number': slide_num,
                        'chunk_index': chunk_idx
                    })

if bugs_found:
    print(f"⚠️ 버그 발견! {len(bugs_found)}개의 잘못된 page_number 발견\n")
    for i, bug in enumerate(bugs_found[:10]):
        print(f"{i+1}. {bug['file']}")
        print(f"   page_number: {bug['page_number']}")
        print(f"   slide_number: {bug['slide_number']}")
        print(f"   chunk_index: {bug['chunk_index']}")
        print(f"   => page_number = chunk_index + 1 (잘못됨!)\n")
else:
    print("✓ 현재 데이터베이스에서 버그 발견 안됨")
    print("  (모든 PPTX의 page_number == slide_number)")

# 추가 검증: PDF 파일도 확인
print("\n=== PDF 파일 검증 ===\n")
pdf_bugs = []
for metadata in all_metas:
    if metadata.get('file_name', '').endswith('.pdf'):
        page_num = metadata.get('page_number')
        chunk_idx = metadata.get('chunk_index')

        # page_number가 chunk_index + 1과 같은지 확인 (PDF는 이게 버그일 수 있음)
        if page_num is not None and chunk_idx is not None:
            if page_num == chunk_idx + 1:
                # 첫 몇개는 맞을 수 있지만, 항상 같으면 의심스러움
                pdf_bugs.append({
                    'file': metadata.get('file_name'),
                    'page_number': page_num,
                    'chunk_index': chunk_idx
                })

if len(pdf_bugs) == len([m for m in all_metas if m.get('file_name', '').endswith('.pdf')]):
    print("⚠️ 의심스러움: 모든 PDF 청크의 page_number = chunk_index + 1")
    print("   (PDF는 한 페이지에 여러 청크가 있을 수 있으므로 잘못된 패턴)")
else:
    print("✓ PDF의 page_number는 chunk_index와 독립적")
