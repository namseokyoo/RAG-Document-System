import re
lines = open('regression_test_day3_v2_result.txt', 'r', encoding='utf-8').read()
tests = re.findall(r'^\[(\d+)/41\]', lines, re.MULTILINE)
print(f'{len(tests)}/41')
print('DONE' if 'regression_test_day3_' in lines and '.json' in lines[-500:] else 'RUNNING')
