"""
테스트 결과의 의미적 품질 분석 스크립트
- 예상 답변과 실제 답변의 의미적 일치도 평가
- 문서 타입 검색 정확도 확인
- 주요 문제점 식별
"""

import json
from typing import Dict, List, Any
from pathlib import Path
import re


def analyze_semantic_quality(results_file: str) -> Dict[str, Any]:
    """테스트 결과의 의미적 품질 분석"""
    
    print(f"📊 분석 시작: {results_file}\n")
    
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    pdf_results = data.get("pdf_results", [])
    pptx_results = data.get("pptx_results", [])
    topic_results = data.get("topic_switching_results", [])
    
    analysis = {
        "pdf_quality": {
            "total": len(pdf_results),
            "correct_document_type": 0,  # PDF 질문이 PDF 파일을 검색
            "wrong_document_type": 0,    # PDF 질문이 PPTX 파일을 검색
            "mixed_document_type": 0,    # PDF와 PPTX가 섞임
            "semantically_correct": 0,    # 의미적으로 정확한 답변
            "semantically_wrong": 0,     # 의미적으로 잘못된 답변
            "issues": []
        },
        "pptx_quality": {
            "total": len(pptx_results),
            "correct_document_type": 0,
            "wrong_document_type": 0,
            "mixed_document_type": 0,
            "semantically_correct": 0,
            "semantically_wrong": 0,
            "issues": []
        }
    }
    
    # PDF 결과 분석
    print("📄 PDF 결과 분석 중...")
    for idx, result in enumerate(pdf_results, 1):
        question = result.get("question", "")
        expected_sources = result.get("expected_sources", [])
        actual_sources = result.get("actual_sources", [])
        actual_answer = result.get("actual_answer", "")
        expected_answer = result.get("expected_answer", "")
        
        # 문서 타입 확인
        expected_pdf_files = []
        for source in expected_sources:
            doc_name = source.get("문서", "")
            if "pdf" in doc_name.lower():
                expected_pdf_files.append(doc_name)
        
        actual_pdf_files = [s.get("file_name", "") for s in actual_sources if "pdf" in s.get("file_name", "").lower()]
        actual_pptx_files = [s.get("file_name", "") for s in actual_sources if "pptx" in s.get("file_name", "").lower()]
        
        has_pdf = len(actual_pdf_files) > 0
        has_pptx = len(actual_pptx_files) > 0
        
        # 문서 타입 정확도 평가
        if expected_pdf_files:  # 예상 답변이 PDF를 참조하는 경우
            if has_pdf and not has_pptx:
                analysis["pdf_quality"]["correct_document_type"] += 1
            elif has_pptx and not has_pdf:
                analysis["pdf_quality"]["wrong_document_type"] += 1
                analysis["pdf_quality"]["issues"].append({
                    "index": idx,
                    "question": question[:80] + "..." if len(question) > 80 else question,
                    "expected_pdf": expected_pdf_files,
                    "actual_pptx": actual_pptx_files[:3],
                    "issue_type": "wrong_document_type"
                })
            elif has_pdf and has_pptx:
                analysis["pdf_quality"]["mixed_document_type"] += 1
                analysis["pdf_quality"]["issues"].append({
                    "index": idx,
                    "question": question[:80] + "..." if len(question) > 80 else question,
                    "expected_pdf": expected_pdf_files,
                    "actual_pdf": actual_pdf_files[:2],
                    "actual_pptx": actual_pptx_files[:2],
                    "issue_type": "mixed_document_type"
                })
        
        # 의미적 일치도 간단 평가 (키워드 기반)
        if expected_answer and actual_answer:
            # 예상 답변의 핵심 키워드 추출
            expected_keywords = set(re.findall(r'\b\w{4,}\b', expected_answer.lower()))
            actual_keywords = set(re.findall(r'\b\w{4,}\b', actual_answer.lower()))
            
            # 키워드 겹침 비율 계산
            if expected_keywords:
                overlap_ratio = len(expected_keywords & actual_keywords) / len(expected_keywords)
                
                # 의미적으로 완전히 다른 경우 (매출, OLED 등 잘못된 키워드)
                wrong_keywords = ["매출", "채널", "온라인", "오프라인", "분기", "억원"]
                has_wrong_keywords = any(kw in actual_answer.lower() for kw in wrong_keywords)
                
                if has_wrong_keywords and len(expected_pdf_files) > 0:
                    analysis["pdf_quality"]["semantically_wrong"] += 1
                    if idx not in [i["index"] for i in analysis["pdf_quality"]["issues"]]:
                        analysis["pdf_quality"]["issues"].append({
                            "index": idx,
                            "question": question[:80] + "..." if len(question) > 80 else question,
                            "issue_type": "semantically_wrong",
                            "expected_keywords": list(expected_keywords)[:5],
                            "actual_keywords": list(actual_keywords)[:5]
                        })
                elif overlap_ratio > 0.3:
                    analysis["pdf_quality"]["semantically_correct"] += 1
    
    # PPTX 결과 분석
    print("📊 PPTX 결과 분석 중...")
    for idx, result in enumerate(pptx_results, 1):
        question = result.get("question", "")
        actual_sources = result.get("actual_sources", [])
        expected_answer = result.get("expected_answer", "")
        actual_answer = result.get("actual_answer", "")
        
        actual_has_pptx = any("pptx" in s.get("file_name", "").lower() for s in actual_sources)
        actual_has_pdf = any("pdf" in s.get("file_name", "").lower() for s in actual_sources)
        
        if actual_has_pptx and not actual_has_pdf:
            analysis["pptx_quality"]["correct_document_type"] += 1
        elif actual_has_pdf and not actual_has_pptx:
            analysis["pptx_quality"]["wrong_document_type"] += 1
            analysis["pptx_quality"]["issues"].append({
                "index": idx,
                "question": question[:80] + "..." if len(question) > 80 else question,
                "actual_pdf": [s.get("file_name", "") for s in actual_sources if "pdf" in s.get("file_name", "").lower()][:3],
                "issue_type": "wrong_document_type"
            })
        elif actual_has_pptx and actual_has_pdf:
            analysis["pptx_quality"]["mixed_document_type"] += 1
        
        # 의미적 일치도 평가
        if expected_answer and actual_answer:
            expected_keywords = set(re.findall(r'\b\w{4,}\b', expected_answer.lower()))
            actual_keywords = set(re.findall(r'\b\w{4,}\b', actual_answer.lower()))
            
            if expected_keywords:
                overlap_ratio = len(expected_keywords & actual_keywords) / len(expected_keywords)
                
                if overlap_ratio > 0.3:
                    analysis["pptx_quality"]["semantically_correct"] += 1
                else:
                    analysis["pptx_quality"]["semantically_wrong"] += 1
    
    return analysis


def print_analysis_report(analysis: Dict[str, Any]):
    """분석 결과 리포트 출력"""
    
    print("\n" + "="*80)
    print("📊 의미적 품질 분석 결과")
    print("="*80)
    
    # PDF 품질
    pdf_q = analysis["pdf_quality"]
    print(f"\n📄 PDF 문서 질문 분석:")
    print(f"  총 질문 수: {pdf_q['total']}")
    print(f"  ✅ 올바른 문서 타입 검색: {pdf_q['correct_document_type']} ({pdf_q['correct_document_type']/pdf_q['total']*100:.1f}%)")
    print(f"  ❌ 잘못된 문서 타입 검색: {pdf_q['wrong_document_type']} ({pdf_q['wrong_document_type']/pdf_q['total']*100:.1f}%)")
    print(f"  ⚠️  혼합 문서 타입 검색: {pdf_q['mixed_document_type']} ({pdf_q['mixed_document_type']/pdf_q['total']*100:.1f}%)")
    print(f"  ✅ 의미적으로 정확: {pdf_q['semantically_correct']}")
    print(f"  ❌ 의미적으로 잘못: {pdf_q['semantically_wrong']}")
    
    if pdf_q['issues']:
        print(f"\n  ⚠️  문제 사례 ({len(pdf_q['issues'])}개):")
        for issue in pdf_q['issues'][:10]:  # 상위 10개만
            print(f"\n    [{issue['index']}] {issue.get('issue_type', 'unknown')}")
            print(f"        질문: {issue.get('question', '')}")
            if issue.get('expected_pdf'):
                print(f"        예상: {issue['expected_pdf']}")
            if issue.get('actual_pptx'):
                print(f"        실제(PPTX): {issue['actual_pptx']}")
            if issue.get('actual_pdf'):
                print(f"        실제(PDF): {issue['actual_pdf']}")
    
    # PPTX 품질
    pptx_q = analysis["pptx_quality"]
    print(f"\n📊 PPTX 문서 질문 분석:")
    print(f"  총 질문 수: {pptx_q['total']}")
    print(f"  ✅ 올바른 문서 타입 검색: {pptx_q['correct_document_type']} ({pptx_q['correct_document_type']/pptx_q['total']*100:.1f}%)")
    print(f"  ❌ 잘못된 문서 타입 검색: {pptx_q['wrong_document_type']} ({pptx_q['wrong_document_type']/pptx_q['total']*100:.1f}%)")
    print(f"  ⚠️  혼합 문서 타입 검색: {pptx_q['mixed_document_type']} ({pptx_q['mixed_document_type']/pptx_q['total']*100:.1f}%)")
    print(f"  ✅ 의미적으로 정확: {pptx_q['semantically_correct']}")
    print(f"  ❌ 의미적으로 잘못: {pptx_q['semantically_wrong']}")
    
    if pptx_q['issues']:
        print(f"\n  ⚠️  문제 사례 ({len(pptx_q['issues'])}개):")
        for issue in pptx_q['issues'][:5]:
            print(f"\n    [{issue['index']}] {issue.get('issue_type', 'unknown')}")
            print(f"        질문: {issue.get('question', '')}")
            if issue.get('actual_pdf'):
                print(f"        실제(PDF): {issue['actual_pdf']}")
    
    # 전체 요약
    print(f"\n" + "="*80)
    print("📈 전체 요약")
    print("="*80)
    
    total_questions = pdf_q['total'] + pptx_q['total']
    total_correct_type = pdf_q['correct_document_type'] + pptx_q['correct_document_type']
    total_wrong_type = pdf_q['wrong_document_type'] + pptx_q['wrong_document_type']
    
    print(f"  총 질문 수: {total_questions}")
    print(f"  올바른 문서 타입 검색률: {total_correct_type/total_questions*100:.1f}%")
    print(f"  잘못된 문서 타입 검색률: {total_wrong_type/total_questions*100:.1f}%")
    print(f"  총 문제 사례: {len(pdf_q['issues']) + len(pptx_q['issues'])}개")


if __name__ == "__main__":
    results_file = "test_results/test_results_20251105_013634.json"
    
    if not Path(results_file).exists():
        print(f"❌ 결과 파일을 찾을 수 없습니다: {results_file}")
    else:
        analysis = analyze_semantic_quality(results_file)
        print_analysis_report(analysis)
        
        # JSON으로도 저장
        output_file = "test_results/semantic_analysis.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"\n✅ 분석 결과 저장: {output_file}")









