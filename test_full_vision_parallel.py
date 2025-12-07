"""
Full Vision 모드 병렬 처리 테스트
max_parallel_workers=3일 때 병렬 처리가 작동하는지 확인
"""
import sys
import os
import time
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.pdf_chunking_engine import PDFChunkingEngine


def main():
    """Full Vision 모드 병렬 처리 테스트"""
    print("="*80)
    print("Full Vision 모드 병렬 처리 테스트")
    print("="*80)
    print("\nmax_parallel_workers=3으로 설정하여 Full Vision 모드에서")
    print("병렬 처리가 작동하는지 확인합니다.\n")
    
    # 테스트 파일 경로
    test_file = "dist/RAG_System_v0.5.4/data/embedded_documents/OLED 강의 자료.pdf"
    if not Path(test_file).exists():
        print(f"[ERROR] 테스트 파일을 찾을 수 없습니다: {test_file}")
        return
    
    print(f"[INFO] 테스트 파일: {test_file}")
    print(f"[INFO] 파일 크기: {Path(test_file).stat().st_size / 1024 / 1024:.2f} MB\n")
    
    # Config 로드
    config_manager = ConfigManager()
    config = config_manager.get_all()
    
    # max_parallel_workers를 3으로 설정
    config['max_parallel_workers'] = 3
    print(f"[CONFIG] max_parallel_workers = 3 설정\n")
    
    # PDF 엔진 초기화
    pdf_engine = PDFChunkingEngine(config)
    
    # LLM 설정
    llm_api_type = config.get("llm_api_type", "openai")
    llm_base_url = config.get("llm_base_url", "")
    llm_model = config.get("llm_model", "gpt-4o-mini")
    llm_api_key = config.get("llm_api_key", "")
    
    # 시간 측정 시작
    start_time = time.perf_counter()
    
    print("[INFO] PDF 처리 시작 (Full Vision 모드, 병렬 처리)...\n")
    
    try:
        # PDF 처리 (Full Vision 모드 - PPTX 변환 PDF로 감지되어 Full Vision 사용)
        chunks = pdf_engine.process_pdf_document(
            pdf_path=test_file,
            llm_api_type=llm_api_type,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_api_key=llm_api_key
        )
        
        # 시간 측정 종료
        elapsed_time = time.perf_counter() - start_time
        
        # 결과 출력
        print(f"\n{'='*80}")
        print("테스트 결과")
        print(f"{'='*80}\n")
        print(f"처리 시간: {elapsed_time:.2f}초")
        print(f"생성된 청크: {len(chunks) if chunks else 0}개")
        print(f"성공 여부: {'✅ 성공' if chunks and len(chunks) > 0 else '❌ 실패'}")
        
        # 병렬 처리 확인
        print(f"\n[병렬 처리 확인]")
        print(f"로그에서 여러 페이지가 동시에 처리되는 것을 확인하세요.")
        print(f"예: '페이지 1/21 처리 중...', '페이지 2/21 처리 중...', '페이지 3/21 처리 중...'")
        print(f"이런 메시지가 동시에 나타나면 병렬 처리가 작동하는 것입니다.")
        
    except Exception as e:
        elapsed_time = time.perf_counter() - start_time
        print(f"\n[ERROR] PDF 처리 실패: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*80}")
    print("테스트 완료")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()





