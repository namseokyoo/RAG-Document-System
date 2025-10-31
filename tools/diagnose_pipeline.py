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


def print_header(title: str):
    print("=" * 100)
    print(title)
    print("=" * 100)


def main():
    cfg = ConfigManager()
    conf = cfg.get_all()

    # 설정 표시
    print_header("[1/4] 설정 요약")
    print(json.dumps({
        "embedding_api_type": conf.get("embedding_api_type"),
        "embedding_base_url": conf.get("embedding_base_url"),
        "embedding_model": conf.get("embedding_model"),
        "top_k": conf.get("top_k"),
        "use_reranker": conf.get("use_reranker"),
        "reranker_initial_k": conf.get("reranker_initial_k"),
        "reranker_top_k": conf.get("reranker_top_k"),
    }, ensure_ascii=False, indent=2))

    # 벡터스토어 초기화
    vsm = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=conf.get("embedding_api_type"),
        embedding_base_url=conf.get("embedding_base_url"),
        embedding_model=conf.get("embedding_model"),
        embedding_api_key=conf.get("embedding_api_key", "")
    )

    # [2/4] 벡터 스토어 상태
    print_header("[2/4] 벡터 스토어 상태 점검")
    try:
        import chromadb
        client = chromadb.PersistentClient(path=vsm.persist_directory)
        coll = client.get_or_create_collection(name="documents")
        count = coll.count()
        print(f"✅ 컬렉션 문서(청크) 수: {count}")
        peek = coll.peek(limit=1)
        print(f"샘플 메타데이터 키: {list((peek.get('metadatas') or [{}])[0].keys()) if peek else []}")
    except Exception as e:
        print(f"⚠️ 벡터 스토어 점검 실패: {e}")

    # 파일별 청크 개수 요약
    files = vsm.get_documents_list()
    print(f"파일 개수: {len(files)}")
    for f in files[:10]:
        print(f"- {f.get('file_name')} | chunks={f.get('chunk_count')} | type={f.get('file_type')}")
    if len(files) > 10:
        print(f"... 외 {len(files)-10}개 파일")

    # [3/4] 엔티티 인덱스 상태
    print_header("[3/4] 엔티티 인덱스 상태 점검")
    entity_index_path = os.path.join(os.path.dirname(vsm.persist_directory), "entity_index.json")
    exists = os.path.exists(entity_index_path)
    print(f"엔티티 인덱스 파일 존재: {exists} ({entity_index_path})")
    if exists:
        try:
            with open(entity_index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"✅ 엔티티 인덱스 로드: {len(data)}개 청크")
            # 임의 3개 샘플 키
            sample_keys = list(data.keys())[:3]
            for k in sample_keys:
                print(f"- chunk_id={k} -> {list((data[k] or {}).keys())}")
        except Exception as e:
            print(f"⚠️ 엔티티 인덱스 파싱 실패: {e}")

    # [4/4] 키워드 간이 검색 재검증
    print_header("[4/4] 키워드 기반 간이 검색 (hybrid 폴백 포함) 재검증")
    keywords = ["TADF", "ACRSA", "HF"]
    for kw in keywords:
        print("-" * 60)
        print(f"쿼리: {kw}")
        try:
            # 하이브리드 검색: 임베딩 실패 시 BM25-only로 자동 폴백
            results = vsm.similarity_search_hybrid(kw, initial_k=40, top_k=5)
            if not results:
                print("결과 없음")
                continue
            for i, (doc, score) in enumerate(results, 1):
                meta = doc.metadata or {}
                print(f"#{i} score={score:.4f} file={meta.get('file_name')} page={meta.get('page_number')} type={meta.get('chunk_type')} heading={meta.get('heading_level')} section={meta.get('section_number')}")
                print(doc.page_content[:120].replace('\n', ' ') + ("..." if len(doc.page_content) > 120 else ""))
        except Exception as e:
            print(f"검색 실패: {e}")


if __name__ == "__main__":
    main()


