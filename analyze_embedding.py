"""
ChromaDB 임베딩 분석 스크립트
- 임베딩된 문서 통계
- 검색 결과 분석
- 문서별 청크 분포
"""
import sys
import os

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.vector_store import VectorStoreManager

def analyze_chromadb():
    """ChromaDB 임베딩 분석"""
    print("=" * 80)
    print("ChromaDB 임베딩 분석")
    print("=" * 80)

    # 1. VectorStoreManager 초기화
    config = ConfigManager().get_all()
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    # 2. Chroma collection 접근
    collection = vector_manager.vectorstore._collection
    all_docs = collection.get()

    print(f"\n[전체 통계]")
    print(f"  - 총 청크 개수: {len(all_docs['ids'])}")

    # 3. 문서별 청크 개수 분석
    file_stats = {}
    for i, metadata in enumerate(all_docs['metadatas']):
        file_name = metadata.get('file_name', 'unknown')
        if file_name not in file_stats:
            file_stats[file_name] = {
                'count': 0,
                'sample_text': None,
                'chunk_types': set()
            }
        file_stats[file_name]['count'] += 1

        # 샘플 텍스트 저장 (첫 번째 청크)
        if file_stats[file_name]['sample_text'] is None:
            file_stats[file_name]['sample_text'] = all_docs['documents'][i][:200]

        # 청크 타입 수집
        chunk_type = metadata.get('chunk_type', 'unknown')
        file_stats[file_name]['chunk_types'].add(chunk_type)

    print(f"\n[문서별 청크 분포]")
    for file_name, stats in sorted(file_stats.items(), key=lambda x: x[1]['count'], reverse=True):
        print(f"\n  파일: {file_name}")
        print(f"    - 청크 개수: {stats['count']}")
        print(f"    - 청크 타입: {', '.join(stats['chunk_types'])}")
        print(f"    - 샘플 텍스트: {stats['sample_text'][:100]}...")

    # 4. 테스트 쿼리로 검색 분석
    print("\n" + "=" * 80)
    print("[검색 테스트 분석]")
    print("=" * 80)

    test_queries = [
        "TADF 재료는?",
        "ACRSA 효율은?",
        "분기별 성과는?",
    ]

    for query in test_queries:
        print(f"\n[쿼리] {query}")
        print("-" * 60)

        # 쿼리 임베딩
        query_embedding = vector_manager.embeddings.embed_query(query)

        # Vector 검색
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5,
            include=['documents', 'metadatas', 'distances']
        )

        if results and results['ids'] and len(results['ids'][0]) > 0:
            print(f"  검색된 문서: {len(results['ids'][0])}개")
            for i, (doc_id, doc, metadata, distance) in enumerate(zip(
                results['ids'][0],
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ), 1):
                file_name = metadata.get('file_name', 'unknown')
                chunk_type = metadata.get('chunk_type', 'unknown')
                similarity = 1 - distance  # 거리를 유사도로 변환

                print(f"\n  [{i}위] 유사도: {similarity:.3f}")
                print(f"       파일: {file_name}")
                print(f"       청크 타입: {chunk_type}")
                print(f"       내용: {doc[:150]}...")
        else:
            print("  [ERROR] 검색 결과 없음")

    print("\n" + "=" * 80)
    print("분석 완료")
    print("=" * 80)


if __name__ == "__main__":
    try:
        analyze_chromadb()
    except Exception as e:
        print(f"\n[ERROR] 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
