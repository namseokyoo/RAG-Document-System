#!/usr/bin/env python3
"""
Deep Quality Assessment for RAG Test Results
사용자 요구사항:
- 단순히 답변이 나왔다고 성공이 아님
- 실제 문서를 확인하여 적절한 답이 나왔는지
- 과정이 명확하고 합리적인지
- 추가 답변이 없이도 적당한 분량인지
- 세세하게 성공여부, 실패 원인을 따져야 함
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict


class DeepQualityAssessor:
    """심층 품질 평가자"""

    def __init__(self, test_logs_dir: str):
        self.test_logs_dir = Path(test_logs_dir)
        self.assessments = []

    def load_test_result(self, log_file: Path) -> Dict:
        """테스트 결과 로드"""
        with open(log_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def assess_document_relevance(self, test_result: Dict) -> Dict:
        """문서 적합성 평가"""
        sources = test_result.get('citation', {}).get('sources', [])
        question = test_result.get('test_id', '')

        if not sources:
            return {
                "score": 0,
                "verdict": "FAIL",
                "reason": "출처 문서가 전혀 없음"
            }

        # 출처 분석
        source_analysis = {
            "total_sources": len(sources),
            "unique_docs": len(set(s.get('source', '') for s in sources)),
            "has_citations": all('source' in s for s in sources),
            "has_page_numbers": sum(1 for s in sources if s.get('page') is not None)
        }

        # 기본 평가
        if source_analysis["total_sources"] == 0:
            score = 0
            verdict = "FAIL"
            reason = "출처 없음"
        elif source_analysis["total_sources"] < 3:
            score = 50
            verdict = "PARTIAL"
            reason = f"출처가 부족함 ({source_analysis['total_sources']}개)"
        elif source_analysis["unique_docs"] < 2:
            score = 60
            verdict = "PARTIAL"
            reason = "단일 문서에만 의존"
        else:
            score = 85
            verdict = "PASS"
            reason = f"{source_analysis['unique_docs']}개 문서 참조, 충분"

        return {
            "score": score,
            "verdict": verdict,
            "reason": reason,
            "details": source_analysis
        }

    def assess_answer_completeness(self, test_result: Dict) -> Dict:
        """답변 완전성 평가"""
        answer = test_result.get('answer', '')

        if not answer or answer == "ERROR":
            return {
                "score": 0,
                "verdict": "FAIL",
                "reason": "답변이 생성되지 않음"
            }

        answer_len = len(answer)

        # 길이 기반 평가
        if answer_len < 50:
            score = 30
            verdict = "FAIL"
            reason = "답변이 너무 짧음 (불충분)"
        elif answer_len < 150:
            score = 60
            verdict = "PARTIAL"
            reason = "답변이 간략함 (보통)"
        elif answer_len > 2000:
            score = 70
            verdict = "PARTIAL"
            reason = "답변이 너무 장황함"
        else:
            score = 90
            verdict = "PASS"
            reason = "적절한 분량"

        # Citation 포함 확인
        has_citations = '[' in answer and ']' in answer
        if not has_citations:
            score -= 20
            reason += " (Citation 누락)"

        return {
            "score": max(0, score),
            "verdict": verdict,
            "reason": reason,
            "details": {
                "length": answer_len,
                "has_citations": has_citations,
                "answer_preview": answer[:100] + "..." if len(answer) > 100 else answer
            }
        }

    def assess_process_clarity(self, test_result: Dict) -> Dict:
        """처리 과정 명확성 평가"""

        # 필수 단계 확인
        required_steps = ['classification', 'search', 'reranking', 'citation', 'generation']
        present_steps = [step for step in required_steps if step in test_result]

        score = (len(present_steps) / len(required_steps)) * 100

        # 시간 측정 확인
        total_time = test_result.get('total', {}).get('elapsed_time', 0)

        if total_time == 0:
            score -= 20
            verdict = "PARTIAL"
            reason = "시간 측정 안됨"
        elif total_time > 120:  # 2분 이상
            score -= 10
            verdict = "PARTIAL"
            reason = f"처리 시간 과다 ({total_time:.1f}s)"
        else:
            verdict = "PASS" if score >= 80 else "PARTIAL"
            reason = f"정상 처리 ({total_time:.1f}s)"

        return {
            "score": max(0, score),
            "verdict": verdict,
            "reason": reason,
            "details": {
                "present_steps": present_steps,
                "missing_steps": [s for s in required_steps if s not in present_steps],
                "total_time": total_time
            }
        }

    def assess_hallucination_risk(self, test_result: Dict) -> Dict:
        """환각 위험 평가"""
        answer = test_result.get('answer', '')
        sources = test_result.get('citation', {}).get('sources', [])

        # Citation이 있는지 확인
        citation_count = answer.count('[')

        # 답변 길이 대비 citation 비율
        answer_sentences = answer.count('.') + answer.count('!') + answer.count('?')
        if answer_sentences == 0:
            answer_sentences = 1

        citations_per_sentence = citation_count / answer_sentences

        if len(sources) == 0:
            score = 0
            verdict = "HIGH_RISK"
            reason = "출처 없음 - 환각 가능성 높음"
        elif citation_count == 0:
            score = 20
            verdict = "HIGH_RISK"
            reason = "Citation 없음 - 근거 불명확"
        elif citations_per_sentence < 0.2:
            score = 50
            verdict = "MEDIUM_RISK"
            reason = "Citation 부족"
        else:
            score = 90
            verdict = "LOW_RISK"
            reason = "적절한 Citation"

        return {
            "score": score,
            "verdict": verdict,
            "reason": reason,
            "details": {
                "citation_count": citation_count,
                "source_count": len(sources),
                "citations_per_sentence": round(citations_per_sentence, 2)
            }
        }

    def comprehensive_assessment(self, log_file: Path) -> Dict:
        """종합 평가"""
        test_result = self.load_test_result(log_file)
        test_id = test_result.get('test_id', 'unknown')
        question = test_result.get('question', 'unknown')

        # 4가지 차원 평가
        doc_relevance = self.assess_document_relevance(test_result)
        answer_complete = self.assess_answer_completeness(test_result)
        process_clarity = self.assess_process_clarity(test_result)
        hallucination = self.assess_hallucination_risk(test_result)

        # 종합 점수 계산 (가중 평균)
        weights = {
            "document_relevance": 0.3,
            "answer_completeness": 0.25,
            "process_clarity": 0.25,
            "hallucination_prevention": 0.2
        }

        overall_score = (
            doc_relevance["score"] * weights["document_relevance"] +
            answer_complete["score"] * weights["answer_completeness"] +
            process_clarity["score"] * weights["process_clarity"] +
            hallucination["score"] * weights["hallucination_prevention"]
        )

        # 종합 판정
        if overall_score >= 80:
            final_verdict = "SUCCESS"
        elif overall_score >= 60:
            final_verdict = "PARTIAL_SUCCESS"
        else:
            final_verdict = "FAILURE"

        # 실패 원인 분석
        failure_reasons = []
        if doc_relevance["verdict"] == "FAIL":
            failure_reasons.append(f"문서 적합성: {doc_relevance['reason']}")
        if answer_complete["verdict"] == "FAIL":
            failure_reasons.append(f"답변 완전성: {answer_complete['reason']}")
        if hallucination["verdict"] == "HIGH_RISK":
            failure_reasons.append(f"환각 위험: {hallucination['reason']}")
        if process_clarity["score"] < 50:
            failure_reasons.append(f"처리 과정: {process_clarity['reason']}")

        return {
            "test_id": test_id,
            "question": question,
            "overall_score": round(overall_score, 1),
            "final_verdict": final_verdict,
            "failure_reasons": failure_reasons,
            "assessments": {
                "document_relevance": doc_relevance,
                "answer_completeness": answer_complete,
                "process_clarity": process_clarity,
                "hallucination_prevention": hallucination
            },
            "test_result_summary": {
                "answer_length": len(test_result.get('answer', '')),
                "sources_count": len(test_result.get('citation', {}).get('sources', [])),
                "total_time": test_result.get('total', {}).get('elapsed_time', 0),
                "llm_calls": test_result.get('total', {}).get('llm_calls', 0)
            }
        }

    def assess_all_tests(self) -> List[Dict]:
        """모든 테스트 평가"""
        log_files = sorted(self.test_logs_dir.glob("*.json"))

        if not log_files:
            print(f"[ERROR] No test logs found in {self.test_logs_dir}")
            return []

        print(f"[INFO] Found {len(log_files)} test result files")

        assessments = []
        for log_file in log_files:
            try:
                assessment = self.comprehensive_assessment(log_file)
                assessments.append(assessment)

                # 터미널 출력
                print(f"\n{'='*60}")
                print(f"[{assessment['final_verdict']}] {assessment['test_id']}")
                print(f"  Overall Score: {assessment['overall_score']}/100")
                print(f"  Question: {assessment['question'][:80]}...")

                if assessment['failure_reasons']:
                    print(f"  Failure Reasons:")
                    for reason in assessment['failure_reasons']:
                        print(f"    - {reason}")

                # 각 차원 점수
                print(f"  Dimension Scores:")
                for dim_name, dim_result in assessment['assessments'].items():
                    print(f"    - {dim_name}: {dim_result['score']}/100 ({dim_result['verdict']})")

            except Exception as e:
                print(f"[ERROR] Failed to assess {log_file.name}: {e}")
                continue

        return assessments

    def generate_report(self, assessments: List[Dict], output_file: str):
        """평가 보고서 생성"""

        # 통계 계산
        total_tests = len(assessments)
        success_count = sum(1 for a in assessments if a['final_verdict'] == 'SUCCESS')
        partial_count = sum(1 for a in assessments if a['final_verdict'] == 'PARTIAL_SUCCESS')
        failure_count = sum(1 for a in assessments if a['final_verdict'] == 'FAILURE')

        avg_score = sum(a['overall_score'] for a in assessments) / total_tests if total_tests > 0 else 0

        # Dimension별 평균 점수
        dim_scores = defaultdict(list)
        for assessment in assessments:
            for dim_name, dim_result in assessment['assessments'].items():
                dim_scores[dim_name].append(dim_result['score'])

        dim_averages = {
            dim: sum(scores)/len(scores) if scores else 0
            for dim, scores in dim_scores.items()
        }

        # 실패 원인 빈도
        failure_reason_freq = defaultdict(int)
        for assessment in assessments:
            for reason in assessment['failure_reasons']:
                failure_reason_freq[reason] += 1

        # 보고서 작성
        report = {
            "summary": {
                "total_tests": total_tests,
                "success": success_count,
                "partial_success": partial_count,
                "failure": failure_count,
                "success_rate": round((success_count / total_tests * 100) if total_tests > 0 else 0, 1),
                "average_score": round(avg_score, 1)
            },
            "dimension_averages": {k: round(v, 1) for k, v in dim_averages.items()},
            "failure_reasons": dict(sorted(failure_reason_freq.items(), key=lambda x: x[1], reverse=True)),
            "detailed_assessments": assessments
        }

        # 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # 콘솔 출력
        print(f"\n{'='*60}")
        print("DEEP QUALITY ASSESSMENT REPORT")
        print(f"{'='*60}")
        print(f"\n[Summary]")
        print(f"  Total Tests: {total_tests}")
        print(f"  Success: {success_count} ({success_count/total_tests*100:.1f}%)")
        print(f"  Partial Success: {partial_count} ({partial_count/total_tests*100:.1f}%)")
        print(f"  Failure: {failure_count} ({failure_count/total_tests*100:.1f}%)")
        print(f"  Average Score: {avg_score:.1f}/100")

        print(f"\n[Dimension Scores]")
        for dim, score in dim_averages.items():
            print(f"  {dim}: {score:.1f}/100")

        print(f"\n[Top Failure Reasons]")
        for reason, count in list(failure_reason_freq.items())[:5]:
            print(f"  {count}x: {reason}")

        print(f"\n[Report saved to: {output_file}]")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Deep Quality Assessment for RAG Tests")
    parser.add_argument(
        "--test-logs-dir",
        required=True,
        help="Directory containing test log JSON files"
    )
    parser.add_argument(
        "--output",
        default="deep_quality_report.json",
        help="Output report file"
    )

    args = parser.parse_args()

    # 평가 실행
    assessor = DeepQualityAssessor(args.test_logs_dir)
    assessments = assessor.assess_all_tests()

    if assessments:
        assessor.generate_report(assessments, args.output)
    else:
        print("[ERROR] No assessments generated")


if __name__ == "__main__":
    main()
