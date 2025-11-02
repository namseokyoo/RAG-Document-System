# -*- coding: utf-8 -*-
import sys
import os
import json
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

cfg = ConfigManager().get_all()

vector_manager = VectorStoreManager(
    persist_directory='data/chroma_db',
    embedding_api_type=cfg.get('embedding_api_type','ollama'),
    embedding_base_url=cfg.get('embedding_base_url'),
    embedding_model=cfg.get('embedding_model'),
    embedding_api_key=cfg.get('embedding_api_key','')
)

multi_query_num = 3
rag_chain = RAGChain(
    vectorstore=vector_manager.get_vectorstore(),
    llm_api_type=cfg.get('llm_api_type','ollama'),
    llm_base_url=cfg.get('llm_base_url'),
    llm_model=cfg.get('llm_model'),
    llm_api_key=cfg.get('llm_api_key',''),
    temperature=cfg.get('temperature',0.7),
    top_k=cfg.get('top_k',3),
    use_reranker=cfg.get('use_reranker', True),
    reranker_model=cfg.get('reranker_model', 'multilingual-mini'),
    reranker_initial_k=cfg.get('reranker_initial_k', 20),
    enable_synonym_expansion=cfg.get('enable_synonym_expansion', True),
    enable_multi_query=True,
    multi_query_num=multi_query_num
)

questions = [
    "MIPS(운동성 유도 상분리)는 무엇이며, 수동적 시스템의 상분리와 어떤 차이가 있습니까?",
    "DC 마그노닉 결정이 스핀파 스펙트럼을 어떻게 변화시키며 생성된 밴드 갭은 어떤 파라미터에 비례합니까?",
    "베이지안 X-ray 단층 촬영 재구성에서 프라이어 분포는 어떤 역할을 하며, 가능성 함수와 어떻게 상호작용합니까?"
]

results = []

for idx, question in enumerate(questions, start=1):
    print("=" * 80)
    print(f"질문 {idx}: {question}")
    rewrites = rag_chain.generate_rewritten_queries(question, num_queries=multi_query_num)
    for i, rewrite in enumerate(rewrites, start=1):
        print(f"  - 蹂??{i}: {rewrite}")
    results.append({
        "question": question,
        "rewrites": rewrites
    })

output_path = os.path.join("experiments", f"multi_query_samples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("=" * 80)
print(f"결과 저장: {output_path}")
