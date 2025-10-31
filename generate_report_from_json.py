"""JSON 결과에서 리포트 재생성"""
import json
import sys
import os
from test_rag_comprehensive_analysis import generate_markdown_report, ComprehensiveTestResult

# 간단한 JSON -> 객체 변환 (필요한 필드만)
def load_result_from_json(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # ComprehensiveTestResult 생성 (간단화)
    result = ComprehensiveTestResult(
        test_date=data.get('test_date', ''),
        test_config=data.get('test_config', {}),
        total_questions=data.get('total_questions', 0),
        success_rate=data.get('success_rate', 0.0),
        avg_total_time=data.get('avg_total_time', 0.0),
        avg_confidence=data.get('avg_confidence', 0.0),
        avg_source_count=data.get('avg_source_count', 0.0),
        avg_embedding_time=data.get('avg_embedding_time', 0.0),
        avg_retrieval_time=data.get('avg_retrieval_time', 0.0),
        avg_reranking_time=data.get('avg_reranking_time', 0.0),
        avg_context_time=data.get('avg_context_time', 0.0),
        avg_generation_time=data.get('avg_generation_time', 0.0),
        avg_top_k_accuracy=data.get('avg_top_k_accuracy', 0.0),
        avg_recall_at_k=data.get('avg_recall_at_k', 0.0),
        avg_precision_at_k=data.get('avg_precision_at_k', 0.0),
        avg_rank_improvement=data.get('avg_rank_improvement', 0.0),
        avg_relevant_doc_ratio=data.get('avg_relevant_doc_ratio', 0.0),
        avg_context_length=data.get('avg_context_length', 0),
        avg_relevance_score=data.get('avg_relevance_score', 0.0),
        avg_accuracy_score=data.get('avg_accuracy_score', 0.0),
        avg_completeness_score=data.get('avg_completeness_score', 0.0),
        question_results=[],  # 빈 리스트 (상세는 JSON 참조)
        bottleneck_analysis=data.get('bottleneck_analysis', {}),
        embedding_quality_analysis=data.get('embedding_quality_analysis', {})
    )
    
    return result, data

if __name__ == "__main__":
    json_path = "test_reports/comprehensive_analysis_20251030_085648.json"
    
    if not os.path.exists(json_path):
        print(f"파일을 찾을 수 없습니다: {json_path}")
        sys.exit(1)
    
    result, full_data = load_result_from_json(json_path)
    
    # 리포트 생성
    report = generate_markdown_report(result)
    
    # 리포트 저장
    md_path = json_path.replace('.json', '.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 리포트 생성 완료: {md_path}")
    
    # 요약 출력
    print("\n" + "=" * 80)
    print("테스트 결과 요약")
    print("=" * 80)
    print(f"테스트 일시: {result.test_date}")
    print(f"질문 수: {result.total_questions}개")
    print(f"성공률: {result.success_rate:.1%}")
    print(f"평균 응답 시간: {result.avg_total_time:.2f}초")
    print(f"병목 지점: {result.bottleneck_analysis.get('slowest_stage', 'N/A')}")
    print("=" * 80)
    print(f"\n⚠️ 참고: Ollama 임베딩 모델 로딩 오류로 인해 모든 테스트가 실패했습니다.")
    print("   Ollama 서비스 상태를 확인하거나 다른 임베딩 모델 사용을 고려해주세요.")
    print("=" * 80)

