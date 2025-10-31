import os
import sys
import time
import json
from datetime import datetime
from typing import List, Dict, Any

# 프로젝트 루트 상대 경로에서 실행되도록 가정
sys.path.append(os.path.abspath('.'))

from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def ensure_dirs() -> None:
    os.makedirs('test_reports', exist_ok=True)
    os.makedirs('data', exist_ok=True)


def run_pdf_eval(pdf_path: str, persist_dir: str = 'data/chroma_pdf_eval') -> Dict[str, Any]:
    start_all = time.time()
    cfg = ConfigManager().get_all()

    # 1) 문서 처리 (고급 PDF 청킹 활성)
    docp = DocumentProcessor(
        chunk_size=int(cfg.get('chunk_size', 500)),
        chunk_overlap=int(cfg.get('chunk_overlap', 100)),
        enable_advanced_pdf_chunking=True,
        enable_advanced_pptx_chunking=True,
    )

    file_name = os.path.basename(pdf_path)
    file_type = docp.get_file_type(file_name)

    t0_load = time.time()
    documents = docp.process_document(pdf_path, file_name, file_type)
    t1_load = time.time()

    # 2) 벡터스토어 초기화 및 추가
    vsm = VectorStoreManager(
        persist_directory=persist_dir,
        embedding_api_type=cfg.get('embedding_api_type', 'request'),
        embedding_base_url=cfg.get('embedding_base_url', 'http://localhost:11434'),
        embedding_model=cfg.get('embedding_model', 'mxbai-embed-large:latest'),
        embedding_api_key=cfg.get('embedding_api_key', ''),
    )

    add_ok = False
    t0_add = time.time()
    if documents:
        add_ok = vsm.add_documents(documents)
    t1_add = time.time()

    vectorstore = vsm.get_vectorstore()

    # 3) RAG 체인 구성
    rag = RAGChain(
        vectorstore=vectorstore,
        llm_api_type=cfg.get('llm_api_type', 'request'),
        llm_base_url=cfg.get('llm_base_url', 'http://localhost:11434'),
        llm_model=cfg.get('llm_model', 'gemma3:4b'),
        llm_api_key=cfg.get('llm_api_key', ''),
        temperature=float(cfg.get('temperature', 0.7)),
        top_k=int(cfg.get('top_k', 3)),
        use_reranker=bool(cfg.get('use_reranker', True)),
        reranker_model=cfg.get('reranker_model', 'multilingual-base'),
        reranker_initial_k=int(cfg.get('reranker_initial_k', 60)),
        enable_synonym_expansion=bool(cfg.get('enable_synonym_expansion', True)),
        enable_multi_query=bool(cfg.get('enable_multi_query', True)),
    )

    # 4) 질문 세트 (카테고리 다양화)
    questions: List[Dict[str, str]] = [
        {"q": "이 논문의 핵심 연구 주제와 주요 결론을 요약해줘.", "cat": "summary"},
        {"q": "이 논문에서 제안한 방법의 성능 지표와 수치를 알려줘.", "cat": "specific_info"},
        {"q": "이 방법이 기존 SOTA 대비 개선한 포인트와 한계를 비교해줘.", "cat": "comparison"},
        {"q": "실험 설정(데이터셋, 파라미터, 하드웨어)을 요약해줘.", "cat": "specific_info"},
        {"q": "제안된 메커니즘의 작동 원리와 핵심 요소의 관계를 설명해줘.", "cat": "relationship"},
        {"q": "표나 그림에서 보고된 가장 중요한 수치를 5개만 추출해줘.", "cat": "specific_info"},
        {"q": "어떤 상황에서 성능이 저하되는지 Failure case를 설명해줘.", "cat": "specific_info"},
        {"q": "추가 연구 과제로 제시된 항목이 있으면 나열해줘.", "cat": "specific_info"},
        {"q": "이 연구의 실제 산업 응용 가능성을 평가해줘.", "cat": "general"},
        {"q": "관련 개념(용어) 정의와 본문에서의 사용 맥락을 알려줘.", "cat": "specific_info"},
        {"q": "저자들이 주장하는 기여도의 타당성을 근거와 함께 평가해줘.", "cat": "general"},
        {"q": "한 문단으로 전체 내용을 초록(abstract) 스타일로 요약해줘.", "cat": "summary"},
    ]

    results: List[Dict[str, Any]] = []
    total_retrieval_time = 0.0
    total_generation_time = 0.0

    for item in questions:
        q = item["q"]
        cat = item["cat"]

        # 4-1) 검색/리랭커만 타이밍(대략적): RAG 내부 검색과는 별도 측정
        t0_ret = time.time()
        try:
            retrieved_pairs = vsm.similarity_search_with_rerank(q, top_k=int(cfg.get('top_k', 3)), initial_k=int(cfg.get('reranker_initial_k', 60)), reranker_model=cfg.get('reranker_model', 'multilingual-base'))
        except Exception:
            retrieved_pairs = []
        t1_ret = time.time()

        # 4-2) 전체 질의(생성 포함)
        t0_gen = time.time()
        out = rag.query(q, chat_history=[])
        t1_gen = time.time()

        total_retrieval_time += (t1_ret - t0_ret)
        total_generation_time += (t1_gen - t0_gen)

        results.append({
            "question": q,
            "category": cat,
            "retrieval_time": round(t1_ret - t0_ret, 3),
            "generation_time": round(t1_gen - t0_gen, 3),
            "retrieved_count": len(retrieved_pairs),
            "retrieved_preview": [
                {
                    "file_name": (p[0].metadata.get("file_name") if p and p[0] else None),
                    "page_number": (p[0].metadata.get("page_number") if p and p[0] else None)
                } for p in retrieved_pairs[:3]
            ],
            "success": out.get("success", False),
            "confidence": out.get("confidence", 0.0),
            "answer_len": len(out.get("answer", "")),
            "answer": out.get("answer", ""),
            "sources": out.get("sources", []),
        })

    report = {
        "test_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "pdf": file_name,
        "chunks": len(documents),
        "add_ok": add_ok,
        "avg_retrieval_time": round(total_retrieval_time / max(1, len(questions)), 3),
        "avg_generation_time": round(total_generation_time / max(1, len(questions)), 3),
        "results": results,
        "total_time": round(time.time() - start_all, 3),
    }
    return report


def save_reports(report: Dict[str, Any]) -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = f"test_reports/comprehensive_analysis_{ts}.json"
    md_path = f"test_reports/comprehensive_analysis_{ts}.md"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 간단 MD 요약
    lines = []
    lines.append("# RAG 시스템 종합 분석 리포트\n")
    lines.append(f"- 테스트 일시: {report['test_date']}\n")
    lines.append(f"- 대상 PDF: {report['pdf']}\n")
    lines.append(f"- 생성 청크 수: {report['chunks']}\n")
    lines.append(f"- 문서 추가 결과: {'성공' if report['add_ok'] else '실패'}\n")
    lines.append(f"- 평균 검색 시간: {report['avg_retrieval_time']}s\n")
    lines.append(f"- 평균 생성 시간: {report['avg_generation_time']}s\n")
    lines.append(f"- 총 소요 시간: {report['total_time']}s\n")
    lines.append("\n## 질문별 결과 요약\n")
    for r in report.get('results', []):
        lines.append(f"### Q: {r['question']}\n")
        lines.append(f"- 카테고리: {r['category']}\n")
        lines.append(f"- 검색/리랭킹: {r['retrieval_time']}s, 생성: {r['generation_time']}s\n")
        lines.append(f"- 성공: {r['success']}, 신뢰도: {r['confidence']}\n")
        lines.append(f"- 답변 길이: {r['answer_len']}\n")
        if r.get('sources'):
            src = r['sources'][0]
            lines.append(f"- 대표 출처: {src.get('file_name')} p.{src.get('page_number')} (score~{src.get('similarity_score')})\n")
        lines.append("\n")

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("".join(lines))

    return md_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_pdf_eval.py <PDF_PATH>")
        sys.exit(1)
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(2)

    ensure_dirs()
    report = run_pdf_eval(pdf_path)
    md_path = save_reports(report)
    print(md_path)


if __name__ == '__main__':
    main()


