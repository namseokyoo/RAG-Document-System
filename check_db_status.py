#!/usr/bin/env python3
"""
현재 ChromaDB 상태 확인 스크립트
"""

import chromadb
from chromadb.config import Settings
import json
from collections import Counter

def check_db_status():
    """ChromaDB 상태 확인"""

    print("=" * 60)
    print("ChromaDB 상태 확인")
    print("=" * 60)

    try:
        # ChromaDB 연결
        client = chromadb.PersistentClient(
            path='data/chroma_db',
            settings=Settings(anonymized_telemetry=False)
        )

        collection = client.get_collection('langchain')
        total_count = collection.count()

        print(f"\n📊 전체 통계:")
        print(f"  - 총 청크 수: {total_count:,}개")

        if total_count == 0:
            print("\n⚠️ DB가 비어있습니다!")
            return

        # 샘플 데이터 가져오기
        sample_size = min(100, total_count)
        results = collection.get(
            limit=sample_size,
            include=['metadatas']
        )

        metadatas = results['metadatas']

        # 문서별 통계
        sources = [m.get('source', 'Unknown') for m in metadatas]
        source_counter = Counter(sources)

        print(f"\n📁 문서별 청크 수 (샘플 기준):")
        for source, count in source_counter.most_common(10):
            print(f"  - {source}: {count}개")

        # 고유 문서 수 추정
        unique_sources = len(source_counter)
        estimated_total_sources = int(unique_sources * (total_count / sample_size))

        print(f"\n📄 문서 통계:")
        print(f"  - 샘플 내 고유 문서: {unique_sources}개")
        print(f"  - 전체 예상 문서: 약 {estimated_total_sources}개")
        print(f"  - 문서당 평균 청크: 약 {total_count / estimated_total_sources:.1f}개")

        # 메타데이터 필드 확인
        print(f"\n🔍 메타데이터 필드:")
        if metadatas:
            sample_meta = metadatas[0]
            for key in sample_meta.keys():
                print(f"  - {key}: {type(sample_meta[key]).__name__}")

        # 샘플 메타데이터 출력
        print(f"\n📝 샘플 메타데이터 (3개):")
        for i, meta in enumerate(metadatas[:3], 1):
            print(f"\n  [{i}]")
            for key, value in meta.items():
                if isinstance(value, str) and len(value) > 100:
                    value = value[:100] + "..."
                print(f"    {key}: {value}")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_db_status()
