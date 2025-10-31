"""
청크 품질 진단 스크립트
- DB에 저장된 실제 청크 내용 확인
- 검색 결과의 청크 내용과 길이 분석
- 청킹 전략 유효성 검증
- 임베딩 품질 점검
"""
import os
import sys
import json
from typing import List, Dict, Any

# ensure project root on sys.path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ConfigManager
from utils.vector_store import VectorStoreManager
import chromadb


def print_header(title: str):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def analyze_chunk_content_statistics(vsm: VectorStoreManager):
    """저장된 청크의 내용 통계 분석"""
    print_header("[1/5] 저장된 청크 내용 통계 분석")
    
    try:
        collection = vsm.vectorstore._collection
        data = collection.get(include=["documents", "metadatas"])
        
        documents = data.get("documents", []) or []
        metadatas = data.get("metadatas", []) or []
        
        if not documents:
            print("[WARNING] 저장된 청크가 없습니다.")
            return
        
        print(f"총 청크 수: {len(documents)}")
        
        # 청크 길이 분석
        lengths = [len(doc) for doc in documents]
        avg_length = sum(lengths) / len(lengths) if lengths else 0
        min_length = min(lengths) if lengths else 0
        max_length = max(lengths) if lengths else 0
        
        print(f"\n청크 길이 통계:")
        print(f"  평균: {avg_length:.1f}자")
        print(f"  최소: {min_length}자")
        print(f"  최대: {max_length}자")
        
        # 매우 짧은 청크 찾기 (10자 이하)
        short_chunks = [i for i, doc in enumerate(documents) if len(doc) <= 10]
        if short_chunks:
            print(f"\n[WARNING] 매우 짧은 청크 발견: {len(short_chunks)}개 (10자 이하)")
            print("샘플 5개:")
            for i in short_chunks[:5]:
                meta = metadatas[i] if i < len(metadatas) else {}
                print(f"  - 길이: {len(documents[i])}자 | 파일: {meta.get('file_name', 'Unknown')} | 페이지: {meta.get('page_number', 'Unknown')}")
                print(f"    내용: {repr(documents[i][:100])}")
        
        # 빈 청크 찾기
        empty_chunks = [i for i, doc in enumerate(documents) if len(doc.strip()) == 0]
        if empty_chunks:
            print(f"\n[WARNING] 빈 청크 발견: {len(empty_chunks)}개")
        
        # 의미 없는 단일 문자 청크 찾기
        single_char_chunks = [i for i, doc in enumerate(documents) if len(doc.strip()) == 1 and not doc.strip().isalnum()]
        if single_char_chunks:
            print(f"\n[WARNING] 단일 문자 청크 발견: {len(single_char_chunks)}개")
            print("샘플 10개:")
            for i in single_char_chunks[:10]:
                meta = metadatas[i] if i < len(metadatas) else {}
                print(f"  - 내용: {repr(documents[i])} | 파일: {meta.get('file_name', 'Unknown')} | 페이지: {meta.get('page_number', 'Unknown')}")
        
    except Exception as e:
        print(f"[ERROR] 청크 내용 분석 실패: {e}")
        import traceback
        traceback.print_exc()


def inspect_sample_chunks(vsm: VectorStoreManager, num_samples: int = 20):
    """샘플 청크 상세 조회"""
    print_header(f"[2/5] 샘플 청크 {num_samples}개 상세 조회")
    
    try:
        collection = vsm.vectorstore._collection
        data = collection.get(include=["documents", "metadatas"])
        
        documents = data.get("documents", []) or []
        metadatas = data.get("metadatas", []) or []
        
        if not documents:
            print("[WARNING] 저장된 청크가 없습니다.")
            return
        
        # 다양한 길이의 청크 샘플링
        indices = list(range(min(num_samples, len(documents))))
        
        for idx in indices:
            doc_content = documents[idx]
            meta = metadatas[idx] if idx < len(metadatas) else {}
            chunk_id = "chunk_" + str(idx)
            
            print(f"\n--- 청크 #{idx+1} ---")
            print(f"ID: {chunk_id}")
            print(f"파일: {meta.get('file_name', 'Unknown')}")
            print(f"페이지: {meta.get('page_number', 'Unknown')}")
            print(f"청크 타입: {meta.get('chunk_type', 'Unknown')}")
            print(f"길이: {len(doc_content)}자")
            print(f"내용 (처음 200자): {doc_content[:200]}")
            if len(doc_content) > 200:
                print(f"... (전체 {len(doc_content)}자)")
            
            # 메타데이터 요약
            important_meta = {k: v for k, v in meta.items() 
                            if k in ['chunk_type_weight', 'parent_chunk_id', 'section_title', 
                                    'heading_level', 'has_table', 'has_list', 'char_count']}
            if important_meta:
                print(f"중요 메타데이터: {important_meta}")
                
    except Exception as e:
        print(f"[ERROR] 샘플 청크 조회 실패: {e}")
        import traceback
        traceback.print_exc()


def test_search_query_chunks(vsm: VectorStoreManager, query: str = "이 논문에서 제안한 방법의 성능 지표와 수치"):
    """검색 쿼리로 반환되는 청크 확인"""
    print_header(f"[3/5] 검색 쿼리 테스트: '{query}'")
    
    try:
        # 하이브리드 검색으로 상위 12개 확인 (테스트와 동일한 개수)
        results = vsm.similarity_search_hybrid(query, initial_k=40, top_k=12)
        
        if not results:
            print("[WARNING] 검색 결과가 없습니다.")
            return
        
        print(f"검색된 청크 수: {len(results)}")
        
        for i, (doc, score) in enumerate(results, 1):
            meta = doc.metadata or {}
            content = doc.page_content
            
            print(f"\n--- 결과 #{i} (점수: {score:.4f}) ---")
            print(f"파일: {meta.get('file_name', 'Unknown')}")
            print(f"페이지: {meta.get('page_number', 'Unknown')}")
            print(f"청크 타입: {meta.get('chunk_type', 'Unknown')}")
            print(f"길이: {len(content)}자")
            print(f"내용 (전체): {repr(content)}")
            
            # 매우 짧은 내용 경고
            if len(content) <= 20:
                print(f"[WARNING] 매우 짧은 내용 (20자 이하)")
                
    except Exception as e:
        print(f"[ERROR] 검색 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


def verify_chunking_strategy(vsm: VectorStoreManager):
    """청킹 전략 검증"""
    print_header("[4/5] 청킹 전략 검증")
    
    try:
        collection = vsm.vectorstore._collection
        data = collection.get(include=["metadatas"])
        
        metadatas = data.get("metadatas", []) or []
        
        if not metadatas:
            print("[WARNING] 메타데이터가 없습니다.")
            return
        
        # 청크 타입별 통계
        chunk_types = {}
        for meta in metadatas:
            chunk_type = meta.get("chunk_type", "unknown")
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
        
        print("청크 타입별 분포:")
        for chunk_type, count in sorted(chunk_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {chunk_type}: {count}개")
        
        # Small-to-Large 구조 확인
        parent_chunks = sum(1 for meta in metadatas if meta.get("parent_chunk_id"))
        print(f"\nSmall-to-Large 구조:")
        print(f"  부모 청크가 있는 청크: {parent_chunks}개")
        print(f"  독립 청크: {len(metadatas) - parent_chunks}개")
        
        # 페이지별 청크 수 확인
        page_stats = {}
        for meta in metadatas:
            file_name = meta.get("file_name", "Unknown")
            page = meta.get("page_number", "Unknown")
            key = f"{file_name}:{page}"
            page_stats[key] = page_stats.get(key, 0) + 1
        
        print(f"\n페이지별 청크 수 통계:")
        print(f"  총 페이지: {len(page_stats)}개")
        
        if page_stats:
            avg_chunks_per_page = sum(page_stats.values()) / len(page_stats)
            print(f"  페이지당 평균 청크 수: {avg_chunks_per_page:.1f}개")
            
            # 청크가 많은 페이지 확인
            max_chunks = max(page_stats.values())
            pages_with_many = [k for k, v in page_stats.items() if v >= 10]
            if pages_with_many:
                print(f"  청크가 많은 페이지 (10개 이상): {len(pages_with_many)}개")
                print("  샘플:")
                for page_key in pages_with_many[:5]:
                    print(f"    - {page_key}: {page_stats[page_key]}개 청크")
        
    except Exception as e:
        print(f"[ERROR] 청킹 전략 검증 실패: {e}")
        import traceback
        traceback.print_exc()


def test_embedding_quality(vsm: VectorStoreManager):
    """임베딩 품질 테스트"""
    print_header("[5/5] 임베딩 품질 테스트")
    
    try:
        # 테스트 쿼리들
        test_queries = [
            "성능 지표",
            "실험 결과",
            "ACRSA",
            "TADF 재료"
        ]
        
        for query in test_queries:
            print(f"\n--- 쿼리: '{query}' ---")
            
            # 임베딩 생성 테스트
            try:
                embedding = vsm.embeddings.embed_query(query)
                print(f"[OK] 임베딩 생성 성공: 차원={len(embedding)}")
                
                # 벡터 검색 테스트
                results = vsm.vectorstore.similarity_search_with_score(query, k=3)
                if results:
                    print(f"[OK] 벡터 검색 성공: {len(results)}개 결과")
                    for i, (doc, score) in enumerate(results, 1):
                        print(f"  #{i} 점수: {score:.4f} | 내용 앞부분: {doc.page_content[:50]}")
                else:
                    print("[WARNING] 검색 결과 없음")
                    
            except Exception as e:
                print(f"[ERROR] 임베딩/검색 실패: {e}")
                
    except Exception as e:
        print(f"[ERROR] 임베딩 품질 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


def main():
    cfg = ConfigManager()
    conf = cfg.get_all()
    
    print("=" * 100)
    print("청크 품질 종합 진단 시작")
    print("=" * 100)
    
    # 설정 확인
    print(f"\n임베딩 설정:")
    print(f"  API 타입: {conf.get('embedding_api_type')}")
    print(f"  모델: {conf.get('embedding_model')}")
    print(f"  Base URL: {conf.get('embedding_base_url')}")
    
    # 벡터스토어 초기화
    vsm = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=conf.get("embedding_api_type"),
        embedding_base_url=conf.get("embedding_base_url"),
        embedding_model=conf.get("embedding_model"),
        embedding_api_key=conf.get("embedding_api_key", "")
    )
    
    # 진단 실행
    analyze_chunk_content_statistics(vsm)
    inspect_sample_chunks(vsm, num_samples=20)
    test_search_query_chunks(vsm, query="이 논문에서 제안한 방법의 성능 지표와 수치를 알려줘.")
    verify_chunking_strategy(vsm)
    test_embedding_quality(vsm)
    
    print_header("진단 완료")
    print("\n진단 결과를 검토하여 청킹 전략이나 임베딩 설정 개선이 필요한지 확인하세요.")


if __name__ == "__main__":
    main()

