"""
PPTX 메타데이터 버그 테스트
slide_number가 page_number로 매핑되지 않는 문제 확인
"""
import chromadb

# ChromaDB 클라이언트 초기화
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection(name="documents")

# 전체 데이터 가져오기
all_data = collection.get(include=["metadatas"])
all_metas = all_data['metadatas']

print("=== PPTX 파일의 page_number vs slide_number 확인 ===\n")

pptx_files_checked = set()
for metadata in all_metas:
    file_name = metadata.get('file_name', '')
    if file_name.endswith('.pptx') and file_name not in pptx_files_checked:
        pptx_files_checked.add(file_name)

        # 이 파일의 모든 청크 확인
        file_chunks = [m for m in all_metas if m.get('file_name') == file_name]

        has_page_number = any('page_number' in m for m in file_chunks)
        has_slide_number = any('slide_number' in m for m in file_chunks)

        print(f"파일: {file_name}")
        print(f"  청크 수: {len(file_chunks)}")
        print(f"  page_number 필드 있음: {has_page_number}")
        print(f"  slide_number 필드 있음: {has_slide_number}")

        if not has_page_number and has_slide_number:
            print(f"  ⚠️ BUG: page_number 없음! 인용 시 'p.?'로 표시됨")
            # 샘플 출력
            sample = next((m for m in file_chunks if 'slide_number' in m), None)
            if sample:
                print(f"  샘플 slide_number: {sample.get('slide_number')}")
        print()

print("\n=== PDF 파일의 page_number 확인 ===\n")

pdf_files_checked = set()
for metadata in all_metas:
    file_name = metadata.get('file_name', '')
    if file_name.endswith('.pdf') and file_name not in pdf_files_checked:
        pdf_files_checked.add(file_name)

        # 이 파일의 모든 청크 확인
        file_chunks = [m for m in all_metas if m.get('file_name') == file_name]

        has_page_number = any('page_number' in m for m in file_chunks)
        page_numbers = [m.get('page_number') for m in file_chunks if 'page_number' in m]

        print(f"파일: {file_name}")
        print(f"  청크 수: {len(file_chunks)}")
        print(f"  page_number 필드 있음: {has_page_number}")
        if page_numbers:
            print(f"  페이지 범위: {min(page_numbers)} ~ {max(page_numbers)}")
        print()
