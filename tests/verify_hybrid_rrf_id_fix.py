"""
Hybrid Search(RRF) doc_id 기준 변경 전/후를 '재현'하는 검증 스크립트.

의도:
- 기존 구현은 vector_rank에서 doc.metadata["source"](파일 경로)를 ID로 사용해,
  같은 파일에서 나온 서로 다른 청크들이 하나로 뭉개질 수 있었다.
- 또한 BM25는 Chroma의 ids를 쓰고, vector는 source를 써서 ID space가 달라
  RRF 결합이 왜곡될 수 있었다.

이 스크립트는 외부 임베딩/DB 없이, 가짜 Document/메타데이터로
old 방식 vs new 방식(=chunk_id 기반 안정키)의 차이를 출력/검증한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, List, Tuple, Any


@dataclass
class FakeDoc:
    page_content: str
    metadata: dict


def old_vector_key(meta: dict) -> str:
    # 과거: 파일 경로/출처로 뭉개짐(문서 단위)
    return meta.get("source", "")


def new_stable_chunk_key(meta: dict) -> str:
    # 현재: chunk_id 우선 (없으면 조합키)
    if meta.get("chunk_id"):
        return f"chunk_id:{meta['chunk_id']}"
    doc_id = meta.get("document_id")
    slide = meta.get("slide_number")
    if doc_id is not None and slide is not None:
        return f"pptx:{meta.get('file_name','')}:{doc_id}:s{slide}:{meta.get('chunk_type','')}"
    return f"doc:{meta.get('file_name','')}|p:{meta.get('page_number','')}|ci:{meta.get('chunk_index','')}"


def rrf_scores(vector_rank: Dict[str, int], bm25_rank: Dict[str, int], C: float = 60.0) -> Dict[str, float]:
    scores = defaultdict(float)
    all_ids = set(vector_rank.keys()) | set(bm25_rank.keys())
    for did in all_ids:
        if did in vector_rank:
            scores[did] += 1.0 / (C + vector_rank[did])
        if did in bm25_rank:
            scores[did] += 1.0 / (C + bm25_rank[did])
    return dict(scores)


def build_rank_from_vector(candidates: List[Tuple[FakeDoc, float]], key_fn) -> Dict[str, int]:
    rank = {}
    for r, (doc, _s) in enumerate(candidates, start=1):
        k = key_fn(doc.metadata)
        if k and k not in rank:
            rank[k] = r
    return rank


def main() -> None:
    # 같은 파일(source 동일)에서 나온 서로 다른 청크 3개를 가정
    vec_candidates = [
        (FakeDoc("A page1 chunk", {"source": "fileA.pdf", "file_name": "fileA.pdf", "chunk_id": "A_p1"}), 0.1),
        (FakeDoc("A page2 chunk", {"source": "fileA.pdf", "file_name": "fileA.pdf", "chunk_id": "A_p2"}), 0.2),
        (FakeDoc("A page3 chunk", {"source": "fileA.pdf", "file_name": "fileA.pdf", "chunk_id": "A_p3"}), 0.3),
    ]

    # BM25도 같은 3개를 각각 별도 문서로 다룬다고 가정(여기서는 chunk_id를 키로 사용 가능하다고 가정)
    # (실제 구현에서는 metadatas에서 stable_key를 만들고 bm25_rank를 구성)
    bm25_rank_old_space = {
        # 기존 코드의 문제: BM25는 chroma ids 등 다른 ID space를 쓰는 경우가 많음
        "chroma_id_1": 1,
        "chroma_id_2": 2,
        "chroma_id_3": 3,
    }
    bm25_rank_new_space = {
        "chunk_id:A_p2": 1,
        "chunk_id:A_p1": 2,
        "chunk_id:A_p3": 3,
    }

    # --- BEFORE: old vector ID (source) ---
    v_rank_old = build_rank_from_vector(vec_candidates, old_vector_key)
    s_old = rrf_scores(v_rank_old, bm25_rank_old_space)

    # --- AFTER: new stable chunk key ---
    v_rank_new = build_rank_from_vector(vec_candidates, new_stable_chunk_key)
    # new space에서는 BM25도 같은 key space로 들어온다고 가정(=수정 목표)
    s_new = rrf_scores(v_rank_new, bm25_rank_new_space)

    print("=== BEFORE (old: vector id = source) ===")
    print("vector_rank_keys:", list(v_rank_old.keys()))
    print("vector_rank_size:", len(v_rank_old))
    print("rrf_union_size:", len(s_old))
    print("top_ids:", sorted(s_old.items(), key=lambda x: x[1], reverse=True)[:5])

    print("\n=== AFTER (new: vector id = stable chunk key) ===")
    print("vector_rank_keys(sample):", list(v_rank_new.keys())[:5])
    print("vector_rank_size:", len(v_rank_new))
    print("rrf_union_size:", len(s_new))
    print("top_ids:", sorted(s_new.items(), key=lambda x: x[1], reverse=True)[:5])

    # 핵심 검증: old는 동일 파일이 1개로 뭉개지고, new는 3개가 유지됨
    assert len(v_rank_old) == 1, "old 방식은 source 기준이라 같은 파일 청크가 1개로 뭉개져야 합니다"
    assert len(v_rank_new) == 3, "new 방식은 chunk_id 기준이라 청크 단위로 3개가 유지되어야 합니다"

    print("\n[OK] old vs new 차이가 재현되었습니다.")


if __name__ == "__main__":
    main()

