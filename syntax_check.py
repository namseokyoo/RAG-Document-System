"""구문 체크 스크립트"""
import py_compile
import sys

files_to_check = [
    'utils/pdf_chunking_engine.py',
    'utils/document_processor.py',
    'ui/document_widget.py',
]

print("=" * 60)
print("구문 체크 시작")
print("=" * 60)

all_ok = True
for filepath in files_to_check:
    try:
        py_compile.compile(filepath, doraise=True)
        print(f"✓ {filepath} - OK")
    except py_compile.PyCompileError as e:
        print(f"✗ {filepath} - FAILED")
        print(f"  오류: {e}")
        all_ok = False

print("=" * 60)
if all_ok:
    print("✅ 모든 파일 구문 체크 통과!")
else:
    print("❌ 구문 오류 발견")
    sys.exit(1)
