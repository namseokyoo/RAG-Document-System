# 테스트 폴더

**생성일**: 2025-12-07  
**목적**: 모든 테스트 및 분석 스크립트 통합 관리

---

## 📋 포함된 파일 유형

### 테스트 파일
- `test_*.py` - 모든 테스트 스크립트

### 분석 스크립트
- `analyze_*.py` - 분석 스크립트
- `diagnose_*.py` - 진단 스크립트
- `check_*.py` - 체크 스크립트
- `verify_*.py` - 검증 스크립트

### 유틸리티 스크립트
- `quick_*.py` - 빠른 테스트/체크 스크립트
- `create_*.py` - 테스트 데이터 생성 스크립트
- `fix_*.py` - 수정 스크립트
- `reset_*.py` - 리셋 스크립트
- `re_embed_*.py` - 재임베딩 스크립트

### 통합 테스트
- `comprehensive_test.py` - 종합 테스트
- `run_comprehensive_test_real.py` - 실제 환경 종합 테스트
- `syntax_check.py` - 구문 체크
- `update_vision_config.py` - Vision 설정 업데이트
- `simple_bug_check.py` - 간단한 버그 체크
- `clean_and_rebuild.py` - 정리 및 재빌드
- `rebuild_test_db.py` - 테스트 DB 재구축
- `rebuild_db_with_1500.py` - 1500 청크로 DB 재구축

---

## 🔧 사용 방법

각 테스트는 독립적으로 실행 가능합니다:

```bash
# 예시
python tests/test_keyword_search.py
python tests/analyze_embedding.py
```

### PPTX 고급 청킹 재청킹 전/후 비교(스모크)

```bash
.\venv\Scripts\python.exe tests/compare_pptx_resplit_before_after.py
```

- **기본 동작**: `data/test_pptx`의 대표 PPTX를 대상으로, old(resplit) vs new(no-resplit) 비교 출력
- **외부 호출 방지**: 실행 중에만 설정을 임시 오버라이드하여 Vision/PPTX→PDF 변환을 비활성화(파일 수정 없음)
- **주요 옵션(환경변수)**:
  - `PPTX_FILES`: 비교할 파일명 목록(세미콜론 `;` 구분). 예: `chart_test.pptx;complex_06_mixed_structures.pptx`
  - `MAX_FILES`: 최대 몇 개 파일까지 실행할지 (기본 3)
  - `FORCE_RESPLIT_CHUNK_SIZE`: old(resplit) 경로의 강제 split chunk_size (기본 200)
  - `FORCE_RESPLIT_CHUNK_OVERLAP`: old(resplit) 경로의 overlap (기본 30)

---

## ⚠️ 주의사항

- 이 파일들은 메인 프로그램과 분리되어 있습니다.
- 빌드 시 자동으로 제외됩니다.
- 프로젝트 루트에서 실행할 때는 경로를 확인하세요.

