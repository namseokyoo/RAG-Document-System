# -*- coding: utf-8 -*-
import sys
import time
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
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
multi_query_num = int(cfg.get('multi_query_num', 3))
enable_multi_query = cfg.get('enable_multi_query', True) and multi_query_num > 0
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
    enable_multi_query=enable_multi_query,
    multi_query_num=multi_query_num
)
question = ("What is motility-induced phase separation (MIPS)? "
            "Explain how it differs from phase separation in passive equilibrium systems."
            " Include details about attractive interactions and spontaneous dense/dilute phases.")
print("Question:", question)
answer_parts = []
start = time.time()
for chunk in rag_chain.query_stream(question, chat_history=[]):
    answer_parts.append(chunk)
elapsed = time.time() - start
answer = ''.join(answer_parts)
print("Response time:", f"{elapsed:.2f}s")
print("Answer:", answer[:500])
retrieved = getattr(rag_chain, '_last_retrieved_docs', [])
print("retrieved_docs:", len(retrieved))
for idx, item in enumerate(retrieved, start=1):
    doc = item[0] if isinstance(item, tuple) else item
    score = item[1] if isinstance(item, tuple) else None
    meta = getattr(doc, 'metadata', {}) or {}
    display_score = score if score is not None else meta.get('rerank_score') or meta.get('score')
    snippet = (getattr(doc, 'page_content', '') or '').replace('\n', ' ')
    print(f"{idx}. file={meta.get('file_name')} chunk={meta.get('chunk_id')} score={display_score}")
    print('   ', snippet[:200])
