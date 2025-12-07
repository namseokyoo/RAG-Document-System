# 로그 및 산출물 폴더

**생성일**: 2025-12-07  
**목적**: 빌드 로그, 커밋 메시지, 테스트 출력 등 프로젝트 산출물 정리

---

## 📁 폴더 구조

```
logs/
├── commits/     # 커밋 메시지 파일들
├── build/       # 빌드 로그 및 spec 파일들
└── test/        # 테스트 출력 파일들
```

---

## 📋 각 폴더 설명

### commits/
커밋 메시지 템플릿 및 기록 파일들
- `commit_msg_*.txt` - 버전별 커밋 메시지
- `commit_message_*.txt` - 특정 기능 커밋 메시지

### build/
빌드 관련 로그 및 설정 파일들
- `build_log_*.txt` - 빌드 로그 파일
- `build_*.log` - 빌드 로그 (로그 형식)
- `build_error.txt` - 빌드 에러 로그
- `build_output*.txt` - 빌드 출력 파일
- `*.spec` - PyInstaller spec 파일 (OC.spec 제외)
- `*.zip` - 빌드 산출물 압축 파일

### test/
테스트 실행 결과 및 출력 파일들
- `*_test_output.txt` - 테스트 출력 파일
- `*_test_FINAL.txt` - 최종 테스트 결과
- `phase3_*.txt` - Phase 3 테스트 출력
- `vision_*.txt` - Vision 테스트 출력
- `table_matching_*.txt` - 테이블 매칭 테스트 출력
- `session_integration_*.txt` - 세션 통합 테스트 출력
- `regression_test_output.txt` - 회귀 테스트 출력
- `startup_log.txt` - 시작 로그

---

## 🔧 유지보수

이 폴더의 파일들은 프로젝트 실행에 필수적이지 않으며, 필요 시 삭제해도 됩니다.
빌드 시 자동으로 제외됩니다.

