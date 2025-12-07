"""
비전 프롬프트 최적화 테스트
Phase 1: 프롬프트 간소화 (75라인 → 25라인) 효과 측정
"""
import sys
import os
import time
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(__file__))

from utils.pptx_chunking_engine import PPTXChunkingEngine


class VisionPromptTester:
    """비전 프롬프트 최적화 테스트 클래스"""

    def __init__(self, test_pptx_dir: str = "data/test_pptx"):
        self.test_pptx_dir = Path(test_pptx_dir)
        self.results = []

    def select_test_files(self, count: int = 3) -> List[Path]:
        """테스트용 PPT 파일 선택"""
        # 표/그래프가 있는 복잡한 PPT 우선 선택
        priority_files = [
            "complex_03_data_analysis_report.pptx",
            "advanced_01_financial_report.pptx",
            "complex_04_project_plan.pptx",
        ]

        selected = []
        for filename in priority_files[:count]:
            filepath = self.test_pptx_dir / filename
            if filepath.exists():
                selected.append(filepath)

        return selected

    def test_single_pptx(self, pptx_path: Path, test_name: str) -> Dict[str, Any]:
        """단일 PPT 파일 테스트"""
        print(f"\n{'='*80}")
        print(f"[{test_name}] 테스트 중: {pptx_path.name}")
        print(f"{'='*80}")

        # 청킹 엔진 초기화 (config 전달)
        config = {
            "max_size": 300,
            "overlap_size": 50,
            "enable_small_to_large": True
        }
        chunker = PPTXChunkingEngine(config)

        # 시작 시간 측정
        start_time = time.time()

        try:
            # PPT 처리 (비전 청킹 활성화)
            chunks = chunker.process_pptx_document(
                pptx_path=str(pptx_path),
                enable_vision=True,
                llm_api_type="ollama",
                llm_base_url="http://localhost:11434",
                llm_model="gemma3",  # 현재 사용 가능한 모델
                llm_api_key=""
            )

            # 종료 시간 측정
            elapsed_time = time.time() - start_time

            # 슬라이드 수 계산
            from pptx import Presentation
            prs = Presentation(str(pptx_path))
            slide_count = len(prs.slides)

            # Vision 청크 수 계산 (메타데이터에 vision_analysis가 있는 청크)
            vision_chunk_count = sum(
                1 for chunk in chunks
                if hasattr(chunk.metadata, 'vision_analysis') and chunk.metadata.vision_analysis
            )

            # 결과 저장
            result = {
                "test_name": test_name,
                "file_name": pptx_path.name,
                "slide_count": slide_count,
                "chunk_count": len(chunks),
                "vision_chunk_count": vision_chunk_count,
                "total_time": elapsed_time,
                "time_per_slide": elapsed_time / slide_count if slide_count > 0 else 0,
                "success": True,
                "error": None
            }

            # 샘플 청크 내용 (첫 번째 Vision 청크)
            for chunk in chunks:
                if hasattr(chunk.metadata, 'vision_analysis') and chunk.metadata.vision_analysis:
                    result["sample_vision_content"] = chunk.page_content[:200]
                    break

            print(f"\n[OK] 처리 완료:")
            print(f"  - 슬라이드 수: {slide_count}개")
            print(f"  - 청크 수: {len(chunks)}개")
            print(f"  - Vision 청크: {vision_chunk_count}개")
            print(f"  - 총 소요 시간: {elapsed_time:.2f}초")
            print(f"  - 슬라이드당 시간: {result['time_per_slide']:.2f}초")

            return result

        except Exception as e:
            elapsed_time = time.time() - start_time

            result = {
                "test_name": test_name,
                "file_name": pptx_path.name,
                "slide_count": 0,
                "chunk_count": 0,
                "vision_chunk_count": 0,
                "total_time": elapsed_time,
                "time_per_slide": 0,
                "success": False,
                "error": str(e)
            }

            print(f"\n[NG] 처리 실패: {e}")
            import traceback
            traceback.print_exc()

            return result

    def run_test_suite(self, test_name: str = "현재 프롬프트") -> List[Dict[str, Any]]:
        """테스트 스위트 실행"""
        print(f"\n{'='*80}")
        print(f"비전 프롬프트 테스트 시작: {test_name}")
        print(f"{'='*80}")

        # 테스트 파일 선택
        test_files = self.select_test_files(count=3)

        if not test_files:
            print("[NG] 테스트 파일을 찾을 수 없습니다.")
            return []

        print(f"\n테스트 파일 {len(test_files)}개:")
        for f in test_files:
            print(f"  - {f.name}")

        # 각 파일 테스트
        results = []
        for pptx_path in test_files:
            result = self.test_single_pptx(pptx_path, test_name)
            results.append(result)

        return results

    def print_summary(self, results: List[Dict[str, Any]], test_name: str):
        """테스트 결과 요약"""
        print(f"\n{'='*80}")
        print(f"테스트 결과 요약: {test_name}")
        print(f"{'='*80}")

        if not results:
            print("테스트 결과가 없습니다.")
            return

        # 성공/실패 개수
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)

        print(f"\n전체: {total_count}개 파일")
        print(f"성공: {success_count}개")
        print(f"실패: {total_count - success_count}개")

        # 성공한 테스트만 집계
        success_results = [r for r in results if r['success']]

        if not success_results:
            print("\n성공한 테스트가 없습니다.")
            return

        # 평균 계산
        total_slides = sum(r['slide_count'] for r in success_results)
        total_chunks = sum(r['chunk_count'] for r in success_results)
        total_vision = sum(r['vision_chunk_count'] for r in success_results)
        total_time = sum(r['total_time'] for r in success_results)
        avg_time_per_slide = total_time / total_slides if total_slides > 0 else 0

        print(f"\n[STAT] 집계:")
        print(f"  - 총 슬라이드: {total_slides}개")
        print(f"  - 총 청크: {total_chunks}개")
        print(f"  - Vision 청크: {total_vision}개")
        print(f"  - 총 소요 시간: {total_time:.2f}초")
        print(f"  - 평균 슬라이드당 시간: {avg_time_per_slide:.2f}초")

        # 개별 결과
        print(f"\n[FILE] 개별 결과:")
        for r in success_results:
            print(f"\n  [{r['file_name']}]")
            print(f"    - 슬라이드: {r['slide_count']}개")
            print(f"    - Vision 청크: {r['vision_chunk_count']}개")
            print(f"    - 시간: {r['total_time']:.2f}초 ({r['time_per_slide']:.2f}초/슬라이드)")

            # 샘플 컨텐츠
            if 'sample_vision_content' in r:
                print(f"    - 샘플 내용: {r['sample_vision_content'][:100]}...")

        return {
            "total_slides": total_slides,
            "total_chunks": total_chunks,
            "total_vision": total_vision,
            "total_time": total_time,
            "avg_time_per_slide": avg_time_per_slide,
            "success_rate": success_count / total_count if total_count > 0 else 0
        }


def run_baseline_test():
    """사전 테스트 (현재 프롬프트)"""
    print("\n" + "="*80)
    print("Phase 1 사전 테스트: 현재 프롬프트 (75라인)")
    print("="*80)

    tester = VisionPromptTester()

    # 테스트 실행
    results = tester.run_test_suite(test_name="현재 프롬프트 (75라인)")

    # 결과 요약
    summary = tester.print_summary(results, "현재 프롬프트 (75라인)")

    # 결과 저장 (JSON)
    import json
    output_file = "test_results/vision_prompt_baseline.json"
    os.makedirs("test_results", exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_name": "현재 프롬프트 (75라인)",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
            "summary": summary
        }, f, indent=2, ensure_ascii=False)

    print(f"\n결과 저장: {output_file}")

    return results, summary


def run_optimized_test():
    """사후 테스트 (간소화된 프롬프트)"""
    print("\n" + "="*80)
    print("Phase 1 사후 테스트: 간소화된 프롬프트 (25라인)")
    print("="*80)

    # 프롬프트 간소화 적용 필요 (pptx_chunking_engine.py 수정 후 실행)
    print("\n[WARN] 주의: pptx_chunking_engine.py의 프롬프트를 간소화한 후 실행하세요.")
    print("현재는 사전 테스트만 실행합니다.\n")

    tester = VisionPromptTester()

    # 테스트 실행
    results = tester.run_test_suite(test_name="간소화된 프롬프트 (25라인)")

    # 결과 요약
    summary = tester.print_summary(results, "간소화된 프롬프트 (25라인)")

    # 결과 저장 (JSON)
    import json
    output_file = "test_results/vision_prompt_optimized.json"
    os.makedirs("test_results", exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_name": "간소화된 프롬프트 (25라인)",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
            "summary": summary
        }, f, indent=2, ensure_ascii=False)

    print(f"\n결과 저장: {output_file}")

    return results, summary


def compare_results():
    """사전/사후 테스트 결과 비교"""
    import json

    print("\n" + "="*80)
    print("Phase 1 결과 비교: 사전 vs 사후")
    print("="*80)

    # 결과 로드
    try:
        with open("test_results/vision_prompt_baseline.json", 'r', encoding='utf-8') as f:
            baseline = json.load(f)

        with open("test_results/vision_prompt_optimized.json", 'r', encoding='utf-8') as f:
            optimized = json.load(f)
    except FileNotFoundError as e:
        print(f"[NG] 결과 파일을 찾을 수 없습니다: {e}")
        print("먼저 사전/사후 테스트를 모두 실행하세요.")
        return

    # 비교 리포트 생성
    baseline_summary = baseline.get('summary', {})
    optimized_summary = optimized.get('summary', {})

    print("\n[STAT] 성능 비교:")
    print(f"\n1. 처리 속도:")

    baseline_time = baseline_summary.get('avg_time_per_slide', 0)
    optimized_time = optimized_summary.get('avg_time_per_slide', 0)
    time_improvement = (baseline_time - optimized_time) / baseline_time * 100 if baseline_time > 0 else 0

    print(f"  - 사전 (현재 프롬프트): {baseline_time:.2f}초/슬라이드")
    print(f"  - 사후 (간소화 프롬프트): {optimized_time:.2f}초/슬라이드")
    print(f"  - 개선율: {time_improvement:+.1f}% {'[OK]' if time_improvement > 0 else '[NG]'}")

    print(f"\n2. 청크 생성:")
    baseline_chunks = baseline_summary.get('total_chunks', 0)
    optimized_chunks = optimized_summary.get('total_chunks', 0)
    chunk_diff = optimized_chunks - baseline_chunks

    print(f"  - 사전: {baseline_chunks}개")
    print(f"  - 사후: {optimized_chunks}개")
    print(f"  - 차이: {chunk_diff:+d}개")

    print(f"\n3. Vision 청크:")
    baseline_vision = baseline_summary.get('total_vision', 0)
    optimized_vision = optimized_summary.get('total_vision', 0)
    vision_diff = optimized_vision - baseline_vision

    print(f"  - 사전: {baseline_vision}개")
    print(f"  - 사후: {optimized_vision}개")
    print(f"  - 차이: {vision_diff:+d}개")

    print(f"\n4. 성공률:")
    baseline_success = baseline_summary.get('success_rate', 0) * 100
    optimized_success = optimized_summary.get('success_rate', 0) * 100

    print(f"  - 사전: {baseline_success:.1f}%")
    print(f"  - 사후: {optimized_success:.1f}%")

    # 비교 리포트 저장
    comparison = {
        "baseline": baseline_summary,
        "optimized": optimized_summary,
        "improvements": {
            "time_improvement_pct": time_improvement,
            "chunk_diff": chunk_diff,
            "vision_diff": vision_diff
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    output_file = "test_results/vision_prompt_comparison.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)

    print(f"\n비교 결과 저장: {output_file}")

    return comparison


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="비전 프롬프트 최적화 테스트")
    parser.add_argument("--mode", choices=["baseline", "optimized", "compare"],
                       default="baseline",
                       help="테스트 모드 (baseline: 사전, optimized: 사후, compare: 비교)")

    args = parser.parse_args()

    if args.mode == "baseline":
        run_baseline_test()
    elif args.mode == "optimized":
        run_optimized_test()
    elif args.mode == "compare":
        compare_results()

    sys.exit(0)
