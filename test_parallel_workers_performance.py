"""
병렬 처리 성능 테스트
max_parallel_workers를 1과 3으로 설정하여 같은 파일 임베딩 시간 비교
"""
import sys
import os
import time
import json
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from utils.pdf_chunking_engine import PDFChunkingEngine
from utils.document_processor import DocumentProcessor


def update_config_max_parallel_workers(value: int) -> None:
    """config.json의 max_parallel_workers 값을 업데이트"""
    config_path = Path("config.json")
    if not config_path.exists():
        print(f"[ERROR] config.json 파일을 찾을 수 없습니다: {config_path}")
        return
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        config['max_parallel_workers'] = value
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"[CONFIG] max_parallel_workers를 {value}로 설정했습니다.")
    except Exception as e:
        print(f"[ERROR] config.json 업데이트 실패: {e}")
        raise


def test_pdf_processing(pdf_path: str, max_workers: int) -> dict:
    """PDF 처리 시간 측정"""
    print(f"\n{'='*80}")
    print(f"테스트: max_parallel_workers = {max_workers}")
    print(f"{'='*80}")
    
    # config 업데이트
    update_config_max_parallel_workers(max_workers)
    
    # ConfigManager 재로드
    config_manager = ConfigManager()
    config = config_manager.get_all()
    
    # PDF 엔진 초기화
    pdf_engine = PDFChunkingEngine(config)
    
    # LLM 설정
    llm_api_type = config.get("llm_api_type", "openai")
    llm_base_url = config.get("llm_base_url", "")
    llm_model = config.get("llm_model", "gpt-4o-mini")
    llm_api_key = config.get("llm_api_key", "")
    
    # PDF 파일 확인
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"[ERROR] PDF 파일을 찾을 수 없습니다: {pdf_path}")
        return None
    
    print(f"[INFO] 테스트 파일: {pdf_file.name}")
    print(f"[INFO] 파일 크기: {pdf_file.stat().st_size / 1024 / 1024:.2f} MB")
    
    # 시간 측정 시작
    start_time = time.perf_counter()
    
    try:
        # PDF 처리
        print(f"[INFO] PDF 처리 시작...")
        chunks = pdf_engine.process_pdf_document(
            pdf_path=str(pdf_file.absolute()),
            llm_api_type=llm_api_type,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_api_key=llm_api_key
        )
        
        # 시간 측정 종료
        elapsed_time = time.perf_counter() - start_time
        
        # 결과 수집
        result = {
            'max_workers': max_workers,
            'file_name': pdf_file.name,
            'file_size_mb': pdf_file.stat().st_size / 1024 / 1024,
            'elapsed_time': elapsed_time,
            'num_chunks': len(chunks) if chunks else 0,
            'success': chunks is not None and len(chunks) > 0
        }
        
        # 통계 출력
        print(f"\n[결과]")
        print(f"  - 처리 시간: {elapsed_time:.2f}초")
        print(f"  - 생성된 청크: {len(chunks) if chunks else 0}개")
        print(f"  - 성공 여부: {'✅ 성공' if result['success'] else '❌ 실패'}")
        
        return result
        
    except Exception as e:
        elapsed_time = time.perf_counter() - start_time
        print(f"[ERROR] PDF 처리 실패: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'max_workers': max_workers,
            'file_name': pdf_file.name,
            'file_size_mb': pdf_file.stat().st_size / 1024 / 1024,
            'elapsed_time': elapsed_time,
            'num_chunks': 0,
            'success': False,
            'error': str(e)
        }


def main():
    """메인 테스트 함수"""
    print("="*80)
    print("병렬 처리 성능 테스트")
    print("="*80)
    print("\n이 테스트는 max_parallel_workers를 1과 3으로 설정하여")
    print("같은 PDF 파일의 임베딩 시간을 비교합니다.\n")
    
    # 테스트할 PDF 파일 경로 입력
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if not Path(pdf_path).exists():
            print(f"[ERROR] 지정한 파일을 찾을 수 없습니다: {pdf_path}")
            return
    else:
        # 현재 디렉토리 및 하위 디렉토리에서 PDF 파일 찾기
        print("[INFO] PDF 파일 검색 중...")
        pdf_files = list(Path(".").rglob("*.pdf"))
        
        if not pdf_files:
            print("[ERROR] 테스트할 PDF 파일을 찾을 수 없습니다.")
            print("사용법: python test_parallel_workers_performance.py <PDF파일경로>")
            return
        
        # 가장 최근에 수정된 PDF 파일 선택
        pdf_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        pdf_path = str(pdf_files[0])
        print(f"[INFO] 자동 선택된 파일: {pdf_path}")
    
    print(f"[INFO] 테스트 파일: {pdf_path}\n")
    
    # 원본 config 백업
    config_path = Path("config.json")
    original_config = None
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            original_config = json.load(f)
        original_max_workers = original_config.get('max_parallel_workers', 3)
    else:
        original_max_workers = 3
    
    results = []
    
    try:
        # 테스트 1: max_parallel_workers = 1
        result1 = test_pdf_processing(pdf_path, max_workers=1)
        if result1:
            results.append(result1)
        
        # 잠시 대기 (API rate limit 고려)
        print("\n[INFO] 다음 테스트 전 5초 대기 중...")
        time.sleep(5)
        
        # 테스트 2: max_parallel_workers = 3
        result2 = test_pdf_processing(pdf_path, max_workers=3)
        if result2:
            results.append(result2)
        
        # 결과 비교
        print(f"\n{'='*80}")
        print("성능 비교 결과")
        print(f"{'='*80}\n")
        
        if len(results) == 2:
            r1, r2 = results[0], results[1]
            
            print(f"파일: {r1['file_name']}")
            print(f"파일 크기: {r1['file_size_mb']:.2f} MB\n")
            
            print(f"max_parallel_workers = 1:")
            print(f"  - 처리 시간: {r1['elapsed_time']:.2f}초")
            print(f"  - 생성된 청크: {r1['num_chunks']}개")
            print(f"  - 성공 여부: {'✅' if r1['success'] else '❌'}\n")
            
            print(f"max_parallel_workers = 3:")
            print(f"  - 처리 시간: {r2['elapsed_time']:.2f}초")
            print(f"  - 생성된 청크: {r2['num_chunks']}개")
            print(f"  - 성공 여부: {'✅' if r2['success'] else '❌'}\n")
            
            if r1['success'] and r2['success']:
                time_diff = r1['elapsed_time'] - r2['elapsed_time']
                speedup = r1['elapsed_time'] / r2['elapsed_time'] if r2['elapsed_time'] > 0 else 0
                improvement = (time_diff / r1['elapsed_time'] * 100) if r1['elapsed_time'] > 0 else 0
                
                print(f"성능 개선:")
                print(f"  - 시간 절감: {time_diff:.2f}초 ({improvement:.1f}% 개선)")
                print(f"  - 속도 향상: {speedup:.2f}배")
                
                if speedup > 1:
                    print(f"\n✅ 병렬 처리로 {speedup:.2f}배 빠른 성능을 달성했습니다!")
                elif speedup < 1:
                    print(f"\n⚠️  병렬 처리가 오히려 느렸습니다. (네트워크/API 제한 가능성)")
                else:
                    print(f"\nℹ️  성능 차이가 없습니다.")
            else:
                print("⚠️  테스트 중 일부 실패가 발생했습니다.")
        else:
            print("⚠️  테스트 결과가 부족합니다.")
            for r in results:
                print(f"  - max_workers={r['max_workers']}: {r.get('error', '성공')}")
    
    finally:
        # 원본 config 복원
        if original_config:
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(original_config, f, indent=2, ensure_ascii=False)
                print(f"\n[CONFIG] max_parallel_workers를 원래 값({original_max_workers})으로 복원했습니다.")
            except Exception as e:
                print(f"[WARN] config.json 복원 실패: {e}")
    
    print(f"\n{'='*80}")
    print("테스트 완료")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

