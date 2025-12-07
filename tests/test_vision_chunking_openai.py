"""
Vision 청킹 테스트 - OpenAI GPT-4o-mini 모델
- 간소화된 프롬프트 효과 측정
- 추출 품질 확인
- 속도 및 비용 측정
"""

import sys
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from utils.pptx_chunking_engine import PPTXChunkingEngine
from config import ConfigManager


def test_vision_chunking():
    """Vision 청킹 테스트"""
    print("=" * 80)
    print("Vision 청킹 테스트 - OpenAI GPT-4o-mini (간소화된 프롬프트)")
    print("=" * 80)

    # Config 로드
    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    print(f"\n현재 설정:")
    print(f"  - LLM API Type: {config['llm_api_type']}")
    print(f"  - LLM Model: {config['llm_model']}")
    print(f"  - Vision 청킹 활성화: {config['enable_vision_chunking']}")
    print(f"  - Vision 모드: {config['vision_mode']}")

    # 테스트 파일 선택
    test_file = Path("data/test_pptx/complex_03_data_analysis_report.pptx")

    if not test_file.exists():
        print(f"\n❌ 테스트 파일을 찾을 수 없습니다: {test_file}")
        return

    print(f"\n테스트 파일: {test_file}")
    print(f"파일 크기: {test_file.stat().st_size / 1024:.2f} KB")

    # 엔진 초기화
    engine = PPTXChunkingEngine(config)

    # Vision 청킹 실행
    print("\n" + "-" * 80)
    print("Vision 청킹 시작...")
    print("-" * 80)

    start_time = time.time()

    try:
        chunks = engine.process_pptx_document(
            pptx_path=str(test_file),
            enable_vision=config['enable_vision_chunking'],
            llm_api_type=config['llm_api_type'],
            llm_base_url=config.get('llm_base_url', ''),
            llm_model=config['llm_model'],
            llm_api_key=config.get('llm_api_key', '')
        )

        elapsed_time = time.time() - start_time

        print("\n" + "=" * 80)
        print("[OK] Vision 청킹 완료!")
        print("=" * 80)

        print(f"\n[처리 결과]")
        print(f"  - 총 청크 수: {len(chunks)}")
        print(f"  - 처리 시간: {elapsed_time:.2f}초")
        print(f"  - 평균 속도: {elapsed_time / len(chunks):.2f}초/청크")

        # 비용 추정 (GPT-4o-mini: $0.150/1M input tokens)
        # 간소화된 프롬프트: ~103 tokens, 응답: ~200 tokens (추정)
        estimated_input_tokens = len(chunks) * 103
        estimated_output_tokens = len(chunks) * 200
        estimated_cost = (estimated_input_tokens / 1_000_000 * 0.150 +
                         estimated_output_tokens / 1_000_000 * 0.600)

        print(f"\n[예상 비용]")
        print(f"  - 입력 토큰: ~{estimated_input_tokens:,} tokens")
        print(f"  - 출력 토큰: ~{estimated_output_tokens:,} tokens")
        print(f"  - 예상 비용: ~${estimated_cost:.4f}")

        # 추출된 내용 샘플 출력
        print("\n" + "-" * 80)
        print("[추출된 내용 샘플 (처음 3개 청크)]")
        print("-" * 80)

        for i, chunk in enumerate(chunks[:3]):
            print(f"\n[청크 {i+1}]")
            print(f"슬라이드 번호: {chunk.metadata.slide_number}")
            if hasattr(chunk.metadata, 'slide_title') and chunk.metadata.slide_title:
                print(f"제목: {chunk.metadata.slide_title}")
            print(f"청크 타입: {chunk.chunk_type}")
            print(f"\n내용 (처음 500자):")
            print(chunk.content[:500] if hasattr(chunk, 'content') else chunk.text[:500] if hasattr(chunk, 'text') else str(chunk)[:500])
            print("...")

            # Vision 분석이 포함되어 있는지 확인
            chunk_text = chunk.content if hasattr(chunk, 'content') else chunk.text if hasattr(chunk, 'text') else str(chunk)
            if "[Vision Analysis]" in chunk_text or "[Vision analysis]" in chunk_text.lower():
                print("\n[OK] Vision 분석 포함됨")
            else:
                print("\n[WARN] Vision 분석 미포함 (텍스트만)")

        # 통계
        vision_chunks = sum(1 for c in chunks if "[Vision" in (c.content if hasattr(c, 'content') else c.text if hasattr(c, 'text') else str(c)) or "주제:" in (c.content if hasattr(c, 'content') else c.text if hasattr(c, 'text') else str(c)))
        print(f"\n[Vision 분석 통계]")
        print(f"  - Vision 분석 포함 청크: {vision_chunks}/{len(chunks)}")
        print(f"  - Vision 분석 비율: {vision_chunks/len(chunks)*100:.1f}%")

        # 상세 분석 (선택적)
        print("\n" + "-" * 80)
        print("상세 분석을 보시겠습니까? (y/n): ", end="")
        user_input = input().strip().lower()

        if user_input == 'y':
            print("\n모든 청크 내용:")
            for i, chunk in enumerate(chunks):
                print(f"\n{'=' * 80}")
                print(f"청크 {i+1}/{len(chunks)}")
                print(f"{'=' * 80}")
                print(f"슬라이드: {chunk.metadata.slide_number}")
                if hasattr(chunk.metadata, 'slide_title'):
                    print(f"제목: {chunk.metadata.slide_title}")
                print(f"타입: {chunk.chunk_type}")
                print(f"가중치: {chunk.metadata.chunk_type_weight}")
                chunk_text = chunk.content if hasattr(chunk, 'content') else chunk.text if hasattr(chunk, 'text') else str(chunk)
                print(f"\n내용:\n{chunk_text}")

        print("\n" + "=" * 80)
        print("테스트 완료!")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERROR] 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    test_vision_chunking()
