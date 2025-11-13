import json
import glob
import os
import sys
from datetime import datetime
from collections import Counter

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 모든 테스트 로그 읽기
log_files = glob.glob('test_logs_diversity_day2_comprehensive/*.json')
results = []

print(f"발견된 로그 파일: {len(log_files)}개")

for log_file in sorted(log_files):
    with open(log_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

        # Citation에서 출처 정보 추출
        sources = data.get('citation', {}).get('sources', [])
        unique_sources = list(set([s.get('file_name', 'unknown') for s in sources]))

        # Reranking 정보
        reranking = data.get('reranking', {})

        results.append({
            'test_id': data.get('test_id', ''),
            'question': data.get('question', ''),
            'classification': data.get('classification', {}).get('type', ''),
            'success': data.get('error') is None,
            'error': data.get('error', None),
            'total_time': data.get('total', {}).get('elapsed_time', 0),
            'llm_calls': data.get('total', {}).get('llm_calls', 0),
            'sources_count': len(sources),
            'unique_sources_count': len(unique_sources),
            'unique_sources': unique_sources,
            'reranking_enabled': reranking.get('enabled', False),
            'reranking_input_docs': reranking.get('input_docs', 0),
            'reranking_output_docs': reranking.get('output_docs', 0),
            'answer_preview': data.get('answer', '')[:200] if data.get('answer') else ''
        })

# 통계 계산
total_tests = len(results)
success_tests = sum(1 for r in results if r['success'])
failed_tests = [r for r in results if not r['success']]
total_time = sum(r['total_time'] for r in results)
avg_time = total_time / total_tests if total_tests > 0 else 0

# Diversity 관련 통계
total_sources = sum(r['sources_count'] for r in results if r['success'])
total_unique_sources = sum(r['unique_sources_count'] for r in results if r['success'])
avg_sources = total_sources / success_tests if success_tests > 0 else 0
avg_unique_sources = total_unique_sources / success_tests if success_tests > 0 else 0

# 다중 문서 사용률 (unique sources >= 2)
multi_doc_tests = sum(1 for r in results if r['success'] and r['unique_sources_count'] >= 2)
multi_doc_ratio = multi_doc_tests / success_tests if success_tests > 0 else 0

# Diversity ratio (unique / total)
diversity_ratio = avg_unique_sources / avg_sources if avg_sources > 0 else 0

# Classification 분포
classification_counts = {}
for r in results:
    cls = r['classification']
    classification_counts[cls] = classification_counts.get(cls, 0) + 1

# Summary 객체 생성
summary = {
    'metadata': {
        'generated_at': datetime.now().isoformat(),
        'config_file': 'config_test.json',
        'test_cases_file': 'test_cases_comprehensive_v2.json',
        'output_dir': 'test_logs_diversity_day2_comprehensive',
        'diversity_penalty': 0.3,
        'diversity_source_key': 'source'
    },
    'statistics': {
        'total_tests': total_tests,
        'successful_tests': success_tests,
        'failed_tests': len(failed_tests),
        'success_rate': success_tests / total_tests if total_tests > 0 else 0,
        'total_time_seconds': total_time,
        'total_time_minutes': total_time / 60,
        'avg_time_per_test': avg_time,
        'classification_distribution': classification_counts
    },
    'diversity_metrics': {
        'avg_total_sources': avg_sources,
        'avg_unique_sources': avg_unique_sources,
        'diversity_ratio': diversity_ratio,
        'multi_doc_tests': multi_doc_tests,
        'multi_doc_ratio': multi_doc_ratio,
        'description': 'Metrics for measuring document diversity with penalty=0.3'
    },
    'reranking_stats': {
        'enabled_count': sum(1 for r in results if r['reranking_enabled']),
        'avg_input_docs': sum(r['reranking_input_docs'] for r in results) / total_tests if total_tests > 0 else 0,
        'avg_output_docs': sum(r['reranking_output_docs'] for r in results) / total_tests if total_tests > 0 else 0
    },
    'failed_tests': [
        {
            'test_id': r['test_id'],
            'question': r['question'],
            'error': r['error']
        }
        for r in failed_tests
    ],
    'detailed_results': results
}

# JSON 파일로 저장
output_file = 'test_summary_diversity_day2_comprehensive.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n✓ Summary 파일 생성 완료: {output_file}")
print(f"\n주요 통계:")
print(f"  - 총 테스트: {total_tests}개")
print(f"  - 성공: {success_tests}개 ({success_tests/total_tests*100:.1f}%)")
print(f"  - 평균 출처: {avg_sources:.2f}개")
print(f"  - 평균 고유 출처: {avg_unique_sources:.2f}개")
print(f"  - Diversity ratio: {diversity_ratio*100:.1f}%")
print(f"  - Multi-doc ratio: {multi_doc_ratio*100:.1f}%")
