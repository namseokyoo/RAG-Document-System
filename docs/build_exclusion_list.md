# 빌드 제외 파일 목록 (v0.7.1)

**작성일**: 2025-12-07  
**목적**: PyInstaller 빌드에서 불필요한 파일 제외 설정

---

## 📋 제외 원칙

PyInstaller는 `desktop_app.py`만 진입점으로 사용하므로, 다른 Python 파일들은 자동으로 제외됩니다. 하지만 명확성을 위해 제외 목록을 문서화합니다.

---

## 🚫 제외된 파일/폴더

### 1. 테스트 파일 (자동 제외)
- `tests/` - 모든 테스트 및 분석 스크립트 (122개 파일)
- `analyze_*.py` - 분석 스크립트
- `diagnose_*.py` - 진단 스크립트
- `check_*.py` - 체크 스크립트
- `verify_*.py` - 검증 스크립트
- `quick_*.py` - 빠른 테스트 스크립트
- `create_*.py` - 생성 스크립트
- `download_*.py` - 다운로드 스크립트
- `fix_*.py` - 수정 스크립트
- `reset_*.py` - 리셋 스크립트
- `re_embed_*.py` - 재임베딩 스크립트
- `comprehensive_test.py`
- `run_comprehensive_test_real.py`
- `syntax_check.py`
- `update_vision_config.py`

### 2. 스크립트 폴더 (자동 제외)
- `scripts/` - 유틸리티 스크립트 (8개 파일)

### 3. 로그 폴더 (datas에 미포함)
- `logs/` - 모든 로그 및 산출물 (75개 파일)
  - `logs/commits/` - 커밋 메시지
  - `logs/build/` - 빌드 로그 및 spec 파일
  - `logs/test/` - 테스트 출력

### 4. 런타임 생성 데이터 폴더 (datas에 미포함)
- `chroma_db/` - ChromaDB 벡터 저장소 (런타임 생성)
- `chat_history/` - 대화 이력 (런타임 생성)
- `data/test_*` - 테스트 데이터
- `test_logs/` - 테스트 로그
- `test_results/` - 테스트 결과
- `build/` - 빌드 산출물
- `dist/` - 배포 산출물
- `venv/` - 가상환경

### 5. 개발 문서 (datas에 미포함)
- `docs/` - 개발 문서 폴더 전체
- `*.md` - 마크다운 문서 (README.md 제외, 하지만 datas에 포함하지 않으므로 제외됨)

### 5. 기타 빌드 산출물
- `*.spec` - PyInstaller spec 파일들 (빌드 설정 파일)
- `*.log` - 로그 파일
- `*.txt` - 텍스트 로그/출력 파일
- `*.csv` - CSV 데이터 파일

---

## ✅ 포함된 파일/폴더

### 필수 실행 파일
- `desktop_app.py` - 메인 진입점

### 필수 모듈
- `config.py` - 설정 관리
- `utils/` - 핵심 로직 (모든 파일)
- `ui/` - UI 컴포넌트 (모든 파일)

### 필수 리소스 (datas에 명시적으로 포함)
- `resources/` - 아이콘 등 리소스 파일
- `config.json.example` - 설정 예제
- `models/` - Re-ranker 모델

---

## 🔧 PyInstaller 설정

### OC.spec 파일 설정

```python
# 진입점: desktop_app.py만 포함
a = Analysis(
    ['desktop_app.py'],  # 테스트 파일 자동 제외
    ...
    datas=[
        ('resources', 'resources'),  # 필수 리소스만 포함
        ('config.json.example', '.'),
        ('models', 'models'),
        # 런타임 생성 폴더, 테스트 데이터, 개발 문서는 포함하지 않음
    ],
    ...
)
```

### 자동 제외 메커니즘

1. **Python 파일**: `desktop_app.py`만 진입점이므로 다른 .py 파일은 자동 제외
2. **데이터 파일**: `datas`에 명시적으로 추가하지 않으면 제외
3. **모듈**: `excludes` 리스트에 명시된 모듈 제외

---

## 📊 빌드 크기 최적화 효과

### 제외 전 (예상)
- 테스트 파일: ~100개 파일
- 개발 문서: ~50개 파일
- 테스트 데이터: 수백 MB
- **총 예상 크기**: 1.5GB+

### 제외 후 (실제)
- 필수 실행 파일만 포함
- **총 실제 크기**: ~1GB (torch, transformers 등 포함)

### 절감 효과
- **약 500MB+ 절감** (테스트 파일, 문서, 데이터 제외)

---

## ⚠️ 주의사항

1. **런타임 생성 폴더**: `chroma_db/`, `chat_history/`는 런타임에 생성되므로 빌드에 포함하지 않음
2. **설정 파일**: `config.json`은 사용자가 생성해야 하므로 `config.json.example`만 포함
3. **모델 파일**: `models/` 폴더의 Re-ranker 모델은 포함 (필수)
4. **리소스 파일**: `resources/` 폴더의 아이콘 등은 포함 (필수)

---

## 🔄 업데이트 이력

- **2025-12-07**: v0.7.1 빌드 최적화 - 테스트 파일, 런타임 데이터, 개발 문서 제외 설정

---

**참고**: 이 문서는 빌드 설정을 문서화한 것입니다. 실제 파일은 삭제되지 않으며, 빌드 시에만 제외됩니다.

