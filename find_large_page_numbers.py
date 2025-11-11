"""
ChromaDB에서 큰 페이지 번호를 가진 문서 찾기
"""
import chromadb

# ChromaDB 클라이언트 초기화
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection(name="documents")

# 전체 데이터 가져오기
all_data = collection.get(include=["metadatas"])
all_ids = all_data['ids']
all_metas = all_data['metadatas']

print(f"전체 문서 개수: {len(all_ids)}")

# 페이지 번호가 100 이상인 문서 찾기
large_page_docs = []
for i, (doc_id, metadata) in enumerate(zip(all_ids, all_metas)):
    page_number = metadata.get('page_number')
    if page_number is not None:
        try:
            page_num_int = int(page_number)
            if page_num_int >= 100:
                large_page_docs.append({
                    'index': i,
                    'id': doc_id,
                    'file_name': metadata.get('file_name', 'N/A'),
                    'page_number': page_num_int,
                    'source': metadata.get('source', 'N/A')
                })
        except (ValueError, TypeError):
            pass

print(f"\n페이지 번호 >= 100인 문서: {len(large_page_docs)}개")
if large_page_docs:
    for doc in large_page_docs:
        print(f"  인덱스 {doc['index']}: {doc['file_name']} - p.{doc['page_number']}")
else:
    print("  없음")

# 페이지 번호 범위 확인
page_numbers = []
for metadata in all_metas:
    page_num = metadata.get('page_number')
    if page_num is not None:
        try:
            page_numbers.append(int(page_num))
        except:
            pass

if page_numbers:
    print(f"\n페이지 번호 범위: {min(page_numbers)} ~ {max(page_numbers)}")
    print(f"페이지 번호 개수: {len(page_numbers)}")

# 파일별 페이지 번호 범위
file_pages = {}
for metadata in all_metas:
    file_name = metadata.get('file_name')
    page_num = metadata.get('page_number')
    if file_name and page_num is not None:
        try:
            page_num_int = int(page_num)
            if file_name not in file_pages:
                file_pages[file_name] = []
            file_pages[file_name].append(page_num_int)
        except:
            pass

print("\n파일별 페이지 번호 범위:")
for file_name, pages in sorted(file_pages.items()):
    pages_sorted = sorted(set(pages))
    print(f"  {file_name}: {min(pages_sorted)} ~ {max(pages_sorted)} ({len(pages_sorted)}개 페이지, 총 {len(pages)}개 청크)")
    if max(pages_sorted) > 100:
        print(f"    ⚠️ 주의: 페이지 번호가 100 이상!")

# 문서 인덱스와 ID 패턴 확인
print("\n\n인덱스와 ID 패턴 (처음 20개):")
for i in range(min(20, len(all_ids))):
    doc_id = all_ids[i]
    metadata = all_metas[i]
    print(f"  인덱스 {i}: ID={doc_id[:8]}..., 파일={metadata.get('file_name')}, 페이지={metadata.get('page_number')}")

# 특정 인덱스 확인 (809, 781이 인덱스일 수도 있음)
print("\n\n특정 인덱스 확인 (781, 809는 인덱스로 존재하지 않음 - 총 120개 문서만 있음)")
