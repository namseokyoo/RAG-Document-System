"""
ChromaDB에서 청크 관계 분석
parent_chunk_id가 있는 청크 비율 확인
"""

import os
import sys

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 환경 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from config import ConfigManager
from utils.vector_store import VectorStoreManager

print("=" * 80)
print("ChromaDB 청크 관계 분석")
print("=" * 80)

# Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

# VectorStore 초기화
print("\n[1단계] VectorStore 초기화")
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    embedding_api_key=config.get("embedding_api_key", ""),
)
print(f"  - VectorStore 초기화 완료")

# 전체 청크 가져오기
print(f"\n[2단계] 전체 청크 분석")

try:
    # ChromaDB collection에서 모든 데이터 가져오기
    collection = vector_manager.vectorstore._collection

    # 모든 문서의 메타데이터 가져오기 (배치 처리)
    all_data = collection.get(include=['metadatas'])

    total_chunks = len(all_data['ids'])
    print(f"  - 총 청크 수: {total_chunks:,}개")

    # 통계 수집
    chunk_types = {}
    has_parent = 0
    no_parent = 0
    parent_ids_found = set()

    for metadata in all_data['metadatas']:
        # Chunk Type 통계
        chunk_type = metadata.get('chunk_type', 'unknown')
        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

        # Parent Chunk ID 존재 여부
        parent_id = metadata.get('parent_chunk_id')
        if parent_id:
            has_parent += 1
            parent_ids_found.add(parent_id)
        else:
            no_parent += 1

    # 결과 출력
    print(f"\n[3단계] 청크 타입 분포")
    for chunk_type, count in sorted(chunk_types.items(), key=lambda x: x[1], reverse=True):
        percentage = count / total_chunks * 100
        print(f"  - {chunk_type:20s}: {count:5d}개 ({percentage:5.1f}%)")

    print(f"\n[4단계] 부모-자식 관계")
    print(f"  - parent_chunk_id 있음: {has_parent:,}개 ({has_parent/total_chunks*100:.1f}%)")
    print(f"  - parent_chunk_id 없음: {no_parent:,}개 ({no_parent/total_chunks*100:.1f}%)")
    print(f"  - 고유한 parent_id 수: {len(parent_ids_found):,}개")

    # Parent ID로 검색 가능한지 확인
    print(f"\n[5단계] Parent 청크 검색 가능 여부")
    if parent_ids_found:
        # 샘플 parent_id 몇 개 확인
        sample_parent_ids = list(parent_ids_found)[:3]

        for parent_id in sample_parent_ids:
            print(f"\n  Parent ID: {parent_id[:50]}...")

            # chunk_id로 검색
            results = collection.get(
                where={"chunk_id": parent_id},
                include=['metadatas', 'documents']
            )

            if results['ids']:
                print(f"    -> 찾음: {len(results['ids'])}개")
                if results['documents']:
                    doc_length = len(results['documents'][0])
                    chunk_type = results['metadatas'][0].get('chunk_type', '?')
                    print(f"    -> 길이: {doc_length}자, 타입: {chunk_type}")
            else:
                print(f"    -> 못 찾음")

    # 분석 요약
    print(f"\n" + "=" * 80)
    print("분석 요약")
    print("=" * 80)

    if has_parent / total_chunks < 0.3:
        print(f"\n[발견] parent_chunk_id가 있는 청크 비율이 낮습니다 ({has_parent/total_chunks*100:.1f}%)")
        print(f"  - 대부분의 청크가 Small-to-Large 확장 불가능")
        print(f"  - 이는 정상적인 동작일 수 있습니다:")
        print(f"    · page_summary 타입은 부모가 없음")
        print(f"    · 최상위 섹션 청크도 부모가 없을 수 있음")

    print(f"\n[Small-to-Large 동작 방식]")
    print(f"  1. 검색 시 상위 {has_parent/total_chunks*100:.1f}% 청크만 확장 가능")
    print(f"  2. 나머지 {no_parent/total_chunks*100:.1f}% 청크는 Small 청크 그대로 사용")
    print(f"  3. Partial Parent는 0.8배 점수로 추가됨")
    print(f"  4. 최종 Top-K는 점수순으로 선택")

    print(f"\n[Context Size 파라미터 영향]")
    print(f"  - parent_chunk_id가 있는 청크의 확장 크기에만 영향")
    print(f"  - 하지만 Partial Parent가 Top-K에 포함되려면:")
    print(f"    · 원본 Small 청크의 점수가 높아야 함")
    print(f"    · 0.8배 점수로도 상위권에 들어야 함")

except Exception as e:
    print(f"\n[오류] {e}")
    import traceback
    traceback.print_exc()

print(f"\n" + "=" * 80)
print("분석 완료!")
print("=" * 80)
