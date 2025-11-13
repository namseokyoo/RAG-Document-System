#!/usr/bin/env python3
"""
Retrieval Diversity Analysis
Day 1, Task 1: Analyze current retrieval patterns to confirm root cause

목표:
1. 단일 문서 의존 문제의 정확한 발생 위치 파악
2. Reranking, Small-to-Large, Deduplication 중 어디서 문제가 발생하는지 확인
3. 문서 다양성 패턴 분석
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Any
import statistics


class RetrievalDiversityAnalyzer:
    """Retrieval diversity analyzer"""

    def __init__(self, test_logs_dir: str):
        self.test_logs_dir = Path(test_logs_dir)
        self.analysis_results = []

    def load_test_result(self, log_file: Path) -> Dict:
        """Load test result"""
        with open(log_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def analyze_single_test(self, test_result: Dict) -> Dict:
        """Analyze a single test result"""
        test_id = test_result.get('test_id', 'unknown')
        question = test_result.get('question', '')

        # Extract sources from different stages
        search_results = test_result.get('search', {}).get('retrieved_docs', [])
        reranking_results = test_result.get('reranking', {}).get('reranked_docs', [])
        citation_sources = test_result.get('citation', {}).get('sources', [])

        # Analyze diversity at each stage
        analysis = {
            "test_id": test_id,
            "question_preview": question[:100] if question else "N/A",
            "stages": {}
        }

        # Stage 1: Initial Search
        if search_results:
            search_docs = [doc.get('metadata', {}).get('source', 'unknown') for doc in search_results]
            analysis['stages']['search'] = {
                "total_docs": len(search_docs),
                "unique_docs": len(set(search_docs)),
                "doc_distribution": dict(Counter(search_docs)),
                "diversity_ratio": len(set(search_docs)) / len(search_docs) if search_docs else 0
            }

        # Stage 2: Reranking
        if reranking_results:
            rerank_docs = [doc.get('metadata', {}).get('source', 'unknown') for doc in reranking_results]
            analysis['stages']['reranking'] = {
                "total_docs": len(rerank_docs),
                "unique_docs": len(set(rerank_docs)),
                "doc_distribution": dict(Counter(rerank_docs)),
                "diversity_ratio": len(set(rerank_docs)) / len(rerank_docs) if rerank_docs else 0
            }

        # Stage 3: Final Citation
        if citation_sources:
            citation_docs = [src.get('source', 'unknown') for src in citation_sources]
            analysis['stages']['citation'] = {
                "total_docs": len(citation_docs),
                "unique_docs": len(set(citation_docs)),
                "doc_distribution": dict(Counter(citation_docs)),
                "diversity_ratio": len(set(citation_docs)) / len(citation_docs) if citation_docs else 0
            }

        # Identify problem stage
        problem_stage = self.identify_problem_stage(analysis['stages'])
        analysis['problem_stage'] = problem_stage

        return analysis

    def identify_problem_stage(self, stages: Dict) -> str:
        """Identify which stage causes diversity loss"""
        if not stages:
            return "NO_DATA"

        # Check if diversity decreases at each stage
        search_div = stages.get('search', {}).get('diversity_ratio', 1.0)
        rerank_div = stages.get('reranking', {}).get('diversity_ratio', 1.0)
        citation_div = stages.get('citation', {}).get('diversity_ratio', 1.0)

        # Find where the biggest drop occurs
        drops = []
        if 'search' in stages and 'reranking' in stages:
            drops.append(('search→reranking', search_div - rerank_div))
        if 'reranking' in stages and 'citation' in stages:
            drops.append(('reranking→citation', rerank_div - citation_div))

        if not drops:
            return "UNKNOWN"

        biggest_drop = max(drops, key=lambda x: x[1])

        if biggest_drop[1] > 0.2:  # Significant drop (>20%)
            return biggest_drop[0]
        elif citation_div < 0.4:  # Final diversity too low
            return "ALL_STAGES_LOW"
        else:
            return "NO_SIGNIFICANT_PROBLEM"

    def analyze_all_tests(self) -> List[Dict]:
        """Analyze all test results"""
        log_files = sorted(self.test_logs_dir.glob("*.json"))

        if not log_files:
            print(f"[ERROR] No test logs found in {self.test_logs_dir}")
            return []

        print(f"[INFO] Analyzing {len(log_files)} test result files...")

        for log_file in log_files:
            try:
                test_result = self.load_test_result(log_file)
                analysis = self.analyze_single_test(test_result)
                self.analysis_results.append(analysis)
            except Exception as e:
                print(f"[ERROR] Failed to analyze {log_file.name}: {e}")
                continue

        return self.analysis_results

    def generate_summary_report(self) -> Dict:
        """Generate summary report"""
        if not self.analysis_results:
            return {"error": "No analysis results"}

        # Aggregate statistics
        total_tests = len(self.analysis_results)

        # Problem stage distribution
        problem_stages = Counter([r['problem_stage'] for r in self.analysis_results])

        # Diversity statistics by stage
        stage_stats = defaultdict(lambda: {
            'diversity_ratios': [],
            'unique_docs': [],
            'total_docs': []
        })

        for result in self.analysis_results:
            for stage_name, stage_data in result['stages'].items():
                stage_stats[stage_name]['diversity_ratios'].append(stage_data['diversity_ratio'])
                stage_stats[stage_name]['unique_docs'].append(stage_data['unique_docs'])
                stage_stats[stage_name]['total_docs'].append(stage_data['total_docs'])

        # Calculate averages
        stage_averages = {}
        for stage_name, stats in stage_stats.items():
            stage_averages[stage_name] = {
                'avg_diversity_ratio': statistics.mean(stats['diversity_ratios']) if stats['diversity_ratios'] else 0,
                'avg_unique_docs': statistics.mean(stats['unique_docs']) if stats['unique_docs'] else 0,
                'avg_total_docs': statistics.mean(stats['total_docs']) if stats['total_docs'] else 0,
                'min_unique_docs': min(stats['unique_docs']) if stats['unique_docs'] else 0,
                'max_unique_docs': max(stats['unique_docs']) if stats['unique_docs'] else 0
            }

        # Find tests with worst diversity
        worst_tests = sorted(
            self.analysis_results,
            key=lambda x: x['stages'].get('citation', {}).get('diversity_ratio', 1.0)
        )[:10]

        # Find tests with best diversity
        best_tests = sorted(
            self.analysis_results,
            key=lambda x: x['stages'].get('citation', {}).get('diversity_ratio', 0.0),
            reverse=True
        )[:10]

        summary = {
            "total_tests": total_tests,
            "problem_stage_distribution": dict(problem_stages),
            "stage_averages": stage_averages,
            "worst_diversity_tests": [
                {
                    "test_id": t['test_id'],
                    "question": t['question_preview'],
                    "citation_diversity": t['stages'].get('citation', {}).get('diversity_ratio', 0),
                    "citation_unique_docs": t['stages'].get('citation', {}).get('unique_docs', 0),
                    "problem_stage": t['problem_stage']
                }
                for t in worst_tests
            ],
            "best_diversity_tests": [
                {
                    "test_id": t['test_id'],
                    "question": t['question_preview'],
                    "citation_diversity": t['stages'].get('citation', {}).get('diversity_ratio', 0),
                    "citation_unique_docs": t['stages'].get('citation', {}).get('unique_docs', 0)
                }
                for t in best_tests
            ]
        }

        return summary

    def print_detailed_report(self, summary: Dict):
        """Print detailed analysis report"""
        print("\n" + "="*80)
        print("RETRIEVAL DIVERSITY ANALYSIS REPORT")
        print("="*80)

        print(f"\n[Total Tests Analyzed]: {summary['total_tests']}")

        # Problem stage distribution
        print(f"\n[Problem Stage Distribution]:")
        for stage, count in sorted(summary['problem_stage_distribution'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / summary['total_tests']) * 100
            print(f"  {stage}: {count} tests ({percentage:.1f}%)")

        # Stage averages
        print(f"\n[Diversity by Stage]:")
        for stage_name in ['search', 'reranking', 'citation']:
            if stage_name in summary['stage_averages']:
                stats = summary['stage_averages'][stage_name]
                print(f"\n  {stage_name.upper()}:")
                print(f"    Avg Diversity Ratio: {stats['avg_diversity_ratio']:.2f}")
                print(f"    Avg Unique Docs: {stats['avg_unique_docs']:.1f}")
                print(f"    Avg Total Docs: {stats['avg_total_docs']:.1f}")
                print(f"    Range: {stats['min_unique_docs']:.0f} - {stats['max_unique_docs']:.0f} unique docs")

        # Worst diversity tests
        print(f"\n[Top 10 WORST Diversity Tests]:")
        for i, test in enumerate(summary['worst_diversity_tests'], 1):
            print(f"\n  {i}. {test['test_id']}")
            print(f"     Question: {test['question']}")
            print(f"     Diversity: {test['citation_diversity']:.2f} ({test['citation_unique_docs']} unique docs)")
            print(f"     Problem Stage: {test['problem_stage']}")

        # Best diversity tests
        print(f"\n[Top 10 BEST Diversity Tests]:")
        for i, test in enumerate(summary['best_diversity_tests'], 1):
            print(f"\n  {i}. {test['test_id']}")
            print(f"     Question: {test['question']}")
            print(f"     Diversity: {test['citation_diversity']:.2f} ({test['citation_unique_docs']} unique docs)")

        print("\n" + "="*80)

    def save_report(self, summary: Dict, output_file: str):
        """Save full report to JSON"""
        full_report = {
            "summary": summary,
            "detailed_results": self.analysis_results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, ensure_ascii=False, indent=2)

        print(f"\n[Report saved to: {output_file}]")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze Retrieval Diversity")
    parser.add_argument(
        "--logs",
        default="test_logs_comprehensive_full",
        help="Test logs directory"
    )
    parser.add_argument(
        "--output",
        default="retrieval_diversity_report.json",
        help="Output report file"
    )

    args = parser.parse_args()

    # Run analysis
    analyzer = RetrievalDiversityAnalyzer(args.logs)
    analyzer.analyze_all_tests()

    # Generate summary
    summary = analyzer.generate_summary_report()

    # Print report
    analyzer.print_detailed_report(summary)

    # Save report
    analyzer.save_report(summary, args.output)


if __name__ == "__main__":
    main()
