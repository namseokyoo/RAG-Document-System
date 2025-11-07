"""키워드 필터링 코드 자동 제거"""
import re

# 원본 파일 읽기
with open("utils/rag_chain.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"원본 파일: {len(lines)} 라인")

# 제거할 메서드 범위 (0-based index)
methods_to_remove = [
    (914, 951),  # _detect_query_domain (line 915-951)
    (952, 993),  # _filter_documents_by_domain (line 953-993)
    (994, 1040), # _filter_negative_documents (line 995-1040)
]

# 제거 표시
remove_lines = set()
for start, end in methods_to_remove:
    for i in range(start, end + 1):
        remove_lines.add(i)

# 메서드 제거
new_lines = []
for i, line in enumerate(lines):
    if i not in remove_lines:
        new_lines.append(line)

print(f"메서드 제거 후: {len(new_lines)} 라인 ({len(remove_lines)}줄 제거)")

# 메서드 호출 제거 (라인 단위)
patterns_to_remove = [
    r'\s*domain\s*=\s*self\._detect_query_domain\([^)]+\)',
    r'\s*weighted_results\s*=\s*self\._filter_documents_by_domain\([^)]+\)',
    r'\s*weighted_results\s*=\s*self\._filter_negative_documents\([^)]+\)',
    r'\s*base_filtered\s*=\s*self\._filter_documents_by_domain\([^)]+\)',
    r'\s*base_filtered\s*=\s*self\._filter_negative_documents\([^)]+\)',
    r'\s*results\s*=\s*self\._filter_documents_by_domain\([^)]+\)',
    r'\s*results\s*=\s*self\._filter_negative_documents\([^)]+\)',
    r'\s*all_retrieved_chunks\s*=\s*self\._filter_documents_by_domain\([^)]+\)',
    r'\s*all_retrieved_chunks\s*=\s*self\._filter_negative_documents\([^)]+\)',
    r'\s*pairs\s*=\s*self\._filter_documents_by_domain\([^)]+\)',
    r'\s*pairs\s*=\s*self\._filter_negative_documents\([^)]+\)',
]

# 호출 제거
final_lines = []
removed_calls = 0
for line in new_lines:
    should_remove = False
    for pattern in patterns_to_remove:
        if re.match(pattern, line):
            should_remove = True
            removed_calls += 1
            break

    if not should_remove:
        final_lines.append(line)

print(f"메서드 호출 제거 후: {len(final_lines)} 라인 ({removed_calls}개 호출 제거)")

# 백업 생성
with open("utils/rag_chain.py.backup", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("[OK] 백업 생성: utils/rag_chain.py.backup")

# 새 파일 저장
with open("utils/rag_chain.py", "w", encoding="utf-8") as f:
    f.writelines(final_lines)

print("[OK] 수정 완료: utils/rag_chain.py")
print(f"[SUMMARY] 총 {len(lines) - len(final_lines)}줄 제거됨")
