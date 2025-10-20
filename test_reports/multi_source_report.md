# 다중 문서 검색 평가 요약 (2025-10-20)

## 환경
- VectorDB: Chroma (local)
- Embedding: nomic-embed-text (Ollama)
- Re-ranker: CrossEncoder (multilingual-mini)
- Chunk: 500 / overlap 100
- Retriever k: max(8*top_k, 24)
- Reranker initial k: 30 → 40 (재실행)
- top_k: 3

## 실험 1: 기존 로컬 문서 세트
- 평균 다양성(Diversity@3): 1.50
- 평균 정확도(라벨 2문항): 0.50
- 해석: 특정 파일로 편중(“I-7장.pdf”) 발생

## 개선(파일 다양성·스코어 보정)
- 파일 중복 제거(file_name 기준), softmax 확률 점수, 임계치 15% 미만 제외
- Retriever/Reranker 후보 확대

## 실험 2: 대용량 공개 PDF 5종 추가
- 질문 5개(Transformer, BERT, seq2seq, ResNet, DETR)
- 평균 다양성(Diversity@3): 2.40 (1차), 2.00 (reranker_initial_k=40 재실행)
- 주제 매칭 대체로 적정, BERT 문항은 단일 파일 우세(자연스러움)

## 관찰/결론
- 다양성·정확도 모두 1차 대비 개선
- 질문-문서가 일대일로 타이트할 때 div가 낮아지는 것은 정상
- 추가 데이터/하이브리드 검색 시 더 개선 여지 큼

## 다음 액션
1) 하이브리드 검색(BM25+벡터) → Re-ranker 결합
2) 인용 UX 개선(출처 클릭 미리보기/페이지 이동)
3) 3모드 비교 리포트: Vanilla / ReRankOnly / Hybrid+ReRank
