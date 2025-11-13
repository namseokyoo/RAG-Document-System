#!/usr/bin/env python3
"""
RAG 파이프라인 상세 로깅 시스템
모든 중간 단계의 파라미터, 전달 값, 성능 지표를 기록
"""

import time
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ClassificationLog:
    """질문 분류 단계 로그"""
    type: str = ""
    confidence: float = 0.0
    method: str = ""
    multi_query: bool = False
    max_results: int = 0
    max_tokens: int = 0
    elapsed_time: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryExpansionLog:
    """쿼리 확장 단계 로그"""
    enabled: bool = False
    original_query: str = ""
    expanded_queries: List[str] = field(default_factory=list)
    synonym_expansion: Dict[str, List[str]] = field(default_factory=dict)
    elapsed_time: float = 0.0
    llm_calls: int = 0
    tokens_used: int = 0


@dataclass
class VectorSearchLog:
    """벡터 검색 단계 로그"""
    query: str = ""
    k: int = 0
    results: int = 0
    elapsed_time: float = 0.0
    embedding_time: float = 0.0
    embedding_dimension: int = 0
    top_scores: List[float] = field(default_factory=list)


@dataclass
class BM25SearchLog:
    """BM25 검색 단계 로그"""
    query: str = ""
    k: int = 0
    results: int = 0
    elapsed_time: float = 0.0
    top_scores: List[float] = field(default_factory=list)


@dataclass
class SearchFusionLog:
    """검색 결과 융합 로그"""
    alpha: float = 0.5
    vector_results: int = 0
    bm25_results: int = 0
    combined_results: int = 0
    elapsed_time: float = 0.0


@dataclass
class SearchLog:
    """전체 검색 단계 로그"""
    vector_search: VectorSearchLog = field(default_factory=VectorSearchLog)
    bm25_search: BM25SearchLog = field(default_factory=BM25SearchLog)
    fusion: SearchFusionLog = field(default_factory=SearchFusionLog)
    total_elapsed_time: float = 0.0


@dataclass
class RerankingLog:
    """재정렬 단계 로그"""
    enabled: bool = False
    input_docs: int = 0
    reranker_model: str = ""
    output_docs: int = 0
    score_threshold: float = 0.0
    adaptive_threshold: Optional[float] = None
    scores: List[float] = field(default_factory=list)
    elapsed_time: float = 0.0
    filtered_by_score: int = 0
    filtered_by_max: int = 0


@dataclass
class ContextExpansionLog:
    """컨텍스트 확장 단계 로그 (Small-to-Large)"""
    enabled: bool = False
    initial_chunks: int = 0
    expanded_chunks: int = 0
    context_size_chars: int = 0
    context_size_tokens_estimate: int = 0
    expansion_strategy: str = ""
    elapsed_time: float = 0.0


@dataclass
class GenerationLog:
    """답변 생성 단계 로그"""
    llm_model: str = ""
    temperature: float = 0.0
    max_tokens: int = 0
    context_tokens_estimate: int = 0
    output_tokens_estimate: int = 0
    elapsed_time: float = 0.0
    streaming: bool = False
    prompt_template: str = ""


@dataclass
class CitationLog:
    """인용 단계 로그"""
    sources_count: int = 0
    sources: List[Dict[str, Any]] = field(default_factory=list)
    deduplication: bool = False
    accuracy_check: bool = False
    elapsed_time: float = 0.0


@dataclass
class TotalMetrics:
    """전체 성능 지표"""
    elapsed_time: float = 0.0
    llm_calls: int = 0
    total_tokens_estimate: int = 0
    estimated_cost: float = 0.0


@dataclass
class AnswerQuality:
    """답변 품질 평가 (수동 또는 자동)"""
    relevance: Optional[float] = None
    completeness: Optional[float] = None
    citation_accuracy: Optional[float] = None
    hallucination_detected: bool = False
    notes: str = ""


@dataclass
class DetailedLog:
    """전체 파이프라인 상세 로그"""
    test_id: str = ""
    timestamp: str = ""
    question: str = ""

    # 각 단계 로그
    classification: ClassificationLog = field(default_factory=ClassificationLog)
    query_expansion: QueryExpansionLog = field(default_factory=QueryExpansionLog)
    search: SearchLog = field(default_factory=SearchLog)
    reranking: RerankingLog = field(default_factory=RerankingLog)
    context_expansion: ContextExpansionLog = field(default_factory=ContextExpansionLog)
    generation: GenerationLog = field(default_factory=GenerationLog)
    citation: CitationLog = field(default_factory=CitationLog)

    # 전체 지표
    total: TotalMetrics = field(default_factory=TotalMetrics)

    # 결과
    answer: str = ""
    answer_quality: AnswerQuality = field(default_factory=AnswerQuality)

    # 에러 정보
    error: Optional[str] = None
    error_stage: Optional[str] = None


class DetailedLogger:
    """상세 로깅 관리자"""

    def __init__(self, output_dir: str = "test_logs"):
        """
        Args:
            output_dir: 로그 저장 디렉토리
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.current_log: Optional[DetailedLog] = None
        self.start_time: float = 0.0

    def start_test(self, test_id: str, question: str) -> DetailedLog:
        """테스트 시작 및 로그 초기화"""
        self.current_log = DetailedLog(
            test_id=test_id,
            timestamp=datetime.now().isoformat(),
            question=question
        )
        self.start_time = time.time()
        return self.current_log

    def log_classification(
        self,
        q_type: str,
        confidence: float,
        method: str,
        multi_query: bool,
        max_results: int,
        max_tokens: int,
        elapsed_time: float,
        details: Optional[Dict] = None
    ):
        """질문 분류 로그 기록"""
        if self.current_log:
            self.current_log.classification = ClassificationLog(
                type=q_type,
                confidence=confidence,
                method=method,
                multi_query=multi_query,
                max_results=max_results,
                max_tokens=max_tokens,
                elapsed_time=elapsed_time,
                details=details or {}
            )

    def log_query_expansion(
        self,
        enabled: bool,
        original_query: str,
        expanded_queries: List[str],
        synonym_expansion: Optional[Dict] = None,
        elapsed_time: float = 0.0,
        llm_calls: int = 0,
        tokens_used: int = 0
    ):
        """쿼리 확장 로그 기록"""
        if self.current_log:
            self.current_log.query_expansion = QueryExpansionLog(
                enabled=enabled,
                original_query=original_query,
                expanded_queries=expanded_queries,
                synonym_expansion=synonym_expansion or {},
                elapsed_time=elapsed_time,
                llm_calls=llm_calls,
                tokens_used=tokens_used
            )

    def log_search(
        self,
        vector_search: Optional[Dict] = None,
        bm25_search: Optional[Dict] = None,
        fusion: Optional[Dict] = None,
        total_elapsed_time: float = 0.0
    ):
        """검색 로그 기록"""
        if self.current_log:
            search_log = SearchLog(total_elapsed_time=total_elapsed_time)

            if vector_search:
                search_log.vector_search = VectorSearchLog(**vector_search)

            if bm25_search:
                search_log.bm25_search = BM25SearchLog(**bm25_search)

            if fusion:
                search_log.fusion = SearchFusionLog(**fusion)

            self.current_log.search = search_log

    def log_reranking(
        self,
        enabled: bool,
        input_docs: int,
        reranker_model: str,
        output_docs: int,
        score_threshold: float,
        adaptive_threshold: Optional[float],
        scores: List[float],
        elapsed_time: float,
        filtered_by_score: int = 0,
        filtered_by_max: int = 0
    ):
        """재정렬 로그 기록"""
        if self.current_log:
            self.current_log.reranking = RerankingLog(
                enabled=enabled,
                input_docs=input_docs,
                reranker_model=reranker_model,
                output_docs=output_docs,
                score_threshold=score_threshold,
                adaptive_threshold=adaptive_threshold,
                scores=scores,
                elapsed_time=elapsed_time,
                filtered_by_score=filtered_by_score,
                filtered_by_max=filtered_by_max
            )

    def log_context_expansion(
        self,
        enabled: bool,
        initial_chunks: int,
        expanded_chunks: int,
        context_size_chars: int,
        context_size_tokens_estimate: int,
        expansion_strategy: str,
        elapsed_time: float
    ):
        """컨텍스트 확장 로그 기록"""
        if self.current_log:
            self.current_log.context_expansion = ContextExpansionLog(
                enabled=enabled,
                initial_chunks=initial_chunks,
                expanded_chunks=expanded_chunks,
                context_size_chars=context_size_chars,
                context_size_tokens_estimate=context_size_tokens_estimate,
                expansion_strategy=expansion_strategy,
                elapsed_time=elapsed_time
            )

    def log_generation(
        self,
        llm_model: str,
        temperature: float,
        max_tokens: int,
        context_tokens_estimate: int,
        output_tokens_estimate: int,
        elapsed_time: float,
        streaming: bool,
        prompt_template: str = ""
    ):
        """답변 생성 로그 기록"""
        if self.current_log:
            self.current_log.generation = GenerationLog(
                llm_model=llm_model,
                temperature=temperature,
                max_tokens=max_tokens,
                context_tokens_estimate=context_tokens_estimate,
                output_tokens_estimate=output_tokens_estimate,
                elapsed_time=elapsed_time,
                streaming=streaming,
                prompt_template=prompt_template[:200]  # 프롬프트 일부만 저장
            )

    def log_citation(
        self,
        sources: List[Dict],
        deduplication: bool,
        accuracy_check: bool,
        elapsed_time: float
    ):
        """인용 로그 기록"""
        if self.current_log:
            self.current_log.citation = CitationLog(
                sources_count=len(sources),
                sources=sources,
                deduplication=deduplication,
                accuracy_check=accuracy_check,
                elapsed_time=elapsed_time
            )

    def log_error(self, error: str, stage: str):
        """에러 로그 기록"""
        if self.current_log:
            self.current_log.error = error
            self.current_log.error_stage = stage

    def finalize(self, answer: str, quality: Optional[Dict] = None) -> DetailedLog:
        """로그 완료 및 저장"""
        if not self.current_log:
            raise ValueError("로그가 시작되지 않았습니다")

        # 전체 시간 계산
        total_time = time.time() - self.start_time

        # 전체 지표 계산
        llm_calls = (
            self.current_log.query_expansion.llm_calls +
            1  # Generation
        )

        total_tokens = (
            self.current_log.query_expansion.tokens_used +
            self.current_log.generation.context_tokens_estimate +
            self.current_log.generation.output_tokens_estimate
        )

        # 비용 추정 (예: GPT-3.5 기준 $0.001/1K tokens)
        estimated_cost = total_tokens * 0.000001

        self.current_log.total = TotalMetrics(
            elapsed_time=total_time,
            llm_calls=llm_calls,
            total_tokens_estimate=total_tokens,
            estimated_cost=estimated_cost
        )

        # 답변 저장
        self.current_log.answer = answer

        # 품질 평가 (있는 경우)
        if quality:
            self.current_log.answer_quality = AnswerQuality(**quality)

        # 파일로 저장
        self._save_log(self.current_log)

        return self.current_log

    def _save_log(self, log: DetailedLog):
        """로그를 JSON 파일로 저장"""
        filename = f"{log.test_id}_{log.timestamp.replace(':', '-')}.json"
        filepath = self.output_dir / filename

        # dataclass를 dict로 변환
        log_dict = asdict(log)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(log_dict, f, indent=2, ensure_ascii=False)

        print(f"[DetailedLogger] 로그 저장: {filepath}")

    def save_summary(self, logs: List[DetailedLog], output_file: str = "test_summary.json"):
        """여러 로그의 요약 저장"""
        summary = {
            "total_tests": len(logs),
            "timestamp": datetime.now().isoformat(),
            "statistics": self._calculate_statistics(logs),
            "test_results": [asdict(log) for log in logs]
        }

        filepath = self.output_dir / output_file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"[DetailedLogger] 요약 저장: {filepath}")

    def _calculate_statistics(self, logs: List[DetailedLog]) -> Dict:
        """통계 계산"""
        if not logs:
            return {}

        # 응답 시간 통계
        times = [log.total.elapsed_time for log in logs]
        times_sorted = sorted(times)

        # LLM 호출 통계
        llm_calls = [log.total.llm_calls for log in logs]

        # 토큰 사용 통계
        tokens = [log.total.total_tokens_estimate for log in logs]

        # 비용 통계
        costs = [log.total.estimated_cost for log in logs]

        # 분류기 정확도 (수동 검증 필요)
        classifications = [log.classification.type for log in logs]

        return {
            "response_time": {
                "mean": sum(times) / len(times),
                "median": times_sorted[len(times) // 2],
                "min": min(times),
                "max": max(times),
                "p95": times_sorted[int(len(times) * 0.95)],
                "p99": times_sorted[int(len(times) * 0.99)]
            },
            "llm_calls": {
                "mean": sum(llm_calls) / len(llm_calls),
                "total": sum(llm_calls)
            },
            "tokens": {
                "mean": sum(tokens) / len(tokens),
                "total": sum(tokens)
            },
            "cost": {
                "mean": sum(costs) / len(costs),
                "total": sum(costs)
            },
            "classification_distribution": {
                "simple": classifications.count("simple"),
                "normal": classifications.count("normal"),
                "complex": classifications.count("complex"),
                "exhaustive": classifications.count("exhaustive")
            },
            "errors": len([log for log in logs if log.error is not None])
        }


# 전역 로거 인스턴스
_global_logger: Optional[DetailedLogger] = None


def get_logger(output_dir: str = "test_logs") -> DetailedLogger:
    """전역 로거 인스턴스 가져오기"""
    global _global_logger
    if _global_logger is None:
        _global_logger = DetailedLogger(output_dir)
    return _global_logger


def reset_logger():
    """전역 로거 초기화"""
    global _global_logger
    _global_logger = None
