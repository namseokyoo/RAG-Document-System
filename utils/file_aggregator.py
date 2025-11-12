#!/usr/bin/env python3
"""
File-level Aggregation for RAG System
Chunk 검색 결과를 File 단위로 그룹화하고 점수 계산
"""

from collections import defaultdict
from typing import List, Dict, Any
import numpy as np


class FileAggregator:
    """청크를 파일 단위로 그룹화하는 클래스"""

    def __init__(self, strategy: str = "weighted"):
        """
        Args:
            strategy: 점수 계산 방식
                - "max": 최고 점수 (precision 우선)
                - "mean": 평균 점수 (recall 우선)
                - "weighted": 상위 k개 가중 평균 (추천)
                - "count": 매칭 청크 수 (coverage 우선)
        """
        self.strategy = strategy
        self.valid_strategies = ["max", "mean", "weighted", "count"]

        if strategy not in self.valid_strategies:
            raise ValueError(f"Invalid strategy: {strategy}. Must be one of {self.valid_strategies}")

    def aggregate_chunks_to_files(
        self,
        chunks: List[Any],
        top_n: int = 20,
        min_chunks: int = 1
    ) -> List[Dict[str, Any]]:
        """
        청크를 파일로 그룹화하고 점수 계산

        Args:
            chunks: 검색된 청크 리스트 (Document 객체)
            top_n: 반환할 최대 파일 수
            min_chunks: 최소 매칭 청크 수 (필터링용)

        Returns:
            파일 리스트 (점수 내림차순 정렬)
        """
        # 1. 파일별로 청크 그룹화
        file_groups = defaultdict(list)

        for chunk in chunks:
            # metadata에서 파일명 추출
            file_name = chunk.metadata.get('source', 'unknown')

            # chunk에 score 속성이 있는지 확인
            if hasattr(chunk, 'score'):
                score = chunk.score
            elif 'score' in chunk.metadata:
                score = chunk.metadata['score']
            else:
                # score가 없으면 1.0으로 가정
                score = 1.0

            file_groups[file_name].append({
                'chunk': chunk,
                'score': score,
                'content': chunk.page_content,
                'page': chunk.metadata.get('page_number', 0)
            })

        # 2. 파일별 점수 계산
        file_results = []

        for file_name, file_chunks in file_groups.items():
            # 최소 청크 수 필터링
            if len(file_chunks) < min_chunks:
                continue

            # 점수 추출
            scores = [fc['score'] for fc in file_chunks]

            # 전략별 점수 계산
            if self.strategy == "max":
                file_score = max(scores)
            elif self.strategy == "mean":
                file_score = np.mean(scores)
            elif self.strategy == "weighted":
                # Top-3 가중 평균 (0.5, 0.3, 0.2)
                sorted_scores = sorted(scores, reverse=True)
                weights = [0.5, 0.3, 0.2]
                weighted_scores = [
                    w * s for w, s in zip(weights, sorted_scores[:3])
                ]
                file_score = sum(weighted_scores)
                # 청크 수가 3개 미만이면 가중치 재조정
                if len(sorted_scores) < 3:
                    file_score = file_score / sum(weights[:len(sorted_scores)])
            elif self.strategy == "count":
                # 매칭 청크 수 (정규화: 0~1 범위)
                file_score = min(len(file_chunks) / 10.0, 1.0)
            else:
                file_score = max(scores)  # fallback

            # 청크를 점수 순으로 정렬
            sorted_chunks = sorted(
                file_chunks,
                key=lambda x: x['score'],
                reverse=True
            )

            file_results.append({
                'file_name': file_name,
                'relevance_score': file_score,
                'num_matching_chunks': len(file_chunks),
                'top_chunks': sorted_chunks[:3],  # 상위 3개 청크
                'all_chunk_scores': scores,
                'page_numbers': sorted(set(fc['page'] for fc in file_chunks))
            })

        # 3. 파일을 점수 순으로 정렬
        file_results.sort(key=lambda x: x['relevance_score'], reverse=True)

        # 4. Top-N 반환
        return file_results[:top_n]

    def format_as_markdown_table(
        self,
        file_results: List[Dict[str, Any]],
        include_summary: bool = True
    ) -> str:
        """
        파일 리스트를 Markdown 테이블로 포맷팅

        Args:
            file_results: aggregate_chunks_to_files() 결과
            include_summary: 각 파일의 간단한 요약 포함 여부

        Returns:
            Markdown 형식 문자열
        """
        if not file_results:
            return "검색 결과가 없습니다."

        # 헤더
        lines = [
            f"**검색 결과: 총 {len(file_results)}개 파일**\n",
            "| 순위 | 파일명 | 관련도 | 매칭 청크 | 페이지 | 핵심 내용 |",
            "|------|--------|--------|-----------|--------|-----------|"
        ]

        # 각 파일별 행 생성
        for idx, file_info in enumerate(file_results, 1):
            file_name = file_info['file_name']
            score = file_info['relevance_score']
            num_chunks = file_info['num_matching_chunks']
            pages = file_info['page_numbers']

            # 파일명 줄이기 (너무 길면)
            display_name = file_name
            if len(file_name) > 40:
                display_name = file_name[:37] + "..."

            # 페이지 범위 표시
            if pages:
                if len(pages) == 1:
                    page_str = f"p.{pages[0]}"
                elif len(pages) <= 3:
                    page_str = ", ".join([f"p.{p}" for p in pages])
                else:
                    page_str = f"p.{pages[0]}-{pages[-1]}"
            else:
                page_str = "-"

            # 핵심 내용 (첫 번째 청크의 일부)
            if include_summary and file_info['top_chunks']:
                first_chunk = file_info['top_chunks'][0]['content']
                # 첫 100자만 (또는 첫 문장)
                summary = first_chunk[:100].replace('\n', ' ').strip()
                if len(first_chunk) > 100:
                    summary += "..."
            else:
                summary = f"{num_chunks}개 관련 섹션"

            # 행 추가
            lines.append(
                f"| {idx} | {display_name} | {score:.1%} | {num_chunks} | {page_str} | {summary} |"
            )

        return "\n".join(lines)

    def get_statistics(self, file_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        파일 리스트 통계 계산

        Args:
            file_results: aggregate_chunks_to_files() 결과

        Returns:
            통계 딕셔너리
        """
        if not file_results:
            return {
                'total_files': 0,
                'total_chunks': 0,
                'avg_score': 0,
                'avg_chunks_per_file': 0
            }

        total_files = len(file_results)
        total_chunks = sum(f['num_matching_chunks'] for f in file_results)
        avg_score = np.mean([f['relevance_score'] for f in file_results])
        avg_chunks_per_file = total_chunks / total_files if total_files > 0 else 0

        return {
            'total_files': total_files,
            'total_chunks': total_chunks,
            'avg_score': avg_score,
            'avg_chunks_per_file': avg_chunks_per_file,
            'score_distribution': {
                'min': min(f['relevance_score'] for f in file_results),
                'max': max(f['relevance_score'] for f in file_results),
                'median': np.median([f['relevance_score'] for f in file_results])
            }
        }


# 편의 함수
def aggregate_and_format(
    chunks: List[Any],
    strategy: str = "weighted",
    top_n: int = 20
) -> str:
    """
    원스텝으로 aggregation + formatting

    Args:
        chunks: 검색된 청크 리스트
        strategy: 점수 계산 방식
        top_n: 반환할 파일 수

    Returns:
        Markdown 테이블
    """
    aggregator = FileAggregator(strategy=strategy)
    file_results = aggregator.aggregate_chunks_to_files(chunks, top_n=top_n)
    return aggregator.format_as_markdown_table(file_results)
