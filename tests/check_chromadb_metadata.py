"""
ChromaDB 메타데이터 진단 스크립트
페이지 번호 버그 조사용
"""
import chromadb
import json

# ChromaDB 클라이언트 초기화
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection(name="documents")

# 전체 데이터 개수 확인
total_count = collection.count()
print(f"전체 문서 개수: {total_count}")

# 샘플 데이터 가져오기 (처음 10개)
sample_data = collection.get(limit=10, include=["metadatas", "documents"])

print("\n=== 샘플 데이터 (첫 10개) ===")
for i, (doc_id, metadata, content) in enumerate(zip(
    sample_data['ids'],
    sample_data['metadatas'],
    sample_data['documents']
)):
    print(f"\n[{i}] ID: {doc_id}")
    print(f"  파일명: {metadata.get('file_name', 'N/A')}")
    print(f"  페이지 번호: {metadata.get('page_number', 'N/A')}")
    print(f"  페이지 번호 타입: {type(metadata.get('page_number'))}")
    print(f"  전체 메타데이터: {json.dumps(metadata, ensure_ascii=False, indent=2)}")
    print(f"  내용 (처음 100자): {content[:100]}...")

# 특정 범위의 ID 확인 (809, 781 근처)
print("\n\n=== ID 700-820 범위 확인 ===")
all_data = collection.get(include=["metadatas"])
all_ids = all_data['ids']
all_metas = all_data['metadatas']

# ID가 숫자인지 확인
numeric_ids = []
for doc_id in all_ids:
    try:
        numeric_ids.append(int(doc_id))
    except:
        pass

if numeric_ids:
    print(f"숫자 ID 범위: {min(numeric_ids)} ~ {max(numeric_ids)}")

    # 809와 781 근처 확인
    for target_id in [781, 809]:
        try:
            idx = all_ids.index(str(target_id))
            metadata = all_metas[idx]
            print(f"\nID {target_id}:")
            print(f"  파일명: {metadata.get('file_name', 'N/A')}")
            print(f"  페이지 번호: {metadata.get('page_number', 'N/A')}")
            print(f"  페이지 번호 타입: {type(metadata.get('page_number'))}")
            print(f"  전체 메타데이터: {json.dumps(metadata, ensure_ascii=False)}")
        except (ValueError, IndexError):
            print(f"\nID {target_id}: 존재하지 않음")
else:
    print("숫자 ID를 찾을 수 없습니다.")

# 페이지 번호 분포 확인
print("\n\n=== 페이지 번호 분포 ===")
page_numbers = [m.get('page_number') for m in all_metas if m.get('page_number') is not None]
if page_numbers:
    # 타입별 분류
    int_pages = [p for p in page_numbers if isinstance(p, int)]
    str_pages = [p for p in page_numbers if isinstance(p, str)]
    other_pages = [p for p in page_numbers if not isinstance(p, (int, str))]

    print(f"정수형 페이지 번호: {len(int_pages)}개")
    if int_pages:
        print(f"  범위: {min(int_pages)} ~ {max(int_pages)}")
        print(f"  샘플: {int_pages[:20]}")

    print(f"문자열 페이지 번호: {len(str_pages)}개")
    if str_pages:
        print(f"  샘플: {str_pages[:20]}")

    print(f"기타 타입: {len(other_pages)}개")
    if other_pages:
        print(f"  샘플: {other_pages[:20]}")
else:
    print("페이지 번호가 없습니다.")
