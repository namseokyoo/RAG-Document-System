#!/usr/bin/env python3
"""진행 상황 체크"""
import re

with open('regression_test_day3_v2_result.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# [N/41] 패턴 찾기
tests = [l for l in lines if re.match(r'^\[(\d+)/41\]', l)]

print(f"진행: {len(tests)}/41 테스트 완료")
if tests:
    last = tests[-1]
    match = re.search(r'\[(\d+)/41\] (\S+)', last)
    if match:
        print(f"마지막 테스트: {match.group(1)}/41 - {match.group(2)}")

# 완료 여부 확인
if "테스트 결과 분석" in ''.join(lines[-50:]):
    print("\n✅ 테스트 완료!")
elif "회귀 테스트 완료" in ''.join(lines[-50:]):
    print("\n✅ 테스트 완료!")
else:
    print("\n⏳ 테스트 진행 중...")
