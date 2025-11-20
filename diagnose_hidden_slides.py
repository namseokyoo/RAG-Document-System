"""
숨겨진 슬라이드 진단 스크립트
PPT 파일에서 숨겨진 슬라이드가 있는지 확인
"""

import sys
import os
from pathlib import Path

def diagnose_hidden_slides():
    """숨겨진 슬라이드 확인"""

    test_file = Path("data/test_pptx/advanced_01_financial_report.pptx")
    abs_path = str(test_file.absolute())

    print("=" * 80)
    print(f"숨겨진 슬라이드 진단: {test_file.name}")
    print("=" * 80)
    print()

    # COM으로 숨김 상태 확인
    try:
        import win32com.client

        print("[COM 분석]")
        print("-" * 80)

        powerpoint = win32com.client.Dispatch("PowerPoint.Application")

        try:
            presentation = powerpoint.Presentations.Open(abs_path)

            print(f"총 슬라이드 수: {presentation.Slides.Count}")
            print()

            hidden_count = 0
            for i in range(1, presentation.Slides.Count + 1):
                slide = presentation.Slides[i]

                # 제목 추출
                title = ""
                try:
                    if slide.Shapes.HasTitle:
                        title = slide.Shapes.Title.TextFrame.TextRange.Text
                except:
                    pass

                # 숨김 여부 확인
                try:
                    is_hidden = slide.SlideShowTransition.Hidden
                    hidden_status = "[HIDDEN]" if is_hidden else "[VISIBLE]"
                    if is_hidden:
                        hidden_count += 1
                except Exception as e:
                    is_hidden = None
                    hidden_status = "[ERROR]"

                print(f"COM Slide {i}:")
                print(f"  SlideID: {slide.SlideID}")
                print(f"  SlideIndex: {slide.SlideIndex}")
                print(f"  제목: {title if title else '(제목 없음)'}")
                print(f"  숨김 상태: {hidden_status}")
                print()

            presentation.Close()

            print("=" * 80)
            print(f"요약: 총 {presentation.Slides.Count}개 슬라이드 중 {hidden_count}개 숨김")
            print("=" * 80)

        finally:
            powerpoint.Quit()

    except Exception as e:
        print(f"[ERROR] COM 분석 실패: {e}")
        return

    print()
    print("=" * 80)
    print("진단 결과")
    print("=" * 80)
    print()

    if hidden_count > 0:
        print(f"[발견] 숨겨진 슬라이드 {hidden_count}개 발견!")
        print()
        print("이것이 순서 불일치의 원인일 수 있습니다.")
        print()
        print("해결 방법:")
        print("1. PowerPoint에서 파일 열기")
        print("2. 보기 > 슬라이드 정렬 (Slide Sorter)")
        print("3. 숨겨진 슬라이드 찾기 (흐리게 표시됨)")
        print("4. 슬라이드 우클릭 > '슬라이드 숨기기' 해제")
        print("5. 저장")
    else:
        print("[OK] 숨겨진 슬라이드 없음")
        print()
        print("순서 불일치는 다른 원인일 수 있습니다:")
        print("- PPT 파일 내부 구조 문제")
        print("- COM과 python-pptx의 슬라이드 인덱싱 차이")
        print()
        print("다음 단계: Option B (표 구조 기반 매칭) 구현 권장")


if __name__ == "__main__":
    diagnose_hidden_slides()
