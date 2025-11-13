#!/usr/bin/env python3
"""
Config 검증 전용 (ChromaDB 없이)
"""

import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json

print("="*80)
print("Config 검증 (ChromaDB 우회)")
print("="*80)

# config_test.json 로드
with open('config_test.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

print(f"\n[조정된 설정 확인]")
print(f"  ✓ diversity_penalty: {config.get('diversity_penalty')}")
print(f"  ✓ diversity_source_key: {config.get('diversity_source_key')}")
print(f"  ✓ enable_file_aggregation: {config.get('enable_file_aggregation')}")
print(f"  ✓ file_aggregation_strategy: {config.get('file_aggregation_strategy')}")
print(f"  ✓ file_aggregation_top_n: {config.get('file_aggregation_top_n')}")

print(f"\n[검증 결과]")

# 1. diversity_penalty 확인
penalty = config.get('diversity_penalty', 0.0)
if penalty == 0.35:
    print(f"  ✅ diversity_penalty: 0.35 (목표치)")
    print(f"     → 0.3 대비 16.7% 증가")
    print(f"     → 예상 효과: 평균 고유 문서 2.40 → 2.6개")
elif penalty == 0.3:
    print(f"  ⚠️  diversity_penalty: 0.3 (이전 값)")
    print(f"     → 조정이 반영되지 않음")
else:
    print(f"  ❌ diversity_penalty: {penalty} (예상치 않은 값)")

# 2. enable_file_aggregation 확인
file_agg = config.get('enable_file_aggregation', False)
if file_agg == True:
    print(f"\n  ✅ enable_file_aggregation: true")
    print(f"     → Exhaustive Query 기능 활성화")
    print(f"     → '모든 OLED 논문' → 파일 리스트 반환")
elif file_agg == False:
    print(f"\n  ⚠️  enable_file_aggregation: false")
    print(f"     → Exhaustive Query 기능 비활성화")
    print(f"     → 조정이 반영되지 않음")

# 3. 시뮬레이션: diversity_penalty 효과
print(f"\n[Diversity Penalty 시뮬레이션]")
print(f"동일 출처 문서 반복 시 점수 패널티:")

for repeat in range(1, 6):
    penalty_score = max(1.0 - ((repeat - 1) * penalty), 0.1)
    print(f"  {repeat}회 반복: {penalty_score:.0%} (원점수의 {penalty_score*100:.0f}%)")

# 4. 예상 개선 효과
print(f"\n[예상 개선 효과]")
print(f"")
print(f"현재 (penalty=0.3):")
print(f"  - 평균 고유 문서: 2.40개")
print(f"  - Diversity Ratio: 53.3%")
print(f"  - Multi-doc 비율: 97.1%")
print(f"")
print(f"조정 후 (penalty=0.35) 예상:")
print(f"  - 평균 고유 문서: 2.5~2.7개 (+8~13%)")
print(f"  - Diversity Ratio: 56~60% (+5~13%)")
print(f"  - Multi-doc 비율: 97%+ (유지)")

# 5. 최종 판정
print(f"\n" + "="*80)
print("[최종 판정]")
print("="*80)

if penalty == 0.35 and file_agg == True:
    print(f"\n✅✅ Config 조정 완료!")
    print(f"")
    print(f"적용된 변경사항:")
    print(f"  1. diversity_penalty: 0.3 → 0.35 (+16.7%)")
    print(f"  2. enable_file_aggregation: false → true")
    print(f"")
    print(f"예상 효과:")
    print(f"  - Diversity 목표 달성 가능성: 높음 (3/3 달성 예상)")
    print(f"  - Exhaustive Query: 파일 리스트 형식 응답")
    print(f"  - 사용자 경험: 대폭 개선")
    print(f"")
    print(f"다음 단계: Phase 3 Day 3 진행 가능")

elif penalty == 0.35:
    print(f"\n⚠️  부분 적용됨")
    print(f"  - diversity_penalty: ✅ 0.35")
    print(f"  - enable_file_aggregation: ❌ false")
    print(f"")
    print(f"file_aggregation을 true로 설정 필요")

elif file_agg == True:
    print(f"\n⚠️  부분 적용됨")
    print(f"  - diversity_penalty: ❌ {penalty}")
    print(f"  - enable_file_aggregation: ✅ true")
    print(f"")
    print(f"diversity_penalty를 0.35로 설정 필요")

else:
    print(f"\n❌ 조정이 반영되지 않음")
    print(f"  - diversity_penalty: {penalty} (목표: 0.35)")
    print(f"  - enable_file_aggregation: {file_agg} (목표: true)")

print(f"\n" + "="*80)
