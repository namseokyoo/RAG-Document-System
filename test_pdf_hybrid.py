"""
Phase 3 PDF Hybrid 모드 테스트

Smart Vision Decision 검증:
- 텍스트 전용 페이지 → Vision 스킵
- 표/차트/이미지 페이지 → Vision 사용
- 비용 절감 70% 목표
"""
import os
from pathlib import Path


def test_pdf_hybrid():
    """PDF Hybrid 모드 테스트"""

    print("=" * 80)
    print("Phase 3: PDF Hybrid 모드 테스트")
    print("=" * 80)
    print()

    # 테스트 PDF 파일
    test_file = Path("data/test_pdf/sample.pdf")

    if not test_file.exists():
        print(f"[ERROR] 테스트 파일 없음: {test_file}")
        print()
        print("테스트 PDF 파일을 준비하세요:")
        print(f"  1. {test_file.parent} 폴더 생성")
        print(f"  2. 테스트용 PDF 파일을 'sample.pdf'로 저장")
        print(f"     (권장: 표/차트 포함 + 텍스트 전용 페이지 혼합)")
        print()
        return

    # 환경 설정
    from utils.pdf_chunking_engine import PDFChunkingEngine
    from config import ConfigManager

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    llm_api_type = config.get("llm_api_type", "openai")
    llm_model = config.get("llm_model", "gpt-4o-mini")
    llm_api_key = config.get("llm_api_key", os.getenv("OPENAI_API_KEY"))

    print(f"설정:")
    print(f"  API 타입: {llm_api_type}")
    print(f"  모델: {llm_model}")
    print(f"  Vision 활성화: True (강제)")
    print(f"  Hybrid 모드: True (Phase 3)")
    print(f"  PDF DPI: {config.get('pdf_dpi', 150)}")
    print(f"  Vision Detail: {config.get('pdf_vision_detail', 'high')}")
    print()

    print(f"테스트 파일: {test_file.name}")
    print()

    # Hybrid 청킹 실행
    print("Hybrid 청킹 시작...")
    print("-" * 80)

    engine = PDFChunkingEngine(config)

    try:
        chunks = engine.process_pdf_document(
            pdf_path=str(test_file.absolute()),
            enable_vision=True,  # Vision 활성화
            enable_hybrid=True,  # Hybrid 모드 활성화
            llm_api_type=llm_api_type,
            llm_model=llm_model,
            llm_api_key=llm_api_key
        )

        if not chunks:
            print("[ERROR] 청킹 실패 - 청크 0개")
            return

        print()
        print(f"청킹 완료: {len(chunks)}개 청크 생성")
        print()

        # 청크 분석
        print("청크 분석:")
        print("-" * 80)

        vision_chunks = [c for c in chunks if c.chunk_type == "pdf_page_vision_hybrid"]
        text_chunks = [c for c in chunks if c.chunk_type == "pdf_page_text"]

        print(f"Vision 청크: {len(vision_chunks)}개")
        print(f"텍스트 청크: {len(text_chunks)}개")
        print()

        # 샘플 청크 출력
        if vision_chunks:
            print("Vision 청크 예시 (첫 번째):")
            chunk = vision_chunks[0]
            print(f"  페이지: {chunk.metadata.page_number}")
            print(f"  타입: {chunk.chunk_type}")
            print(f"  내용 (앞 300자):")
            print(f"  {chunk.content[:300]}...")
            print()

        if text_chunks:
            print("텍스트 청크 예시 (첫 번째):")
            chunk = text_chunks[0]
            print(f"  페이지: {chunk.metadata.page_number}")
            print(f"  타입: {chunk.chunk_type}")
            print(f"  내용 (앞 300자):")
            print(f"  {chunk.content[:300]}...")
            print()

        # 통계
        print("=" * 80)
        print("테스트 결과 요약")
        print("=" * 80)
        print(f"총 청크 수: {len(chunks)}")
        print(f"Vision 청크: {len(vision_chunks)}개 ({len(vision_chunks)/len(chunks)*100:.1f}%)")
        print(f"텍스트 청크: {len(text_chunks)}개 ({len(text_chunks)/len(chunks)*100:.1f}%)")
        print()

        # 비용 절감 계산
        if len(chunks) > 0:
            cost_reduction = (len(text_chunks) / len(chunks)) * 100
            print(f"비용 절감: ~{cost_reduction:.1f}% (목표: 70%)")
            print()

            # 성공 기준
            if cost_reduction >= 70:
                print("[SUCCESS] Phase 3 목표 달성 (비용 절감 70%+)")
            elif len(vision_chunks) > 0:
                print("[PARTIAL] Hybrid 모드 작동 (비용 절감 70% 미달, 문서 특성에 따라 다를 수 있음)")
            else:
                print("[INFO] 테스트 문서는 텍스트 전용 페이지만 포함")

        print("=" * 80)

    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        test_pdf_hybrid()
    except Exception as e:
        print(f"[ERROR] 테스트 실행 실패: {e}")
        import traceback
        traceback.print_exc()
