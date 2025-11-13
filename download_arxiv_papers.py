#!/usr/bin/env python3
"""
arXiv에서 관련 논문을 다운로드하는 스크립트
"""

import os
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

# 다운로드 디렉토리
DOWNLOAD_DIR = "embedded_documents"
Path(DOWNLOAD_DIR).mkdir(exist_ok=True)

# arXiv API 설정
ARXIV_API_URL = "http://export.arxiv.org/api/query"

# 검색 쿼리 설정
SEARCH_QUERIES = {
    "OLED": "all:OLED OR all:\"organic light emitting diode\"",
    "Display": "all:\"flexible display\" OR all:\"display technology\"",
    "Perovskite": "all:perovskite AND all:\"solar cell\"",
    "Graphene": "all:graphene AND all:properties",
    "MicroLED": "all:MicroLED OR all:\"micro LED\"",
    "QLED": "all:QLED OR all:\"quantum dot\"",
}

def download_arxiv_papers(query: str, max_results: int = 15, category: str = "unknown"):
    """
    arXiv API를 사용하여 논문 다운로드

    Args:
        query: 검색 쿼리 (arXiv API 형식)
        max_results: 최대 다운로드 개수
        category: 카테고리 이름 (파일명에 사용)
    """
    print(f"\n{'='*60}")
    print(f"[{category}] 논문 검색 중...")
    print(f"Query: {query}")
    print(f"{'='*60}")

    # API 요청 구성
    params = {
        'search_query': query,
        'start': 0,
        'max_results': max_results,
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    }

    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

    try:
        # API 호출
        print(f"[API] 요청 중... {url[:100]}...")
        response = urllib.request.urlopen(url)
        data = response.read().decode('utf-8')

        # XML 파싱
        root = ET.fromstring(data)

        # Namespace 처리
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }

        entries = root.findall('atom:entry', ns)
        print(f"[결과] {len(entries)}개 논문 발견")

        downloaded = 0
        skipped = 0

        for idx, entry in enumerate(entries, 1):
            try:
                # 메타데이터 추출
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                arxiv_id = entry.find('atom:id', ns).text.split('/abs/')[-1]
                published = entry.find('atom:published', ns).text[:10]  # YYYY-MM-DD

                # PDF URL 찾기
                pdf_url = None
                for link in entry.findall('atom:link', ns):
                    if link.get('title') == 'pdf':
                        pdf_url = link.get('href')
                        break

                if not pdf_url:
                    print(f"  [{idx}/{len(entries)}] SKIP: PDF 없음 - {title[:50]}...")
                    skipped += 1
                    continue

                # 파일명 생성 (카테고리_arXiv-ID_날짜.pdf)
                safe_id = arxiv_id.replace('/', '-').replace(':', '-')
                filename = f"{category}_{safe_id}_{published}.pdf"
                filepath = os.path.join(DOWNLOAD_DIR, filename)

                # 이미 존재하면 스킵
                if os.path.exists(filepath):
                    print(f"  [{idx}/{len(entries)}] SKIP: 이미 존재 - {filename}")
                    skipped += 1
                    continue

                # PDF 다운로드
                print(f"  [{idx}/{len(entries)}] 다운로드 중: {title[:60]}...")
                print(f"                   → {filename}")

                urllib.request.urlretrieve(pdf_url, filepath)
                downloaded += 1

                # API 제한 방지 (3초 대기)
                time.sleep(3)

            except Exception as e:
                print(f"  [{idx}/{len(entries)}] ERROR: {e}")
                continue

        print(f"\n[완료] {category}: {downloaded}개 다운로드, {skipped}개 스킵")
        return downloaded, skipped

    except Exception as e:
        print(f"[ERROR] API 호출 실패: {e}")
        return 0, 0


def main():
    print("="*60)
    print("arXiv 논문 대량 다운로드")
    print("="*60)
    print(f"다운로드 디렉토리: {DOWNLOAD_DIR}/")
    print(f"총 카테고리: {len(SEARCH_QUERIES)}개")
    print("="*60)

    total_downloaded = 0
    total_skipped = 0

    for category, query in SEARCH_QUERIES.items():
        downloaded, skipped = download_arxiv_papers(query, max_results=15, category=category)
        total_downloaded += downloaded
        total_skipped += skipped

        # 카테고리 간 대기 (API 제한 방지)
        print(f"\n[대기] 다음 카테고리까지 5초 대기...")
        time.sleep(5)

    print("\n" + "="*60)
    print("전체 다운로드 완료!")
    print("="*60)
    print(f"총 다운로드: {total_downloaded}개")
    print(f"총 스킵: {total_skipped}개")
    print(f"최종 파일 수: {len(list(Path(DOWNLOAD_DIR).glob('*.pdf')))}개")
    print("="*60)

    print("\n다음 단계:")
    print("  python re_embed_documents.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자가 다운로드를 중단했습니다.")
    except Exception as e:
        print(f"\n[오류] {e}")
        import traceback
        traceback.print_exc()
