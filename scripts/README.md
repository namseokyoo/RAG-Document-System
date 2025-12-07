# 스크립트 폴더

**생성일**: 2025-12-07  
**목적**: 메인 프로그램과 분리된 유틸리티 스크립트 관리

---

## 📋 포함된 스크립트

### 데이터 관리
- `download_oled_papers.py` - 논문 다운로드 스크립트
- `download_models.py` - 모델 다운로드 스크립트
- `download_and_embed_multiple_pdfs.py` - 여러 PDF 다운로드 및 임베딩

### 데이터베이스 관리
- `delete_literature_chunks.py` - 문헌 청크 삭제
- `move_literature_file.py` - 문헌 파일 이동
- `remove_keyword_filtering.py` - 키워드 필터링 제거
- `rename_chromadb.py` - ChromaDB 이름 변경
- `find_large_page_numbers.py` - 큰 페이지 번호 찾기

---

## 🔧 사용 방법

각 스크립트는 독립적으로 실행 가능합니다. 필요 시 직접 실행하거나 다른 스크립트에서 import하여 사용할 수 있습니다.

---

## ⚠️ 주의사항

- 이 스크립트들은 메인 프로그램(`desktop_app.py`)과 분리되어 있습니다.
- 빌드 시 자동으로 제외됩니다.
- 프로젝트 루트에서 실행할 때는 경로를 확인하세요.

