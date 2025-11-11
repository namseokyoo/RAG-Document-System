"""
arXiv에서 OLED 관련 논문 다운로드
"""

import os
import sys
import time
import requests
from pathlib import Path
import xml.etree.ElementTree as ET

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

print("=" * 80)
print("arXiv OLED 논문 다운로드")
print("=" * 80)

# 다운로드 폴더 설정
download_dir = Path("data/embedded_documents")
download_dir.mkdir(parents=True, exist_ok=True)

# arXiv API 검색 쿼리
search_terms = [
    "OLED organic light emitting diode",
    "TADF thermally activated delayed fluorescence",
    "phosphorescent OLED",
    "OLED efficiency",
    "OLED device structure",
    "organic semiconductor OLED",
]

print(f"\n[검색 쿼리]")
for i, term in enumerate(search_terms, 1):
    print(f"  {i}. {term}")

# arXiv API로 논문 검색
def search_arxiv(query, max_results=10):
    """arXiv API로 논문 검색"""
    base_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }

    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"  [오류] 검색 실패: {e}")
        return None

# XML 파싱
def parse_arxiv_response(xml_data):
    """arXiv API 응답 파싱"""
    papers = []

    try:
        root = ET.fromstring(xml_data)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}

        for entry in root.findall('atom:entry', namespace):
            title = entry.find('atom:title', namespace).text.strip()
            pdf_link = None

            # PDF 링크 찾기
            for link in entry.findall('atom:link', namespace):
                if link.get('title') == 'pdf':
                    pdf_link = link.get('href')
                    break

            if pdf_link:
                # arXiv ID 추출
                arxiv_id = pdf_link.split('/')[-1].replace('.pdf', '')
                papers.append({
                    'title': title,
                    'pdf_url': pdf_link,
                    'arxiv_id': arxiv_id
                })

    except Exception as e:
        print(f"  [오류] XML 파싱 실패: {e}")

    return papers

# PDF 다운로드
def download_pdf(url, filepath):
    """PDF 다운로드"""
    try:
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True
    except Exception as e:
        print(f"    [오류] 다운로드 실패: {e}")
        return False

# 메인 다운로드 로직
print(f"\n{'=' * 80}")
print(f"논문 검색 및 다운로드")
print(f"{'=' * 80}")

all_papers = []
papers_per_query = 5  # 각 쿼리당 5개씩

for i, query in enumerate(search_terms, 1):
    print(f"\n[검색 {i}/{len(search_terms)}] {query}")
    print(f"-" * 80)

    # 검색
    xml_data = search_arxiv(query, max_results=papers_per_query)
    if not xml_data:
        continue

    # 파싱
    papers = parse_arxiv_response(xml_data)
    print(f"  발견: {len(papers)}개 논문")

    all_papers.extend(papers)
    time.sleep(3)  # API rate limit 준수

# 중복 제거 (arxiv_id 기준)
unique_papers = {}
for paper in all_papers:
    unique_papers[paper['arxiv_id']] = paper

papers_to_download = list(unique_papers.values())[:30]  # 최대 30개

print(f"\n{'=' * 80}")
print(f"다운로드 시작 ({len(papers_to_download)}개)")
print(f"{'=' * 80}")

success_count = 0
fail_count = 0

for i, paper in enumerate(papers_to_download, 1):
    arxiv_id = paper['arxiv_id']
    title = paper['title'][:50]  # 제목 짧게
    pdf_url = paper['pdf_url']

    # 파일명 생성 (안전한 문자만)
    safe_filename = f"OLED_{arxiv_id}.pdf"
    filepath = download_dir / safe_filename

    # 이미 존재하면 스킵
    if filepath.exists():
        print(f"[{i}/{len(papers_to_download)}] 이미 존재: {safe_filename}")
        success_count += 1
        continue

    print(f"\n[{i}/{len(papers_to_download)}] {title}...")
    print(f"  arXiv ID: {arxiv_id}")
    print(f"  URL: {pdf_url}")
    print(f"  다운로드 중...")

    if download_pdf(pdf_url, filepath):
        file_size_mb = filepath.stat().st_size / 1024 / 1024
        print(f"  ✓ 성공: {file_size_mb:.1f} MB")
        success_count += 1
    else:
        print(f"  ✗ 실패")
        fail_count += 1

    time.sleep(3)  # API rate limit 준수

# 결과 요약
print(f"\n{'=' * 80}")
print(f"다운로드 완료")
print(f"{'=' * 80}")

print(f"\n[결과]")
print(f"  - 성공: {success_count}/{len(papers_to_download)}")
print(f"  - 실패: {fail_count}/{len(papers_to_download)}")
print(f"  - 저장 위치: {download_dir}")

print(f"\n{'=' * 80}")
print(f"완료!")
print(f"{'=' * 80}")
