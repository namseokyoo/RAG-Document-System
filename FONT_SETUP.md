# Pretendard 폰트 설정 가이드

프로그램 전체에 Pretendard 폰트를 적용하려면 폰트 파일을 다운로드하고 적절한 위치에 배치해야 합니다.

## 1. 폰트 다운로드

### 방법 1: GitHub Release에서 다운로드 (권장)

1. https://github.com/orioncactus/pretendard/releases 페이지 방문
2. 최신 릴리스에서 다음 중 하나를 다운로드:
   - **PretendardVariable.ttf** (권장) - Variable 폰트 (하나의 파일로 다양한 굵기 지원)
   - **Pretendard-1.3.9-static.zip** - Static 폰트 (여러 굵기 파일)

### 방법 2: 직접 다운로드 링크

Variable 폰트 (권장):
```
https://github.com/orioncactus/pretendard/releases/latest/download/PretendardVariable.ttf
```

Static 폰트:
```
https://github.com/orioncactus/pretendard/releases/latest/download/Pretendard-1.3.9-static.zip
```

## 2. 폰트 파일 배치

다운로드한 폰트 파일을 다음 위치에 배치하세요:

```
RAG_for_OC_251014/
└── resources/
    └── fonts/
        ├── PretendardVariable.ttf          (권장 - Variable 폰트)
        또는
        ├── Pretendard-Regular.ttf          (Static 폰트)
        ├── Pretendard-Medium.ttf
        ├── Pretendard-Bold.ttf
        └── ... (기타 굵기)
```

**참고**: Variable 폰트 사용 시 `PretendardVariable.ttf` 하나만 있으면 됩니다.

## 3. 폰트 적용 확인

1. 프로그램 실행 (`python desktop_app.py`)
2. 콘솔 출력 확인:
   - ✓ 성공: `[폰트] ✓ Pretendard 폰트 로드 성공: resources/fonts/PretendardVariable.ttf`
   - ⚠ 실패: `[폰트] ℹ Pretendard 폰트 파일을 찾을 수 없습니다`

## 4. 폰트가 없는 경우

폰트 파일이 없어도 프로그램은 정상 작동합니다. 시스템 기본 폰트가 사용됩니다.

## 5. 자동 다운로드 (선택사항)

Windows PowerShell에서 자동 다운로드:

```powershell
# Variable 폰트 다운로드 (권장)
Invoke-WebRequest -Uri "https://github.com/orioncactus/pretendard/releases/latest/download/PretendardVariable.ttf" -OutFile "resources/fonts/PretendardVariable.ttf"
```

또는 curl 사용:

```bash
curl -L "https://github.com/orioncactus/pretendard/releases/latest/download/PretendardVariable.ttf" -o "resources/fonts/PretendardVariable.ttf"
```

## 참고

- Pretendard는 오픈소스 폰트로 무료로 사용 가능합니다 (SIL Open Font License)
- 한글, 영문, 숫자, 특수문자를 모두 지원합니다
- Variable 폰트 사용 시 파일 크기가 작고 다양한 굵기를 지원합니다
- 공식 GitHub: https://github.com/orioncactus/pretendard
