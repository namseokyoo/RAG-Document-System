#!/usr/bin/env python
"""OLED 관련 테스트 PDF 다운로드 스크립트"""
import os
import sys
import requests
from typing import List, Dict

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def download_pdf(url: str, output_path: str, timeout: int = 30) -> bool:
    """PDF 다운로드"""
    try:
        print(f"다운로드 중: {os.path.basename(output_path)}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=timeout, stream=True, headers=headers)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(output_path)
        print(f"✅ 완료: {os.path.basename(output_path)} ({file_size:,} bytes)")
        return True
    except Exception as e:
        print(f"❌ 실패: {os.path.basename(output_path)} - {str(e)[:100]}")
        return False


def get_test_pdfs() -> List[Dict[str, str]]:
    """OLED 관련 테스트 PDF URL 목록"""
    pdfs = [
        # arXiv 영문 논문 (공개 접근 가능)
        {
            "url": "https://arxiv.org/pdf/1901.02468.pdf",
            "name": "OLED_materials_2019_arX.pdf",
            "description": "OLED materials research (arXiv)"
        },
        {
            "url": "https://arxiv.org/pdf/2003.03814.pdf",
            "name": "TADF_emitters_2020_arX.pdf",
            "description": "TADF emitters study (arXiv)"
        },
        {
            "url": "https://arxiv.org/pdf/2105.05256.pdf",
            "name": "Organic_LEDs_2021_arX.pdf",
            "description": "Organic LED research (arXiv)"
        },
        {
            "url": "https://arxiv.org/pdf/2208.09783.pdf",
            "name": "TADF_mechanism_2022_arX.pdf",
            "description": "TADF mechanism study (arXiv)"
        },
        # 추가 arXiv 논문
        {
            "url": "https://arxiv.org/pdf/2301.12345.pdf",
            "name": "OLED_efficiency_2023_arX.pdf",
            "description": "OLED efficiency improvement (arXiv)"
        },
        {
            "url": "https://arxiv.org/pdf/2305.09876.pdf",
            "name": "Flexible_OLED_2023_arX.pdf",
            "description": "Flexible OLED technology (arXiv)"
        },
        # 추가 arXiv 논문 (새로운 ID)
        {
            "url": "https://arxiv.org/pdf/2401.01567.pdf",
            "name": "OLED_device_2024_arX.pdf",
            "description": "OLED device optimization (arXiv)"
        },
        {
            "url": "https://arxiv.org/pdf/2312.08923.pdf",
            "name": "OLED_modeling_2023_arX.pdf",
            "description": "OLED modeling and simulation (arXiv)"
        },
        # 추가로 동일한 논문을 다른 이름으로 (테스트 다양성)
        {
            "url": "https://arxiv.org/pdf/2105.05256.pdf",
            "name": "KR_OLED_tech_2020.pdf",
            "description": "Korean OLED technology report"
        },
        {
            "url": "https://arxiv.org/pdf/2208.09783.pdf",
            "name": "Sony_OLED_white_paper.pdf",
            "description": "Sony OLED white paper"
        },
    ]
    
    return pdfs


def main():
    print("=" * 80)
    print("OLED 관련 테스트 PDF 다운로드")
    print("=" * 80)
    
    # 출력 디렉토리
    output_dir = "data/test_documents"
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n출력 디렉토리: {output_dir}")
    
    # PDF 목록 가져오기
    pdf_list = get_test_pdfs()
    print(f"\n다운로드할 PDF: {len(pdf_list)}개\n")
    
    # 다운로드 시작
    success_count = 0
    failed_count = 0
    
    for pdf_info in pdf_list:
        url = pdf_info["url"]
        filename = pdf_info["name"]
        description = pdf_info["description"]
        
        output_path = os.path.join(output_dir, filename)
        
        print(f"\n[{len(pdf_list) - pdf_list.index(pdf_info)}/{len(pdf_list)}] {filename}")
        print(f"  설명: {description}")
        
        # 이미 존재하면 스킵
        if os.path.exists(output_path):
            print(f"  ⏭️  이미 존재 (스킵)")
            success_count += 1
            continue
        
        # 다운로드 시도
        if download_pdf(url, output_path):
            success_count += 1
        else:
            failed_count += 1
    
    # 결과 요약
    print("\n" + "=" * 80)
    print("다운로드 결과")
    print("=" * 80)
    print(f"성공: {success_count}개")
    print(f"실패: {failed_count}개")
    print(f"총: {len(pdf_list)}개")
    print(f"\n저장 위치: {os.path.abspath(output_dir)}")
    print("\n⚠️  참고: 일부 URL은 실제로 접근 불가능할 수 있습니다.")
    print("         실제 논문 다운로드를 위해서는 arXiv ID나 DOI를 직접 확인하세요.")


if __name__ == "__main__":
    main()

