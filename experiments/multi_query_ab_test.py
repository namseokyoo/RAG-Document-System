# -*- coding: utf-8 -*-
import sys
import os
import time
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
default_multi_query_num = int(cfg.get('multi_query_num', 3))
default_enable_multi_query = cfg.get('enable_multi_query', True) and default_multi_query_num > 0
vector_manager = VectorStoreManager(
    persist_directory='data/chroma_db',
    embedding_api_type=cfg.get('embedding_api_type', 'ollama'),
    embedding_base_url=cfg.get('embedding_base_url'),
    embedding_model=cfg.get('embedding_model'),
    embedding_api_key=cfg.get('embedding_api_key', '')
)

rag_chain = RAGChain(
    vectorstore=vector_manager.get_vectorstore(),
    llm_api_type=cfg.get('llm_api_type', 'ollama'),
    llm_base_url=cfg.get('llm_base_url'),
    llm_model=cfg.get('llm_model'),
    llm_api_key=cfg.get('llm_api_key', ''),
    temperature=cfg.get('temperature', 0.7),
    top_k=cfg.get('top_k', 3),
    use_reranker=cfg.get('use_reranker', True),
    reranker_model=cfg.get('reranker_model', 'multilingual-mini'),
    reranker_initial_k=cfg.get('reranker_initial_k', 20),
    enable_synonym_expansion=cfg.get('enable_synonym_expansion', True),
    enable_multi_query=default_enable_multi_query,
    multi_query_num=default_multi_query_num
)

# 테스트용 질문 3개
questions = [
    (
        "Q1",
        "What is motility-induced phase separation (MIPS)? Explain how it differs from phase separation in passive equilibrium systems, especially with respect to attractive interactions and spontaneous dilute/dense phases."
    ),
    (
        "Q2",
        "In chemotactic MIPS models, how does chemotaxis appear in the particle flux J, and what does the chemotactic Péclet number Pe_C quantify about the competition between directed motion and active diffusion?"
    ),
    (
        "Q6",
        "How does a DC magnonic crystal modify the spin-wave spectrum and to what parameter is the resulting band gap Δ proportional when a DC current drives the system?"
    )
]

cases = [
    ("mq1", 1),
    ("mq3", 3),
    ("mq5", 5),
]

all_results = []

for label, mq_count in cases:
    print("=" * 100)
    print(f"[Case] {label} (multi_query_num={mq_count})")
    rag_chain.multi_query_num = mq_count
    rag_chain.enable_multi_query = mq_count > 0

    case_results = {
        "case": label,
        "multi_query_num": mq_count,
        "timestamp": datetime.now().isoformat(),
        "questions": []
    }

    for q_label, question in questions:
        print("-" * 80)
        print(f"[{q_label}] Question: {question}")
        answer_parts = []
        start = time.time()
        for chunk in rag_chain.query_stream(question, chat_history=[]):
            answer_parts.append(chunk)
        elapsed = time.time() - start
        answer = ''.join(answer_parts)

        retrieved = getattr(rag_chain, '_last_retrieved_docs', [])
        retrieved_info = []
        for idx, item in enumerate(retrieved, start=1):
            doc = item[0] if isinstance(item, tuple) else item
            score = item[1] if isinstance(item, tuple) else None
            meta = getattr(doc, 'metadata', {}) or {}
            retrieved_info.append({
                "rank": idx,
                "file_name": meta.get('file_name'),
                "page_number": meta.get('page_number'),
                "slide_number": meta.get('slide_number'),
                "chunk_id": meta.get('chunk_id'),
                "score": score if score is not None else meta.get('rerank_score') or meta.get('score')
            })

        case_results["questions"].append({
            "label": q_label,
            "question": question,
            "answer": answer,
            "response_time": elapsed,
            "retrieved": retrieved_info
        })

        print(f"Response time: {elapsed:.2f}s | Retrieved docs: {len(retrieved_info)}")

    all_results.append(case_results)

output_path = f"experiments/multi_query_ab_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

print("=" * 100)
print(f"결과 저장: {output_path}")
