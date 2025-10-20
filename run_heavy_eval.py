import os
import time
import requests
from typing import List, Dict

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
from utils.document_processor import DocumentProcessor

DATA_DIR = os.path.join("data", "uploaded_files")
os.makedirs(DATA_DIR, exist_ok=True)

ARXIV_PDFS = [
    ("attention_is_all_you_need.pdf", "https://arxiv.org/pdf/1706.03762.pdf"),
    ("bert_pretraining.pdf", "https://arxiv.org/pdf/1810.04805.pdf"),
    ("seq2seq_rnn.pdf", "https://arxiv.org/pdf/1406.1078.pdf"),
    ("resnet_he.pdf", "https://arxiv.org/pdf/1512.03385.pdf"),
    ("detr_object_detection.pdf", "https://arxiv.org/pdf/2005.12872.pdf"),
]


def download_pdfs(pairs: List[tuple]) -> List[str]:
    saved = []
    for fname, url in pairs:
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path) and os.path.getsize(path) > 1024 * 100:
            saved.append(path)
            continue
        try:
            print(f"⬇️  Downloading {fname} ...")
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
            if os.path.getsize(path) < 1024 * 50:
                print(f"⚠️  {fname} size too small, maybe blocked.")
            saved.append(path)
        except Exception as e:
            print(f"❌ Download failed for {url}: {e}")
    return saved


def build_index_on_files(file_paths: List[str], cfg: Dict):
    dp = DocumentProcessor(chunk_size=cfg.get("chunk_size", 500), chunk_overlap=cfg.get("chunk_overlap", 100))
    vsm = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=cfg.get("embedding_api_type", "ollama"),
        embedding_base_url=cfg.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=cfg.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=cfg.get("embedding_api_key", ""),
    )
    for p in file_paths:
        fname = os.path.basename(p)
        chunks = dp.process_document(file_path=p, file_name=fname, file_type="pdf")
        vsm.add_documents(chunks)
    return vsm


def evaluate(vsm: VectorStoreManager, cfg: Dict, questions: List[str], top_k: int = 3):
    rag = RAGChain(
        vectorstore=vsm.get_vectorstore(),
        llm_api_type=cfg.get("llm_api_type", "request"),
        llm_base_url=cfg.get("llm_base_url", "http://localhost:11434"),
        llm_model=cfg.get("llm_model", "gemma3:4b"),
        llm_api_key=cfg.get("llm_api_key", ""),
        temperature=cfg.get("temperature", 0.7),
        top_k=top_k,
        use_reranker=cfg.get("use_reranker", True),
        reranker_model=cfg.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=40,
    )
    rows = []
    for q in questions:
        t0 = time.time()
        ans = rag.query(q, [])
        dt = time.time() - t0
        files = [s.get("file_name", "?") for s in ans.get("sources", [])]
        rows.append((q, files, len(set(files)), dt))
        print(f"Q: {q}\n -> files: {files} | div={len(set(files))} | {dt:.2f}s\n")
    return rows


def main():
    cfg = ConfigManager().get_all()
    pdfs = download_pdfs(ARXIV_PDFS)
    if not pdfs:
        print("No PDFs downloaded. Abort.")
        return
    vsm = build_index_on_files(pdfs, cfg)
    questions = [
        "Transformer의 self-attention 핵심 개념은?",
        "BERT 사전학습에서 MLM은 무엇을 의미하나?",
        "RNN seq2seq와 Transformer 차이점은?",
        "ResNet의 skip connection 목적은?",
        "DETR의 object detection 접근 방식 요약?",
    ]
    rows = evaluate(vsm, cfg, questions, top_k=3)
    # 간단 요약 출력
    avg_div = sum(r[2] for r in rows) / len(rows)
    print(f"평균 다양성(Diversity@3): {avg_div:.2f}")


if __name__ == "__main__":
    main()
