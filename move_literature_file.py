"""현진건 소설 파일을 아카이브로 이동"""
import os
import shutil

source = "data/embedded_documents/현진건-운수좋은날+B3356-개벽.pdf"
dest_dir = "data/embedded_documents_archive"
dest = os.path.join(dest_dir, "현진건-운수좋은날+B3356-개벽.pdf")

if os.path.exists(source):
    os.makedirs(dest_dir, exist_ok=True)
    shutil.move(source, dest)
    print(f"[OK] 파일 이동 완료: {source} -> {dest}")
else:
    print(f"[INFO] 파일이 이미 이동되었거나 존재하지 않음: {source}")
