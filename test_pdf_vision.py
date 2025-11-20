"""
Phase 2: PDF Vision 테스트

PDF 파일을 Vision API로 분석하는 기능 테스트
"""
import os
from pathlib import Path


def test_pdf_vision():
    """PDF Vision 청킹 테스트"""

    print("=" * 80)
    print("Phase 2: PDF Vision 테스트")
    print("=" * 80)
    print()

    # 테스트 PDF 파일 경로
    test_pdf_dir = Path("data/test_pdf")
    test_pdf_dir.mkdir(parents=True, exist_ok=True)

    test_file = test_pdf_dir / "sample.pdf"

    if not test_file.exists():
        print(f"[INFO] 테스트 PDF 파일 없음: {test_file}")
        print()
        print("테스트 PDF 파일을 준비하세요:")
        print(f"  1. {test_pdf_dir} 폴더에 'sample.pdf' 파일 복사")
        print(f"  2. 권장: 표, 차트, 이미지가 포함된 3-5페이지 PDF")
        print()
        return

    # 환경 설정
    from utils.pdf_chunking_engine import PDFChunkingEngine
    from config import ConfigManager

    config_mgr = ConfigManager()
    config = config_mgr.get_all()

    # Vision 활성화
    llm_api_type = config.get("llm_api_type", "openai")
    llm_model = config.get("llm_model", "gpt-4o-mini")
    llm_api_key = config.get("llm_api_key", os.getenv("OPENAI_API_KEY"))

    print(f"설정:")
    print(f"  API 타입: {llm_api_type}")
    print(f"  모델: {llm_model}")
    print(f"  Vision 활성화: True (강제)")
    print(f"  PDF DPI: {config.get('pdf_dpi', 150)}")
    print(f"  Vision Detail: {config.get('pdf_vision_detail', 'high')}")
    print()

    # PDF 파일 정보
    print(f"테스트 파일: {test_file.name}")
    print(f"파일 크기: {test_file.stat().st_size / 1024:.1f} KB")
    print()

    # PDF 청킹 엔진 초기화
    print("PDFChunkingEngine 초기화...")
    engine = PDFChunkingEngine(config)

    # Vision 청킹 실행
    print()
    print("Vision 청킹 시작...")
    print("-" * 80)

    try:
        chunks = engine.process_pdf_document(
            pdf_path=str(test_file.absolute()),
            enable_vision=True,  # Vision 강제 활성화
            llm_api_type=llm_api_type,
            llm_base_url=config.get('llm_base_url', ''),
            llm_model=llm_model,
            llm_api_key=llm_api_key
        )

        print()
        print("-" * 80)
        print(f"청킹 완료: {len(chunks)}개 청크 생성")
        print()

        if not chunks:
            print("[WARNING] 청크가 생성되지 않았습니다.")
            return

        # 결과 분석
        print("청크 분석:")
        print("-" * 80)

        for i, chunk in enumerate(chunks[:3], 1):  # 최대 3개만 출력
            print(f"\n청크 {i}:")
            print(f"  타입: {chunk.chunk_type}")
            print(f"  페이지: {chunk.metadata.page_number}")
            print(f"  내용 (앞 300자):")
            print(f"  {chunk.content[:300]}...")
            print()

        # 통계
        print()
        print("=" * 80)
        print("테스트 결과 요약")
        print("=" * 80)
        print(f"총 청크 수: {len(chunks)}")

        page_numbers = set(chunk.metadata.page_number for chunk in chunks)
        print(f"처리된 페이지: {sorted(page_numbers)}")
        print(f"페이지 수: {len(page_numbers)}")

        vision_chunks = [c for c in chunks if "vision" in c.chunk_type.lower()]
        print(f"Vision 청크: {len(vision_chunks)}개 ({len(vision_chunks)/len(chunks)*100:.1f}%)")

        print()
        if len(chunks) > 0 and len(vision_chunks) > 0:
            print("[SUCCESS] Phase 2 PDF Vision 테스트 통과")
        else:
            print("[WARNING] Vision 청크가 생성되지 않았습니다")

        print("=" * 80)

    except ImportError as e:
        print()
        print("[ERROR] 필수 라이브러리 누락:")
        print(f"  {e}")
        print()
        print("해결 방법:")
        print("  1. pip install pdf2image pypdf")
        print("  2. Poppler 설치 (POPPLER_INSTALL_GUIDE.md 참조)")
        print()

    except RuntimeError as e:
        print()
        print("[ERROR] PDF 처리 실패:")
        print(f"  {e}")
        print()
        if "poppler" in str(e).lower():
            print("Poppler 설치 가이드: POPPLER_INSTALL_GUIDE.md")
        print()

    except Exception as e:
        print()
        print(f"[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        print()


if __name__ == "__main__":
    test_pdf_vision()
