import json
import glob
import os
import sys

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 모든 테스트 로그 읽기
log_files = glob.glob('test_logs_diversity_day2_comprehensive/*.json')
results = []

for log_file in sorted(log_files):
    with open(log_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        results.append({
            'test_id': data.get('test_id', ''),
            'classification': data.get('classification', {}).get('type', ''),
            'success': data.get('error') is None,
            'error': data.get('error', ''),
            'total_time': data.get('total', {}).get('elapsed_time', 0),
            'sources_count': data.get('citation', {}).get('sources_count', 0),
            'llm_calls': data.get('total', {}).get('llm_calls', 0),
            'reranking': data.get('reranking', {})
        })

# 통계 계산
total_tests = len(results)
success_tests = sum(1 for r in results if r['success'])
failed_tests = [r for r in results if not r['success']]
total_time = sum(r['total_time'] for r in results)
avg_time = total_time / total_tests if total_tests > 0 else 0
avg_sources = sum(r['sources_count'] for r in results) / total_tests if total_tests > 0 else 0

print('=' * 60)
print('Comprehensive Test 완료 결과')
print('=' * 60)
print(f'\n총 테스트: {total_tests}개')
print(f'성공: {success_tests}개 ({success_tests/total_tests*100:.1f}%)')
print(f'실패: {len(failed_tests)}개')
print(f'\n총 소요시간: {total_time:.1f}초 ({total_time/60:.1f}분)')
print(f'평균 소요시간: {avg_time:.1f}초/테스트')
print(f'평균 출처 개수: {avg_sources:.1f}개')

print(f'\n테스트 분류:')
for classification in ['simple', 'normal', 'exhaustive', 'conversation']:
    count = sum(1 for r in results if r['classification'] == classification)
    if count > 0:
        print(f'  {classification}: {count}개')

# Reranking 정보 확인
rerank_enabled = sum(1 for r in results if r.get('reranking', {}).get('enabled', False))
print(f'\nReranking 사용: {rerank_enabled}/{total_tests}개')

# 실패한 테스트 상세
if failed_tests:
    print(f'\n실패한 테스트:')
    for result in failed_tests:
        print(f'  - {result["test_id"]}: {result["error"][:100] if result["error"] else "Unknown error"}')

# 성공한 테스트 목록
print(f'\n성공한 테스트 ({len([r for r in results if r["success"]])}개):')
for result in results:
    if result['success']:
        print(f'  OK {result["test_id"]} ({result["classification"]}, {result["total_time"]:.1f}s)')
