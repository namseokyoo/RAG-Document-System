"""
RAG 알고리즘 및 파라미터 종합 분석
- 청킹 설정
- 임베딩 설정
- ChromaDB 거리 메트릭
- Reranker 설정
- Query Expansion 설정
- 기타 검색 알고리즘 파라미터
"""
import sys
import os

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.vector_store import VectorStoreManager

def analyze_algorithm_settings():
    """알고리즘 설정 종합 분석"""
    print("=" * 80)
    print("RAG 알고리즘 및 파라미터 종합 분석")
    print("=" * 80)

    # 1. Config 로드
    config = ConfigManager().get_all()

    print("\n[1. 청킹 설정]")
    chunk_size = config.get("chunk_size", 1500)
    chunk_overlap = config.get("chunk_overlap", 200)
    overlap_ratio = (chunk_overlap / chunk_size * 100) if chunk_size > 0 else 0

    print(f"  - chunk_size: {chunk_size}")
    print(f"  - chunk_overlap: {chunk_overlap}")
    print(f"  - overlap ratio: {overlap_ratio:.1f}%")

    # 청킹 크기 평가
    if chunk_size > 1000:
        print(f"  [경고] chunk_size가 매우 큼 (1000 이상)")
        print(f"         PPT는 슬라이드당 내용이 짧아 800 이하 권장")
    if overlap_ratio > 30:
        print(f"  [경고] overlap ratio가 높음 (30% 이상)")
        print(f"         중복 청크가 많아져 검색 노이즈 증가 가능")

    print("\n[2. 임베딩 설정]")
    print(f"  - embedding_api_type: {config.get('embedding_api_type')}")
    print(f"  - embedding_base_url: {config.get('embedding_base_url')}")
    print(f"  - embedding_model: {config.get('embedding_model')}")

    # VectorStoreManager 초기화
    vector_manager = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=config.get("embedding_api_key", ""),
    )

    print("\n[3. ChromaDB 설정]")
    collection = vector_manager.vectorstore._collection

    # Collection 메타데이터 확인
    print(f"  - collection name: {collection.name}")

    # Chroma collection의 메타데이터에서 거리 메트릭 확인
    try:
        collection_metadata = collection.metadata
        if collection_metadata:
            print(f"  - collection metadata: {collection_metadata}")

            # 거리 함수 확인
            if 'hnsw:space' in collection_metadata:
                distance_metric = collection_metadata['hnsw:space']
                print(f"  - distance metric: {distance_metric}")

                if distance_metric == "l2":
                    print(f"    (L2 Euclidean distance - 범위: [0, ∞))")
                elif distance_metric == "cosine":
                    print(f"    (Cosine similarity - 범위: [0, 2])")
                elif distance_metric == "ip":
                    print(f"    (Inner Product - 범위: (-∞, ∞), 음수 가능)")
            else:
                print(f"  [경고] 거리 메트릭 정보 없음 (기본값 l2 추정)")
    except Exception as e:
        print(f"  [오류] 메타데이터 확인 실패: {e}")

    # 총 문서 개수
    all_docs = collection.get()
    print(f"  - total chunks: {len(all_docs['ids'])}")

    print("\n[4. Reranker 설정]")
    print(f"  - use_reranker: {config.get('use_reranker')}")
    print(f"  - reranker_model: {config.get('reranker_model')}")
    print(f"  - reranker_initial_k: {config.get('reranker_initial_k')}")
    print(f"  - reranker_top_k (final): {config.get('reranker_top_k', config.get('top_k'))}")

    initial_k = config.get('reranker_initial_k', 20)
    final_k = config.get('reranker_top_k', config.get('top_k', 5))
    compression_ratio = (final_k / initial_k * 100) if initial_k > 0 else 0

    print(f"  - compression ratio: {initial_k} -> {final_k} ({compression_ratio:.1f}%)")

    if initial_k > 50:
        print(f"  [경고] reranker_initial_k가 매우 큼 (50 이상)")
        print(f"         초기 검색 비용이 높아지고 노이즈 증가 가능")

    print("\n[5. Query Expansion 설정]")
    print(f"  - enable_synonym_expansion: {config.get('enable_synonym_expansion')}")
    print(f"  - enable_multi_query: {config.get('enable_multi_query')}")
    print(f"  - multi_query_num: {config.get('multi_query_num')}")

    if config.get('enable_multi_query') and config.get('multi_query_num', 0) > 3:
        print(f"  [경고] multi_query_num이 높음 (3 이상)")
        print(f"         검색 비용 증가 및 노이즈 가능성")

    print("\n[6. 검색 알고리즘 설정]")
    print(f"  - top_k (최종 반환): {config.get('top_k')}")
    print(f"  - enable_hybrid_search: {config.get('enable_hybrid_search', 'N/A')}")
    print(f"  - hybrid_bm25_weight: {config.get('hybrid_bm25_weight', 'N/A')}")

    print("\n[7. LLM 설정]")
    print(f"  - llm_api_type: {config.get('llm_api_type')}")
    print(f"  - llm_model: {config.get('llm_model')}")
    print(f"  - temperature: {config.get('temperature')}")

    print("\n" + "=" * 80)
    print("종합 평가")
    print("=" * 80)

    issues = []
    recommendations = []

    # 청킹 크기 평가
    if chunk_size > 1000:
        issues.append("chunk_size가 매우 큼 (PPT에 부적합)")
        recommendations.append("chunk_size를 800 이하로 줄이기 (PPT 권장: 500-800)")

    # 오버랩 비율 평가
    if overlap_ratio > 30:
        issues.append("chunk_overlap 비율이 높음 (중복 증가)")
        recommendations.append("chunk_overlap을 15-20%로 줄이기")

    # Reranker initial_k 평가
    if initial_k > 50:
        issues.append("reranker_initial_k가 매우 큼 (검색 비용 증가)")
        recommendations.append("reranker_initial_k를 20-30으로 줄이기")

    # ChromaDB 오래된 데이터 확인
    file_stats = {}
    for metadata in all_docs['metadatas']:
        file_name = metadata.get('file_name', 'unknown')
        file_stats[file_name] = file_stats.get(file_name, 0) + 1

    embedded_files_dir = "data/embedded_documents"
    if os.path.exists(embedded_files_dir):
        actual_files = set(os.listdir(embedded_files_dir))
        chromadb_files = set(file_stats.keys())

        orphan_files = chromadb_files - actual_files
        if orphan_files:
            issues.append(f"ChromaDB에 실제 파일이 없는 문서 {len(orphan_files)}개 존재")
            recommendations.append("ChromaDB 초기화 (data/chroma_db 삭제 후 재임베딩)")
            print(f"\n[경고] 실제 파일이 없는 문서:")
            for f in list(orphan_files)[:5]:  # 최대 5개만 출력
                print(f"  - {f} ({file_stats[f]} 청크)")
            if len(orphan_files) > 5:
                print(f"  ... 외 {len(orphan_files) - 5}개")

    # 요약
    print(f"\n[발견된 문제점] ({len(issues)}개)")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")

    print(f"\n[권장사항] ({len(recommendations)}개)")
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec}")

    print("\n" + "=" * 80)
    print("분석 완료")
    print("=" * 80)


if __name__ == "__main__":
    try:
        analyze_algorithm_settings()
    except Exception as e:
        print(f"\n[ERROR] 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
