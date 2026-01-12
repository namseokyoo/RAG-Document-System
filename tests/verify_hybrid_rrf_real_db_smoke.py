"""
실제 로컬 ChromaDB(data/chroma_db)를 대상으로 Hybrid(RRF) 전/후를 비교하는 스모크 테스트.

비교 대상:
- BEFORE(구 방식): vector_rank 키 = metadata["source"](파일 단위로 뭉개질 위험) + bm25_rank 키 = self.doc_ids(Chroma id)
- AFTER(신 방식): VectorStoreManager.similarity_search_hybrid() (chunk_id 기반 stable key로 vector/bm25 동일 key space)

주의:
- 이 테스트는 실제 임베딩 쿼리 생성이 필요하므로, embedding_base_url(Ollama)이 실행 중이어야 합니다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from langchain.schema import Document


def _old_rrf_simulate(
    vm,
    query: str,
    initial_k: int,
    top_k: int,
) -> List[Tuple[Document, float]]:
    """
    과거 구현(문제 있는 방식)을 '가급적 동일하게' 시뮬레이션.
    - vector_rank: doc.metadata['source'] 기준
    - bm25_rank: self.doc_ids(Chroma ids) 기준
    - 이후 ranked_ids를 source/Chroma id로 doc 재구성 시도
    """
    vector_candidates = vm.vectorstore.similarity_search_with_score(query, k=initial_k)
    if not vector_candidates:
        return []

    # BM25 준비 확인
    if not (getattr(vm, "bm25_ready", False) and getattr(vm, "bm25", None) is not None):
        return []

    query_tokens = vm._tokenize(query)
    if not query_tokens:
        return []
    bm25_scores = vm.bm25.get_scores(query_tokens)

    # vector_rank (source 기반)
    vector_rank: Dict[str, int] = {}
    for r, (doc, _score) in enumerate(vector_candidates, start=1):
        did = (doc.metadata or {}).get("source", "")
        if did and did not in vector_rank:
            vector_rank[did] = r

    # bm25_rank (Chroma id 기반)
    bm25_rank: Dict[str, int] = {}
    bm25_sorted = sorted(list(enumerate(bm25_scores)), key=lambda x: x[1], reverse=True)
    for r, (idx, _s) in enumerate(bm25_sorted, start=1):
        if 0 <= idx < len(vm.doc_ids):
            did = vm.doc_ids[idx]
            if did and did not in bm25_rank:
                bm25_rank[did] = r

    # RRF 계산
    rrf_scores: Dict[str, float] = defaultdict(float)
    C = 60.0
    all_ids = set(vector_rank.keys()) | set(bm25_rank.keys())
    for did in all_ids:
        if did in vector_rank:
            rrf_scores[did] += 1.0 / (C + vector_rank[did])
        if did in bm25_rank:
            rrf_scores[did] += 1.0 / (C + bm25_rank[did])

    ranked_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    # 컬렉션 로드
    coll = vm.vectorstore._collection
    data = coll.get()
    docs_raw = data.get("documents", []) or []
    metas_raw = data.get("metadatas", []) or []
    ids_raw = data.get("ids", []) or []
    id_to_index = {idv: i for i, idv in enumerate(ids_raw)}

    results: List[Tuple[Document, float]] = []
    for did, score in ranked_ids:
        doc_obj: Optional[Document] = None
        # 1) vector 후보에서 source 매칭
        for d, _ in vector_candidates:
            if (d.metadata or {}).get("source", "") == did:
                doc_obj = d
                break
        # 2) Chroma id로 재구성
        if doc_obj is None and did in id_to_index:
            idx = id_to_index[did]
            if 0 <= idx < len(docs_raw):
                meta = metas_raw[idx] if idx < len(metas_raw) else {}
                doc_obj = Document(page_content=docs_raw[idx], metadata=meta or {})
        if doc_obj is not None:
            results.append((doc_obj, float(score)))
    return results


def _summarize_results(tag: str, results: List[Tuple[Document, float]]) -> None:
    print("\n" + "=" * 80)
    print(tag)
    print("results:", len(results))

    # (file_name, page_number) 다양성
    pairs = []
    for doc, _s in results:
        m = doc.metadata or {}
        pairs.append((m.get("file_name", "Unknown"), m.get("page_number", m.get("slide_number", "?"))))
    unique_pairs = list(dict.fromkeys(pairs))
    print("unique(file,page_or_slide):", len(unique_pairs))
    print("top unique pairs (first 10):", unique_pairs[:10])

    # 파일 분포
    counts: Dict[str, int] = {}
    for fn, _p in pairs:
        counts[fn] = counts.get(fn, 0) + 1
    top_files = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    print("top files by count:", top_files)

    # 상위 결과 일부
    print("\nTop items:")
    for i, (doc, score) in enumerate(results[:10], start=1):
        m = doc.metadata or {}
        print(
            f"{i:02d}. score={score:.6f} "
            f"file={m.get('file_name','?')} page/slide={m.get('page_number', m.get('slide_number','?'))} "
            f"chunk_id={m.get('chunk_id','-')} chunk_type={m.get('chunk_type','-')}"
        )


def main() -> int:
    # tests/ 아래에서 실행되어도 루트 모듈(import config 등)이 잡히도록 경로 보정
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from config import ConfigManager
    from utils.vector_store import VectorStoreManager

    cfg = ConfigManager().get_all()
    query = os.getenv("QUERY", "OLED efficiency EQE")
    initial_k = int(os.getenv("INITIAL_K", "40"))
    top_k = int(os.getenv("TOP_K", "10"))

    vm = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=cfg.get("embedding_api_type", "ollama"),
        embedding_base_url=cfg.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=cfg.get("embedding_model", "mxbai-embed-large"),
        embedding_api_key=cfg.get("embedding_api_key", ""),
        shared_db_enabled=False,
        distance_function=cfg.get("chroma_distance_function", "cosine"),
    )

    # BM25를 동기적으로 준비(테스트 안정성)
    if getattr(vm, "bm25", None) is not None and not getattr(vm, "bm25_ready", False):
        try:
            with vm.bm25_lock:
                vm._load_bm25_corpus()
                # 로드가 끝났다면 ready를 강제로 True로 올림(콘솔 인코딩 경고가 나도 테스트는 진행)
                vm.bm25_ready = True
        except Exception:
            pass

    print("QUERY:", query)
    print("initial_k:", initial_k, "top_k:", top_k)
    print("bm25_ready:", getattr(vm, "bm25_ready", False))

    before = _old_rrf_simulate(vm, query=query, initial_k=initial_k, top_k=top_k)
    after = vm.similarity_search_hybrid(query=query, initial_k=initial_k, top_k=top_k)

    _summarize_results("BEFORE (simulated old RRF: vector id=source, bm25 id=chroma_id)", before)
    _summarize_results("AFTER  (new RRF: stable chunk key, vector/bm25 same key space)", after)

    # 핵심 시그널: old는 (file,page) 다양성이 떨어지기 쉽고, union id space가 섞여 빈약해질 수 있음
    # 여기서는 최소한 결과가 비어있지 않음을 확인
    if not after:
        print("\n[WARN] AFTER 결과가 비어있습니다. 임베딩/DB 상태를 확인하세요.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

