# Phase 3.5 GUI 통합 테스트 계획

## 개요
SessionContext + Intent Detection 기능이 실제 GUI 앱에서 올바르게 작동하는지 검증합니다.

## 설정 확인

### config.json 필수 설정
```json
{
  "enable_session_priority": true,
  "session_relevance_threshold": 0.7,
  "enable_hybrid_search": true,
  "hybrid_bm25_weight": 0.5
}
```

✅ 설정 추가 완료

---

## 테스트 시나리오

### 🧪 테스트 1: 앱 기본 실행
**목적:** Import 오류 없이 앱이 정상적으로 시작되는지 확인

**실행 방법:**
```bash
venv/Scripts/python.exe desktop_app.py
```

**기대 결과:**
- ✅ 앱 실행 성공
- ✅ 콘솔에 "[초기화] SessionContext 생성 완료 (타임아웃: 300초)" 메시지 출력
- ✅ 에러 없이 메인 윈도우 표시

**검증 포인트:**
- [ ] SessionContext 초기화 메시지 확인
- [ ] Intent Detection 초기화 로그 확인
- [ ] GUI 정상 표시

---

### 🧪 테스트 2: PDF 업로드 + 세션 추적
**목적:** PDF 업로드 시 SessionContext에 자동으로 기록되는지 확인

**실행 방법:**
1. "업로드" 탭으로 이동
2. 테스트 PDF 파일 업로드 (예: `data/test_documents/OLED_materials_2019_arX.pdf`)
3. 개인 DB 선택 (세션 추적은 개인 DB만 적용)
4. 업로드 진행

**기대 결과:**
- ✅ PDF 처리 및 임베딩 성공
- ✅ 로그에 "📌 Session 추적 활성화: [파일명]" 메시지 출력
- ✅ "✅ 완료: [파일명]" 메시지 출력

**검증 포인트:**
- [ ] "문서 처리: [파일명] ..." 출력
- [ ] "임베딩 추가: [파일명] (청크 N개) → 개인 DB" 출력
- [ ] "📌 Session 추적 활성화: [파일명]" 출력 ← **핵심**
- [ ] "✅ 완료: [파일명]" 출력

**실패 시 확인:**
- UploadWorker에 session_context가 전달되었는지
- chunks가 비어있지 않은지
- target_db가 "personal"인지

---

### 🧪 테스트 3: Intent Detection - 지시대명사
**목적:** "이 문서", "그 파일" 같은 지시대명사로 문서 참조 시 세션 문서 우선 검색

**실행 방법:**
1. 테스트 2에서 PDF 업로드 완료
2. "채팅" 탭으로 이동
3. 질문 입력: **"이 문서에서 뭐라고 했어?"**
4. 응답 확인

**기대 결과:**
- ✅ 콘솔에 Intent Detection 로그 출력:
  ```
  📎 Intent: 문서 참조 감지 (신뢰도=0.7~0.95), 세션 문서=1개
  ```
- ✅ 업로드한 PDF에서 답변 생성
- ✅ 출처(Sources)에 업로드한 PDF 파일명 표시

**검증 포인트:**
- [ ] Intent Detection이 참조 패턴 감지 ("이 문서")
- [ ] 세션 문서 내에서 검색 수행
- [ ] 답변이 업로드한 PDF 내용 기반
- [ ] Sources 버블에 올바른 파일명 표시

**실패 시 확인:**
- IntentDetector가 패턴을 감지했는지 (콘솔 로그)
- SessionContext가 활성 상태인지 (5분 이내)
- RAGChain이 session_context를 받았는지

---

### 🧪 테스트 4: Intent Detection - 시간 기반 참조
**목적:** "방금 올린 파일", "아까 업로드한 문서" 같은 시간 기반 참조 감지

**실행 방법:**
1. 테스트 2에서 PDF 업로드 완료
2. 채팅에서 질문: **"방금 올린 파일 요약해줘"**
3. 응답 확인

**기대 결과:**
- ✅ Intent Detection이 시간 기반 패턴 감지
- ✅ 콘솔 로그: `📎 Intent: 문서 참조 감지 (신뢰도=0.7~0.95)`
- ✅ 업로드한 PDF에서 요약 생성
- ✅ Sources에 올바른 파일명 표시

**검증 포인트:**
- [ ] "방금 올린" 패턴 감지
- [ ] 세션 문서 내에서 검색
- [ ] 요약 답변 생성
- [ ] 출처 표시 정확

**추가 테스트 문구:**
- "아까 업로드한 자료에서 찾아줘"
- "조금 전에 올린 PDF 분석해줘"
- "직전에 추가한 문서 읽어줘"

---

### 🧪 테스트 5: Auto Session Context (참조 패턴 없음)
**목적:** 명시적 참조 없이도 5분 이내 업로드 문서를 자동으로 우선 검색

**실행 방법:**
1. 테스트 2에서 PDF 업로드 완료
2. 채팅에서 **문서 내용과 관련된** 질문 입력 (참조 표현 없이)
   - 예: "chromatic symmetric function이 뭐야?" (OLED_materials PDF 업로드 시)
3. 응답 확인

**기대 결과:**
- ✅ 콘솔 로그: `🕒 Session: 활성 문서 1개`
- ✅ relevance threshold(0.7) 이상이면 세션 문서 우선 사용
- ✅ threshold 미만이면 전체 DB 검색으로 fallback (정상 동작)

**검증 포인트:**
- [ ] 세션 활성 상태 확인
- [ ] 문서 relevance 체크 수행
- [ ] relevance >= 0.7이면 세션 문서 사용
- [ ] relevance < 0.7이면 전체 DB 검색 (fallback)

**참고:**
- 이 테스트는 질문이 문서 내용과 관련있어야 성공합니다.
- 무관한 질문("날씨 어때?")은 정상적으로 fallback됩니다.

---

### 🧪 테스트 6: 타임아웃 동작 확인 (선택사항)
**목적:** 5분 경과 후 세션이 만료되는지 확인

**실행 방법:**
1. PDF 업로드
2. **5분 대기**
3. "이 문서 요약해줘" 입력
4. 응답 확인

**기대 결과:**
- ✅ 세션 비활성 상태 (5분 초과)
- ✅ 전체 DB에서 검색 수행 (세션 우선순위 적용 안 됨)
- ✅ 여전히 답변 생성 가능 (fallback 정상 작동)

**검증 포인트:**
- [ ] SessionContext.is_active() = False
- [ ] Intent Detection은 감지하지만 세션 비활성
- [ ] 전체 DB 검색으로 자동 전환

---

## 테스트 체크리스트

### 필수 테스트
- [ ] 테스트 1: 앱 기본 실행
- [ ] 테스트 2: PDF 업로드 + 세션 추적
- [ ] 테스트 3: Intent Detection - 지시대명사
- [ ] 테스트 4: Intent Detection - 시간 기반
- [ ] 테스트 5: Auto Session Context

### 선택 테스트
- [ ] 테스트 6: 타임아웃 동작

---

## 테스트 자동화 스크립트

자동화된 통합 테스트는 이미 작성되어 있습니다:
```bash
venv/Scripts/python.exe test_session_integration.py
```

**통합 테스트 결과:**
- ✅ Scenario 1 (Intent Detection): PASS
- ✅ Scenario 2 (Time-based): PASS
- ✅ Scenario 3 (Auto Session): PASS

---

## 트러블슈팅

### 문제: "📌 Session 추적 활성화" 메시지가 안 보임
**원인:**
- session_context가 None
- target_db가 "shared" (공유 DB는 세션 추적 안 함)
- chunks가 비어있음

**해결:**
- desktop_app.py에서 SessionContext 초기화 확인
- DocumentWidget에 session_context 전달 확인
- UploadWorker에 session_context 전달 확인
- 개인 DB로 업로드했는지 확인

### 문제: Intent Detection이 작동 안 함
**원인:**
- enable_session_priority=False
- IntentDetector 초기화 실패

**해결:**
- config.json에 `"enable_session_priority": true` 추가
- 콘솔 로그에서 "Session Context + Intent Detection 활성화" 메시지 확인

### 문제: 세션 문서를 안 쓰고 전체 DB 검색
**원인:**
- relevance threshold 미달
- 세션 타임아웃 (5분 경과)
- 질문이 문서 내용과 무관

**해결:**
- session_relevance_threshold 값 낮추기 (0.7 → 0.5)
- 업로드 후 5분 이내에 질문
- 문서 내용과 관련된 질문 입력

---

## 성공 기준

### Phase 3.5 완전 성공 조건:
1. ✅ 앱 실행 시 SessionContext 초기화 메시지 출력
2. ✅ PDF 업로드 시 "📌 Session 추적 활성화" 메시지 출력
3. ✅ "이 문서" 질문 시 Intent Detection 작동
4. ✅ "방금 올린 파일" 질문 시 세션 문서 우선 검색
5. ✅ 참조 없는 질문도 5분 이내면 세션 우선 검색 시도
6. ✅ 의미적으로 올바른 답변 생성 ("작동" + "쓸모")

---

## 다음 단계

Phase 3.5 GUI 통합 테스트 통과 후:
- [ ] .CLAUDE.md 업데이트 (v3.6.4 추가)
- [ ] 개발 히스토리 문서화
- [ ] 사용자 매뉴얼에 새 기능 설명 추가
- [ ] Phase 4 기능 기획 (필요 시)
