# RAG 시스템 평가 가이드

이 문서는 Hugging Face의 [RAG-Evaluation-Dataset-KO](https://huggingface.co/datasets/allganize/RAG-Evaluation-Dataset-KO) 데이터셋을 사용하여 RAG 시스템의 성능을 평가하는 방법을 설명합니다.

## 개요

평가 스크립트는 다음을 수행합니다:

1. **데이터셋 다운로드**: Hugging Face에서 한국어 RAG 평가 데이터셋 자동 다운로드
2. **질문 처리**: 각 질문에 대해 RAG 시스템으로 답변 생성
3. **평가 메트릭 계산**:
   - 유사도 점수 (코사인 유사도)
   - 정확 일치율 (Exact Match)
   - 도메인별 성능 분석
4. **결과 리포트 생성**: 상세한 평가 결과 및 통계 리포트 생성

## 데이터셋 정보

- **총 질문 수**: 300개
- **도메인**: finance(금융), public(공공), medical(의료), law(법률), commerce(커머스)
- **각 도메인별**: 60개 질문
- **컬럼**: question, target_answer, target_file_name, target_page_no, context_type 등

## 설치

필요한 라이브러리 설치:

```bash
pip install datasets tqdm scikit-learn
```

또는 requirements.txt 업데이트 후:

```bash
pip install -r requirements.txt
```

## 사용법

### 기본 사용법

전체 데이터셋으로 평가:

```bash
python evaluate_rag_system.py
```

### 옵션

#### 질문 수 제한

처음 10개 질문만 평가:

```bash
python evaluate_rag_system.py --limit 10
```

#### 특정 도메인만 평가

금융 도메인만 평가:

```bash
python evaluate_rag_system.py --domain finance
```

#### 결과 저장 디렉토리 지정

```bash
python evaluate_rag_system.py --output my_evaluation_results
```

#### 중간 저장 비활성화

```bash
python evaluate_rag_system.py --no-intermediate
```

### 전체 옵션

```bash
python evaluate_rag_system.py [OPTIONS]

옵션:
  --limit N              평가할 질문 수 제한 (기본: 전체)
  --domain DOMAIN        특정 도메인만 평가 (finance, public, medical, law, commerce)
  --output OUTPUT_DIR    결과 저장 디렉토리 (기본: evaluation_results/)
  --no-intermediate      중간 저장 비활성화
```

## 평가 메트릭

### 1. 유사도 점수 (Similarity Score)

- **방법**: Sentence Transformer를 사용한 코사인 유사도
- **범위**: 0.0 ~ 1.0 (1.0에 가까울수록 유사)
- **모델**: `paraphrase-multilingual-MiniLM-L12-v2`

### 2. 정확 일치율 (Exact Match Rate)

- **방법**: 생성된 답변과 정답이 정확히 일치하는 비율
- **범위**: 0.0 ~ 1.0

### 3. 도메인별 성능

각 도메인(finance, public, medical, law, commerce)별로:
- 평균 유사도
- 정확 일치율
- 완료/실패 통계

## 결과 파일

평가 실행 후 `evaluation_results/` 디렉토리에 다음 파일이 생성됩니다:

1. **evaluation_results.json**: 전체 평가 결과 (JSON 형식)
   - 모든 질문별 상세 결과
   - 도메인별 통계
   - 전체 요약 통계

2. **evaluation_report.txt**: 텍스트 형식 리포트
   - 시스템 정보
   - 전체 통계
   - 도메인별 성능

3. **intermediate_N.json**: 중간 저장 파일 (매 10개 질문마다)

## 결과 해석

### 예시 리포트

```
================================================================================
RAG 시스템 평가 리포트
================================================================================
생성 시간: 2025-01-15 14:30:00

시스템 정보:
  - LLM: gemma3:latest (request)
  - Embedding: mxbai-embed-large (request)
  - Multi-Query: 3개
  - Reranker: True

전체 통계:
  - 총 질문 수: 300
  - 완료: 295
  - 실패: 5
  - 성공률: 98.33%
  - 평균 유사도: 0.752
  - 정확 일치율: 12.54%

도메인별 성능:
  [finance]
    - 유사도: 0.785
    - 정확 일치율: 15.00%
    - 완료: 60 / 실패: 0
  [public]
    - 유사도: 0.742
    - 정확 일치율: 11.67%
    - 완료: 60 / 실패: 0
  ...
```

### 성능 기준

참고: [원본 데이터셋 페이지](https://huggingface.co/datasets/allganize/RAG-Evaluation-Dataset-KO)의 벤치마크 결과:

- **최고 성능**: Alli (gpt-4-turbo) - 0.733 (220/300)
- **OpenAI Assistant (gpt-4)**: 0.707 (212/300)
- **LangChain (gpt-4-turbo)**: 0.610 (183/300)

## 주의사항

1. **문서 준비**: 평가를 실행하기 전에 해당 도메인의 문서가 벡터 스토어에 업로드되어 있어야 합니다.
   - 데이터셋의 `target_file_name`을 참고하여 필요한 문서를 업로드하세요.

2. **API 설정**: `config.json`에서 LLM 및 임베딩 API 설정이 올바른지 확인하세요.

3. **평가 시간**: 전체 300개 질문 평가는 시간이 오래 걸릴 수 있습니다 (질문당 약 5-10초).

4. **메모리 사용량**: 대량 평가 시 메모리 사용량이 증가할 수 있습니다.

## 문제 해결

### 데이터셋 다운로드 실패

```bash
# datasets 라이브러리 재설치
pip install --upgrade datasets
```

### 유사도 모델 로딩 실패

유사도 평가는 선택적 기능입니다. 모델 로딩 실패 시에도 평가는 계속 진행되며, 유사도 점수만 0.0으로 표시됩니다.

### 질문 처리 실패

일부 질문 처리 실패는 정상입니다. 실패한 질문은 통계에 반영되며, 전체 성공률로 표시됩니다.

## 향후 개선 계획

- [ ] LLM 기반 O/X 판정 기능 추가
- [ ] BLEU, ROUGE 점수 추가
- [ ] Citation 정확도 평가
- [ ] 응답 시간 분석
- [ ] 시각화 대시보드 생성

## 참고 자료

- [Hugging Face 데이터셋 페이지](https://huggingface.co/datasets/allganize/RAG-Evaluation-Dataset-KO)
- [원본 블로그 포스트](https://blog-ko.allganize.ai)



