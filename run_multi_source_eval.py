import os
import time
from typing import List, Dict

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def run_eval(questions: List[Dict[str, str]], top_k: int = 3) -> Dict:
    cfg = ConfigManager().get_all()
    vsm = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=cfg.get("embedding_api_type", "ollama"),
        embedding_base_url=cfg.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=cfg.get("embedding_model", "nomic-embed-text"),
        embedding_api_key=cfg.get("embedding_api_key", ""),
    )
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
        reranker_initial_k=cfg.get("reranker_initial_k", 20),
    )

    results = []
    total_div = 0.0
    total_acc = 0.0

    for q in questions:
        qs = q["question"]
        expect_file = q.get("expect_file")  # optional
        t0 = time.time()
        ans = rag.query(qs, [])
        elapsed = time.time() - t0
        srcs = ans.get("sources", [])
        file_names = [s.get("file_name", "?") for s in srcs]
        diversity = len(set(file_names))
        accuracy = 1.0 if (expect_file and expect_file in file_names) else 0.0 if expect_file else None
        results.append({
            "question": qs,
            "files": file_names,
            "diversity": diversity,
            "accuracy": accuracy,
            "elapsed_sec": round(elapsed, 2),
        })
        total_div += diversity
        if accuracy is not None:
            total_acc += accuracy

    avg_div = total_div / len(questions)
    labeled = [r for r in results if r["accuracy"] is not None]
    avg_acc = (sum(r["accuracy"] for r in labeled) / len(labeled)) if labeled else None

    return {"results": results, "avg_diversity": avg_div, "avg_accuracy": avg_acc}


if __name__ == "__main__":
    # 예시 질문들 (expect_file은 파일명이 다르면 생략 가능)
    questions = [
        {"question": "파이썬 리스트 컴프리헨션이 뭐야?", "expect_file": "python_advanced.txt"},
        {"question": "도플러 효과 설명해줘", "expect_file": "I-7장.pdf"},
        {"question": "웹 백엔드 배포 자동화 단계는?", "expect_file": None},
        {"question": "회귀의 MSE 정의는?", "expect_file": None},
    ]
    out = run_eval(questions, top_k=3)
    print(out)
