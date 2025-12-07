"""Quick Syntax Check - Using AST"""
import ast
import sys

def check_syntax(filepath):
    """Check Python syntax of file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code, filename=filepath)
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

files_to_check = [
    ('utils/pdf_chunking_engine.py', 'PDF Chunking Engine'),
    ('utils/document_processor.py', 'Document Processor'),
    ('ui/document_widget.py', 'Document Widget'),
]

print("=" * 70)
print("Upload Stability Improvement - Syntax Check")
print("=" * 70)

all_ok = True
for filepath, name in files_to_check:
    ok, error = check_syntax(filepath)
    if ok:
        print(f"[OK] {name:30s} ({filepath})")
    else:
        print(f"[FAIL] {name:30s} ({filepath})")
        print(f"  Error: {error}")
        all_ok = False

print("=" * 70)

if all_ok:
    print("[PASS] All files passed syntax check!")
    print("\nNext: Summary of Changes")
    print("-" * 70)

    # Summary of major changes
    changes = [
        ("Exception Classes", "CancelledException, PartialUploadException"),
        ("time module import", "pdf_chunking_engine.py line 15"),
        ("Callback params", "cancel_callback, progress_callback added to all layers"),
        ("Retry logic", "MAX_RETRIES=3, exponential backoff (2s, 4s, 8s)"),
        ("Timeout tuple", "timeout=(10, 60) - connect 10s, read 60s"),
        ("Cancel mechanism", "Check before each page & during retry"),
        ("Full rollback", "PartialUploadException triggers complete rollback"),
    ]

    print("\nKey Changes:")
    for i, (title, desc) in enumerate(changes, 1):
        print(f"  {i}. {title:20s} - {desc}")

    print("\n" + "=" * 70)
    sys.exit(0)
else:
    print("[FAIL] Syntax errors found - fix required")
    sys.exit(1)
