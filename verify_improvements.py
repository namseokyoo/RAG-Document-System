"""
개선 사항 실제 확인 - 청크 샘플 출력
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from utils.pptx_chunking_engine import PPTXChunkingEngine

# 테스트 파일
test_file = Path("data/test_pptx/complex_03_data_analysis_report.pptx")

if not test_file.exists():
    print(f"테스트 파일 없음: {test_file}")
    sys.exit(1)

print("="*80)
print("Phase 1 & 2 개선 사항 실제 확인")
print("="*80)

# 청킹 엔진 초기화
config = {
    "max_size": 300,
    "overlap_size": 50,
    "enable_small_to_large": True
}
chunker = PPTXChunkingEngine(config)

# PPT 처리
print(f"\n테스트 파일: {test_file.name}")
chunks = chunker.process_pptx_document(
    pptx_path=str(test_file),
    enable_vision=False
)

print(f"총 청크 수: {len(chunks)}개\n")

# 표 청크 찾기 (Phase 1 확인)
print("="*80)
print("[Phase 1 확인] 표 청크 개선 사항")
print("="*80)

table_found = False
for i, chunk in enumerate(chunks):
    if chunk.chunk_type == 'table_full':
        print(f"\n[청크 #{i+1}] {chunk.chunk_type}")
        print(f"슬라이드: {chunk.metadata.slide_number}")
        print(f"표 ID: {chunk.metadata.table_id}")
        print(f"\n[내용 미리보기]")
        print(chunk.content[:500])
        print("...")
        table_found = True
        break

if not table_found:
    print("\n[INFO] 표 청크를 찾을 수 없습니다.")

# 슬라이드 요약 청크 찾기 (Phase 2 확인)
print("\n" + "="*80)
print("[Phase 2 확인] 슬라이드 문맥 개선 사항")
print("="*80)

slide_summary_found = False
for i, chunk in enumerate(chunks):
    if chunk.chunk_type == 'slide_summary':
        print(f"\n[청크 #{i+1}] {chunk.chunk_type}")
        print(f"슬라이드: {chunk.metadata.slide_number}")
        print(f"\n[내용 미리보기]")
        print(chunk.content[:600])
        print("...")

        # 문맥 키워드 확인
        has_prev = "[이전 슬라이드]" in chunk.content
        has_current = "[현재 슬라이드]" in chunk.content
        has_next = "[다음 슬라이드]" in chunk.content

        print(f"\n[문맥 정보 확인]")
        print(f"  - 이전 슬라이드 포함: {'✓' if has_prev else '✗'}")
        print(f"  - 현재 슬라이드 마커: {'✓' if has_current else '✗'}")
        print(f"  - 다음 슬라이드 포함: {'✓' if has_next else '✗'}")

        slide_summary_found = True
        break

if not slide_summary_found:
    print("\n[INFO] 슬라이드 요약 청크를 찾을 수 없습니다.")

print("\n" + "="*80)
print("검증 완료")
print("="*80)
