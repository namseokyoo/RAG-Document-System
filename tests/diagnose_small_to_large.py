"""
Small-to-Large 진단 스크립트
실제로 어떤 문서가 반환되는지 상세 분석
"""

import json
import os
import sys
from pathlib import Path

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
from utils.small_to_large_search import SmallToLargeSearch

print("=" * 80)
print("Small-to-Large 진단 스크립트")
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

# Small-to-Large 검색 초기화
print(f"\n[2단계] Small-to-Large 검색 초기화")
stl_search = SmallToLargeSearch(vector_manager)
print(f"  - Small-to-Large 검색 초기화 완료")

# 테스트 질문 - 하나만
test_question = "MIPS란 무엇인가?"

print(f"\n[3단계] 진단 테스트")
print(f"  질문: {test_question}")

# Context Size 600으로 테스트
context_size = 600

print(f"\n{'=' * 80}")
print(f"Context Size = {context_size}")
print(f"{'=' * 80}")

try:
    # 내부 동작을 추적하기 위해 직접 구현
    print(f"\n[검색 시작]")

    # 1단계: Small 청크 검색
    print(f"\n[1단계] Small 청크 검색 (k=10)")
    small_results = vector_manager.similarity_search_with_score(test_question, k=10)

    print(f"  검색된 Small 청크: {len(small_results)}개")
    for i, (doc, score) in enumerate(small_results[:3], 1):
        print(f"\n  [{i}] Score: {score:.4f}")
        print(f"      길이: {len(doc.page_content)}자")
        print(f"      Chunk Type: {doc.metadata.get('chunk_type', '?')}")
        print(f"      Parent ID: {doc.metadata.get('parent_chunk_id', '없음')}")
        print(f"      내용: {doc.page_content[:100]}...")

    # 2단계: 부모 청크 확장 추적
    print(f"\n[2단계] 부모 청크 확장 추적 (max_parents=3)")

    expanded_results = []
    processed_parents = set()
    parent_count = 0
    content_hashes = set()

    for i, (doc, score) in enumerate(small_results, 1):
        print(f"\n  처리 중: Small 청크 #{i}")

        # 콘텐츠 해시 체크
        import hashlib
        content_hash = hashlib.md5(doc.page_content.encode()).hexdigest()
        if content_hash in content_hashes:
            print(f"    -> SKIP: 중복 콘텐츠")
            continue

        # Small 청크 추가
        expanded_results.append((doc, score, "small"))
        content_hashes.add(content_hash)
        print(f"    -> 추가: Small 청크 (score={score:.4f})")

        # 부모 청크 확장
        if parent_count >= 3:
            print(f"    -> SKIP: 부모 개수 제한 도달 ({parent_count}/3)")
            continue

        parent_id = doc.metadata.get("parent_chunk_id")
        if not parent_id:
            print(f"    -> SKIP: parent_chunk_id 없음")
            continue

        if parent_id in processed_parents:
            print(f"    -> SKIP: 이미 처리된 부모 ({parent_id})")
            continue

        # 부모 청크 조회
        print(f"    -> 부모 조회 중: {parent_id}")
        parent_doc = stl_search._get_parent_chunk(parent_id)

        if not parent_doc:
            print(f"    -> SKIP: 부모 청크 조회 실패")
            continue

        print(f"    -> 부모 찾음: 길이 {len(parent_doc.page_content)}자")

        # 유사도 체크
        is_similar = stl_search._is_similar_content(
            doc.page_content,
            parent_doc.page_content,
            threshold=0.9
        )
        if is_similar:
            print(f"    -> SKIP: 부모와 유사도 >= 0.9")
            continue

        # 부분 컨텍스트 추출
        print(f"    -> 부분 컨텍스트 추출 중 (context_size={context_size})")
        partial_parent = stl_search._extract_partial_context(
            parent_doc.page_content,
            doc.page_content,
            context_size=context_size
        )

        print(f"    -> 추출된 길이: {len(partial_parent)}자")
        print(f"    -> 원본 child 길이: {len(doc.page_content)}자")
        print(f"    -> 원본 parent 길이: {len(parent_doc.page_content)}자")

        if partial_parent and partial_parent != doc.page_content:
            from langchain.schema import Document
            partial_parent_doc = Document(
                page_content=partial_parent,
                metadata={
                    **parent_doc.metadata,
                    "expanded_from": doc.metadata.get("chunk_id", ""),
                    "is_partial_parent": True
                }
            )

            parent_score = score * 0.8
            expanded_results.append((partial_parent_doc, parent_score, "parent"))
            processed_parents.add(parent_id)
            parent_count += 1
            print(f"    -> 추가: Partial Parent (score={parent_score:.4f})")
        else:
            print(f"    -> SKIP: partial_parent가 child와 동일")

    # 3단계: 정렬 및 최종 선택
    print(f"\n[3단계] 정렬 및 최종 선택")
    print(f"  확장된 결과 총 {len(expanded_results)}개")

    # 점수로 정렬
    expanded_results.sort(key=lambda x: x[1], reverse=True)

    print(f"\n  정렬된 상위 10개:")
    for i, (doc, score, doc_type) in enumerate(expanded_results[:10], 1):
        print(f"    {i}. [{doc_type:6s}] Score: {score:.4f}, 길이: {len(doc.page_content):4d}자")

    # 중복 제거
    final_results = stl_search._deduplicate_by_similarity(
        [(doc, score) for doc, score, _ in expanded_results],
        threshold=0.85
    )

    print(f"\n  중복 제거 후: {len(final_results)}개")

    # Top 5 선택
    top5 = final_results[:5]

    print(f"\n[최종 결과] Top 5")
    for i, (doc, score) in enumerate(top5, 1):
        is_parent = doc.metadata.get("is_partial_parent", False)
        doc_type = "Partial Parent" if is_parent else "Small Chunk"
        print(f"\n  [{i}] {doc_type}")
        print(f"      Score: {score:.4f}")
        print(f"      길이: {len(doc.page_content)}자")
        print(f"      내용: {doc.page_content[:150]}...")

    # 통계
    parent_count_final = sum(1 for doc, _ in top5 if doc.metadata.get("is_partial_parent", False))
    small_count_final = len(top5) - parent_count_final
    avg_length = sum(len(doc.page_content) for doc, _ in top5) / len(top5)

    print(f"\n[통계]")
    print(f"  - Small 청크: {small_count_final}개")
    print(f"  - Partial Parent: {parent_count_final}개")
    print(f"  - 평균 길이: {avg_length:.0f}자")

except Exception as e:
    print(f"\n[오류] {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("진단 완료!")
print("=" * 80)
