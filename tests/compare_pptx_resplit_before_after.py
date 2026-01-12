"""
PPTX 고급 청킹(advanced_pptx_chunking ON)에서
재청킹(split_documents) 전/후 결과를 비교하는 스모크 스크립트.

목적:
- 기존(재청킹) 경로는 동일 메타데이터를 가진 청크가 여러 개로 복제되어
  chunk 경계/ID/추적이 깨질 수 있음.
- 신규(재청킹 금지) 경로는 고급 청킹 엔진이 만든 "이미 청킹된 Document"를 그대로 사용.

주의:
- 외부 호출/비용을 피하기 위해 테스트 실행 중에만 ConfigManager.get_all()을 몽키패치하여
  enable_vision_chunking=False, auto_convert_pptx_to_pdf=False로 강제합니다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from collections import Counter
from typing import Iterable, Tuple, Any


def _patch_config_for_test() -> None:
    """테스트 중에만 설정을 임시로 오버라이드 (파일 수정 없음)."""
    # tests/ 아래에서 실행되어도 루트 모듈(import config 등)이 잡히도록 경로 보정
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import config as _config

    orig_get_all = _config.ConfigManager.get_all

    def patched_get_all(self):  # type: ignore[no-untyped-def]
        cfg = orig_get_all(self)
        cfg = dict(cfg)
        cfg["enable_vision_chunking"] = False
        cfg["vision_enabled"] = False
        cfg["auto_convert_pptx_to_pdf"] = False  # PPTX 엔진 경로 강제
        return cfg

    _config.ConfigManager.get_all = patched_get_all  # type: ignore[method-assign]


def _make_identity_key(meta: dict) -> Tuple[Any, ...]:
    """
    PPTX 청크를 식별하는 '안정 키'.
    재청킹 시 동일 메타데이터가 여러 조각으로 복제되는지(=키 중복) 확인한다.
    """
    return (
        meta.get("document_id"),
        meta.get("slide_number"),
        meta.get("chunk_type"),
        meta.get("parent_chunk_id"),
        meta.get("table_id"),
        meta.get("row_index"),
        meta.get("col_index"),
        meta.get("item_number"),
        meta.get("bullet_level"),
    )


def _to_int_if_digits(x) -> int | None:
    if x is None:
        return None
    s = str(x)
    return int(s) if s.isdigit() else None


def _summarize(tag: str, chunks: Iterable) -> None:
    chunks = list(chunks)
    print(f"\n=== {tag} ===")
    print("chunks:", len(chunks))

    page_numbers = [((d.metadata or {}).get("page_number")) for d in chunks]
    slide_numbers = [((d.metadata or {}).get("slide_number")) for d in chunks]
    chunk_types = [((d.metadata or {}).get("chunk_type")) for d in chunks]

    pn_ints = [_to_int_if_digits(x) for x in page_numbers]
    pn_ints = [x for x in pn_ints if x is not None]
    sn_ints = [_to_int_if_digits(x) for x in slide_numbers]
    sn_ints = [x for x in sn_ints if x is not None]

    print("page_number_nonnull:", sum(x is not None for x in page_numbers))
    if pn_ints:
        print("page_number_min/max:", min(pn_ints), "/", max(pn_ints))
    print("slide_number_nonnull:", sum(x is not None for x in slide_numbers))
    if sn_ints:
        print("slide_number_min/max:", min(sn_ints), "/", max(sn_ints))

    print("chunk_type_nonnull:", sum(x is not None for x in chunk_types))

    keys = [_make_identity_key(d.metadata or {}) for d in chunks]
    c = Counter(keys)
    dup_keys = sum(1 for _k, v in c.items() if v > 1)
    print("unique_identity_keys:", len(c))
    print("duplicate_identity_keys(keys with >1 occurrences):", dup_keys)


def main() -> int:
    _patch_config_for_test()

    from utils.document_processor import DocumentProcessor
    from langchain.schema import Document

    pptx_dir = os.path.join("data", "test_pptx")
    candidates = [
        "chart_test.pptx",
        "advanced_02_product_plan.pptx",
        "complex_06_mixed_structures.pptx",
    ]
    pptx_paths = [os.path.join(pptx_dir, f) for f in candidates if os.path.exists(os.path.join(pptx_dir, f))]

    if not pptx_paths:
        print("[ERROR] data/test_pptx 에서 비교할 PPTX 파일을 찾지 못했습니다.")
        return 2

    proc = DocumentProcessor(
        chunk_size=1500,
        chunk_overlap=200,
        enable_advanced_pdf_chunking=False,
        enable_advanced_pptx_chunking=True,
        llm_client=None,
    )

    for pptx_path in pptx_paths[:3]:  # 대표 3개까지 (복합 구조 포함)
        print("\n" + "=" * 80)
        print("FILE:", pptx_path)

        docs = proc.load_document(pptx_path, "pptx")
        print("advanced_docs:", len(docs))
        # 재청킹이 실제로 발생 가능한지(=원본 청크가 text_splitter chunk_size를 넘는지) 확인
        lengths = [len(d.page_content or "") for d in docs]
        max_len = max(lengths) if lengths else 0
        over = sum(1 for x in lengths if x > proc.text_splitter._chunk_size)  # 내부값(1500) 참조
        print("advanced_doc_max_len:", max_len)
        print("advanced_docs_over_chunk_size:", over)

        # (A) BEFORE: old behavior (page_number overwrite) + resplit
        old_docs = []
        for i, d in enumerate(docs):
            meta = dict(d.metadata or {})
            meta.update(
                {
                    "file_name": os.path.basename(pptx_path),
                    "file_type": "pptx",
                    "file_path": pptx_path,
                    "upload_time": "TEST",
                    "category": "reference",
                    "page_number": meta.get("slide_number") or meta.get("page", i + 1),
                }
            )
            old_docs.append(Document(page_content=d.page_content, metadata=meta))

        old_split = proc.text_splitter.split_documents(old_docs)

        # (B) AFTER: new behavior (preserve page_number) + no resplit if already chunked
        new_docs = []
        for i, d in enumerate(docs):
            meta = dict(d.metadata or {})
            meta.update(
                {
                    "file_name": os.path.basename(pptx_path),
                    "file_type": "pptx",
                    "file_path": pptx_path,
                    "upload_time": "TEST",
                    "category": "reference",
                    "page_number": meta.get("page_number") or meta.get("slide_number") or meta.get("page", i + 1),
                }
            )
            new_docs.append(Document(page_content=d.page_content, metadata=meta))

        is_already_chunked = any(
            ("chunk_id" in (d.metadata or {}) or "chunk_type" in (d.metadata or {})) for d in new_docs
        )
        new_final = new_docs if is_already_chunked else proc.text_splitter.split_documents(new_docs)

        _summarize("A) BEFORE (old: resplit)", old_split)
        _summarize("B) AFTER (new: no resplit)", new_final)
        print("\nΔ chunks (old_split - new_final):", len(old_split) - len(new_final))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

