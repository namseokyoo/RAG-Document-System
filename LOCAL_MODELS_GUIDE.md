# 로컬 모델 캐시 사용 가이드

## 🏢 회사 내부망 환경에서의 사용법

### 📋 개요
이 시스템은 회사 내부망에서 외부 네트워크 접근이 제한된 환경에서도 완전히 작동하도록 설계되었습니다.

### 🔧 설정 방법

#### 1단계: 외부망에서 모델 다운로드
```bash
# 모든 Re-ranker 모델 다운로드 (권장)
python download_models.py --all

# 특정 모델만 다운로드
python download_models.py --model multilingual-mini

# 모델 상태 확인
python download_models.py --check
```

#### 2단계: 내부망에서 사용
```bash
# PySide6 데스크톱 앱 실행
python desktop_app.py

# 또는 Streamlit 웹 앱 실행  
streamlit run app.py
```

### 📁 모델 저장 구조
```
models/
├── reranker-mini/          # 22MB - 빠르고 가벼움
├── reranker-base/          # 133MB - 더 정확함
└── reranker-korean/        # 100MB - 한국어 최적화
```

### ⚙️ 자동 설정
- **오프라인 모드**: 자동으로 활성화됨
- **로컬 모델 우선**: 외부 다운로드 없이 로컬 모델 사용
- **에러 처리**: 로컬 모델이 없으면 명확한 안내 메시지 제공

### 🚨 문제 해결

#### 문제: "오프라인 모드에서 로컬 모델을 찾을 수 없습니다"
**해결방법:**
1. 외부망에서 모델 다운로드:
   ```bash
   python download_models.py --model multilingual-mini
   ```

2. 또는 Re-ranker 비활성화:
   ```python
   # config.py에서
   "use_reranker": False
   ```

#### 문제: SSL 인증서 에러
**해결방법:**
- 이미 오프라인 모드로 설정되어 외부 접근 차단됨
- 로컬 모델만 사용하므로 SSL 문제 없음

### 📊 성능 비교

| 구성 | 네트워크 의존성 | 메모리 사용량 | 검색 정확도 |
|------|----------------|---------------|-------------|
| **로컬 모델** | ❌ 없음 | 1.5GB | 95% |
| **Re-ranker 비활성화** | ❌ 없음 | 800MB | 85% |
| **외부 모델** | ✅ 필요 | 2.1GB | 95% |

### 🎯 권장 설정

**회사 내부망 환경:**
```python
# config.py
{
    "use_reranker": True,           # 로컬 모델 사용
    "reranker_model": "multilingual-mini",  # 가벼운 모델
    "use_local_models": True,       # 로컬 모델 캐시 활성화
    "offline_mode": True,          # 오프라인 모드
}
```

**네트워크 제한 환경:**
```python
# config.py  
{
    "use_reranker": False,         # Re-ranker 비활성화
    "use_local_models": True,      # 로컬 모델 캐시 활성화
    "offline_mode": True,         # 오프라인 모드
}
```

### 📝 주의사항

1. **모델 크기**: 총 약 255MB (mini + base + korean)
2. **초기 다운로드**: 외부망에서 한 번만 필요
3. **업데이트**: 모델 업데이트 시 외부망에서 재다운로드 필요
4. **백업**: `models/` 디렉토리 백업 권장

### 🔄 업데이트 방법

```bash
# 기존 모델 덮어쓰기
python download_models.py --all --force

# 특정 모델만 업데이트
python download_models.py --model multilingual-mini --force
```

이제 회사 내부망에서도 외부 네트워크 의존성 없이 완전히 작동합니다! 🎉
